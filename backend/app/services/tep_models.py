"""Shared model inference for dataset, API and legacy replay adapters."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path

import joblib
import numpy as np
from app.services.cache import singleflight_cache

ROOT = Path(__file__).resolve().parents[3]
DETECTOR = ROOT / "models/tep_fault_detector.joblib"
PRESSURE_MODEL = ROOT / "models/tep_pressure_20m.joblib"
FEATURES = tuple(f"xmeas_{i}" for i in range(1, 42)) + tuple(f"xmv_{i}" for i in range(1, 12))
PRESSURE_FEATURES = ("xmeas_7", "xmeas_8", "xmeas_9", "xmeas_13", "xmeas_16", "reactor_pressure_delta_1", "reactor_pressure_delta_3")
CARDS = {"detector": ROOT / "docs/models/TEP_fault_detector.json", "pressure": ROOT / "docs/models/TEP_pressure_20m.json"}
logger = logging.getLogger(__name__)
EXPLANATION_DISCLAIMER = (
    "One-feature median-replacement sensitivity is non-causal and does not allocate risk. "
    "The detector score and ensemble-tree spread are not calibrated real-world probabilities or safety uncertainty bounds."
)


@singleflight_cache(maxsize=4)
def _load(path: Path, card_path: Path, signature: tuple, expected_features: tuple[str, ...]) -> dict:
    # File signatures invalidate the cache after a locally retrained model/card.
    bundle = joblib.load(path)
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if tuple(bundle.get("features", ())) != expected_features or tuple(card.get("features", ())) != expected_features:
        raise ValueError("Model features and evaluation card do not match the inference contract")
    if not bundle.get("dataset_sha256") or bundle["dataset_sha256"] != card.get("dataset_sha256"):
        raise ValueError("Model and evaluation card have different dataset fingerprints")
    if not bundle.get("artifact_id") or bundle["artifact_id"] != card.get("artifact_id"):
        raise ValueError("Model and evaluation card are not one atomic training artifact")
    if getattr(bundle.get("estimator"), "n_features_in_", None) != len(expected_features):
        raise ValueError("Model input dimension is incompatible")
    if path == DETECTOR:
        medians = np.asarray(bundle.get("training_medians", ()), dtype=np.float32)
        if medians.shape != (len(expected_features),) or not np.isfinite(medians).all():
            raise ValueError("Detector training medians are missing or incompatible")
        bundle["training_medians"] = medians
    if hasattr(bundle["estimator"], "n_jobs"):
        bundle["estimator"].n_jobs = 1
    bundle["_evaluation_card"] = card
    return bundle


def _bundle(kind: str) -> dict:
    path = DETECTOR if kind == "detector" else PRESSURE_MODEL
    card = CARDS[kind]
    expected = FEATURES if kind == "detector" else PRESSURE_FEATURES
    stat, card_stat = path.stat(), card.stat()
    return _load(path, card, (stat.st_mtime_ns, stat.st_size, card_stat.st_mtime_ns, card_stat.st_size), expected)


def availability() -> dict[str, str]:
    status = {}
    for kind, path in (("detector", DETECTOR), ("pressure", PRESSURE_MODEL)):
        if not path.is_file():
            status[kind] = "missing"
            continue
        try:
            _bundle(kind)
            status[kind] = "ready"
        except Exception:
            logger.exception("TEP %s model could not be validated", kind)
            status[kind] = "invalid"
    return status


def evaluation_card(kind: str) -> dict:
    if kind not in {"detector", "pressure"}:
        raise ValueError(f"Unknown model kind: {kind}")
    return deepcopy(_bundle(kind)["_evaluation_card"])


def pressure_features(rows: tuple[dict, ...] | list[dict], sample: int) -> np.ndarray:
    if not 4 <= sample <= len(rows):
        raise ValueError("Pressure inference requires at least four observed samples")
    row = rows[sample - 1]
    current = np.float32(row["xmeas_7"])
    values = {name: float(row[name]) for name in PRESSURE_FEATURES[:5]}
    values["reactor_pressure_delta_1"] = current - np.float32(rows[sample - 2]["xmeas_7"])
    values["reactor_pressure_delta_3"] = current - np.float32(rows[sample - 4]["xmeas_7"])
    return np.asarray([[values[name] for name in PRESSURE_FEATURES]], dtype=np.float32)


def _positive_probability(estimator, values: np.ndarray) -> np.ndarray:
    probabilities = estimator.predict_proba(values)
    classes = np.asarray(estimator.classes_)
    matches = np.flatnonzero(classes == 1)
    if len(matches) != 1:
        raise ValueError("Detector does not expose the expected positive class")
    return np.asarray(probabilities[:, int(matches[0])], dtype=float)


def explain_detector(bundle: dict, values: np.ndarray, score: float, limit: int = 3) -> dict:
    """Return local sensitivity, not a causal or additive feature attribution."""
    medians = bundle["training_medians"]
    perturbed = np.repeat(values, len(FEATURES), axis=0)
    indexes = np.arange(len(FEATURES))
    perturbed[indexes, indexes] = medians
    changed_scores = _positive_probability(bundle["estimator"], perturbed)
    deltas = score - changed_scores

    factors = [{
        "feature": feature,
        "observed_value": float(values[0, index]),
        "reference_median": float(medians[index]),
        "score_delta": float(delta),
    } for index, (feature, delta) in enumerate(zip(FEATURES, deltas, strict=True))]
    positive = sorted((item for item in factors if item["score_delta"] > 0), key=lambda item: (-item["score_delta"], item["feature"]))[:limit]
    negative = sorted((item for item in factors if item["score_delta"] < 0), key=lambda item: (item["score_delta"], item["feature"]))[:limit]

    tree_scores = np.asarray([
        _positive_probability(tree, values)[0] for tree in bundle["estimator"].estimators_
    ], dtype=float)
    tree_std = float(tree_scores.std(ddof=0))
    if not np.isfinite(changed_scores).all() or not np.isfinite(tree_std):
        raise ValueError("Non-finite detector explanation")
    return {
        "method": "one_feature_at_a_time_median_replacement",
        "ensemble_tree_std": tree_std,
        "top_positive_factors": positive,
        "top_negative_factors": negative,
        "disclaimer": EXPLANATION_DISCLAIMER,
    }


def infer(rows: tuple[dict, ...] | list[dict], sample: int) -> tuple[float | None, float | None, dict[str, str], dict[str, str], dict | None]:
    status = availability()
    notices = {kind: "Model ready" if value == "ready" else f"Model {value}; prepare a matching model and evaluation card" for kind, value in status.items()}
    score = forecast = None
    explanation = None
    if status["detector"] == "ready":
        try:
            values = np.asarray([[float(rows[sample - 1][name]) for name in FEATURES]], dtype=np.float32)
            detector_bundle = _bundle("detector")
            score = float(_positive_probability(detector_bundle["estimator"], values)[0])
            if not np.isfinite(score):
                raise ValueError("Non-finite detector output")
            explanation = explain_detector(detector_bundle, values, score)
        except Exception:
            logger.exception("TEP detector inference failed")
            score = None
            explanation = None
            status["detector"] = "invalid"
            notices["detector"] = "Detector inference unavailable; measured values remain available"
    if status["pressure"] == "ready" and sample < 4:
        notices["pressure"] = "Needs four observed samples for pressure-history features"
    elif status["pressure"] == "ready":
        try:
            forecast = float(_bundle("pressure")["estimator"].predict(pressure_features(rows, sample))[0]) / 100
            if not np.isfinite(forecast):
                raise ValueError("Non-finite pressure output")
            forecast = round(forecast, 3)
        except Exception:
            logger.exception("TEP pressure inference failed")
            forecast = None
            status["pressure"] = "invalid"
            notices["pressure"] = "Pressure inference unavailable; measured values remain available"
    return score, forecast, status, notices, explanation
