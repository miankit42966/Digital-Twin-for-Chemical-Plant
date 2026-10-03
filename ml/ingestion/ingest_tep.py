"""Validate and combine published TEP RData tables without fabricating labels."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pyreadr
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np

from ml.ingestion.common import REPO_ROOT, atomic_output, write_manifest

VERSION = "harvard-dvn-6c3jr1-v1.0"
RAW_DIR = REPO_ROOT / "data" / "raw" / "tep"
OUTPUT = REPO_ROOT / "data" / "processed" / "tep" / VERSION
FILES = ("TEP_FaultFree_Training.RData", "TEP_Faulty_Training.RData", "TEP_FaultFree_Testing.RData", "TEP_Faulty_Testing.RData")


def normalized(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_one(path: Path) -> pd.DataFrame:
    objects = pyreadr.read_r(path)
    frames = [value for value in objects.values() if isinstance(value, pd.DataFrame)]
    if len(frames) != 1:
        raise ValueError(f"{path.name}: expected one tabular R object; found {len(frames)}")
    frame = frames[0]
    frame.columns = [normalized(str(column)) for column in frame.columns]
    sensor_columns = [column for column in frame.columns if column.startswith("xmeas_") or column.startswith("xmv_")]
    expected_sensors = {f"xmeas_{i}" for i in range(1, 42)} | {f"xmv_{i}" for i in range(1, 12)}
    if set(sensor_columns) != expected_sensors:
        raise ValueError(f"{path.name}: expected 41 xmeas + 11 xmv columns (52); found {len(sensor_columns)}")
    for required in ("faultnumber", "simulationrun", "sample"):
        if required not in frame.columns:
            raise ValueError(f"{path.name}: missing required TEP field {required!r}; got {frame.columns.tolist()}")
    for column in sensor_columns:
        if not np.isfinite(frame[column].to_numpy()).all():
            raise ValueError(f"{path.name}: non-finite sensor values; raw data was not altered.")
    samples = 500 if "Training" in path.name else 960
    faults = [0] if "FaultFree" in path.name else list(range(1, 21))
    if len(frame) != len(faults) * 500 * samples:
        raise ValueError(f"{path.name}: unexpected published row count")
    identifiers = frame[["faultnumber", "simulationrun", "sample"]]
    if identifiers.isna().any().any() or not (identifiers == identifiers.astype('int64')).all().all():
        raise ValueError(f"{path.name}: invalid fractional/null identifiers")
    if not frame.faultnumber.isin(faults).all() or not frame.simulationrun.between(1, 500).all() or not frame['sample'].between(1, samples).all():
        raise ValueError(f"{path.name}: out-of-range identifiers")
    if identifiers.duplicated().any():
        raise ValueError(f"{path.name}: duplicate trajectory sample")
    counts = frame.groupby(['faultnumber', 'simulationrun'], sort=False).size()
    if len(counts) != len(faults) * 500 or not (counts == samples).all():
        raise ValueError(f"{path.name}: incomplete trajectory")
    return frame


def main() -> None:
    paths = [RAW_DIR / name for name in FILES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing TEP source file(s): " + ", ".join(missing) + ". Run: py -m ml.ingestion.fetch_tep")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    row_count = 0
    columns = []
    with atomic_output(OUTPUT / "tep.parquet") as temporary:
        writer = None
        try:
            # Process one R table at a time; don't concatenate all 15.33M rows.
            for path in paths:
                frame = load_one(path)
                frame["dataset_partition"] = "training" if "Training" in path.name else "testing"
                frame["published_condition"] = "fault_free" if "FaultFree" in path.name else "faulty"
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if writer is None:
                    columns = table.column_names
                    writer = pq.ParquetWriter(temporary, table.schema)
                writer.write_table(table, row_group_size=500_000)
                row_count += len(frame)
                del table, frame
        finally:
            if writer is not None:
                writer.close()
    write_manifest(OUTPUT, paths, row_count, columns, "ml.ingestion.ingest_tep")
    print(f"Wrote {row_count} rows to {OUTPUT}")


if __name__ == "__main__":
    main()

