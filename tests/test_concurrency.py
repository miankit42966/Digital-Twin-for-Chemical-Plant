import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.main import app
from app.services import ai4i_dataset, tep_dataset, tep_models
from app.services.cache import singleflight_cache


class CacheConcurrencyTests(unittest.TestCase):
    def test_same_cold_key_loads_once_for_concurrent_callers(self):
        barrier = threading.Barrier(16)
        calls = []
        @singleflight_cache(maxsize=2)
        def load(key):
            calls.append(key)
            time.sleep(.03)
            return object()
        def request(_):
            barrier.wait(timeout=5)
            return load('one')
        with ThreadPoolExecutor(max_workers=16) as pool:
            values = list(pool.map(request, range(16)))
        self.assertEqual(calls, ['one'])
        self.assertTrue(all(value is values[0] for value in values))
        self.assertEqual(load.cache_info().currsize, 1)

    def test_cache_is_bounded_and_new_signature_invalidates_key(self):
        @singleflight_cache(maxsize=2)
        def load(signature):
            return object()
        previous = load((1, 100))
        self.assertIsNot(previous, load((2, 100)))
        for signature in range(20):
            load((signature, 200))
        self.assertLessEqual(load.cache_info().currsize, 2)


@unittest.skipUnless(tep_dataset.available() and ai4i_dataset.available(), 'local datasets required')
class ApiConcurrencyTests(unittest.TestCase):
    def test_parallel_mixed_source_requests_remain_isolated(self):
        tep_dataset._trajectory.cache_clear()
        tep_models._load.cache_clear()
        ai4i_dataset._read_rows.cache_clear()
        barrier = threading.Barrier(12)
        with TestClient(app) as client:
            def request(index):
                barrier.wait(timeout=10)
                if index % 3 == 0:
                    udi = index + 1
                    data = client.get(f'/api/v1/report?source=ai4i&udi={udi}')
                    self.assertEqual(data.status_code, 200)
                    self.assertEqual(data.json()['record']['udi'], udi)
                    self.assertNotIn('state', data.json())
                else:
                    run, sample = 401 + index % 2, 170 + index
                    data = client.get(f'/api/v1/tep/dataset/frame?sample={sample}&run={run}')
                    self.assertEqual(data.status_code, 200)
                    frame = data.json()
                    self.assertEqual(frame['state']['sample_index'], sample)
                    self.assertEqual(frame['state']['simulation_run'], run)
                    self.assertEqual(frame['history']['simulation_run'], run)
                    self.assertEqual(frame['history']['end_sample'], sample)
                    self.assertEqual(frame['state']['assets'][0]['pressure_bar'], frame['history']['points'][-1]['reactor_pressure_bar_g'])
                    self.assertTrue(all(value == 'ready' for value in frame['state']['model_status'].values()))
                payload = data.json()
                return payload.get('source_kind', payload.get('state', {}).get('source_kind'))
            with ThreadPoolExecutor(max_workers=12) as pool:
                sources = list(pool.map(request, range(12)))
        self.assertEqual(sources.count('AI4I_DATASET'), 4)
        self.assertEqual(sources.count('TEP_DATASET'), 8)
        self.assertEqual(tep_dataset._trajectory.cache_info().misses, 2)
        self.assertEqual(tep_models._load.cache_info().misses, 2)
        self.assertEqual(ai4i_dataset._read_rows.cache_info().misses, 1)

    def test_parallel_repeated_predictions_are_deterministic(self):
        rows = tep_dataset.trajectory()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outputs = list(pool.map(lambda _: tep_models.infer(rows, 170)[:2], range(32)))
        self.assertTrue(all(output == outputs[0] for output in outputs))


if __name__ == '__main__':
    unittest.main()
