"""Separate run-to-failure replay and fail-closed research prognosis."""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq

from app.schemas import RtfFrame, RtfHistory, RtfHistoryPoint, RtfPrognosis, RtfState, RtfTelemetry
from app.services.cache import singleflight_cache

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/processed/tep_rtf/recherche-data-gouv-1katn7-v1"
MANIFEST = DATA / "manifest.json"
MODEL = ROOT / "models/tep_rtf_prognosis.joblib"
CARD = ROOT / "docs/models/TEP_RTF_prognosis.json"
DOCUMENTED_CASES = frozenset(("case1", "case2", "case3", "case4", "case5", "case6"))
ARCHIVE_CASES = ("case1", "case2", "case3", "case4", "case5", "case5_1", "case6", "case7")
SENSORS = (
    "Reactor Feed Rate", "Reactor Pressure", "Reactor Level", "Reactor Temperature",
    "Product Sep Temp", "Product Sep Level", "Product Sep Pressure", "Product Sep Underflow",
    "Stripper Level", "Stripper Pressure", "Stripper Underflow", "Stripper Temp",
    "Liquid Input Stripper", "Liquid Input Separator", "Liquid Input Reactor",
    "Recycle Flow", "Purge Rate", "Stripper Steam Flow", "Compressor Work",
)
FEATURES = tuple(f"{kind}:{sensor}" for kind in ("now", "delta_1", "delta_20", "mean_20") for sensor in SENSORS)
NOTICE = ("Published TEP run-to-failure simulation, not live plant telemetry. "
          "Remaining time means simulated process shutdown, not physical equipment breakdown.")
logger = logging.getLogger(__name__)


def available() -> bool:
    try:
        return (MANIFEST.is_file() and all((DATA / f"{case}.parquet").is_file()
                                           and (DATA / f"{case}.parquet").stat().st_size > 0
                                           for case in ARCHIVE_CASES))
    except OSError:
        return False


@singleflight_cache(maxsize=1)
def _manifest(signature: tuple[int, int]) -> dict:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = value.get("cases")
    columns = value.get("columns")
    if (value.get("schema_version") != 1 or value.get("source_doi") != "10.57745/1KATN7"
            or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("source_sha256", "")))
            or not isinstance(columns, list) or len(columns) != 58 or len(set(columns)) != 58
            or not {"Id", "Time", *SENSORS}.issubset(columns)
            or not isinstance(cases, dict) or set(cases) != set(ARCHIVE_CASES)):
        raise ValueError("RTF manifest source contract is invalid")
    for case in ARCHIVE_CASES:
        detail = cases[case]
        runs = detail.get("runs") if isinstance(detail, dict) else None
        if (not isinstance(detail, dict)
                or detail.get("documented_scenario") is not (case in DOCUMENTED_CASES)
                or not isinstance(runs, dict) or detail.get("run_count") != len(runs) or not runs):
            raise ValueError(f"RTF manifest case contract is invalid: {case}")
        for key, run in runs.items():
            if (not str(key).isdigit() or int(key) < 1 or not isinstance(run, dict)
                    or not isinstance(run.get("samples"), int) or run["samples"] < 1
                    or not isinstance(run.get("start_time_hours"), (int, float))
                    or not isinstance(run.get("end_time_hours"), (int, float))
                    or run["end_time_hours"] < run["start_time_hours"]):
                raise ValueError(f"RTF manifest run contract is invalid: {case}/{key}")
    return value


def manifest() -> dict:
    stat = MANIFEST.stat()
    return _manifest((stat.st_mtime_ns, stat.st_size))


def options() -> dict:
    source = manifest()
    return {"source_kind": "TEP_RTF", "source_notice": NOTICE,
            "cases": [{"id": case, "documented_scenario": detail["documented_scenario"],
                       "run_count": detail["run_count"], "runs": [{"id": int(key), "samples": value["samples"]}
                                                                    for key, value in detail["runs"].items()]}
                      for case in ARCHIVE_CASES for detail in (source["cases"][case],)]}


@singleflight_cache(maxsize=3)
def _trajectory(case: str, run: int, signature: tuple[int, int]) -> tuple[dict, ...]:
    table = pq.read_table(DATA / f"{case}.parquet", filters=[("Id", "=", run)])
    rows = tuple(table.to_pylist())
    if not rows:
        raise ValueError(f"No samples for {case}/Id {run}")
    times = np.asarray([row["Time"] for row in rows], dtype=float)
    if not np.isfinite(times).all() or (np.diff(times) <= 0).any():
        raise ValueError(f"Invalid time sequence for {case}/Id {run}")
    return rows


def trajectory(case: str, run: int) -> tuple[dict, ...]:
    source = manifest()
    if case not in source["cases"] or str(run) not in source["cases"][case]["runs"]:
        raise ValueError(f"Unknown RTF trajectory {case}/Id {run}")
    path = DATA / f"{case}.parquet"
    stat = path.stat()
    rows = _trajectory(case, run, (stat.st_mtime_ns, stat.st_size))
    if len(rows) != source["cases"][case]["runs"][str(run)]["samples"]:
        raise ValueError(f"RTF trajectory length changed for {case}/Id {run}")
    return rows


@singleflight_cache(maxsize=2)
def _model(signature: tuple) -> tuple[dict, dict]:
    bundle = joblib.load(MODEL)
    card = json.loads(CARD.read_text(encoding="utf-8"))
    if tuple(bundle.get("features", ())) != FEATURES or tuple(card.get("features", ())) != FEATURES:
        raise ValueError("RTF model feature contract is incompatible")
    if not bundle.get("artifact_id") or bundle["artifact_id"] != card.get("artifact_id"):
        raise ValueError("RTF model and card are not one atomic training artifact")
    if bundle.get("source_sha256") != manifest()["source_sha256"] or card.get("source_sha256") != bundle["source_sha256"]:
        raise ValueError("RTF model and data source fingerprints differ")
    if getattr(bundle.get("estimator"), "n_features_in_", None) != len(FEATURES):
        raise ValueError("RTF model input dimension is incompatible")
    return bundle, card


def model_availability() -> str:
    if not MODEL.is_file() or not CARD.is_file() or not available():
        return "missing"
    try:
        model()
        return "ready"
    except Exception:
        logger.exception("RTF prognosis model could not be validated")
        return "invalid"


def model() -> tuple[dict, dict]:
    a, b, source = MODEL.stat(), CARD.stat(), MANIFEST.stat()
    return _model((a.st_mtime_ns, a.st_size, b.st_mtime_ns, b.st_size,
                   source.st_mtime_ns, source.st_size))


def feature_row(rows: tuple[dict, ...], sample: int) -> np.ndarray:
    if sample < 21 or sample > len(rows):
        raise ValueError("RTF prognosis needs 21 observed samples")
    values = np.asarray([[float(row[name]) for name in SENSORS] for row in rows[sample - 21:sample]], dtype=np.float64)
    current = values[-1]
    result = np.concatenate((current, current - values[-2], current - values[0], values[-20:].mean(axis=0)))
    return result.astype(np.float32).reshape(1, -1)


def prognosis(rows: tuple[dict, ...], sample: int, case: str) -> RtfPrognosis:
    if case not in DOCUMENTED_CASES:
        return RtfPrognosis(status="missing", unit_status="unavailable_no_verified_labels",
                            notice="This archive case is undocumented; no prognosis is produced.")
    status = model_availability()
    if status != "ready":
        return RtfPrognosis(status=status, unit_status="unavailable_no_verified_labels",
                            notice=f"RTF model {status}; measured data remain available.")
    if sample < 21:
        return RtfPrognosis(status="needs_history", unit_status="unavailable_no_verified_labels",
                            notice="At least 21 recorded samples are needed for prognosis.")
    try:
        bundle, card = model()
        row = feature_row(rows, sample)
        remaining = float(np.expm1(bundle["estimator"].predict(row)[0]))
        if not np.isfinite(remaining):
            raise ValueError("Non-finite remaining-time estimate")
        remaining = round(max(0.0, remaining), 1)
        classifier = bundle.get("next_unit_estimator")
        if classifier is None or card.get("next_unit_status") != "ready":
            return RtfPrognosis(status="ready", remaining_minutes=remaining,
                                unit_status="unavailable_no_verified_labels",
                                notice="Next equipment is unknown: no independently verified terminal-unit labels were published in the CSVs.")
        provenance = card.get("next_unit_label_provenance")
        threshold = card.get("next_unit_min_score")
        metrics = card.get("next_unit_per_equipment_precision_recall")
        if (not isinstance(provenance, dict) or provenance.get("verified") is not True
                or not provenance.get("source_sha256") or not isinstance(metrics, dict)
                or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1
                or set(map(str, getattr(classifier, "classes_", ()))) - {"RX-201", "SP-201", "ST-301"}):
            return RtfPrognosis(status="invalid", unit_status="unavailable_no_verified_labels",
                                notice="Equipment classifier evidence is incomplete; no unit warning is allowed.")
        scores = classifier.predict_proba(row)[0]
        winner = int(np.argmax(scores))
        confidence = float(scores[winner])
        selected = str(classifier.classes_[winner])
        if selected not in {"RX-201", "SP-201", "ST-301"} or confidence < threshold:
            return RtfPrognosis(status="ready", remaining_minutes=remaining, unit_status="abstained",
                                notice="The model abstained from naming a next equipment unit.")
        return RtfPrognosis(status="ready", remaining_minutes=remaining, next_unit_id=selected,
                            highlight_unit_id=selected if remaining <= 60 else None, unit_status="ready",
                            notice="Research forecast of a simulated shutdown condition; not an operational safety alert.")
    except Exception:
        logger.exception("RTF prognosis failed")
        return RtfPrognosis(status="invalid", unit_status="unavailable_no_verified_labels",
                            notice="RTF prognosis unavailable; measured values remain available.")


def frame(case: str, run: int, sample: int, points: int = 90) -> RtfFrame:
    rows = trajectory(case, run)
    if not 1 <= sample <= len(rows) or not 1 <= points <= 500:
        raise ValueError("RTF sample or history length is out of range")
    row = rows[sample - 1]
    now = datetime.now(UTC)
    mapping = (
        ("RX-201", "Reactor", "Reactor Temperature", "Reactor Pressure", "Reactor Level", "Reactor Feed Rate"),
        ("SP-201", "Separator", "Product Sep Temp", "Product Sep Pressure", "Product Sep Level", "Product Sep Underflow"),
        ("ST-301", "Stripper", "Stripper Temp", "Stripper Pressure", "Stripper Level", "Stripper Underflow"),
    )
    assets = [RtfTelemetry(asset_id=asset_id, asset_name=name, temperature_c=float(row[temp]),
                           pressure_bar=round(float(row[pressure]) / 100, 3), level_percent=float(row[level]),
                           flow_value=float(row[flow]), flow_unit="source unit", alarm_level="unassessed",
                           updated_at=now)
              for asset_id, name, temp, pressure, level, flow in mapping]
    state = RtfState(source_notice=NOTICE, generated_at=now, case_id=case, simulation_id=run,
                     sample_index=sample, total_samples=len(rows), time_hours=float(row["Time"]),
                     assets=assets, prognosis=prognosis(rows, sample, case))
    history = RtfHistory(case_id=case, simulation_id=run, end_sample=sample, total_samples=len(rows),
                         points=[RtfHistoryPoint(sample_index=index + 1, time_hours=float(rows[index]["Time"]),
                                                 reactor_pressure_bar_g=round(float(rows[index]["Reactor Pressure"]) / 100, 3))
                                 for index in range(max(0, sample - points), sample)])
    return RtfFrame(state=state, history=history)
