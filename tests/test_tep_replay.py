import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import tep_replay  # noqa: E402


@unittest.skipUnless(tep_replay.available(), "prepare local TEP replay first")
class TepReplayContractTests(unittest.TestCase):
    def test_source_values_are_recorded_and_not_fabricated(self):
        source = json.loads(tep_replay.REPLAY.read_text(encoding="utf-8"))
        state = tep_replay.state(1)
        row = source["rows"][0]
        reactor, separator, stripper = state.assets
        self.assertEqual(state.source_kind, "TEP_REPLAY")
        self.assertEqual(state.sample_index, 1)
        self.assertEqual(state.elapsed_minutes, 0)
        self.assertEqual(reactor.temperature_c, round(row["xmeas_9"], 2))
        self.assertEqual(reactor.pressure_bar, round(row["xmeas_7"] / 100, 3))
        self.assertEqual(separator.flow_unit, "m3/h")
        self.assertEqual(stripper.flow_value, round(row["xmeas_17"], 3))
        for asset in state.assets:
            self.assertEqual(asset.alarm_level, "unassessed")
            self.assertIsNone(asset.risk_score)
            self.assertIsNone(asset.gas_ppm)
            self.assertIsNone(asset.valve_open)

    def test_sample_bounds_and_sequence(self):
        self.assertEqual(tep_replay.state(960).sample_index, 960)
        with self.assertRaises(ValueError):
            tep_replay.state(0)
        with self.assertRaises(ValueError):
            tep_replay.state(961)

    def test_bounded_series_is_recorded_only(self):
        source = json.loads(tep_replay.REPLAY.read_text(encoding="utf-8"))
        history = tep_replay.series(170, 12)
        self.assertEqual(history.source_kind, "TEP_REPLAY")
        self.assertEqual(len(history.points), 12)
        self.assertEqual(history.points[0].sample_index, 159)
        self.assertEqual(history.points[-1].sample_index, 170)
        self.assertEqual(history.points[-1].reactor_pressure_bar_g, round(source["rows"][169]["xmeas_7"] / 100, 3))
        self.assertEqual(len(tep_replay.series(1, 90).points), 1)
        self.assertEqual(set(type(history.points[-1]).model_fields), {
            "sample_index", "elapsed_minutes", "reactor_pressure_bar_g", "reactor_temperature_c",
            "reactor_level_percent", "separator_pressure_bar_g", "stripper_pressure_bar_g",
        })
        with self.assertRaises(ValueError):
            tep_replay.series(0, 12)
        with self.assertRaises(ValueError):
            tep_replay.series(170, 241)

    @unittest.skipUnless(tep_replay.pressure_model_available(), "train local pressure model first")
    def test_pressure_forecast_needs_history_and_remains_unassessed(self):
        self.assertIsNone(tep_replay.state(1).reactor_pressure_20m_bar_g)
        state = tep_replay.state(170)
        self.assertIsInstance(state.reactor_pressure_20m_bar_g, float)
        self.assertGreater(state.reactor_pressure_20m_bar_g, 0)
        self.assertEqual(state.simulation_run, 401)
        self.assertTrue(all(asset.alarm_level == "unassessed" for asset in state.assets))


if __name__ == "__main__":
    unittest.main()
