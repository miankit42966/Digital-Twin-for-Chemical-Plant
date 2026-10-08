r"""Local Chrome/CDP regression checks for the TEP run-to-failure view."""
import json
import time
import urllib.request

from websockets.sync.client import connect


def main():
    targets = json.load(urllib.request.urlopen("http://127.0.0.1:9225/json"))
    target = next(item for item in targets if item.get("type") == "page")
    errors = []
    sequence = 0
    with connect(target["webSocketDebuggerUrl"], max_size=25_000_000) as socket:
        def call(method, params=None):
            nonlocal sequence
            sequence += 1
            socket.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
            while True:
                message = json.loads(socket.recv(timeout=25))
                if message.get("method") == "Runtime.exceptionThrown":
                    errors.append(message["params"]["exceptionDetails"].get("text", "Runtime error"))
                if message.get("id") == sequence:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message.get("result", {})

        def evaluate(expression):
            result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        def wait_for(expression, timeout=20):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = evaluate(expression)
                if value:
                    return value
                time.sleep(.15)
            raise AssertionError(f"Timed out: {expression}")

        call("Runtime.enable")
        call("Page.enable")
        call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": "http://127.0.0.1:5173/"})
        wait_for("!!document.querySelector('.dashboard')")
        evaluate("[...document.querySelectorAll('.source-tabs button')].find(b=>b.textContent.includes('run-to-failure')).click()")
        wait_for("!!document.querySelector('.rtf-dashboard') && document.querySelector('.playback-status')?.dataset.sample==='21' && !!document.querySelector('.scene canvas')")
        assert evaluate("document.querySelector('.summary-strip')?.innerText.includes('Unassessed')")
        assert not evaluate("!!document.querySelector('.rtf-forecast-note.has-warning')")
        assert evaluate("document.querySelector('.rtf-forecast-note')?.innerText.includes('no independently verified terminal-unit labels')")

        evaluate("""window.__rtfRealFetch=window.fetch;window.__rtfPending=null;
          window.fetch=async(url,options={})=>{if(!String(url).includes('/api/v1/report?source=rtf'))return window.__rtfRealFetch(url,options);
          const entry={signal:options.signal,release:null};window.__rtfPending=entry;
          const response=await window.__rtfRealFetch(url,{...options,signal:undefined});
          await new Promise(resolve=>entry.release=resolve);return response};
          document.querySelector('.snapshot-actions button').click()""")
        wait_for("window.__rtfPending?.release && document.querySelector('.snapshot-actions button').disabled")
        evaluate("""const seek=document.getElementById('rtf-sample');
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(seek,'22');
          seek.dispatchEvent(new Event('input',{bubbles:true}));seek.dispatchEvent(new Event('change',{bubbles:true}))""")
        wait_for("window.__rtfPending.signal.aborted && !document.querySelector('.snapshot-actions button').disabled")
        assert not evaluate("!!document.querySelector('.snapshot-dialog')")
        evaluate("window.__rtfPending.release();window.fetch=window.__rtfRealFetch")
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='22'")

        evaluate("document.querySelector('.dataset-controls .control-button').click()")
        advanced = wait_for("Number(document.querySelector('.playback-status')?.dataset.sample)>22", 8)
        evaluate("document.querySelector('.dataset-controls .control-button').click()")
        paused = evaluate("Number(document.querySelector('.playback-status').dataset.sample)")
        time.sleep(2.4)
        assert evaluate("Number(document.querySelector('.playback-status').dataset.sample)") == paused
        assert advanced

        evaluate("[...document.querySelectorAll('.view-tabs button')].find(b=>b.textContent.includes('2D flow')).click()")
        wait_for("!!document.querySelector('.process-map')")
        assert evaluate("document.querySelectorAll('.equipment-node').length===3")
        assert not evaluate("!!document.querySelector('.equipment-node.forecast-warning')")

        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        assert wait_for("document.documentElement.scrollWidth<=window.innerWidth+2")
        call("Page.navigate", {"url": "http://127.0.0.1:5173/?evaluation=tep-rtf-prognosis"})
        wait_for("!!document.querySelector('.evaluation-metrics')")
        assert evaluate("document.querySelector('.evaluation-metrics')?.innerText.includes('Unassessed')")
        assert evaluate("document.body.innerText.includes('115.0 min')")
        assert not errors, errors
    print(json.dumps({"status": "pass", "checks": 12, "console_errors": errors}, indent=2))


if __name__ == "__main__":
    main()
