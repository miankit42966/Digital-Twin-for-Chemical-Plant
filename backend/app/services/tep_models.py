"""Shared model inference for dataset, API and legacy replay adapters."""
from __future__ import annotations

import json
import logging
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


@singleflight_cache(maxsize=4)
def _load(path: Path, card_path: Path, signature: tuple, expected_features: tuple[str, ...]) -> dict:
    # File signatures invalidate the cache after a locally retrained model/card.
    bundle = joblib.load(path)
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if tuple(bundle.get("features", ())) != expected_features or tuple(card.get("features", ())) != expected_features:
        raise ValueError("Model features and evaluation card do not match the inference contract")
    if not bundle.get("dataset_sha256") or bundle["dataset_sha256"] != card.get("dataset_sha256"):
        raise ValueError("Model and evaluation card have different dataset fingerprints")
    if getattr(bundle.get("estimator"), "n_features_in_", None) != len(expected_features):
        raise ValueError("Model input dimension is incompatible")
    if hasattr(bundle["estimator"], "n_jobs"):
        bundle["estimator"].n_jobs = 1
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


def pressure_features(rows: tuple[dict, ...] | list[dict], sample: int) -> np.ndarray:
    if not 4 <= sample <= len(rows):
        raise ValueError("Pressure inference requires at least four observed samples")
    row = rows[sample - 1]
    current = np.float32(row["xmeas_7"])
    values = {name: float(row[name]) for name in PRESSURE_FEATURES[:5]}
    values["reactor_pressure_delta_1"] = current - np.float32(rows[sample - 2]["xmeas_7"])
    values["reactor_pressure_delta_3"] = current - np.float32(rows[sample - 4]["xmeas_7"])
    return np.asarray([[values[name] for name in PRESSURE_FEATURES]], dtype=np.float32)


def infer(rows: tuple[dict, ...] | list[dict], sample: int) -> tuple[float | None, float | None, dict[str, str], dict[str, str]]:
    status = availability()
    notices = {kind: "Model ready" if value == "ready" else f"Model {value}; prepare a matching model and evaluation card" for kind, value in status.items()}
    score = forecast = None
    if status["detector"] == "ready":
        try:
            values = np.asarray([[float(rows[sample - 1][name]) for name in FEATURES]], dtype=np.float32)
            score = float(_bundle("detector")["estimator"].predict_proba(values)[0, 1])
            if not np.isfinite(score):
                raise ValueError("Non-finite detector output")
        except Exception:
            logger.exception("TEP detector inference failed")
            score = None
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
    return score, forecast, status, notices
