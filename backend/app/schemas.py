from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AlarmLevel = Literal["normal", "warning", "critical", "emergency_shutdown", "unassessed"]


class DetectorSensitivityFactor(BaseModel):
    feature: str
    observed_value: float
    reference_median: float
    score_delta: float


class DetectorExplanation(BaseModel):
    method: Literal["one_feature_at_a_time_median_replacement"]
    ensemble_tree_std: float = Field(ge=0)
    top_positive_factors: list[DetectorSensitivityFactor]
    top_negative_factors: list[DetectorSensitivityFactor]
    disclaimer: str


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
    detector_explanation: DetectorExplanation | None = None
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
        reactor = next((asset for asset in self.state.assets if asset.asset_id == "RX-201"), None)
        if reactor is None or reactor.pressure_bar != self.history.points[-1].reactor_pressure_bar_g:
            raise ValueError("State and history reactor pressure must match")
        return self


class RtfTelemetry(Telemetry):
    # The source records can cross a shutdown limit; retain their raw readings.
    level_percent: float


class RtfPrognosis(BaseModel):
    status: Literal["ready", "missing", "invalid", "needs_history"]
    remaining_minutes: float | None = Field(default=None, ge=0)
    next_unit_id: Literal["RX-201", "SP-201", "ST-301"] | None = None
    highlight_unit_id: Literal["RX-201", "SP-201", "ST-301"] | None = None
    unit_status: Literal["unavailable_no_verified_labels", "abstained", "ready"]
    warning_horizon_minutes: int = 60
    notice: str

    @model_validator(mode="after")
    def fail_closed_warning(self) -> "RtfPrognosis":
        if self.highlight_unit_id is not None and (self.unit_status != "ready"
                or self.next_unit_id != self.highlight_unit_id or self.remaining_minutes is None
                or self.remaining_minutes > self.warning_horizon_minutes):
            raise ValueError("Equipment highlight requires a ready matching unit within the warning horizon")
        if self.next_unit_id is not None and self.unit_status != "ready":
            raise ValueError("Next equipment requires ready verified-label inference")
        return self


class RtfState(BaseModel):
    source_kind: Literal["TEP_RTF"] = "TEP_RTF"
    source_notice: str
    generated_at: datetime
    case_id: str
    simulation_id: int
    sample_index: int
    total_samples: int
    time_hours: float
    assets: list[RtfTelemetry]
    prognosis: RtfPrognosis


class RtfHistoryPoint(BaseModel):
    sample_index: int
    time_hours: float
    reactor_pressure_bar_g: float


class RtfHistory(BaseModel):
    source_kind: Literal["TEP_RTF"] = "TEP_RTF"
    case_id: str
    simulation_id: int
    end_sample: int
    total_samples: int
    points: list[RtfHistoryPoint]


class RtfFrame(BaseModel):
    state: RtfState
    history: RtfHistory

    @model_validator(mode="after")
    def synchronized(self) -> "RtfFrame":
        if (self.state.case_id != self.history.case_id or self.state.simulation_id != self.history.simulation_id
                or self.state.sample_index != self.history.end_sample or self.state.total_samples != self.history.total_samples
                or not self.history.points or self.history.points[-1].sample_index != self.state.sample_index):
            raise ValueError("RTF state and history must refer to one committed sample")
        reactor = next((asset for asset in self.state.assets if asset.asset_id == "RX-201"), None)
        if reactor is None or reactor.pressure_bar != self.history.points[-1].reactor_pressure_bar_g:
            raise ValueError("RTF state and history reactor pressure must match")
        return self


LabEquipmentId = Literal["RX-201", "CD-201", "SP-201", "ST-301", "CP-201"]


class LabTelemetry(BaseModel):
    asset_id: LabEquipmentId
    asset_name: str
    temperature_c: float | None = None
    pressure_bar: float | None = None
    level_percent: float | None = Field(default=None, ge=0, le=100)
    flow_value: float | None = None
    flow_unit: str | None = None
    performance_percent: float | None = None
    work_kw: float | None = None
    alarm_level: Literal["unassessed"] = "unassessed"
    updated_at: datetime


class LabPrognosis(BaseModel):
    status: Literal["ready", "missing", "invalid", "needs_history"]
    failure_within_horizon_probability: float | None = Field(default=None, ge=0, le=1)
    remaining_minutes: float | None = Field(default=None, ge=0)
    predicted_equipment_id: LabEquipmentId | None = None
    predicted_failure_mode: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    unit_status: Literal["unassessed", "abstained", "ready"]
    warning_horizon_minutes: int = 60
    highlight_equipment_id: LabEquipmentId | None = None
    notice: str

    @model_validator(mode="after")
    def fail_closed_warning(self) -> "LabPrognosis":
        if self.highlight_equipment_id is not None and (
            self.status != "ready" or self.unit_status != "ready"
            or self.predicted_equipment_id != self.highlight_equipment_id
            or self.remaining_minutes is None or self.remaining_minutes > self.warning_horizon_minutes
        ):
            raise ValueError("Lab highlight requires a validated ready prediction within the warning horizon")
        if self.unit_status != "ready" and self.predicted_equipment_id is not None:
            raise ValueError("Abstained lab prognosis cannot name equipment")
        return self


class LabOutcome(BaseModel):
    censored: bool
    failed_equipment_id: LabEquipmentId | None = None
    failure_mode: str | None = None
    shutdown_reason: str


class LabState(BaseModel):
    source_kind: Literal["SYNTHETIC_EQUIPMENT_PROGNOSIS"] = "SYNTHETIC_EQUIPMENT_PROGNOSIS"
    source_notice: str
    generated_at: datetime
    run_id: int
    sample_index: int
    total_samples: int
    time_minutes: int
    assets: list[LabTelemetry]
    prognosis: LabPrognosis
    observed_outcome: LabOutcome | None = None


class LabHistoryPoint(BaseModel):
    sample_index: int
    time_minutes: int
    reactor_pressure_bar: float


class LabHistory(BaseModel):
    source_kind: Literal["SYNTHETIC_EQUIPMENT_PROGNOSIS"] = "SYNTHETIC_EQUIPMENT_PROGNOSIS"
    run_id: int
    end_sample: int
    total_samples: int
    points: list[LabHistoryPoint]


class LabFrame(BaseModel):
    state: LabState
    history: LabHistory

    @model_validator(mode="after")
    def synchronized(self) -> "LabFrame":
        if (self.state.run_id != self.history.run_id or self.state.sample_index != self.history.end_sample
                or self.state.total_samples != self.history.total_samples or not self.history.points
                or self.history.points[-1].sample_index != self.state.sample_index):
            raise ValueError("Lab state and history must refer to one committed sample")
        reactor = next((asset for asset in self.state.assets if asset.asset_id == "RX-201"), None)
        if (reactor is None or reactor.pressure_bar is None
                or abs(reactor.pressure_bar - self.history.points[-1].reactor_pressure_bar) > 0.0001):
            raise ValueError("Lab state and history reactor pressure must match")
        if self.state.observed_outcome is not None and self.state.sample_index != self.state.total_samples:
            raise ValueError("Synthetic outcome may be revealed only at the terminal sample")
        return self


class Incident(BaseModel):
    id: str
    title: str
    source_url: str
    status: Literal["PLACEHOLDER_NOT_A_REAL_INCIDENT"]
    similarity_note: str

