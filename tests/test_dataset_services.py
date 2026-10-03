import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import ai4i_dataset, tep_dataset  # noqa: E402


@unittest.skipUnless(tep_dataset.available(), "local TEP dataset required")
class TepDatasetTests(unittest.TestCase):
    def test_selects_distinct_published_runs(self):
        first = tep_dataset.state(170, "testing", 6, 401)
        second = tep_dataset.state(170, "testing", 6, 402)
        normal = tep_dataset.state(170, "testing", 0, 401)
        self.assertEqual(first.source_kind, "TEP_DATASET")
        self.assertEqual(first.total_samples, 960)
        self.assertNotEqual(first.assets[0].pressure_bar, second.assets[0].pressure_bar)
        self.assertEqual(normal.fault_number, 0)
        self.assertTrue(all(asset.alarm_level == "unassessed" for asset in first.assets))
        self.assertTrue(all(asset.gas_ppm is None for asset in first.assets))

    def test_training_length_and_series_bounds(self):
        state = tep_dataset.state(500, "training", 0, 1)
        self.assertEqual(state.total_samples, 500)
        history = tep_dataset.series(500, 20, "training", 0, 1)
        self.assertEqual((history.points[0].sample_index, history.points[-1].sample_index), (481, 500))
        self.assertEqual(len(history.points), 20)
        with self.assertRaises(ValueError):
            tep_dataset.state(501, "training", 0, 1)
        with self.assertRaises(ValueError):
            tep_dataset.series(170, 241)


@unittest.skipUnless(ai4i_dataset.available(), "local AI4I dataset required")
class Ai4iDatasetTests(unittest.TestCase):
    def test_summary_and_record_are_dataset_values(self):
        summary = ai4i_dataset.summary()
        first = ai4i_dataset.record(1)
        self.assertEqual(summary["total_records"], 10_000)
        self.assertEqual(summary["failure_records"], 339)
        self.assertEqual(first["product_id"], "M14860")
        self.assertEqual(first["air_temperature_k"], 298.1)
        self.assertEqual(first["source_kind"], "AI4I_DATASET")
        with self.assertRaises(ValueError):
            ai4i_dataset.record(0)
