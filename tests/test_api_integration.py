"""Cross-layer API/data/model contracts; uses local datasets, never mutates them."""
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.main import app
from app.schemas import DatasetFrame
from app.services import tep_dataset, tep_models, ai4i_dataset
from ml.train_tep_pressure_forecast import rows_for_run
from ml.ingestion.common import atomic_output
from ml.ingestion import ingest_tep


class AtomicOutputTests(unittest.TestCase):
    def test_dataset_io_errors_are_explicit_service_unavailable(self):
        with TestClient(app) as client:
            for service, function, endpoint in (
                (tep_dataset, 'frame', '/api/v1/tep/dataset/frame'),
                (tep_dataset, 'state', '/api/v1/plant/state'),
                (tep_dataset, 'series', '/api/v1/tep/dataset/series'),
                (ai4i_dataset, 'frame', '/api/v1/ai4i/frame'),
                (ai4i_dataset, 'record', '/api/v1/ai4i/record'),
            ):
                with self.subTest(endpoint=endpoint), patch.object(service, function, side_effect=OSError('Dataset temporarily unreadable')):
                    response = client.get(endpoint)
                    self.assertEqual(response.status_code, 503)
                    self.assertIn('temporarily unreadable', response.json()['detail'])

    def test_failed_write_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'dataset'
            with atomic_output(target) as temporary:
                temporary.write_bytes(b'previous good data')
            with self.assertRaises(ValueError):
                with atomic_output(target) as temporary:
                    temporary.write_bytes(b'incomplete')
                    raise ValueError('validation failed')
            self.assertEqual(target.read_bytes(), b'previous good data')
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_streamed_ingestion_commits_only_complete_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            for name in ingest_tep.FILES:
                with atomic_output(raw / name) as temporary:
                    temporary.write_bytes(b'test source')
            frame = pd.DataFrame({'sample': [1.0], **{name: [1.0] for name in tep_models.FEATURES}})
            output = root / 'processed'
            with patch.object(ingest_tep, 'RAW_DIR', raw), patch.object(ingest_tep, 'OUTPUT', output), patch.object(ingest_tep, 'load_one', return_value=frame):
                ingest_tep.main()
            from pyarrow import parquet
            table = parquet.read_table(output / 'tep.parquet')
            self.assertEqual(table.num_rows, 4)
            self.assertEqual(table.column('dataset_partition').to_pylist(), ['training', 'training', 'testing', 'testing'])
            original = (output / 'tep.parquet').read_bytes()
            with patch.object(ingest_tep, 'RAW_DIR', raw), patch.object(ingest_tep, 'OUTPUT', output), patch.object(ingest_tep, 'load_one', side_effect=[frame, ValueError('bad source')]):
                with self.assertRaises(ValueError):
                    ingest_tep.main()
            self.assertEqual((output / 'tep.parquet').read_bytes(), original)
            self.assertFalse(list(output.glob('*.partial')))

    def test_model_feature_contract_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            card = Path(directory) / 'card.json'
            with atomic_output(card) as temporary:
                temporary.write_text(json.dumps({'features': tep_models.FEATURES, 'dataset_sha256': 'test'}))
            bundle = {'features': list(reversed(tep_models.FEATURES)), 'dataset_sha256': 'test'}
            with patch.object(tep_models.joblib, 'load', return_value=bundle):
                with self.assertRaisesRegex(ValueError, 'features'):
                    tep_models._load(Path(directory) / 'model', card, ('test',), tep_models.FEATURES)


@unittest.skipUnless(tep_dataset.available() and ai4i_dataset.available(), 'local datasets required')
class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_atomic_frame_aligns_chart_and_asset(self):
        response = self.client.get('/api/v1/tep/dataset/frame?sample=170&points=12')
        self.assertEqual(response.status_code, 200)
        frame = DatasetFrame.model_validate(response.json())
        self.assertEqual(frame.state.assets[0].pressure_bar, frame.history.points[-1].reactor_pressure_bar_g)
        self.assertEqual(len(frame.history.points), 12)
        malformed = response.json()
        malformed['history']['simulation_run'] = 402
        with self.assertRaises(ValueError):
            DatasetFrame.model_validate(malformed)

    def test_primary_api_and_testing_baseline_are_separate(self):
        actual = self.client.get('/api/v1/plant/state').json()
        baseline = self.client.get('/api/v1/testing/baseline').json()
        self.assertEqual(actual['source_kind'], 'TEP_DATASET')
        self.assertEqual(baseline['source_kind'], 'SIMULATED_INTEGRATION_BASELINE')
        self.assertTrue(all(a['alarm_level'] == 'unassessed' and a['risk_score'] is None for a in actual['assets']))

    def test_invalid_queries_never_return_other_run(self):
        for query in ('sample=0', 'sample=961', 'partition=training&sample=501', 'fault=21', 'run=0', 'points=241', 'partition=live'):
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/v1/tep/dataset/frame?' + query).status_code, 422)
        self.assertEqual(self.client.get('/api/v1/ai4i/frame?udi=10001').status_code, 422)

    def test_missing_and_corrupt_models_keep_measured_data(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'missing.joblib'
            with patch.object(tep_models, 'DETECTOR', missing), patch.object(tep_models, 'PRESSURE_MODEL', missing):
                response = self.client.get('/api/v1/tep/dataset/frame')
                self.assertEqual(response.status_code, 200)
                state = response.json()['state']
                self.assertEqual(state['model_status'], {'detector': 'missing', 'pressure': 'missing'})
                self.assertIsNone(state['detector_score'])
                self.assertIsNone(state['reactor_pressure_20m_bar_g'])
                self.assertEqual(len(state['assets']), 3)
            with atomic_output(missing) as temporary:
                temporary.write_bytes(b'not a model')
            with patch.object(tep_models, 'DETECTOR', missing), self.assertLogs('app.services.tep_models', level='ERROR'):
                state = self.client.get('/api/v1/tep/dataset/frame').json()['state']
                self.assertEqual(state['model_status']['detector'], 'invalid')
                self.assertIsNone(state['detector_score'])
                self.assertIsNotNone(state['reactor_pressure_20m_bar_g'])

    def test_pressure_features_match_training_without_future_leakage(self):
        rows = tep_dataset.trajectory()
        features, targets = rows_for_run(pd.DataFrame(rows))
        for index, sample in enumerate(range(12, 954, 12)):
            np.testing.assert_array_equal(tep_models.pressure_features(rows, sample)[0], features[index])
            expected = np.float32(rows[sample + 5]['xmeas_7']) / np.float32(3) + np.float32(rows[sample + 6]['xmeas_7']) * np.float32(2 / 3)
            self.assertAlmostEqual(float(targets[index]), float(expected), places=3)

    def test_snapshot_exports_selected_source_and_sample(self):
        tep = self.client.get('/api/v1/report?sample=500&partition=training&fault=0&run=1').json()
        self.assertEqual(tep['source_kind'], 'TEP_DATASET')
        self.assertEqual(tep['state']['sample_index'], 500)
        self.assertEqual(tep['history']['end_sample'], 500)
        ai = self.client.get('/api/v1/report?source=ai4i&udi=10000').json()
        self.assertEqual(ai['record']['udi'], 10000)
        self.assertEqual(ai['source_kind'], 'AI4I_DATASET')
        self.assertNotIn('state', ai)
        self.assertEqual(ai['summary']['failure_records'], 339)

    def test_websocket_matches_rest_and_stops_at_final_sample(self):
        with self.client.websocket_connect('/ws/telemetry?sample=960&fault=0&run=1') as socket:
            frame = socket.receive_json()
            rest = self.client.get('/api/v1/plant/state?sample=960&fault=0&run=1').json()
            self.assertEqual(frame['assets'][0]['pressure_bar'], rest['assets'][0]['pressure_bar'])
            self.assertEqual(frame['source_kind'], 'TEP_DATASET')
            self.assertEqual(socket.receive()['code'], 1000)
        with self.client.websocket_connect('/ws/telemetry?sample=0') as socket:
            self.assertEqual(socket.receive()['code'], 1008)

    def test_models_and_health_are_ready(self):
        self.assertEqual(self.client.get('/health').json()['status'], 'ok')
        for endpoint in ('tep-detector', 'tep-pressure-20m'):
            self.assertEqual(self.client.get('/api/v1/models/' + endpoint).status_code, 200)


if __name__ == '__main__':
    unittest.main()
