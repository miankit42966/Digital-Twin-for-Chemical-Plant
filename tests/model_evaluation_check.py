r"""Verify readable evaluation pages and unchanged JSON APIs on local QA Chrome."""
import base64
import json
from pathlib import Path
import tempfile
import time
import urllib.request
from websockets.sync.client import connect


def main():
    targets = json.load(urllib.request.urlopen('http://127.0.0.1:9225/json'))
    target = next(item for item in targets if item.get('type') == 'page')
    artifacts = Path(tempfile.mkdtemp(prefix='sentineltwin-evaluation-qa-'))
    sequence, errors = 0, []
    with connect(target['webSocketDebuggerUrl'], max_size=25_000_000) as socket:
        def call(method, params=None):
            nonlocal sequence
            sequence += 1
            socket.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
            while True:
                message = json.loads(socket.recv(timeout=20))
                if message.get('method') == 'Runtime.exceptionThrown':
                    errors.append(message['params']['exceptionDetails'].get('text'))
                if message.get('id') == sequence:
                    if 'error' in message:
                        raise RuntimeError(message['error'])
                    return message.get('result', {})

        def evaluate(expression):
            result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
            if 'exceptionDetails' in result:
                raise RuntimeError(result['exceptionDetails'])
            return result.get('result', {}).get('value')

        def wait(expression):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if evaluate(f'Boolean({expression})'):
                    return
                time.sleep(.1)
            raise AssertionError('Timed out: ' + expression)

        def navigate(url):
            token = str(time.time_ns())
            script = call('Page.addScriptToEvaluateOnNewDocument', {'source': f"window.__modelQaToken='{token}'"})
            call('Page.navigate', {'url': url})
            wait(f"window.__modelQaToken==='{token}' && document.readyState==='complete'")
            call('Page.removeScriptToEvaluateOnNewDocument', {'identifier': script['identifier']})

        def screenshot(name):
            data = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True})
            (artifacts / name).write_bytes(base64.b64decode(data['data']))

        call('Runtime.enable'); call('Page.enable'); call('Network.enable')
        call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
        navigate('http://127.0.0.1:5173/')
        wait("document.querySelectorAll('.model-links a').length===2")
        links = evaluate("Array.from(document.querySelectorAll('.model-links a')).map(a=>a.getAttribute('href'))")
        assert links == ['/?evaluation=tep-detector', '/?evaluation=tep-pressure-20m']
        for origin in ('http://127.0.0.1:5173', 'http://127.0.0.1:8000'):
            for kind, values in (('tep-detector', ['99.68%', '54.63%', '0.953', '0.872']), ('tep-pressure-20m', ['5.25 kPa', '8.57 kPa', '0.988', '16.06 kPa'])):
                navigate(origin + '/?evaluation=' + kind)
                wait("document.querySelectorAll('.evaluation-metrics strong').length===4")
                assert evaluate("Array.from(document.querySelectorAll('.evaluation-metrics strong')).map(x=>x.innerText)") == values
                assert evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                assert evaluate("document.querySelector('.evaluation-limitations').innerText.includes('No live plant connection')")
                assert evaluate("fetch('/api/v1/models/' + document.querySelector('.evaluation-page').dataset.model).then(async r=>r.headers.get('content-type').includes('application/json') && !!(await r.json()).model_name)")
                if kind == 'tep-detector':
                    assert evaluate("document.querySelector('.evaluation-matrix').innerText.includes('7,259')")
                screenshot(kind + '-' + origin.rsplit(':', 1)[-1] + '.png')
        # Mobile layout and long provenance/raw JSON cannot widen the document.
        call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        navigate('http://127.0.0.1:5173/?evaluation=tep-detector')
        wait("document.querySelectorAll('.evaluation-metrics strong').length===4")
        evaluate("document.querySelectorAll('.evaluation-details').forEach(d=>d.open=true)")
        assert evaluate('document.documentElement.scrollWidth<=window.innerWidth'), 'Mobile evaluation overflow'
        screenshot('detector-mobile.png')
        # A card API failure gets an honest error and retry, not fabricated metrics.
        script = call('Page.addScriptToEvaluateOnNewDocument', {'source': "window.__realFetch=window.fetch;window.fetch=(url,options)=>String(url).includes('/api/v1/models/')?Promise.resolve(new Response('{}',{status:503})):window.__realFetch(url,options)"})
        navigate('http://127.0.0.1:5173/?evaluation=tep-pressure-20m')
        wait("document.querySelector('.error-banner')")
        assert evaluate("document.querySelectorAll('.evaluation-metrics strong').length===0")
        evaluate("window.fetch=window.__realFetch;document.querySelector('.error-banner button').click()")
        wait("document.querySelectorAll('.evaluation-metrics strong').length===4 && !document.querySelector('.error-banner')")
        call('Page.removeScriptToEvaluateOnNewDocument', {'identifier': script['identifier']})
        call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
        navigate('http://127.0.0.1:5173/')
        wait("document.querySelector('.playback-status')?.dataset.sample==='170'")
        assert not errors, errors
    print(json.dumps({'status': 'passed', 'checks': ['dashboard report links', 'both dev evaluation pages', 'both built evaluation pages',
        'metrics match real cards', 'confusion matrix', 'safety explanation', 'JSON APIs unchanged', 'mobile expanded details', 'API failure and retry', 'no runtime exceptions'], 'artifacts': str(artifacts)}))


if __name__ == '__main__':
    main()
