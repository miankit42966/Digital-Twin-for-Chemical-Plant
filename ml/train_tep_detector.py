"""Train and evaluate a CPU TEP current-fault detector with held-out runs.

This is deliberately not a forecast: pre-onset rows have negative labels and
the model never receives fault number, sample index, or run ID as features.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import average_precision_score, confusion_matrix, precision_score, recall_score, roc_auc_score

from ml.ingestion.common import REPO_ROOT, sha256

SOURCE = REPO_ROOT / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet"
MODEL = REPO_ROOT / "models/tep_fault_detector.joblib"
CARD = REPO_ROOT / "docs/models/TEP_fault_detector.json"
FEATURES = [f"xmeas_{i}" for i in range(1, 42)] + [f"xmv_{i}" for i in range(1, 12)]


def samples() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    train_x, train_y, test_x, test_y = [], [], [], []
    columns = ["faultnumber", "simulationrun", "sample", "dataset_partition", *FEATURES]
    for batch in pq.ParquetFile(SOURCE).iter_batches(batch_size=25_000, columns=columns):
        frame = batch.to_pandas()
        fault = frame["faultnumber"].to_numpy(dtype=np.int16)
        run = frame["simulationrun"].to_numpy(dtype=np.int16)
        sample = frame["sample"].to_numpy(dtype=np.int16)
        partition = frame["dataset_partition"].to_numpy()
        train_partition = partition == "training"
        test_partition = partition == "testing"
        train_select = train_partition & (run <= 400) & (
            ((fault == 0) & (sample % 5 == 0))
            | ((fault > 0) & (run % 5 == 0) & (sample >= 21) & (sample % 20 == 0))
            | ((fault > 0) & (run % 5 == 0) & (sample < 21) & (sample % 4 == 0))
        )
        test_select = test_partition & (run >= 401) & (run <= 500) & (
            ((fault == 0) & (sample % 20 == 0))
            | ((fault > 0) & (run % 5 == 1) & (sample >= 161) & (sample % 20 == 0))
            | ((fault > 0) & (run % 5 == 1) & (sample < 161) & (sample % 40 == 0))
        )
        if train_select.any():
            train_x.append(frame.loc[train_select, FEATURES].to_numpy(dtype=np.float32))
            train_y.append(((fault > 0) & (sample >= 21))[train_select].astype(np.int8))
        if test_select.any():
            test_x.append(frame.loc[test_select, FEATURES].to_numpy(dtype=np.float32))
            test_y.append(((fault > 0) & (sample >= 161))[test_select].astype(np.int8))
    return np.concatenate(train_x), np.concatenate(train_y), np.concatenate(test_x), np.concatenate(test_y)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Run TEP ingestion first: {SOURCE}")
    train_x, train_y, test_x, test_y = samples()
    detector = ExtraTreesClassifier(
        n_estimators=64, max_depth=14, min_samples_leaf=5,
        class_weight="balanced", n_jobs=4, random_state=42,
    )
    detector.fit(train_x, train_y)
    scores = detector.predict_proba(test_x)[:, 1]
    predicted = scores >= .5
    benchmark = test_x[:1000]
    started = time.perf_counter()
    detector.predict_proba(benchmark)
    inference_ms_per_row = (time.perf_counter() - started) * 1000 / len(benchmark)
    tn, fp, fn, tp = (int(item) for item in confusion_matrix(test_y, predicted).ravel())
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"estimator": detector, "features": FEATURES, "dataset_sha256": sha256(SOURCE)}, MODEL)
    card = {
        "model_name": "TEP current-fault detector", "created_utc": datetime.now(UTC).isoformat(),
        "task": "Detect current injected TEP faults after their published onset; not a 20-minute forecast or real-world hazard probability.",
        "dataset": "Harvard Dataverse doi:10.7910/DVN/6C3JR1 v1.0",
        "dataset_sha256": sha256(SOURCE), "features": FEATURES,
        "label_rule": "faultnumber > 0 and sample >= 21 in training; faultnumber > 0 and sample >= 161 in testing",
        "split": "Training partition simulationRun 1-400; held-out testing partition simulationRun 401-500. Explicit deterministic row sampling in ml/train_tep_detector.py.",
        "n_train": int(len(train_y)), "n_train_positive": int(train_y.sum()),
        "n_test": int(len(test_y)), "n_test_positive": int(test_y.sum()),
        "threshold": .5, "precision": float(precision_score(test_y, predicted, zero_division=0)),
        "recall": float(recall_score(test_y, predicted, zero_division=0)),
        "average_precision": float(average_precision_score(test_y, scores)),
        "roc_auc": float(roc_auc_score(test_y, scores)),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "inference_ms_per_row_batch_1000": inference_ms_per_row,
        "limitations": [
            "A TEP simulated fault label is not an equipment failure, leak, or pressure safety limit.",
            "The test sample is enriched with faults; score is not a calibrated real-world probability.",
            "No independent plant data, physical validation, 20-minute forecast, or safety certification.",
        ],
    }
    CARD.write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(json.dumps({key: card[key] for key in ("n_train", "n_test", "precision", "recall", "average_precision", "roc_auc", "confusion_matrix")}, indent=2))


if __name__ == "__main__":
    main()
