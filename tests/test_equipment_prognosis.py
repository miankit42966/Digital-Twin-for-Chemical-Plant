import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app
from app.schemas import LabPrognosis
from app.services import equipment_prognosis
from ml.ingestion.common import sha256
from ml.simulation.generate_equipment_prognosis import DATA, MANIFEST, _trajectory
from ml.train_equipment_prognosis import FEATURES, feature_rows, split_for_run


class EquipmentPrognosisDataTests(unittest.TestCase):
    def test_generated_dataset_manifest_and_hash(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["run_count"], 1200)
        self.assertEqual(manifest["failure_run_count"], 1000)
        self.assertEqual(manifest["censored_run_count"], 200)
        self.assertEqual(manifest["data_sha256"], sha256(DATA))
        self.assertEqual(set(manifest["equipment"]), {"RX-201", "CD-201", "SP-201", "ST-301", "CP-201"})

    def test_generator_is_deterministic_and_coupled(self):
        first = _trajectory(1, "RX-201", "cooling_capacity_loss", np.random.default_rng(7))
        second = _trajectory(1, "RX-201", "cooling_capacity_loss", np.random.default_rng(7))
        for name in ("reactor_temperature_c", "reactor_pressure_bar", "condenser_temperature_c"):
            np.testing.assert_array_equal(first[name], second[name])
        onset = int(first["degradation_onset_sample"][0])
        self.assertGreater(first["reactor_temperature_c"][-1], first["reactor_temperature_c"][onset - 1] + 15)
        self.assertGreater(first["condenser_temperature_c"][-1], first["condenser_temperature_c"][onset - 1] + 2)

    def test_features_are_past_only_and_split_by_complete_run(self):
        self.assertEqual(len(FEATURES), 80)
        self.assertFalse(any("label" in feature or "remaining" in feature or "terminal" in feature for feature in FEATURES))
        values = np.arange(30 * 20, dtype=np.float32).reshape(30, 20)
        original = feature_rows(values, np.asarray([20]))
        values[21:] = -999999
        np.testing.assert_array_equal(original, feature_rows(values, np.asarray([20])))
        self.assertEqual(split_for_run(42), split_for_run(42))


@unittest.skipUnless(equipment_prognosis.available(), "synthetic prognosis dataset required")
class EquipmentPrognosisApiTests(unittest.TestCase):
    client = TestClient(app)

    def test_options_frame_and_terminal_outcome_contract(self):
        options = self.client.get("/api/v1/prognosis-lab/options").json()
        self.assertEqual(options["source_kind"], "SYNTHETIC_EQUIPMENT_PROGNOSIS")
        self.assertEqual(len(options["runs"]), 1200)
        selected = options["runs"][0]
        before = self.client.get("/api/v1/prognosis-lab/frame", params={"run": selected["id"], "sample": 21}).json()
        self.assertIsNone(before["state"]["observed_outcome"])
        terminal = self.client.get("/api/v1/prognosis-lab/frame", params={"run": selected["id"], "sample": selected["samples"]}).json()
        self.assertIsNotNone(terminal["state"]["observed_outcome"])
        self.assertEqual(terminal["state"]["prognosis"]["highlight_equipment_id"], terminal["state"]["observed_outcome"]["failed_equipment_id"])
        self.assertEqual(len(terminal["state"]["assets"]), 5)

    def test_model_card_and_health_are_ready(self):
        card = self.client.get("/api/v1/models/equipment-prognosis").json()
        self.assertTrue(card["release_ready"])
        self.assertTrue(all(card["release_gates"].values()))
        health = self.client.get("/health").json()
        self.assertEqual(health["equipment_prognosis_dataset"], "available")
        self.assertEqual(health["equipment_prognosis_model"], "ready")

    def test_model_failure_never_highlights(self):
        rows = equipment_prognosis.trajectory(1)
        with patch.object(equipment_prognosis, "model_availability", return_value="invalid"):
            result = equipment_prognosis.prognosis(rows, len(rows))
        self.assertIsNone(result.highlight_equipment_id)
        self.assertEqual(result.unit_status, "unassessed")

    def test_schema_rejects_unsafe_highlight(self):
        with self.assertRaisesRegex(ValueError, "highlight"):
            LabPrognosis(status="ready", failure_within_horizon_probability=.99, remaining_minutes=70,
                         predicted_equipment_id="RX-201", predicted_failure_mode="cooling_capacity_loss",
                         confidence=.99, unit_status="ready", highlight_equipment_id="RX-201", notice="invalid")


if __name__ == "__main__":
    unittest.main()
