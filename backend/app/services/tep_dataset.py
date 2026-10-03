"""Query published TEP trajectories directly from the local Parquet dataset.

The benchmark is a recorded *simulation*. It is never represented as a live
plant connection or as a calibrated equipment-failure forecast.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyarrow.dataset as ds

from app.schemas import DatasetFrame, PlantState, ReplayPoint, ReplaySeries, Telemetry
from app.services import tep_models
from app.services.cache import singleflight_cache

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet"
FEATURES = tep_models.FEATURES
NOTICE = (
    "Published Tennessee Eastman Process simulation data selected from the local dataset. "
    "Not live plant telemetry, an operational alarm, or a failure-probability forecast."
)


def available() -> bool:
    return SOURCE.is_file()


def _validate(partition: str, fault: int, run: int) -> int:
    if partition not in {"training", "testing"}:
        raise ValueError("partition must be training or testing")
    if not 0 <= fault <= 20:
        raise ValueError("fault must be from 0 to 20")
    if not 1 <= run <= 500:
        raise ValueError("run must be from 1 to 500")
    return 500 if partition == "training" else 960


@singleflight_cache(maxsize=1)
def _dataset(signature: tuple[int, int]) -> ds.Dataset:
    if not available():
        raise FileNotFoundError(f"TEP Parquet dataset missing: {SOURCE}")
    return ds.dataset(str(SOURCE), format="parquet")


def trajectory(partition: str = "testing", fault: int = 6, run: int = 401) -> tuple[dict, ...]:
    _validate(partition, fault, run)
    stat = SOURCE.stat()
    return _trajectory(partition, fault, run, (stat.st_mtime_ns, stat.st_size))


@singleflight_cache(maxsize=8)
def _trajectory(partition: str, fault: int, run: int, signature: tuple[int, int]) -> tuple[dict, ...]:
    expected = _validate(partition, fault, run)
    condition = "fault_free" if fault == 0 else "faulty"
    predicate = (
        (ds.field("dataset_partition") == partition)
        & (ds.field("published_condition") == condition)
        & (ds.field("faultnumber") == float(fault))
        & (ds.field("simulationrun") == float(run))
    )
    table = _dataset(signature).to_table(filter=predicate, columns=["sample", *FEATURES])
    if table.num_rows != expected:
        raise ValueError(f"Expected {expected} rows for {partition}/fault {fault}/run {run}; found {table.num_rows}")
    rows = tuple(table.sort_by([("sample", "ascending")]).to_pylist())
    if [int(row["sample"]) for row in rows] != list(range(1, expected + 1)):
        raise ValueError("TEP sample sequence is incomplete")
    return rows


def state(sample: int = 170, partition: str = "testing", fault: int = 6, run: int = 401) -> PlantState:
    rows = trajectory(partition, fault, run)
    return _state(rows, sample, partition, fault, run)


def _state(rows: tuple[dict, ...], sample: int, partition: str, fault: int, run: int) -> PlantState:
    if not 1 <= sample <= len(rows):
        raise ValueError(f"sample must be from 1 to {len(rows)}")
    row = rows[sample - 1]
    now = datetime.now(UTC)
    mapping = (
        ("RX-201", "Reactor", 9, 7, 8, 6, "kscmh"),
        ("SP-201", "Separator", 11, 13, 12, 14, "m3/h"),
        ("ST-301", "Stripper", 18, 16, 15, 17, "m3/h"),
    )
    assets = [
        Telemetry(
            asset_id=asset_id, asset_name=name,
            temperature_c=round(float(row[f"xmeas_{temperature}"]), 2),
            pressure_bar=round(float(row[f"xmeas_{pressure}"]) / 100, 3),
            level_percent=round(float(row[f"xmeas_{level}"]), 2),
            flow_value=round(float(row[f"xmeas_{flow}"]), 3), flow_unit=unit,
            alarm_level="unassessed", updated_at=now,
        ) for asset_id, name, temperature, pressure, level, flow, unit in mapping
    ]
    score, forecast, model_status, model_notices = tep_models.infer(rows, sample)
    return PlantState(
        source_kind="TEP_DATASET", source_notice=NOTICE, generated_at=now,
        assets=assets, sample_index=sample, elapsed_minutes=(sample - 1) * 3,
        fault_number=fault, simulation_run=run, dataset_partition=partition,
        total_samples=len(rows), sample_period_minutes=3,
        detector_score=score, reactor_pressure_20m_bar_g=forecast,
        model_status=model_status, model_notices=model_notices,
    )


def series(end_sample: int = 170, points: int = 90, partition: str = "testing", fault: int = 6, run: int = 401) -> ReplaySeries:
    rows = trajectory(partition, fault, run)
    return _series(rows, end_sample, points, partition, fault, run)


def _series(rows: tuple[dict, ...], end_sample: int, points: int, partition: str, fault: int, run: int) -> ReplaySeries:
    if not 1 <= end_sample <= len(rows):
        raise ValueError(f"end_sample must be from 1 to {len(rows)}")
    if not 2 <= points <= 240:
        raise ValueError("points must be from 2 to 240")
    values = []
    for row in rows[max(0, end_sample - points):end_sample]:
        sample = int(row["sample"])
        values.append(ReplayPoint(
            sample_index=sample, elapsed_minutes=(sample - 1) * 3,
            reactor_pressure_bar_g=round(float(row["xmeas_7"]) / 100, 3),
            reactor_temperature_c=round(float(row["xmeas_9"]), 2),
            reactor_level_percent=round(float(row["xmeas_8"]), 2),
            separator_pressure_bar_g=round(float(row["xmeas_13"]) / 100, 3),
            stripper_pressure_bar_g=round(float(row["xmeas_16"]) / 100, 3),
        ))
    return ReplaySeries(
        source_kind="TEP_DATASET", dataset_partition=partition,
        simulation_run=run, fault_number=fault, sample_period_minutes=3,
        end_sample=end_sample, total_samples=len(rows), points=values,
    )


def frame(sample: int = 170, points: int = 90, partition: str = "testing", fault: int = 6, run: int = 401) -> DatasetFrame:
    rows = trajectory(partition, fault, run)
    return DatasetFrame(state=_state(rows, sample, partition, fault, run), history=_series(rows, sample, points, partition, fault, run))
