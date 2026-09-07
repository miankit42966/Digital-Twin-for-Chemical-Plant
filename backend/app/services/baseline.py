"""A deterministic UI integration baseline. This is not plant or ML data."""
from datetime import UTC, datetime
from math import sin

from app.schemas import PlantState, Telemetry

SOURCE_NOTICE = (
    "Synthetic integration baseline for UI/API testing only. Not TEP replay, "
    "live plant data, or ML inference."
)

ASSETS = (
    ("TK-101", "Feed Tank", 47.0, 4.1, 66.0, 82.0, False, 4.0),
    ("RX-201", "Reactor", 96.0, 6.9, 58.0, 66.0, True, 11.0),
    ("TK-301", "Buffer Tank", 54.0, 3.4, 42.0, 55.0, False, 3.0),
)


def _alarm(risk: float) -> str:
    if risk >= 0.85:
        return "emergency_shutdown"
    if risk >= 0.62:
        return "critical"
    if risk >= 0.35:
        return "warning"
    return "normal"


def state(tick: int = 0) -> PlantState:
    now = datetime.now(UTC)
    assets: list[Telemetry] = []
    for index, (asset_id, name, temp, pressure, level, flow, valve, gas) in enumerate(ASSETS):
        wave = sin((tick + index * 9) / 8)
        risk = max(0.04, min(0.95, 0.12 + index * 0.09 + (wave + 1) * 0.12))
        assets.append(Telemetry(
            asset_id=asset_id, asset_name=name,
            temperature_c=round(temp + wave * 2.6, 1),
            pressure_bar=round(pressure + wave * 0.18, 2),
            level_percent=round(level + wave * 3.0, 1),
            flow_m3h=round(flow + wave * 2.0, 1), valve_open=valve,
            gas_ppm=round(gas + max(0, wave) * 2.5, 1), risk_score=round(risk, 3),
            alarm_level=_alarm(risk), updated_at=now,
        ))
    return PlantState(source_kind="SIMULATED_INTEGRATION_BASELINE", source_notice=SOURCE_NOTICE,
                      generated_at=now, assets=assets)

