"""Read-only replay of an actual published TEP testing trajectory."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import PlantState, ReplayPoint, ReplaySeries, Telemetry
from app.services import tep_models
from app.services.cache import singleflight_cache

REPLAY = Path(__file__).resolve().parents[3] / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/replay.json"
NOTICE = (
    "Recorded Tennessee Eastman Process simulation, played back faster than source time. "
    "No live plant connection, validated hazard alarm, or future risk prediction."
)


def _data() -> dict:
    if not REPLAY.exists():
        raise FileNotFoundError("TEP replay is not prepared. Run: python -m ml.ingestion.prepare_tep_replay")
    stat = REPLAY.stat()
    return _read_data((stat.st_mtime_ns, stat.st_size))


@singleflight_cache(maxsize=1)
def _read_data(signature: tuple[int, int]) -> dict:
    payload = json.loads(REPLAY.read_text(encoding="utf-8"))
    if len(payload["rows"]) != 960:
        raise ValueError("TEP replay file is incomplete")
    return payload


def available() -> bool:
    return REPLAY.exists()


def model_available() -> bool:
    return tep_models.availability()["detector"] == "ready"


def pressure_model_available() -> bool:
    return tep_models.availability()["pressure"] == "ready"


def state(sample: int = 1) -> PlantState:
    data = _data()
    if sample < 1 or sample > len(data["rows"]):
        raise ValueError("sample must be from 1 to 960")
    row = data["rows"][sample - 1]
    now = datetime.now(UTC)
    mapping = (
        ("RX-201", "Reactor", 9, 7, 8, 6, "kscmh"),
        ("SP-201", "Separator", 11, 13, 12, 14, "m3/h"),
        ("ST-301", "Stripper", 18, 16, 15, 17, "m3/h"),
    )
    assets = [
        Telemetry(
            asset_id=asset_id, asset_name=name,
            temperature_c=round(float(row[f"xmeas_{temp}"]), 2),
            pressure_bar=round(float(row[f"xmeas_{pressure}"]) / 100, 3),
            level_percent=round(float(row[f"xmeas_{level}"]), 2),
            flow_value=round(float(row[f"xmeas_{flow}"]), 3), flow_unit=unit,
            alarm_level="unassessed", updated_at=now,
        )
        for asset_id, name, temp, pressure, level, flow, unit in mapping
    ]
    detector_score, pressure_forecast, model_status, model_notices, explanation = tep_models.infer(data["rows"], sample)
    return PlantState(
        source_kind="TEP_REPLAY", source_notice=NOTICE, generated_at=now,
        sample_index=sample, elapsed_minutes=(sample - 1) * int(data["sample_period_minutes"]),
        fault_number=int(data["fault_number"]), simulation_run=int(data["simulation_run"]),
        detector_score=detector_score, detector_explanation=explanation,
        reactor_pressure_20m_bar_g=pressure_forecast, assets=assets,
        dataset_partition="testing", total_samples=len(data["rows"]), sample_period_minutes=int(data["sample_period_minutes"]),
        model_status=model_status, model_notices=model_notices,
    )


def series(end_sample: int = 170, points: int = 90) -> ReplaySeries:
    """Return a bounded recorded history, without synthetic or model-derived points."""
    data = _data()
    if not 1 <= end_sample <= len(data["rows"]):
        raise ValueError("end_sample must be from 1 to 960")
    if not 2 <= points <= 240:
        raise ValueError("points must be from 2 to 240")
    start = max(0, end_sample - points)
    period = int(data["sample_period_minutes"])
    values = []
    for row in data["rows"][start:end_sample]:
        sample = int(row["sample"])
        values.append(ReplayPoint(
            sample_index=sample, elapsed_minutes=(sample - 1) * period,
            reactor_pressure_bar_g=round(float(row["xmeas_7"]) / 100, 3),
            reactor_temperature_c=round(float(row["xmeas_9"]), 2),
            reactor_level_percent=round(float(row["xmeas_8"]), 2),
            separator_pressure_bar_g=round(float(row["xmeas_13"]) / 100, 3),
            stripper_pressure_bar_g=round(float(row["xmeas_16"]) / 100, 3),
        ))
    return ReplaySeries(
        simulation_run=int(data["simulation_run"]), fault_number=int(data["fault_number"]),
        sample_period_minutes=period, end_sample=end_sample, points=values,
        dataset_partition="testing", total_samples=len(data["rows"]),
    )
