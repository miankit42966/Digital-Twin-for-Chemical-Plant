"""Read-only local load regression; deliberately bounded, not a capacity certification."""
import asyncio
import base64
import json
import os
import socket
import statistics
import struct
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from websockets.asyncio.client import connect


async def main():
    limit = asyncio.Semaphore(16)
    latencies = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000', timeout=60) as client:
        async def request(index):
            async with limit:
                run, sample, udi = 401 + index % 2, 170 + index % 20, index + 1
                kind = index % 4
                path = (
                    f'/api/v1/tep/dataset/frame?run={run}&sample={sample}',
                    f'/api/v1/report?source=tep&run={run}&sample={sample}',
                    f'/api/v1/report?source=ai4i&udi={udi}',
                    '/health',
                )[kind]
                started = time.monotonic()
                response = await client.get(path)
                latencies.append((time.monotonic() - started) * 1000)
                response.raise_for_status()
                payload = response.json()
                if kind in (0, 1):
                    state, history = payload['state'], payload['history']
                    assert state['simulation_run'] == history['simulation_run'] == run
                    assert state['sample_index'] == history['end_sample'] == sample
                    assert state['assets'][0]['pressure_bar'] == history['points'][-1]['reactor_pressure_bar_g']
                    assert all(status == 'ready' for status in state['model_status'].values())
                elif kind == 2:
                    assert payload['source_kind'] == 'AI4I_DATASET' and payload['record']['udi'] == udi
                    assert 'state' not in payload
                else:
                    assert payload['status'] == 'ok'
        await asyncio.gather(*(request(index) for index in range(128)))
        async def stream(index):
            run = 401 + index % 2
            async with connect(f'ws://127.0.0.1:8000/ws/telemetry?run={run}&sample=959', open_timeout=30) as websocket:
                for sample in (959, 960):
                    payload = json.loads(await asyncio.wait_for(websocket.recv(), 30))
                    assert payload['sample_index'] == sample and payload['simulation_run'] == run
                    assert payload['source_kind'] == 'TEP_DATASET'
                await websocket.wait_closed()
                assert websocket.close_code == 1000
        await asyncio.gather(*(stream(index) for index in range(8)))
        # Deliberately reset upgraded peers, reproducing the historical Windows log.
        def reset_peer(_):
            key = base64.b64encode(os.urandom(16)).decode()
            with socket.create_connection(('127.0.0.1', 8000), timeout=20) as peer:
                peer.sendall((f'GET /ws/telemetry?sample=170 HTTP/1.1\r\nHost: 127.0.0.1:8000\r\n'
                    f'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                    'Sec-WebSocket-Version: 13\r\n\r\n').encode())
                response = b''
                while b'\r\n\r\n' not in response:
                    packet = peer.recv(4096)
                    if not packet:
                        raise AssertionError('No WebSocket upgrade response')
                    response += packet
                assert b'101 Switching Protocols' in response
                linger = struct.pack('hh' if os.name == 'nt' else 'ii', 1, 0)
                peer.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
        with ThreadPoolExecutor(max_workers=8) as pool:
            await asyncio.to_thread(lambda: list(pool.map(reset_peer, range(8))))
        # Give all reset connections two sender cycles to finish cleanup.
        await asyncio.sleep(4.2)
        response = await client.get('/health')
        response.raise_for_status()
        assert response.json()['status'] == 'ok'
    ordered = sorted(latencies)
    print(json.dumps({'status': 'passed', 'http_requests': 128, 'http_concurrency': 16,
        'websocket_clients': 8, 'abrupt_resets': 8, 'latency_ms': {
            'median': round(statistics.median(ordered), 1), 'p95': round(ordered[int(.95 * (len(ordered) - 1))], 1)},
        'checks': ['atomic source/sample identity', 'measured/chart agreement', 'models ready',
            'separate stream cursors', 'ordered final samples', 'normal end closure', 'health after peer resets']}))


if __name__ == '__main__':
    asyncio.run(main())
