from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AlarmLevel = Literal["normal", "warning", "critical", "emergency_shutdown", "unassessed"]


class Telemetry(BaseModel):
    asset_id: str
    asset_name: str
    temperature_c: float
    pressure_bar: float
    level_percent: float = Field(ge=0, le=100)
    flow_m3h: float | None = None
    flow_value: float | None = None
    flow_unit: str | None = None
    valve_open: bool | None = None
    gas_ppm: float | None = None
    risk_score: float | None = Field(default=None, ge=0, le=1)
    alarm_level: AlarmLevel
    updated_at: datetime


class PlantState(BaseModel):
    source_kind: Literal["SIMULATED_INTEGRATION_BASELINE", "TEP_REPLAY", "TEP_DATASET"]
    source_notice: str
    generated_at: datetime
    assets: list[Telemetry]
    sample_index: int | None = None
    elapsed_minutes: int | None = None
    fault_number: int | None = None
    simulation_run: int | None = None
    dataset_partition: Literal["training", "testing"] | None = None
    total_samples: int | None = None
    sample_period_minutes: int | None = None
    detector_score: float | None = Field(default=None, ge=0, le=1)
    reactor_pressure_20m_bar_g: float | None = None
    model_status: dict[str, Literal["ready", "missing", "invalid"]] = Field(default_factory=dict)
    model_notices: dict[str, str] = Field(default_factory=dict)


class ReplayPoint(BaseModel):
    sample_index: int
    elapsed_minutes: int
    reactor_pressure_bar_g: float
    reactor_temperature_c: float
    reactor_level_percent: float
    separator_pressure_bar_g: float
    stripper_pressure_bar_g: float


class ReplaySeries(BaseModel):
    source_kind: Literal["TEP_REPLAY", "TEP_DATASET"] = "TEP_REPLAY"
    simulation_run: int
    fault_number: int
    dataset_partition: Literal["training", "testing"] | None = None
    sample_period_minutes: int
    end_sample: int
    total_samples: int | None = None
    points: list[ReplayPoint]


class DatasetFrame(BaseModel):
    state: PlantState
    history: ReplaySeries

    @model_validator(mode="after")
    def synchronized(self) -> "DatasetFrame":
        fields = ("source_kind", "dataset_partition", "fault_number", "simulation_run", "total_samples", "sample_period_minutes")
        if any(getattr(self.state, name) != getattr(self.history, name) for name in fields):
            raise ValueError("State and history must refer to the same dataset trajectory")
        if self.state.sample_index != self.history.end_sample or not self.history.points or self.history.points[-1].sample_index != self.state.sample_index:
            raise ValueError("State and history must end at the same sample")
        return self


class Incident(BaseModel):
    id: str
    title: str
    source_url: str
    status: Literal["PLACEHOLDER_NOT_A_REAL_INCIDENT"]
    similarity_note: str

