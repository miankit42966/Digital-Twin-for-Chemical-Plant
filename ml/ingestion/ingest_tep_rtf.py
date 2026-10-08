"""Stream the official run-to-failure CSVs into a separate, validated dataset."""
from __future__ import annotations

import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import h5py
import pyarrow as pa
import pyarrow.parquet as pq

from ml.ingestion.common import REPO_ROOT, atomic_output, sha256
from ml.ingestion.fetch_tep_rtf import DESTINATION, EXPECTED_BYTES, EXPECTED_MD5, md5sum

VERSION = "recherche-data-gouv-1katn7-v1"
OUTPUT = REPO_ROOT / "data/processed/tep_rtf" / VERSION
CSV_NAMES = ("case1", "case2", "case3", "case4", "case5", "case5_1", "case6", "case7")
DOCUMENTED_CASES = {"case1", "case2", "case3", "case4", "case5", "case6"}
CORE_COLUMNS = (
    "Id", "Time", "Reactor Feed Rate", "Reactor Pressure", "Reactor Level", "Reactor Temperature",
    "Product Sep Temp", "Product Sep Level", "Product Sep Pressure", "Product Sep Underflow",
    "Stripper Level", "Stripper Pressure", "Stripper Underflow", "Stripper Temp",
    "Liquid Input Stripper", "Liquid Input Separator", "Liquid Input Reactor",
)


def validate_chunk(frame: pd.DataFrame, case: str, expected_columns: list[str] | None) -> list[str]:
    columns = frame.columns.tolist()
    if len(columns) != 58 or len(set(columns)) != 58 or any(name not in columns for name in CORE_COLUMNS):
        raise ValueError(f"{case}: source CSV must contain 58 distinct columns including all equipment readings")
    if expected_columns is not None and columns != expected_columns:
        raise ValueError(f"{case}: columns changed within the CSV")
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy(dtype=np.float64)).all():
        raise ValueError(f"{case}: missing or non-finite data; no values are imputed")
    if not np.equal(frame["Id"], np.floor(frame["Id"])).all() or (frame["Id"] < 1).any():
        raise ValueError(f"{case}: invalid simulation Id")
    return columns


def update_runs(frame: pd.DataFrame, case: str, runs: dict[str, dict]) -> None:
    for run_id, group in frame.groupby("Id", sort=False):
        key = str(int(run_id))
        times = group["Time"].to_numpy(dtype=np.float64)
        if len(times) > 1 and (np.diff(times) <= 0).any():
            raise ValueError(f"{case}/Id {key}: time is not strictly increasing")
        first, last = float(times[0]), float(times[-1])
        if key in runs:
            previous = runs[key]["end_time_hours"]
            if first <= previous:
                raise ValueError(f"{case}/Id {key}: repeated or reversed time")
            steps = np.concatenate(([first - previous], np.diff(times)))
            runs[key]["end_time_hours"] = last
            runs[key]["samples"] += len(group)
        else:
            if runs and int(key) <= int(next(reversed(runs))):
                raise ValueError(f"{case}: simulation Ids are not contiguous ordered groups")
            steps = np.diff(times)
            runs[key] = {"samples": len(group), "start_time_hours": first, "end_time_hours": last,
                         "min_step_hours": None, "max_step_hours": None}
        if len(steps):
            smallest, largest = float(steps.min()), float(steps.max())
            prior_min, prior_max = runs[key]["min_step_hours"], runs[key]["max_step_hours"]
            runs[key]["min_step_hours"] = smallest if prior_min is None else min(prior_min, smallest)
            runs[key]["max_step_hours"] = largest if prior_max is None else max(prior_max, largest)


def _decoded(values: np.ndarray) -> list[str]:
    return [value.decode("utf-8") if isinstance(value, bytes) else str(value) for value in values]


def validate_hdf5_chunk(frame: pd.DataFrame, group: h5py.Group, offset: int, case: str) -> None:
    end = offset + len(frame)
    if end > len(group["axis1"]):
        raise ValueError(f"{case}: CSV has more rows than teps.h5")
    for number in (0, 1):
        items = _decoded(group[f"block{number}_items"][:])
        recorded = group[f"block{number}_values"][offset:end]
        observed = frame.loc[:, items].to_numpy()
        if recorded.shape != observed.shape or not np.allclose(recorded, observed, rtol=1e-12, atol=1e-12, equal_nan=False):
            raise ValueError(f"{case}: CSV and teps.h5 differ in rows {offset + 1}-{end}, block {number}")


def ingest_case(archive: zipfile.ZipFile, case: str, hdf5: h5py.File | None) -> tuple[dict[str, dict], list[str], int]:
    member = f"TEP/{case}.csv"
    runs: dict[str, dict] = {}
    columns: list[str] | None = None
    row_count = 0
    with atomic_output(OUTPUT / f"{case}.parquet") as temporary:
        writer = None
        try:
            with archive.open(member) as source:
                for frame in pd.read_csv(source, chunksize=100_000):
                    columns = validate_chunk(frame, case, columns)
                    if hdf5 is not None:
                        group = hdf5[case]
                        if _decoded(group["axis0"][:]) != columns:
                            raise ValueError(f"{case}: CSV and teps.h5 column order differs")
                        validate_hdf5_chunk(frame, group, row_count, case)
                    update_runs(frame, case, runs)
                    frame["Id"] = frame["Id"].astype("int32")
                    table = pa.Table.from_pandas(frame, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                    writer.write_table(table)
                    row_count += len(frame)
        finally:
            if writer is not None:
                writer.close()
    if not runs or row_count != sum(run["samples"] for run in runs.values()):
        raise ValueError(f"{case}: empty or incomplete run index")
    if hdf5 is not None and row_count != len(hdf5[case]["axis1"]):
        raise ValueError(f"{case}: CSV and teps.h5 row counts differ")
    return runs, columns or [], row_count


def audit_existing(existing: dict) -> bool:
    """Validate a completed ingestion and add output hashes to legacy manifests."""
    changed = False
    if set(existing.get("cases", {})) != set(CSV_NAMES) or len(existing.get("columns", [])) != 58:
        raise RuntimeError("Existing RTF manifest structure is incomplete")
    for case in CSV_NAMES:
        path = OUTPUT / f"{case}.parquet"
        if not path.is_file():
            raise RuntimeError(f"Existing RTF output is missing: {path}")
        detail = existing["cases"][case]
        parquet = pq.ParquetFile(path)
        if parquet.metadata.num_rows != detail.get("rows") or parquet.schema_arrow.names != existing["columns"]:
            raise RuntimeError(f"Existing RTF output does not match its manifest: {case}")
        digest = sha256(path)
        recorded = detail.get("processed_sha256")
        if recorded is not None and recorded != digest:
            raise RuntimeError(f"Existing RTF output checksum mismatch: {case}")
        if recorded is None:
            for batch in parquet.iter_batches(batch_size=100_000):
                for column in batch.columns:
                    if column.null_count or not np.isfinite(column.to_numpy()).all():
                        raise RuntimeError(f"Existing RTF output has missing/non-finite values: {case}")
            detail["processed_sha256"] = digest
            changed = True
    return changed


def main() -> None:
    if not DESTINATION.is_file() or DESTINATION.stat().st_size != EXPECTED_BYTES or md5sum(DESTINATION) != EXPECTED_MD5:
        raise FileNotFoundError("Verified TEP run-to-failure archive missing; run ml.ingestion.fetch_tep_rtf first")
    manifest = OUTPUT / "manifest.json"
    source_sha = sha256(DESTINATION)
    if manifest.exists():
        existing = json.loads(manifest.read_text(encoding="utf-8"))
        if existing.get("source_sha256") == source_sha:
            changed = audit_existing(existing)
            if changed:
                with atomic_output(manifest) as temporary:
                    temporary.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
                print("Upgraded legacy RTF manifest with verified Parquet hashes", flush=True)
            print(f"Verified ingestion already present: {OUTPUT}")
            return
        raise RuntimeError(f"Existing ingestion must be preserved and audited before replacement: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases = {}
    with zipfile.ZipFile(DESTINATION) as archive, archive.open("TEP/teps.h5") as hdf_source, h5py.File(hdf_source, "r") as hdf5:
        actual = {Path(name).stem for name in archive.namelist() if re.fullmatch(r"TEP/case[0-9_]+\.csv", name)}
        if actual != set(CSV_NAMES):
            raise ValueError(f"Unexpected archive CSV case set: {sorted(actual)}")
        if set(hdf5.keys()) != DOCUMENTED_CASES:
            raise ValueError(f"Unexpected teps.h5 case set: {sorted(hdf5.keys())}")
        for case in CSV_NAMES:
            hdf_reference = hdf5 if case in DOCUMENTED_CASES else None
            runs, columns, row_count = ingest_case(archive, case, hdf_reference)
            cases[case] = {"documented_scenario": case in DOCUMENTED_CASES,
                           "hdf5_consistency": "all_values_match" if hdf_reference is not None else "not_present_in_hdf5",
                           "rows": row_count, "run_count": len(runs),
                           "processed_sha256": sha256(OUTPUT / f"{case}.parquet"), "runs": runs}
            print(f"{case}: {row_count:,} rows in {len(runs)} runs", flush=True)
    record = {
        "schema_version": 1,
        "source_doi": "10.57745/1KATN7",
        "source_file_id": 762134,
        "source_archive_bytes": EXPECTED_BYTES,
        "source_md5": EXPECTED_MD5,
        "source_sha256": source_sha,
        "ingested_utc": datetime.now(UTC).isoformat(),
        "columns": columns,
        "time_unit": "hours (Time column); observed cadence is audited per run in the manifest",
        "hdf5_audit": "teps.h5 contains case1-case6; all CSV values and column order for those cases matched during streaming ingestion",
        "scenario_warning": "The scenario figure and teps.h5 contain six scenarios; ZIP has eight CSV files. case5_1 and case7 are quarantined from modeling until documented.",
        "equipment_label_status": "not_provided_in_csv; verify terminal shutdown unit independently before classifier training",
        "cases": cases,
    }
    with atomic_output(manifest) as temporary:
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Ingestion ready: {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
