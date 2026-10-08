"""Fit a 20-minute-ahead reactor-pressure regression benchmark on TEP runs."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.ingestion.common import REPO_ROOT, atomic_output, sha256

SOURCE = REPO_ROOT / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet"
MODEL = REPO_ROOT / "models/tep_pressure_20m.joblib"
CARD = REPO_ROOT / "docs/models/TEP_pressure_20m.json"
SENSORS = ("xmeas_7", "xmeas_8", "xmeas_9", "xmeas_13", "xmeas_16")
FEATURES = [*SENSORS, "reactor_pressure_delta_1", "reactor_pressure_delta_3"]


def rows_for_run(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    frame = frame.sort_values("sample")
    samples = frame["sample"].to_numpy(dtype=np.int32)
    if len(samples) < 8 or not np.all(np.diff(samples) == 1):
        raise ValueError("TEP run is incomplete or sample indices are discontinuous")
    values = frame.loc[:, list(SENSORS)].to_numpy(dtype=np.float32)
    pressure = values[:, 0]
    # Simulated measurement spacing is 3 min. Linear interpolation between
    # future samples at +18 and +21 min estimates pressure at exactly +20 min.
    target = pressure[6:-1] / 3 + pressure[7:] * (2 / 3)
    current = values[:-7]
    delta_1 = current[:, 0] - np.r_[pressure[0], pressure[:len(current) - 1]]
    delta_3 = current[:, 0] - np.r_[np.repeat(pressure[0], 3), pressure[:len(current) - 3]]
    features = np.column_stack((current, delta_1, delta_3))
    keep = (samples[:-7] % 12 == 0) & (samples[:-7] > 3)
    return features[keep], target[keep]


def dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    columns = ["faultnumber", "simulationrun", "sample", "dataset_partition", *SENSORS]
    groups: dict[tuple[str, int, int], list[pd.DataFrame]] = {}
    for batch in pq.ParquetFile(SOURCE).iter_batches(batch_size=25_000, columns=columns):
        frame = batch.to_pandas()
        run = frame["simulationrun"].to_numpy(dtype=np.int16)
        partition = frame["dataset_partition"].to_numpy()
        selected = ((partition == "training") & (run <= 400) & (run % 10 == 0)) | (
            (partition == "testing") & (run >= 401) & (run % 10 == 1)
        )
        for key, segment in frame.loc[selected].groupby(["dataset_partition", "faultnumber", "simulationrun"], sort=False):
            groups.setdefault((str(key[0]), int(key[1]), int(key[2])), []).append(segment[["sample", *SENSORS]])
    train_x, train_y, test_x, test_y = [], [], [], []
    for (partition, _, _), chunks in groups.items():
        features, target = rows_for_run(pd.concat(chunks, ignore_index=True))
        if partition == "training":
            train_x.append(features); train_y.append(target)
        else:
            test_x.append(features); test_y.append(target)
    return np.concatenate(train_x), np.concatenate(train_y), np.concatenate(test_x), np.concatenate(test_y)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Run TEP ingestion first: {SOURCE}")
    train_x, train_y, test_x, test_y = dataset()
    model = HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=31, max_depth=8, l2_regularization=1, random_state=42)
    model.fit(train_x, train_y)
    predicted = model.predict(test_x)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    dataset_sha256 = sha256(SOURCE)
    artifact_id = uuid4().hex
    bundle = {"estimator": model, "features": FEATURES, "dataset_sha256": dataset_sha256,
              "artifact_id": artifact_id}
    card = {
        "model_name": "TEP reactor pressure at +20 simulated minutes",
        "created_utc": datetime.now(UTC).isoformat(),
        "task": "Estimate reactor pressure in kPa gauge at +20 simulated minutes; not an event or hazard probability.",
        "dataset": "Harvard Dataverse doi:10.7910/DVN/6C3JR1 v1.0",
        "dataset_sha256": dataset_sha256, "artifact_id": artifact_id, "features": FEATURES,
        "target": "Linear interpolation of xmeas_7 at samples +6 and +7, corresponding to +18 and +21 minutes at the documented three-minute cadence.",
        "split": "Training partition runs divisible by 10 up to 400; held-out testing partition runs ending in 1 from 401–500. Rows every 12 samples.",
        "n_train": int(len(train_y)), "n_test": int(len(test_y)),
        "mae_kpa_gauge": float(mean_absolute_error(test_y, predicted)),
        "rmse_kpa_gauge": float(np.sqrt(mean_squared_error(test_y, predicted))),
        "r2": float(r2_score(test_y, predicted)),
        "p95_absolute_error_kpa_gauge": float(np.quantile(np.abs(test_y - predicted), .95)),
        "limitations": [
            "The +20 minute target is interpolated between two future simulation samples, not directly observed at that instant.",
            "A pressure estimate is not a leak, overpressure, or equipment-failure probability.",
            "No plant-specific limits, independent operational validation, uncertainty calibration, or safety certification.",
        ],
    }
    with atomic_output(MODEL) as temporary:
        joblib.dump(bundle, temporary)
    with atomic_output(CARD) as temporary:
        temporary.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: card[key] for key in ("n_train", "n_test", "mae_kpa_gauge", "rmse_kpa_gauge", "r2", "p95_absolute_error_kpa_gauge")}, indent=2))


if __name__ == "__main__":
    main()
