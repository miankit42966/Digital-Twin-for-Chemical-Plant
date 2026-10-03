r"""Browser source/export/production-origin regression checks on QA Chrome :9225."""
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
    artifacts = Path(tempfile.mkdtemp(prefix='sentineltwin-integration-qa-'))
    errors = []
    sequence = 0
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

        def wait_for(expression, timeout=20):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if evaluate(f'Boolean({expression})'):
                    return
                time.sleep(.15)
            error = evaluate("document.querySelector('.snapshot-actions [role=alert]')?.innerText ?? document.querySelector('.error-banner')?.innerText ?? ''")
            raise AssertionError('Timed out: ' + expression + ' / UI error: ' + str(error))

        def capture(name):
            image = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True})
            (artifacts / name).write_bytes(base64.b64decode(image['data']))

        call('Runtime.enable')
        call('Page.enable')
        call('Network.enable')
        call('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        for origin in ('http://127.0.0.1:8000', 'http://127.0.0.1:4173', 'http://127.0.0.1:5173'):
            token = str(time.time_ns())
            call('Page.addScriptToEvaluateOnNewDocument', {'source': f"window.__integrationToken='{token}'"})
            call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
            call('Page.navigate', {'url': origin + '/'})
            wait_for(f"window.__integrationToken==='{token}' && document.querySelector('.playback-status')?.dataset.sample==='170' && document.querySelector('.scene canvas')")
            assert evaluate("fetch('/api/v1/models/tep-pressure-20m').then(r=>r.ok)"), 'Model links unavailable on ' + origin
            assert evaluate("document.documentElement.scrollWidth<=window.innerWidth"), 'Desktop horizontal overflow'
            evaluate("document.querySelector('.scene').scrollIntoView({block:'center'})")
            time.sleep(2)  # Allow the WebGL/font frame to finish, not only the API response.
            scene = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
            (artifacts / ('scene-' + origin.rsplit(':', 1)[-1] + '.png')).write_bytes(base64.b64decode(scene['data']))
            capture('desktop-' + origin.rsplit(':', 1)[-1] + '.png')
        # Hold report responses even after abort, simulating out-of-order networks.
        evaluate("""window.__raceFetch=window.fetch;window.__pendingReports=[];
          window.fetch=async (url,options)=>{
            if(!String(url).includes('/api/v1/report?'))return window.__raceFetch(url,options);
            const entry={url:String(url),signal:options.signal,release:null};window.__pendingReports.push(entry);
            const response=await window.__raceFetch(url,{...options,signal:undefined});
            await new Promise(resolve=>entry.release=resolve);return response};
          const button=document.querySelector('.snapshot-actions button');button.click();button.click();""")
        wait_for("window.__pendingReports.length===1 && !!window.__pendingReports[0].release")
        assert evaluate("document.querySelector('.snapshot-actions button').disabled"), 'Double export not guarded'
        evaluate("document.querySelectorAll('.source-tabs button')[1].click()")
        wait_for("document.querySelector('.inspector-head span')?.innerText.includes('UDI 1') && !document.querySelector('.snapshot-actions button').disabled")
        assert evaluate('window.__pendingReports[0].signal.aborted'), 'Changing source did not cancel export'
        evaluate("document.querySelector('.snapshot-actions button').click()")
        wait_for("window.__pendingReports.length===2 && !!window.__pendingReports[1].release")
        evaluate("window.__pendingReports[0].release()")
        # Wait for the canceled request's finally block to run before checking busy state.
        evaluate("new Promise(resolve=>setTimeout(resolve,100))")
        assert evaluate("!document.querySelector('.snapshot-dialog') && document.querySelector('.snapshot-actions button').disabled"), 'Old export cleared newer request or opened stale report'
        evaluate("window.__pendingReports[1].release()")
        wait_for("document.querySelector('.snapshot-dialog')?.open")
        assert evaluate("document.querySelector('.snapshot-report').dataset.source==='AI4I_DATASET'"), 'New source report was mixed'
        evaluate("window.fetch=window.__raceFetch;document.querySelector('.snapshot-close').click();document.querySelectorAll('.source-tabs button')[0].click()")
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='170'")
        # Intercept the browser Blob, not the report API, to verify the actual export.
        evaluate("""window.__exportBlob=null;window.__originalObjectURL=URL.createObjectURL;
          URL.createObjectURL=function(blob){window.__exportBlob=blob;return window.__originalObjectURL(blob)};
          HTMLAnchorElement.prototype.click=function(){window.__exportFilename=this.download};
          document.querySelector('.snapshot-actions button').click()""")
        wait_for("document.querySelector('.snapshot-dialog')?.open")
        assert evaluate('window.__exportBlob===null'), 'Readable export unexpectedly downloaded JSON'
        assert evaluate("document.querySelector('.snapshot-report').dataset.sample==='170' && !!document.querySelector('.snapshot-report .pressure-chart')"), 'Snapshot preview/sample/chart missing'
        assert evaluate("document.activeElement.classList.contains('snapshot-close')"), 'Report did not receive keyboard focus'
        capture('tep-readable-report.png')
        evaluate("window.__printCalls=0;window.__priorTitle=document.title;window.__actualPrint=window.print;window.print=()=>{window.__printCalls++;window.__printTitle=document.title};document.querySelector('.snapshot-toolbar .control-button').click()")
        assert evaluate("window.__printCalls===1 && window.__printTitle.includes('sample-170') && document.title===window.__priorTitle"), 'Print action/title restoration failed'
        evaluate('window.print=window.__actualPrint')
        call('Emulation.setEmulatedMedia', {'media': 'print'})
        assert evaluate("Array.from(document.querySelector('.dashboard').children).filter(x=>!x.classList.contains('snapshot-dialog')).every(x=>getComputedStyle(x).display==='none')"), 'Background dashboard leaked into print layout'
        assert evaluate("getComputedStyle(document.querySelector('.snapshot-toolbar')).display==='none' && getComputedStyle(document.querySelector('.snapshot-dialog')).maxHeight==='none'"), 'Print layout is clipped or includes controls'
        capture('tep-print-layout.png')
        call('Emulation.setEmulatedMedia', {'media': ''})
        pdf = base64.b64decode(call('Page.printToPDF', {'printBackground': True, 'preferCSSPageSize': True})['data'])
        assert pdf.startswith(b'%PDF') and len(pdf)>5000, 'Readable PDF was not generated'
        (artifacts / 'tep-readable-report.pdf').write_bytes(pdf)
        evaluate("document.querySelector('.snapshot-technical button').click()")
        wait_for('window.__exportBlob!==null')
        report = evaluate('window.__exportBlob.text().then(JSON.parse)')
        assert report['source_kind'] == 'TEP_DATASET' and report['state']['sample_index'] == 170
        assert report['history']['end_sample'] == 170
        evaluate("document.querySelector('.snapshot-close').click()")
        evaluate("document.querySelectorAll('.source-tabs button')[1].click()")
        wait_for("document.querySelector('.inspector-head span')?.innerText.includes('UDI 1') && !document.querySelector('.playback-status')")
        assert evaluate("document.querySelector('.summary-strip strong').innerText==='10,000'")
        evaluate("document.querySelector('.record-nav button:last-child').click()")
        wait_for("document.querySelector('.inspector-head span')?.innerText.includes('UDI 2')")
        # A failed request must not show another UDI or report success from a second request.
        call('Network.emulateNetworkConditions', {'offline': True, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        evaluate("document.querySelector('.record-nav button:last-child').click()")
        wait_for("document.querySelector('.error-banner') && document.querySelector('.snapshot-actions button').disabled")
        assert evaluate("!document.querySelector('.inspector-head')"), 'Stale UDI shown as current after failure'
        call('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        evaluate("document.querySelector('.error-banner button').click()")
        wait_for("!document.querySelector('.error-banner') && document.querySelector('.inspector-head span')?.innerText.includes('UDI 3')")
        evaluate("window.__exportBlob=null;document.querySelector('.snapshot-actions button').click()")
        wait_for("document.querySelector('.snapshot-dialog')?.open")
        evaluate("document.querySelector('.snapshot-technical button').click()")
        wait_for('window.__exportBlob!==null')
        report = evaluate('window.__exportBlob.text().then(JSON.parse)')
        assert report['source_kind'] == 'AI4I_DATASET' and report['record']['udi'] == 3 and 'state' not in report
        assert evaluate("document.querySelector('.snapshot-report').dataset.source==='AI4I_DATASET' && !document.querySelector('.snapshot-report .pressure-chart')"), 'AI4I report includes plant chart'
        capture('ai4i-readable-report.png')
        evaluate("document.querySelector('.snapshot-close').click()")
        capture('ai4i-desktop.png')
        # Missing-model UI retains measured equipment and chart.
        evaluate("""window.__actualFetch=window.fetch;window.fetch=async function(url,options){
          const response=await window.__actualFetch(url,options);
          if(String(url).includes('/tep/dataset/frame')&&response.ok){const payload=await response.json();
          payload.state.detector_score=null;payload.state.reactor_pressure_20m_bar_g=null;
          payload.state.model_status={detector:'missing',pressure:'missing'};
          payload.state.model_notices={detector:'Model missing',pressure:'Model missing'};
          return new Response(JSON.stringify(payload),{headers:{'Content-Type':'application/json'}})}return response};
          document.querySelectorAll('.source-tabs button')[0].click();""")
        wait_for("document.getElementById('sample-seek')")
        evaluate("""const seek=document.getElementById('sample-seek');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(seek,'171');
          seek.dispatchEvent(new Event('input',{bubbles:true}));seek.dispatchEvent(new Event('change',{bubbles:true}));""")
        wait_for("document.querySelectorAll('.model-availability').length===2 && document.querySelector('.playback-status')?.dataset.sample==='171'")
        assert evaluate("document.querySelectorAll('.asset-playback-cards button').length===3 && !!document.querySelector('.pressure-chart')")
        capture('missing-model.png')
        call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        call('Page.reload', {'ignoreCache': True})
        wait_for("window.innerWidth===390 && document.querySelector('.playback-status')?.dataset.sample==='170'")
        evaluate("document.querySelectorAll('.source-tabs button')[1].click()")
        wait_for("document.querySelector('.inspector-head span')?.innerText.includes('UDI 1')")
        assert evaluate('document.documentElement.scrollWidth<=window.innerWidth'), 'Mobile AI4I overflow'
        capture('ai4i-mobile.png')
        evaluate("document.querySelector('.snapshot-actions button').click()")
        wait_for("document.querySelector('.snapshot-dialog')?.open")
        assert evaluate("document.querySelector('.snapshot-dialog').scrollWidth<=document.querySelector('.snapshot-dialog').clientWidth"), 'Mobile snapshot overflow'
        capture('ai4i-mobile-report.png')
        call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
        call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
        wait_for("!document.querySelector('.snapshot-dialog')")
        # Restore the user's default local workbench.
        call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
        call('Page.reload', {'ignoreCache': True})
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='170'")
        assert not errors, errors
    print(json.dumps({'status': 'passed', 'checks': ['API-hosted production UI', 'preview same-origin proxy', 'dev same-origin proxy',
        'TEP snapshot export', 'AI4I source separation', 'AI4I error/retry no stale UDI', 'AI4I export', 'missing-model measured-data retention',
        'mobile AI4I overflow', 'no browser exceptions', 'readable snapshot without automatic download', 'print action and PDF render',
        'report-only unclipped print layout', 'report keyboard focus and Escape', 'mobile report layout',
        'duplicate export guard', 'source change cancels export', 'old response cannot open stale report or clear newer busy state'], 'artifacts': str(artifacts)}))


if __name__ == '__main__':
    main()
