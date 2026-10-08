"""Read-only playback and fail-closed inference for the synthetic prognosis lab."""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq

from app.schemas import LabFrame, LabHistory, LabHistoryPoint, LabOutcome, LabPrognosis, LabState, LabTelemetry
from app.services.cache import singleflight_cache

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data/processed/equipment_prognosis"
DATA = DATA_DIR / "runs.parquet"
MANIFEST = DATA_DIR / "manifest.json"
MODEL = ROOT / "models/equipment_prognosis.joblib"
CARD = ROOT / "docs/models/EQUIPMENT_PROGNOSIS.json"
EQUIPMENT = ("RX-201", "CD-201", "SP-201", "ST-301", "CP-201")
SENSORS = (
    "reactor_temperature_c", "reactor_pressure_bar", "reactor_level_percent", "reactor_feed_flow",
    "condenser_temperature_c", "condenser_pressure_bar", "condenser_duty_percent", "condenser_flow",
    "separator_temperature_c", "separator_pressure_bar", "separator_level_percent", "separator_underflow",
    "stripper_temperature_c", "stripper_pressure_bar", "stripper_level_percent", "stripper_underflow",
    "compressor_temperature_c", "compressor_pressure_bar", "compressor_efficiency_percent", "compressor_work_kw",
)
FEATURES = tuple(f"{kind}:{sensor}" for kind in ("now", "delta_1", "delta_20", "mean_20") for sensor in SENSORS)
NOTICE = "Labelled dynamic-surrogate simulation; not official TEP RTF data or physical plant evidence."
logger = logging.getLogger(__name__)


def available() -> bool:
    try:
        return DATA.is_file() and MANIFEST.is_file() and DATA.stat().st_size > 0
    except OSError:
        return False


@singleflight_cache(maxsize=1)
def _manifest(signature: tuple[int, int]) -> dict:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runs = value.get("runs")
    if (value.get("schema_version") != 1 or value.get("source_kind") != "SYNTHETIC_EQUIPMENT_PROGNOSIS"
            or value.get("run_count") != 1200 or value.get("failure_run_count") != 1000
            or value.get("censored_run_count") != 200 or value.get("equipment") != list(EQUIPMENT)
            or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("data_sha256", "")))
            or not isinstance(runs, list) or len(runs) != 1200):
        raise ValueError("Synthetic prognosis manifest contract is invalid")
    return value


def manifest() -> dict:
    stat = MANIFEST.stat()
    return _manifest((stat.st_mtime_ns, stat.st_size))


def options() -> dict:
    source = manifest()
    return {"source_kind": source["source_kind"], "source_notice": NOTICE,
            "sample_period_minutes": source["sample_period_minutes"],
            "runs": [{"id": item["id"], "samples": item["samples"]} for item in source["runs"]]}


@singleflight_cache(maxsize=5)
def _trajectory(run: int, signature: tuple[int, int]) -> tuple[dict, ...]:
    rows = tuple(pq.read_table(DATA, filters=[("run_id", "=", run)]).to_pylist())
    if not rows or any(int(row["sample_index"]) != index for index, row in enumerate(rows, 1)):
        raise ValueError(f"Invalid synthetic run {run}")
    return rows


def trajectory(run: int) -> tuple[dict, ...]:
    source = manifest()
    detail = next((item for item in source["runs"] if item["id"] == run), None)
    if detail is None:
        raise ValueError(f"Unknown synthetic prognosis run {run}")
    stat = DATA.stat(); rows = _trajectory(run, (stat.st_mtime_ns, stat.st_size))
    if len(rows) != detail["samples"]:
        raise ValueError("Synthetic run length differs from its manifest")
    return rows


@singleflight_cache(maxsize=1)
def _model(signature: tuple) -> tuple[dict, dict]:
    bundle = joblib.load(MODEL); card = json.loads(CARD.read_text(encoding="utf-8"))
    if tuple(bundle.get("features", ())) != FEATURES or tuple(card.get("features", ())) != FEATURES:
        raise ValueError("Synthetic prognosis feature contract is incompatible")
    if not bundle.get("artifact_id") or bundle["artifact_id"] != card.get("artifact_id"):
        raise ValueError("Synthetic prognosis model/card versions differ")
    if bundle.get("data_sha256") != manifest()["data_sha256"] or card.get("data_sha256") != bundle["data_sha256"]:
        raise ValueError("Synthetic prognosis data fingerprint differs")
    if not bundle.get("release_ready") or not card.get("release_ready") or not all(card.get("release_gates", {}).values()):
        raise ValueError("Synthetic prognosis release gates did not pass")
    for name in ("risk_model", "unit_model", "mode_model", "rul_model"):
        if getattr(bundle.get(name), "n_features_in_", None) != len(FEATURES):
            raise ValueError(f"{name} input contract is incompatible")
    return bundle, card


def model() -> tuple[dict, dict]:
    a, b, c = MODEL.stat(), CARD.stat(), MANIFEST.stat()
    return _model((a.st_mtime_ns, a.st_size, b.st_mtime_ns, b.st_size, c.st_mtime_ns, c.st_size))


def model_availability() -> str:
    if not available() or not MODEL.is_file() or not CARD.is_file():
        return "missing"
    try:
        model(); return "ready"
    except Exception:
        logger.exception("Synthetic prognosis model validation failed"); return "invalid"


def feature_row(rows: tuple[dict, ...], sample: int) -> np.ndarray:
    if sample < 21 or sample > len(rows):
        raise ValueError("Synthetic prognosis needs 21 observed samples")
    values = np.asarray([[float(row[name]) for name in SENSORS] for row in rows[sample - 21:sample]], dtype=np.float64)
    current = values[-1]
    return np.concatenate((current, current - values[-2], current - values[0], values[-20:].mean(axis=0))).astype(np.float32).reshape(1, -1)


def prognosis(rows: tuple[dict, ...], sample: int) -> LabPrognosis:
    status = model_availability()
    if status != "ready":
        return LabPrognosis(status=status, unit_status="unassessed", notice=f"Synthetic prognosis model {status}; playback remains available.")
    if sample < 21:
        return LabPrognosis(status="needs_history", unit_status="unassessed", notice="At least 21 past samples are required.")
    try:
        bundle, _ = model(); features = feature_row(rows, sample)
        risk = float(bundle["risk_model"].predict_proba(features)[0, 1])
        risk_threshold = float(bundle["risk_threshold"])
        if risk < risk_threshold:
            return LabPrognosis(status="ready", failure_within_horizon_probability=risk, unit_status="abstained",
                                notice="No validated within-hour warning threshold was crossed.")
        unit_scores = bundle["unit_model"].predict_proba(features)[0]; index = int(np.argmax(unit_scores))
        equipment = str(bundle["unit_model"].classes_[index]); confidence = float(unit_scores[index])
        threshold = float(bundle["unit_thresholds"].get(equipment, 1.0))
        remaining = round(max(0.0, float(bundle["rul_model"].predict(features)[0])), 1)
        if equipment not in EQUIPMENT or confidence < threshold or remaining > 60:
            return LabPrognosis(status="ready", failure_within_horizon_probability=risk, remaining_minutes=remaining,
                                confidence=confidence, unit_status="abstained", notice="Risk rose, but equipment/RUL evidence did not pass every warning gate.")
        mode = str(bundle["mode_model"].predict(features)[0])
        return LabPrognosis(status="ready", failure_within_horizon_probability=risk, remaining_minutes=remaining,
                            predicted_equipment_id=equipment, predicted_failure_mode=mode, confidence=confidence,
                            unit_status="ready", highlight_equipment_id=equipment,
                            notice="Validated only against labelled dynamic-surrogate runs; not an operational alarm.")
    except Exception:
        logger.exception("Synthetic prognosis inference failed")
        return LabPrognosis(status="invalid", unit_status="unassessed", notice="Prediction failed closed; no equipment is highlighted.")


def frame(run: int, sample: int, points: int = 90) -> LabFrame:
    rows = trajectory(run)
    if not 1 <= sample <= len(rows) or not 1 <= points <= 500:
        raise ValueError("Synthetic prognosis sample or history length is out of range")
    row = rows[sample - 1]; now = datetime.now(UTC)
    assets = [
        LabTelemetry(asset_id="RX-201", asset_name="Reactor", temperature_c=row["reactor_temperature_c"], pressure_bar=row["reactor_pressure_bar"], level_percent=row["reactor_level_percent"], flow_value=row["reactor_feed_flow"], flow_unit="simulated unit/h", updated_at=now),
        LabTelemetry(asset_id="CD-201", asset_name="Condenser", temperature_c=row["condenser_temperature_c"], pressure_bar=row["condenser_pressure_bar"], flow_value=row["condenser_flow"], flow_unit="simulated unit/h", performance_percent=row["condenser_duty_percent"], updated_at=now),
        LabTelemetry(asset_id="SP-201", asset_name="Separator", temperature_c=row["separator_temperature_c"], pressure_bar=row["separator_pressure_bar"], level_percent=row["separator_level_percent"], flow_value=row["separator_underflow"], flow_unit="simulated unit/h", updated_at=now),
        LabTelemetry(asset_id="ST-301", asset_name="Stripper", temperature_c=row["stripper_temperature_c"], pressure_bar=row["stripper_pressure_bar"], level_percent=row["stripper_level_percent"], flow_value=row["stripper_underflow"], flow_unit="simulated unit/h", updated_at=now),
        LabTelemetry(asset_id="CP-201", asset_name="Compressor", temperature_c=row["compressor_temperature_c"], pressure_bar=row["compressor_pressure_bar"], performance_percent=row["compressor_efficiency_percent"], work_kw=row["compressor_work_kw"], updated_at=now),
    ]
    outcome = None
    if sample == len(rows):
        censored = bool(row["censored"])
        outcome = LabOutcome(censored=censored, failed_equipment_id=None if censored else row["failed_equipment"],
                             failure_mode=None if censored else row["failure_mode"], shutdown_reason=row["shutdown_reason"])
    state = LabState(source_notice=NOTICE, generated_at=now, run_id=run, sample_index=sample,
                     total_samples=len(rows), time_minutes=int(row["time_minutes"]), assets=assets,
                     prognosis=prognosis(rows, sample), observed_outcome=outcome)
    history = LabHistory(run_id=run, end_sample=sample, total_samples=len(rows), points=[
        LabHistoryPoint(sample_index=index + 1, time_minutes=int(rows[index]["time_minutes"]),
                        reactor_pressure_bar=round(float(rows[index]["reactor_pressure_bar"]), 4))
        for index in range(max(0, sample - points), sample)])
    return LabFrame(state=state, history=history)
