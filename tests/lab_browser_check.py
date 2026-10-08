"""Chrome-CDP regression for the labelled synthetic equipment prognosis lab."""
import json
import time
import urllib.request

from websockets.sync.client import connect


def main():
    pages = [item for item in json.load(urllib.request.urlopen("http://127.0.0.1:9225/json")) if item.get("type") == "page"]
    if not pages:
        raise RuntimeError("No QA Chrome page on CDP port 9225")
    target = pages[0]; sequence = 0; errors = []
    with connect(target["webSocketDebuggerUrl"], max_size=25_000_000) as socket:
        def call(method, params=None):
            nonlocal sequence
            sequence += 1; current = sequence
            socket.send(json.dumps({"id": current, "method": method, "params": params or {}}))
            while True:
                message = json.loads(socket.recv(timeout=20))
                if message.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded"):
                    errors.append(message.get("params", {}))
                if message.get("id") == current:
                    if "error" in message: raise RuntimeError(message["error"])
                    return message.get("result", {})
        def evaluate(expression):
            result = call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            if "exceptionDetails" in result: raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")
        def wait_for(expression, timeout=20):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if evaluate(expression): return
                time.sleep(.15)
            raise AssertionError(f"Timed out: {expression}")
        call("Runtime.enable"); call("Log.enable"); call("Page.enable")
        call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": "http://127.0.0.1:5173/"})
        wait_for("document.querySelector('.dashboard') && [...document.querySelectorAll('.source-tabs button')].some(b=>b.textContent.includes('Prognosis lab'))")
        evaluate("[...document.querySelectorAll('.source-tabs button')].find(b=>b.textContent.includes('Prognosis lab')).click()")
        wait_for("document.querySelector('.lab-dashboard') && document.querySelector('.scene canvas') && document.querySelectorAll('.scene-callout').length===5")
        assert evaluate("document.querySelector('.summary-strip').innerText.includes('SP-201')")
        assert evaluate("document.querySelectorAll('.scene-forecast-warning').length===1")
        assert evaluate("document.querySelector('.rtf-forecast-note').innerText.includes('SP-201')")
        evaluate("[...document.querySelectorAll('.view-tabs button')].find(b=>b.textContent.includes('2D flow')).click()")
        wait_for("document.querySelectorAll('.lab-process-map .equipment-node').length===5")
        assert evaluate("document.querySelectorAll('.lab-process-map .equipment-node.forecast-warning').length===1")
        evaluate("(()=>{const e=document.querySelector('#lab-sample');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'21');e.dispatchEvent(new Event('change',{bubbles:true}))})()")
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='21'")
        assert evaluate("document.querySelector('.summary-strip').innerText.includes('Abstained')")
        evaluate("(()=>{const e=document.querySelector('#lab-sample');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,e.max);e.dispatchEvent(new Event('change',{bubbles:true}))})()")
        wait_for("document.querySelector('.lab-outcome') && document.querySelector('.playback-status')?.dataset.sample===document.querySelector('#lab-sample').max")
        assert evaluate("document.querySelector('.lab-outcome').innerText.includes('SP-201')")
        evaluate("[...document.querySelectorAll('.snapshot-actions button')].find(b=>b.textContent.includes('Export')).click()")
        wait_for("!!document.querySelector('dialog[open]')")
        assert evaluate("document.querySelector('dialog').innerText.toLowerCase().includes('synthetic prognosis snapshot')")
        evaluate("document.querySelector('.snapshot-close').click()")
        call("Page.navigate", {"url": "http://127.0.0.1:5173/?evaluation=equipment-prognosis"})
        wait_for("document.querySelector('.evaluation-page') && document.body.innerText.includes('90.4%')")
        assert evaluate("document.body.innerText.includes('Gates passed') && document.body.innerText.includes('Not physical plant validation')")
        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        call("Page.reload", {"ignoreCache": True})
        wait_for("!!document.querySelector('.evaluation-page')")
        assert evaluate("document.documentElement.scrollWidth<=document.documentElement.clientWidth+2")
        console_errors = [item for item in errors if "error" in json.dumps(item).lower() and "favicon.ico" not in json.dumps(item)]
        assert not console_errors, console_errors
    print(json.dumps({"status": "passed", "checks": ["five 3D assets", "correct amber target", "five-unit 2D map", "early abstention", "terminal truth reveal", "snapshot", "held-out evaluation", "mobile layout", "no console errors"]}))


if __name__ == "__main__":
    main()
