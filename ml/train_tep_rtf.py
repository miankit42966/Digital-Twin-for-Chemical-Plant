"""Group-held-out remaining-time benchmark for the separate TEP RTF dataset.

No component classifier is fitted without independently verified terminal-unit
labels. The published CSVs contain no such label column.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from ml.ingestion.common import REPO_ROOT, atomic_output
from ml.ingestion.ingest_tep_rtf import DOCUMENTED_CASES, OUTPUT

MODEL = REPO_ROOT / "models/tep_rtf_prognosis.joblib"
CARD = REPO_ROOT / "docs/models/TEP_RTF_prognosis.json"
SENSORS = (
    "Reactor Feed Rate", "Reactor Pressure", "Reactor Level", "Reactor Temperature",
    "Product Sep Temp", "Product Sep Level", "Product Sep Pressure", "Product Sep Underflow",
    "Stripper Level", "Stripper Pressure", "Stripper Underflow", "Stripper Temp",
    "Liquid Input Stripper", "Liquid Input Separator", "Liquid Input Reactor",
    "Recycle Flow", "Purge Rate", "Stripper Steam Flow", "Compressor Work",
)
FEATURES = tuple(f"{kind}:{sensor}" for kind in ("now", "delta_1", "delta_20", "mean_20") for sensor in SENSORS)
HISTORY_SAMPLES = 21


def split_for_run(case: str, run: int) -> str:
    bucket = int(hashlib.sha256(f"tep-rtf-v1/{case}/{run}".encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def feature_rows(values: np.ndarray, indexes: np.ndarray) -> np.ndarray:
    """Current and past-only features; indexes must have 20 predecessors."""
    if len(indexes) and (indexes.min() < 20 or indexes.max() >= len(values)):
        raise ValueError("A full 21-sample observed history is required")
    prefix = np.vstack((np.zeros((1, values.shape[1]), dtype=np.float64), values.cumsum(axis=0, dtype=np.float64)))
    mean_20 = (prefix[indexes + 1] - prefix[indexes - 19]) / 20
    return np.column_stack((values[indexes], values[indexes] - values[indexes - 1],
                            values[indexes] - values[indexes - 20], mean_20)).astype(np.float32)


def run_examples(values: np.ndarray, times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(values) != len(times) or len(values) < HISTORY_SAMPLES + 2:
        return np.empty((0, len(FEATURES)), dtype=np.float32), np.empty(0, dtype=np.float32)
    indexes = np.arange(20, len(values) - 1)
    # Cover full trajectories without letting long healthy stretches dominate;
    # retain more examples near the simulated terminal condition.
    indexes = indexes[(indexes % 10 == 0) | ((len(values) - 1 - indexes <= 80) & (indexes % 2 == 0))]
    remaining = (times[-1] - times[indexes]) * 60
    if (remaining <= 0).any():
        raise ValueError("Remaining-time targets must be strictly positive before the terminal sample")
    return feature_rows(values, indexes), remaining.astype(np.float32)


def load_examples(manifest: dict) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, set[str]]]:
    xs: dict[str, list[np.ndarray]] = {kind: [] for kind in ("train", "validation", "test")}
    ys: dict[str, list[np.ndarray]] = {kind: [] for kind in xs}
    groups: dict[str, set[str]] = {kind: set() for kind in xs}
    for case in sorted(DOCUMENTED_CASES):
        source = OUTPUT / f"{case}.parquet"
        frame = pq.read_table(source, columns=["Id", "Time", *SENSORS]).to_pandas()
        for run_id, group in frame.groupby("Id", sort=False):
            run = int(run_id)
            values = group.loc[:, list(SENSORS)].to_numpy(dtype=np.float32)
            times = group["Time"].to_numpy(dtype=np.float64)
            x, y = run_examples(values, times)
            if not len(y):
                continue
            split = split_for_run(case, run)
            xs[split].append(x); ys[split].append(y); groups[split].add(f"{case}/{run}")
        del frame
    if any(not value for value in groups.values()) or len(set.union(*groups.values())) != sum(map(len, groups.values())):
        raise ValueError("Run-group split is empty or overlaps")
    return ({kind: np.concatenate(rows) for kind, rows in xs.items()},
            {kind: np.concatenate(rows) for kind, rows in ys.items()}, groups)


def metrics(truth: np.ndarray, predicted: np.ndarray) -> dict:
    absolute = np.abs(predicted - truth)
    near = truth <= 240
    return {
        "mae_minutes": float(mean_absolute_error(truth, predicted)),
        "rmse_minutes": float(np.sqrt(mean_squared_error(truth, predicted))),
        "p90_absolute_error_minutes": float(np.quantile(absolute, .9)),
        "last_4h_support": int(near.sum()),
        "last_4h_mae_minutes": float(mean_absolute_error(truth[near], predicted[near])) if near.any() else None,
    }


def main() -> None:
    manifest_path = OUTPUT / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("TEP RTF ingestion is not complete; run ml.ingestion.ingest_tep_rtf")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    xs, ys, groups = load_examples(manifest)
    model = HistGradientBoostingRegressor(max_iter=160, max_leaf_nodes=31, max_depth=8,
                                          l2_regularization=1, random_state=42)
    model.fit(xs["train"], np.log1p(ys["train"]))
    validation = np.expm1(model.predict(xs["validation"])).clip(min=0)
    test = np.expm1(model.predict(xs["test"])).clip(min=0)
    artifact_id = uuid4().hex
    card = {
        "model_name": "TEP simulated time to process shutdown",
        "artifact_id": artifact_id,
        "created_utc": datetime.now(UTC).isoformat(),
        "source_doi": manifest["source_doi"], "source_sha256": manifest["source_sha256"],
        "task": "Estimate minutes until the selected run reaches its simulated terminal shutdown condition.",
        "features": FEATURES, "history_samples": HISTORY_SAMPLES,
        "split": "Deterministic 70/15/15 train/validation/test by complete (case, Id) run; cases 5_1 and 7 excluded pending documentation.",
        "evaluation_sampling": "Every 10th eligible point across held-out runs, plus every 2nd point in each run's final 80 samples; last-four-hour error is reported separately.",
        "run_counts": {kind: len(group) for kind, group in groups.items()},
        "sample_counts": {kind: len(ys[kind]) for kind in ys},
        "validation": metrics(ys["validation"], validation),
        "test": metrics(ys["test"], test),
        "warning_horizon_minutes": 60,
        "next_unit_status": "unavailable_no_verified_terminal_unit_labels",
        "next_unit_label_provenance": None,
        "next_unit_confusion_matrix": None,
        "next_unit_per_equipment_precision_recall": None,
        "warning_performance": None,
        "abstention_rate": 1.0,
        "limitations": [
            "No equipment-wise terminal-unit label is present in the source CSVs; no unit is predicted or highlighted.",
            "The target is simulated process shutdown, not physical equipment breakdown or a causal flow effect.",
            "This model is not validated on real plant data and must not drive safety actions.",
        ],
    }
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    with atomic_output(MODEL) as temporary:
        joblib.dump({"estimator": model, "features": FEATURES, "source_sha256": manifest["source_sha256"],
                     "artifact_id": artifact_id, "history_samples": HISTORY_SAMPLES,
                     "next_unit_estimator": None}, temporary)
    with atomic_output(CARD) as temporary:
        temporary.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runs": card["run_counts"], "samples": card["sample_counts"],
                      "test": card["test"], "next_unit_status": card["next_unit_status"]}, indent=2))


if __name__ == "__main__":
    main()
