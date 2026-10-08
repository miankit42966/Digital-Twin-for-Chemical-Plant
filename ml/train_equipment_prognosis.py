"""Train past-only failure-window, equipment/mode and RUL models."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.metrics import (confusion_matrix, f1_score, mean_absolute_error, precision_recall_fscore_support,
                             precision_score, recall_score)

from ml.ingestion.common import REPO_ROOT, atomic_output, sha256
from ml.simulation.generate_equipment_prognosis import DATA, EQUIPMENT, MANIFEST, MODES, SENSORS

MODEL = REPO_ROOT / "models/equipment_prognosis.joblib"
CARD = REPO_ROOT / "docs/models/EQUIPMENT_PROGNOSIS.json"
FEATURES = tuple(f"{kind}:{sensor}" for kind in ("now", "delta_1", "delta_20", "mean_20") for sensor in SENSORS)
HISTORY = 21
HORIZON = 60


def split_for_run(run_id: int) -> str:
    bucket = int(hashlib.sha256(f"equipment-prognosis-v1/{run_id}".encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def feature_rows(values: np.ndarray, indexes: np.ndarray) -> np.ndarray:
    prefix = np.vstack((np.zeros((1, values.shape[1])), values.cumsum(axis=0, dtype=np.float64)))
    mean = (prefix[indexes + 1] - prefix[indexes - 19]) / 20
    return np.column_stack((values[indexes], values[indexes] - values[indexes - 1],
                            values[indexes] - values[indexes - 20], mean)).astype(np.float32)


def load_examples() -> dict[str, dict[str, np.ndarray]]:
    table = pq.read_table(DATA, columns=["run_id", "sample_index", *SENSORS, "failed_equipment", "failure_mode", "remaining_minutes", "censored"])
    frame = table.to_pandas()
    collected = {split: {key: [] for key in ("x", "risk", "unit", "mode", "rul", "run", "censored")} for split in ("train", "validation", "test")}
    for run_id, group in frame.groupby("run_id", sort=False):
        values = group.loc[:, list(SENSORS)].to_numpy(np.float32)
        indexes = np.arange(20, len(group), 3)
        if len(group) - 1 not in indexes:
            indexes = np.append(indexes, len(group) - 1)
        remaining = group["remaining_minutes"].to_numpy(np.int32)[indexes]
        censored = bool(group["censored"].iloc[0])
        equipment = str(group["failed_equipment"].iloc[0])
        mode = str(group["failure_mode"].iloc[0])
        split = split_for_run(int(run_id)); destination = collected[split]
        destination["x"].append(feature_rows(values, indexes))
        destination["risk"].append(((not censored) & (remaining >= 0) & (remaining <= HORIZON)).astype(np.int8))
        destination["unit"].append(np.full(len(indexes), equipment)); destination["mode"].append(np.full(len(indexes), mode))
        destination["rul"].append(remaining.astype(np.float32)); destination["run"].append(np.full(len(indexes), int(run_id)))
        destination["censored"].append(np.full(len(indexes), censored))
    return {split: {key: np.concatenate(value) for key, value in values.items()} for split, values in collected.items()}


def choose_threshold(truth: np.ndarray, scores: np.ndarray, minimum_precision: float) -> float:
    candidates = np.linspace(.35, .99, 129)
    valid = [(float(t), recall_score(truth, scores >= t, zero_division=0)) for t in candidates
             if precision_score(truth, scores >= t, zero_division=0) >= minimum_precision]
    return max(valid, key=lambda item: item[1])[0] if valid else 1.0


def evaluate(data: dict[str, np.ndarray], risk_model, unit_model, mode_model, rul_model,
             risk_threshold: float, unit_thresholds: dict[str, float]) -> dict:
    risk_scores = risk_model.predict_proba(data["x"])[:, 1]
    risk_pred = risk_scores >= risk_threshold
    positive = data["risk"] == 1
    unit_scores = unit_model.predict_proba(data["x"][positive]); unit_index = unit_scores.argmax(axis=1)
    unit_pred = unit_model.classes_[unit_index]; unit_conf = unit_scores.max(axis=1)
    accepted = np.asarray([unit_conf[i] >= unit_thresholds.get(str(label), 1.0) for i, label in enumerate(unit_pred)])
    labels = list(EQUIPMENT)
    per_precision, per_recall, _, support = precision_recall_fscore_support(data["unit"][positive][accepted], unit_pred[accepted], labels=labels, zero_division=0)
    mode_pred = mode_model.predict(data["x"][positive])
    failure = ~data["censored"]
    rul_mask = failure & (data["rul"] >= 0) & (data["rul"] <= HORIZON)
    rul_prediction = np.maximum(0, rul_model.predict(data["x"][rul_mask]))
    censored_warning = risk_pred[data["censored"]].mean() if data["censored"].any() else 0
    return {
        "risk_precision": float(precision_score(data["risk"], risk_pred, zero_division=0)),
        "risk_recall": float(recall_score(data["risk"], risk_pred, zero_division=0)),
        "risk_f1": float(f1_score(data["risk"], risk_pred, zero_division=0)),
        "censored_false_warning_rate": float(censored_warning),
        "equipment_confusion_matrix": confusion_matrix(data["unit"][positive][accepted], unit_pred[accepted], labels=labels).tolist(),
        "per_equipment": {label: {"precision": float(per_precision[i]), "recall": float(per_recall[i]), "support": int(support[i])} for i, label in enumerate(labels)},
        "equipment_macro_precision": float(np.mean(per_precision)), "equipment_macro_recall": float(np.mean(per_recall)),
        "mode_macro_f1": float(f1_score(data["mode"][positive], mode_pred, average="macro", zero_division=0)),
        "last_hour_rul_mae_minutes": float(mean_absolute_error(data["rul"][rul_mask], rul_prediction)),
        "abstention_rate": float(1 - accepted.mean()), "samples": int(len(data["risk"])),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("data_sha256") != sha256(DATA) or manifest.get("run_count") != 1200:
        raise ValueError("Synthetic dataset manifest is stale or incomplete")
    data = load_examples(); train = data["train"]; validation = data["validation"]
    risk_model = ExtraTreesClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=42).fit(train["x"], train["risk"])
    failure_train = (~train["censored"]) & (train["rul"] >= 0)
    near_train = train["risk"] == 1
    unit_model = ExtraTreesClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=43).fit(train["x"][near_train], train["unit"][near_train])
    mode_model = ExtraTreesClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=44).fit(train["x"][near_train], train["mode"][near_train])
    rul_model = ExtraTreesRegressor(n_estimators=180, min_samples_leaf=2, n_jobs=-1, random_state=45).fit(train["x"][failure_train], train["rul"][failure_train])
    validation_risk_scores = risk_model.predict_proba(validation["x"])[:, 1]
    risk_threshold = choose_threshold(validation["risk"], validation_risk_scores, .90)
    positive = validation["risk"] == 1
    unit_scores = unit_model.predict_proba(validation["x"][positive]); unit_pred = unit_model.classes_[unit_scores.argmax(axis=1)]
    unit_conf = unit_scores.max(axis=1); unit_thresholds = {}
    for label in EQUIPMENT:
        truth = validation["unit"][positive] == label
        predicted_label_score = np.where(unit_pred == label, unit_conf, 0)
        unit_thresholds[label] = choose_threshold(truth, predicted_label_score, .85)
    validation_metrics = evaluate(validation, risk_model, unit_model, mode_model, rul_model, risk_threshold, unit_thresholds)
    test_metrics = evaluate(data["test"], risk_model, unit_model, mode_model, rul_model, risk_threshold, unit_thresholds)
    gates = {"risk_precision": test_metrics["risk_precision"] >= .90, "risk_recall": test_metrics["risk_recall"] >= .80,
             "equipment_macro_precision": test_metrics["equipment_macro_precision"] >= .85,
             "equipment_macro_recall": test_metrics["equipment_macro_recall"] >= .85,
             "censored_false_warning_rate": test_metrics["censored_false_warning_rate"] <= .05,
             "last_hour_rul_mae": test_metrics["last_hour_rul_mae_minutes"] <= 15,
             "mode_macro_f1": test_metrics["mode_macro_f1"] >= .80}
    artifact_id = uuid4().hex
    card = {"model_name": "Synthetic equipment prognosis lab", "artifact_id": artifact_id,
            "created_utc": datetime.now(UTC).isoformat(), "source_kind": manifest["source_kind"],
            "data_sha256": manifest["data_sha256"], "generator_seed": manifest["generator_seed"],
            "features": FEATURES, "history_samples": HISTORY, "warning_horizon_minutes": HORIZON,
            "split": "Deterministic complete-run-family 70/15/15 split; no run crosses partitions.",
            "run_counts": {kind: len(set(values["run"].tolist())) for kind, values in data.items()},
            "risk_threshold": risk_threshold, "unit_thresholds": unit_thresholds,
            "validation": validation_metrics, "test": test_metrics, "release_gates": gates,
            "release_ready": all(gates.values()), "equipment": list(EQUIPMENT), "failure_modes": MODES,
            "limitations": ["Labels are generated by a dynamic surrogate, not observed physical failures.",
                            "This model must not control equipment or issue operational safety alarms."]}
    bundle = {"artifact_id": artifact_id, "data_sha256": manifest["data_sha256"], "features": FEATURES,
              "history_samples": HISTORY, "risk_model": risk_model, "unit_model": unit_model,
              "mode_model": mode_model, "rul_model": rul_model, "risk_threshold": risk_threshold,
              "unit_thresholds": unit_thresholds, "release_ready": card["release_ready"]}
    with atomic_output(MODEL) as temporary: joblib.dump(bundle, temporary)
    with atomic_output(CARD) as temporary: temporary.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"validation": validation_metrics, "test": test_metrics, "release_gates": gates}, indent=2))


if __name__ == "__main__":
    main()
