"""Generate the labelled, explicitly synthetic equipment-prognosis benchmark."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ml.ingestion.common import REPO_ROOT, atomic_output, sha256

OUTPUT = REPO_ROOT / "data/processed/equipment_prognosis"
DATA = OUTPUT / "runs.parquet"
MANIFEST = OUTPUT / "manifest.json"
SEED = 20261008
SAMPLE_MINUTES = 3
MAX_SAMPLES = 480
EQUIPMENT = ("RX-201", "CD-201", "SP-201", "ST-301", "CP-201")
MODES = {
    "RX-201": ("cooling_capacity_loss", "agitator_efficiency_loss"),
    "CD-201": ("heat_transfer_fouling", "coolant_flow_loss"),
    "SP-201": ("outlet_restriction", "level_control_drift"),
    "ST-301": ("reboiler_duty_loss", "column_flooding"),
    "CP-201": ("compressor_efficiency_loss", "surge_recycle_instability"),
}
SENSORS = (
    "reactor_temperature_c", "reactor_pressure_bar", "reactor_level_percent", "reactor_feed_flow",
    "condenser_temperature_c", "condenser_pressure_bar", "condenser_duty_percent", "condenser_flow",
    "separator_temperature_c", "separator_pressure_bar", "separator_level_percent", "separator_underflow",
    "stripper_temperature_c", "stripper_pressure_bar", "stripper_level_percent", "stripper_underflow",
    "compressor_temperature_c", "compressor_pressure_bar", "compressor_efficiency_percent", "compressor_work_kw",
)
LABELS = ("failed_equipment", "failure_mode", "degradation_onset_sample", "terminal_sample",
          "remaining_minutes", "shutdown_reason", "censored")


def _trajectory(run_id: int, equipment: str | None, mode: str | None, rng: np.random.Generator) -> dict[str, np.ndarray]:
    censored = equipment is None
    terminal = MAX_SAMPLES if censored else int(rng.integers(360, MAX_SAMPLES + 1))
    onset = -1 if censored else int(terminal - rng.integers(80, 161))
    n = terminal if not censored else MAX_SAMPLES
    index = np.arange(1, n + 1)
    phase = rng.uniform(0, 2 * np.pi)
    slow = np.sin(index / 31 + phase)
    fast = np.sin(index / 8 + phase / 2)
    noise = rng.normal(0, 1, (n, len(SENSORS)))
    severity = np.zeros(n)
    if not censored:
        active = index >= onset
        severity[active] = np.clip((index[active] - onset) / max(1, terminal - onset), 0, 1) ** 1.6

    feed = 42 + 1.3 * slow + .35 * fast + noise[:, 3] * .25
    recycle = 31 + .7 * slow + noise[:, 19] * .2
    reactor_temp = 120 + 1.2 * slow + .35 * fast + noise[:, 0] * .18
    reactor_pressure = 27 + .28 * slow + noise[:, 1] * .06
    reactor_level = 58 + 3 * slow + noise[:, 2] * .45
    condenser_temp = 66 + .16 * (reactor_temp - 120) + noise[:, 4] * .15
    condenser_pressure = 25.8 + .25 * (reactor_pressure - 27) + noise[:, 5] * .05
    condenser_duty = 79 + 2 * slow + noise[:, 6] * .35
    condenser_flow = feed * .94 + noise[:, 7] * .18
    separator_temp = 80 + .18 * (condenser_temp - 66) + noise[:, 8] * .18
    separator_pressure = 26.2 + .45 * (condenser_pressure - 25.8) + noise[:, 9] * .05
    separator_level = 51 + 2.7 * slow + noise[:, 10] * .4
    separator_underflow = 24 + .15 * (feed - 42) + noise[:, 11] * .18
    stripper_temp = 65 + .12 * (separator_temp - 80) + noise[:, 12] * .18
    stripper_pressure = 31 + .2 * (separator_pressure - 26.2) + noise[:, 13] * .06
    stripper_level = 49 + 2.4 * slow + noise[:, 14] * .4
    stripper_underflow = 21 + .13 * (separator_underflow - 24) + noise[:, 15] * .16
    compressor_temp = 74 + .18 * (separator_temp - 80) + noise[:, 16] * .2
    compressor_pressure = 32 + .38 * (separator_pressure - 26.2) + noise[:, 17] * .06
    compressor_eff = 84 + .8 * slow + noise[:, 18] * .22
    compressor_work = 46 + .12 * recycle + noise[:, 19] * .28

    if mode == "cooling_capacity_loss": reactor_temp += 25 * severity; reactor_pressure += 5.2 * severity; condenser_temp += 5 * severity
    elif mode == "agitator_efficiency_loss": reactor_temp += 12 * severity; reactor_level += 15 * severity; feed -= 5 * severity
    elif mode == "heat_transfer_fouling": condenser_temp += 22 * severity; condenser_pressure += 4 * severity; condenser_duty += 17 * severity; separator_temp += 7 * severity
    elif mode == "coolant_flow_loss": condenser_temp += 18 * severity; condenser_flow -= 13 * severity; condenser_duty -= 24 * severity; separator_pressure += 2 * severity
    elif mode == "outlet_restriction": separator_level += 34 * severity; separator_pressure += 4.2 * severity; separator_underflow -= 10 * severity
    elif mode == "level_control_drift": separator_level += 27 * severity + 4 * severity * fast; separator_underflow += 7 * severity * fast
    elif mode == "reboiler_duty_loss": stripper_temp -= 19 * severity; stripper_pressure -= 4 * severity; stripper_underflow -= 8 * severity
    elif mode == "column_flooding": stripper_level += 37 * severity; stripper_pressure += 5 * severity; stripper_underflow -= 11 * severity
    elif mode == "compressor_efficiency_loss": compressor_eff -= 34 * severity; compressor_work += 25 * severity; compressor_temp += 18 * severity
    elif mode == "surge_recycle_instability":
        surge = severity * np.sin(index * 1.15)
        compressor_pressure += 7 * surge; compressor_work += 22 * np.abs(surge); recycle += 10 * surge

    arrays = [reactor_temp, reactor_pressure, reactor_level, feed, condenser_temp, condenser_pressure,
              condenser_duty, condenser_flow, separator_temp, separator_pressure, separator_level,
              separator_underflow, stripper_temp, stripper_pressure, stripper_level, stripper_underflow,
              compressor_temp, compressor_pressure, compressor_eff, compressor_work]
    result: dict[str, np.ndarray] = {
        "run_id": np.full(n, run_id, dtype=np.int32), "sample_index": index.astype(np.int16),
        "time_minutes": ((index - 1) * SAMPLE_MINUTES).astype(np.int16),
    }
    for name, values in zip(SENSORS, arrays):
        result[name] = np.asarray(values, dtype=np.float32)
    result.update({
        "failed_equipment": np.full(n, equipment or "NONE"), "failure_mode": np.full(n, mode or "healthy_censored"),
        "degradation_onset_sample": np.full(n, onset, dtype=np.int16), "terminal_sample": np.full(n, terminal, dtype=np.int16),
        "remaining_minutes": np.where(censored, -1, (terminal - index) * SAMPLE_MINUTES).astype(np.int16),
        "shutdown_reason": np.full(n, "censored_24h" if censored else f"synthetic_{mode}_limit"),
        "censored": np.full(n, censored),
    })
    return result


def generate() -> None:
    rng = np.random.default_rng(SEED)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metadata: list[dict] = []
    with atomic_output(DATA) as temporary:
        writer = None
        try:
            run_id = 0
            scenarios = [(equipment, mode) for equipment, modes in MODES.items() for mode in modes for _ in range(100)]
            scenarios.extend([(None, None)] * 200)
            rng.shuffle(scenarios)
            for equipment, mode in scenarios:
                run_id += 1
                values = _trajectory(run_id, equipment, mode, rng)
                table = pa.table(values)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                writer.write_table(table)
                metadata.append({"id": run_id, "samples": len(values["run_id"]), "censored": equipment is None,
                                 "equipment": equipment, "failure_mode": mode,
                                 "onset_sample": int(values["degradation_onset_sample"][0]),
                                 "terminal_sample": int(values["terminal_sample"][0])})
        finally:
            if writer is not None:
                writer.close()
    manifest = {
        "schema_version": 1, "source_kind": "SYNTHETIC_EQUIPMENT_PROGNOSIS", "generator_seed": SEED,
        "generator": "dynamic_surrogate_v1", "created_utc": datetime.now(UTC).isoformat(),
        "sample_period_minutes": SAMPLE_MINUTES, "nominal_duration_hours": 24, "run_count": len(metadata),
        "failure_run_count": 1000, "censored_run_count": 200, "equipment": list(EQUIPMENT),
        "failure_modes": MODES, "sensor_columns": list(SENSORS), "label_columns": list(LABELS),
        "columns": pq.ParquetFile(DATA).schema_arrow.names, "rows": pq.ParquetFile(DATA).metadata.num_rows,
        "data_sha256": sha256(DATA), "runs": metadata,
        "notice": "Labelled dynamic-surrogate simulation; not official TEP RTF data or physical plant evidence.",
    }
    with atomic_output(MANIFEST) as temporary:
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(metadata), "rows": manifest["rows"], "sha256": manifest["data_sha256"]}, indent=2))


if __name__ == "__main__":
    generate()
