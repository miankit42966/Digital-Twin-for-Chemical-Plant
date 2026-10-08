"""Train and evaluate a CPU TEP current-fault detector with held-out runs.

This is deliberately not a forecast: pre-onset rows have negative labels and
the model never receives fault number, sample index, or run ID as features.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, precision_score, recall_score, roc_auc_score

from ml.ingestion.common import REPO_ROOT, atomic_output, sha256

SOURCE = REPO_ROOT / "data/processed/tep/harvard-dvn-6c3jr1-v1.0/tep.parquet"
MODEL = REPO_ROOT / "models/tep_fault_detector.joblib"
CARD = REPO_ROOT / "docs/models/TEP_fault_detector.json"
FEATURES = [f"xmeas_{i}" for i in range(1, 42)] + [f"xmv_{i}" for i in range(1, 12)]


def samples() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    train_x, train_y, test_x, test_y, test_fault = [], [], [], [], []
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
            test_fault.append(fault[test_select])
    return (
        np.concatenate(train_x), np.concatenate(train_y),
        np.concatenate(test_x), np.concatenate(test_y), np.concatenate(test_fault),
    )


def calibration_evidence(labels: np.ndarray, scores: np.ndarray, bin_count: int = 10) -> dict:
    """Summarize held-out score calibration without treating it as plant probability."""
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    # Include a score of exactly one in the final bin.
    memberships = np.minimum(np.digitize(scores, edges[1:-1], right=False), bin_count - 1)
    bins = []
    ece = 0.0
    for index in range(bin_count):
        selected = memberships == index
        count = int(selected.sum())
        if count:
            mean_score = float(scores[selected].mean())
            observed_rate = float(labels[selected].mean())
            ece += count / len(labels) * abs(mean_score - observed_rate)
        else:
            mean_score = observed_rate = None
        bins.append({
            "lower": float(edges[index]), "upper": float(edges[index + 1]),
            "count": count, "mean_score": mean_score, "observed_positive_rate": observed_rate,
        })
    return {
        "brier_score": float(brier_score_loss(labels, scores)),
        "expected_calibration_error": float(ece),
        "bin_count": bin_count,
        "method": "Equal-width bins on the held-out TEP sample set; the enriched case mix is not real-world probability calibration.",
        "bins": bins,
    }


def per_fault_recall(labels: np.ndarray, predicted: np.ndarray, faults: np.ndarray) -> dict[str, dict[str, float | int]]:
    evidence = {}
    for fault in sorted(int(value) for value in np.unique(faults) if value > 0):
        selected = (faults == fault) & (labels == 1)
        support = int(selected.sum())
        true_positive = int(predicted[selected].sum())
        evidence[str(fault)] = {
            "recall": float(true_positive / support) if support else 0.0,
            "support": support,
            "true_positive": true_positive,
        }
    return evidence


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Run TEP ingestion first: {SOURCE}")
    train_x, train_y, test_x, test_y, test_fault = samples()
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
    training_medians = np.median(train_x, axis=0).astype(np.float32)
    global_feature_importance = sorted(
        ({"feature": name, "importance": float(importance)} for name, importance in zip(FEATURES, detector.feature_importances_, strict=True)),
        key=lambda item: (-item["importance"], item["feature"]),
    )
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    dataset_sha256 = sha256(SOURCE)
    artifact_id = uuid4().hex
    bundle = {
        "estimator": detector, "features": FEATURES, "dataset_sha256": dataset_sha256,
        "artifact_id": artifact_id, "training_medians": training_medians,
    }
    card = {
        "model_name": "TEP current-fault detector", "created_utc": datetime.now(UTC).isoformat(),
        "task": "Detect current injected TEP faults after their published onset; not a 20-minute forecast or real-world hazard probability.",
        "dataset": "Harvard Dataverse doi:10.7910/DVN/6C3JR1 v1.0",
        "dataset_sha256": dataset_sha256, "artifact_id": artifact_id, "features": FEATURES,
        "label_rule": "faultnumber > 0 and sample >= 21 in training; faultnumber > 0 and sample >= 161 in testing",
        "split": "Training partition simulationRun 1-400; held-out testing partition simulationRun 401-500. Explicit deterministic row sampling in ml/train_tep_detector.py.",
        "n_train": int(len(train_y)), "n_train_positive": int(train_y.sum()),
        "n_test": int(len(test_y)), "n_test_positive": int(test_y.sum()),
        "threshold": .5, "precision": float(precision_score(test_y, predicted, zero_division=0)),
        "recall": float(recall_score(test_y, predicted, zero_division=0)),
        "average_precision": float(average_precision_score(test_y, scores)),
        "roc_auc": float(roc_auc_score(test_y, scores)),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "calibration_evidence": calibration_evidence(test_y, scores),
        "per_fault_recall": per_fault_recall(test_y, predicted, test_fault),
        "global_feature_importance": global_feature_importance,
        "inference_ms_per_row_batch_1000": inference_ms_per_row,
        "limitations": [
            "A TEP simulated fault label is not an equipment failure, leak, or pressure safety limit.",
            "The test sample is enriched with faults; score is not a calibrated real-world probability.",
            "No independent plant data, physical validation, 20-minute forecast, or safety certification.",
        ],
    }
    with atomic_output(MODEL) as temporary:
        joblib.dump(bundle, temporary)
    with atomic_output(CARD) as temporary:
        temporary.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: card[key] for key in ("n_train", "n_test", "precision", "recall", "average_precision", "roc_auc", "confusion_matrix", "calibration_evidence", "per_fault_recall")}, indent=2))


if __name__ == "__main__":
    main()
