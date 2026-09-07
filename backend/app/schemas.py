from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AlarmLevel = Literal["normal", "warning", "critical", "emergency_shutdown"]


class Telemetry(BaseModel):
    asset_id: str
    asset_name: str
    temperature_c: float
    pressure_bar: float
    level_percent: float = Field(ge=0, le=100)
    flow_m3h: float
    valve_open: bool
    gas_ppm: float
    risk_score: float = Field(ge=0, le=1)
    alarm_level: AlarmLevel
    updated_at: datetime


class PlantState(BaseModel):
    source_kind: Literal["SIMULATED_INTEGRATION_BASELINE"]
    source_notice: str
    generated_at: datetime
    assets: list[Telemetry]


class Incident(BaseModel):
    id: str
    title: str
    source_url: str
    status: Literal["PLACEHOLDER_NOT_A_REAL_INCIDENT"]
    similarity_note: str

