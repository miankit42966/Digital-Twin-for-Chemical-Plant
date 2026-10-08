"""Run-to-failure contracts that do not require the 2.5 GB source archive."""
import sys
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import tep_rtf
from app.main import app
from app.schemas import RtfFrame, RtfPrognosis
from ml.ingestion import fetch_tep_rtf
from ml.train_tep_rtf import FEATURES, feature_rows, run_examples, split_for_run


class TepRtfTrainingContractTests(unittest.TestCase):
    def test_archive_verification_rejects_wrong_checksum(self):
        payload = b"published archive fixture"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TEP.zip"
            path.write_bytes(payload)
            with patch.object(fetch_tep_rtf, "EXPECTED_BYTES", len(payload)), patch.object(
                fetch_tep_rtf, "EXPECTED_MD5", hashlib.md5(payload).hexdigest()
            ):
                self.assertTrue(fetch_tep_rtf.verified(path))
            with patch.object(fetch_tep_rtf, "EXPECTED_BYTES", len(payload)), patch.object(
                fetch_tep_rtf, "EXPECTED_MD5", "0" * 32
            ):
                self.assertFalse(fetch_tep_rtf.verified(path))

    def test_features_use_only_current_and_past_rows(self):
        values = np.arange(45 * 19, dtype=np.float32).reshape(45, 19)
        indexes = np.asarray([20, 30], dtype=int)
        before = feature_rows(values, indexes)
        changed_future = values.copy()
        changed_future[31:] += 1_000_000
        after = feature_rows(changed_future, indexes)
        np.testing.assert_array_equal(before, after)
        self.assertEqual(before.shape[1], len(FEATURES))

    def test_target_is_derived_from_run_end_but_not_input(self):
        values = np.arange(90 * 19, dtype=np.float32).reshape(90, 19)
        times = np.arange(90, dtype=np.float64) * .05
        features, target = run_examples(values, times)
        later_end = times.copy()
        later_end[-1] += 1.0
        unchanged_features, changed_target = run_examples(values, later_end)
        self.assertGreater(len(target), 0)
        self.assertEqual(features.shape[1], len(FEATURES))
        self.assertTrue((target > 0).all())
        np.testing.assert_array_equal(features, unchanged_features)
        self.assertTrue((changed_target > target).all())

    def test_complete_run_has_one_deterministic_split(self):
        allocations = {split_for_run("case1", run) for run in range(1, 100)}
        self.assertEqual(allocations, {"train", "validation", "test"})
        for run in range(1, 20):
            self.assertEqual(split_for_run("case3", run), split_for_run("case3", run))


class TepRtfInferenceContractTests(unittest.TestCase):
    def test_dataset_readiness_requires_manifest_and_every_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            for case in tep_rtf.ARCHIVE_CASES:
                (root / f"{case}.parquet").write_bytes(b"parquet fixture")
            with patch.object(tep_rtf, "DATA", root), patch.object(tep_rtf, "MANIFEST", manifest):
                self.assertTrue(tep_rtf.available())
                (root / "case7.parquet").unlink()
                self.assertFalse(tep_rtf.available())

    def test_manifest_contract_rejects_untrusted_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            tep_rtf._manifest.cache_clear()
            with patch.object(tep_rtf, "MANIFEST", manifest), self.assertRaisesRegex(ValueError, "manifest source contract"):
                tep_rtf.manifest()

    def test_highlight_contract_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "highlight"):
            RtfPrognosis(status="ready", remaining_minutes=30, next_unit_id="RX-201",
                         highlight_unit_id="SP-201", unit_status="ready", notice="invalid")

    def test_unit_prediction_is_disabled_without_verified_labels(self):
        rows = tuple({name: float(index + offset) for offset, name in enumerate(tep_rtf.SENSORS)}
                     for index in range(25))
        bundle = {"estimator": object(), "next_unit_estimator": None}
        card = {"next_unit_status": "unavailable_no_verified_terminal_unit_labels"}
        estimator = type("Estimator", (), {"predict": lambda self, values: np.asarray([np.log1p(55.0)])})()
        bundle["estimator"] = estimator
        with patch.object(tep_rtf, "model_availability", return_value="ready"), patch.object(tep_rtf, "model", return_value=(bundle, card)):
            result = tep_rtf.prognosis(rows, 25, "case1")
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.remaining_minutes, 55.0)
        self.assertIsNone(result.next_unit_id)
        self.assertIsNone(result.highlight_unit_id)
        self.assertEqual(result.unit_status, "unavailable_no_verified_labels")

    def test_undocumented_archive_case_never_produces_forecast(self):
        result = tep_rtf.prognosis(tuple(), 1, "case7")
        self.assertEqual(result.status, "missing")
        self.assertIsNone(result.highlight_unit_id)


@unittest.skipUnless(tep_rtf.available(), "verified local TEP RTF ingestion is not installed")
class TepRtfApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_options_frame_and_report_keep_one_trajectory(self):
        options = self.client.get("/api/v1/tep/rtf/options")
        self.assertEqual(options.status_code, 200)
        payload = options.json()
        self.assertEqual(payload["source_kind"], "TEP_RTF")
        self.assertEqual(len(payload["cases"]), 8)
        frame = self.client.get("/api/v1/tep/rtf/frame", params={"case": "case1", "run": 1, "sample": 21, "points": 20})
        self.assertEqual(frame.status_code, 200)
        body = frame.json()
        self.assertEqual((body["state"]["case_id"], body["state"]["simulation_id"], body["state"]["sample_index"]),
                         (body["history"]["case_id"], body["history"]["simulation_id"], body["history"]["end_sample"]))
        self.assertIsNone(body["state"]["prognosis"]["next_unit_id"])
        self.assertIsNone(body["state"]["prognosis"]["highlight_unit_id"])
        report = self.client.get("/api/v1/report", params={"source": "rtf", "case": "case1", "run": 1, "sample": 21})
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["report_kind"], "rtf_snapshot")

    def test_invalid_sample_and_undocumented_case_fail_closed(self):
        invalid = self.client.get("/api/v1/tep/rtf/frame", params={"case": "case1", "run": 1, "sample": 999_999})
        self.assertEqual(invalid.status_code, 422)
        undocumented = self.client.get("/api/v1/tep/rtf/frame", params={"case": "case7", "run": 1, "sample": 21})
        self.assertEqual(undocumented.status_code, 200)
        prognosis = undocumented.json()["state"]["prognosis"]
        self.assertEqual(prognosis["status"], "missing")
        self.assertIsNone(prognosis["highlight_unit_id"])

    def test_frame_schema_rejects_state_history_pressure_mismatch(self):
        body = self.client.get("/api/v1/tep/rtf/frame", params={"case": "case1", "run": 1, "sample": 21}).json()
        body["history"]["points"][-1]["reactor_pressure_bar_g"] += 1
        with self.assertRaisesRegex(ValueError, "reactor pressure"):
            RtfFrame.model_validate(body)


if __name__ == "__main__":
    unittest.main()
