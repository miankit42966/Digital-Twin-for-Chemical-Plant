r"""Browser regression checks against a running local dashboard and Chrome CDP.

Run with: .venv\Scripts\python.exe tests/dashboard_playback_check.py
Requires the app on :5173, API on :8000 and a QA Chrome on CDP :9225.
"""
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
import urllib.request

from websockets.sync.client import connect
from PIL import Image, ImageChops


def main():
    targets = json.load(urllib.request.urlopen("http://127.0.0.1:9225/json"))
    pages = [target for target in targets if target.get("type") == "page"]
    if not pages:
        raise RuntimeError("No Chrome page target is available on CDP port 9225")
    target = next(
        (page for page in pages if page.get("url") == "http://127.0.0.1:5173/"),
        pages[0],
    )
    artifacts = Path(tempfile.mkdtemp(prefix="sentineltwin-playback-qa-"))
    errors = []
    sequence = 0
    with connect(target["webSocketDebuggerUrl"], max_size=25_000_000) as socket:
        def call(method, params=None):
            nonlocal sequence
            sequence += 1
            socket.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
            while True:
                message = json.loads(socket.recv(timeout=20))
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

        def wait_for(expression, timeout=15):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = evaluate(expression)
                if value:
                    return value
                time.sleep(.15)
            raise AssertionError(f"Timed out: {expression}")

        def screenshot(name, scene_only=False):
            params = {"format": "png", "captureBeyondViewport": not scene_only}
            rect = None
            if scene_only:
                evaluate("document.querySelector('.scene').scrollIntoView({block:'center'})")
                rect = evaluate("(()=>{const r=document.querySelector('.scene').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()")
            data = base64.b64decode(call("Page.captureScreenshot", params)["data"])
            (artifacts / name).write_bytes(data)
            pixels = Image.open(BytesIO(data)).convert('RGB')
            if rect:
                pixels = pixels.crop((round(rect['x']), round(rect['y']), round(rect['x'] + rect['width']), round(rect['y'] + rect['height'])))
            return hashlib.sha256(pixels.tobytes()).hexdigest()

        def screenshot_difference(first_name, second_name):
            first = Image.open(artifacts / first_name).convert('RGB')
            second = Image.open(artifacts / second_name).convert('RGB')
            difference = ImageChops.difference(first, second)
            pixels = difference.get_flattened_data()
            changed = sum(1 for pixel in pixels if pixel != (0, 0, 0))
            maximum = max((max(pixel) for pixel in pixels), default=0)
            return changed, maximum

        def click_play():
            evaluate("document.querySelector('.dataset-controls .control-button').click()")

        call("Runtime.enable")
        call("Network.enable")
        call("Page.enable")
        reload_token = str(time.time_ns())
        call("Page.addScriptToEvaluateOnNewDocument", {"source": f"window.__qaReloadToken='{reload_token}'"})
        call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": "http://127.0.0.1:5173/"})
        wait_for(f"window.__qaReloadToken==='{reload_token}' && document.querySelector('.dashboard') && document.querySelector('.scene canvas') && document.querySelector('.pressure-chart') && document.querySelector('.playback-status')?.dataset.sample==='170' && !document.querySelector('.dataset-controls .control-button')?.disabled")
        evaluate("""window.__playbackCheck={blanks:0,canvas:document.querySelector('.scene canvas'),chart:document.querySelector('.pressure-chart')};
          window.__playbackObserver=new MutationObserver(()=>{const q=window.__playbackCheck;
          if(!document.querySelector('.playback-status')?.dataset.sample || document.querySelector('.scene canvas')!==q.canvas || document.querySelector('.pressure-chart')!==q.chart || document.querySelectorAll('.asset-playback-cards button').length!==3)q.blanks++});
          window.__playbackObserver.observe(document.querySelector('.dashboard'),{childList:true,subtree:true,attributes:true});""")
        # Slow responses expose the previous blank-frame bug while playback runs.
        # Hold the committed dataset frame while the slower GPU screenshot path
        # compares flow-only animation. This prevents a sample change from being
        # mistaken for pipe motion on software-rendered CI/browser sessions.
        call("Network.emulateNetworkConditions", {"offline": False, "latency": 120000, "downloadThroughput": 800000, "uploadThroughput": 800000})
        click_play()
        time.sleep(.2)
        sample_before = evaluate("document.querySelector('.playback-status').dataset.sample")
        first = screenshot("playing-a.png", scene_only=True)
        time.sleep(.45)
        second = screenshot("playing-b.png", scene_only=True)
        assert evaluate("document.querySelector('.playback-status').dataset.sample") == sample_before, "Animation check crossed a sample boundary"
        assert first != second, "3D scene does not animate between dataset updates"
        # Pause rolls the requested slider sample back to the committed frame and
        # aborts the deliberately stalled fetch. Resume under normal QA latency.
        click_play()
        wait_for("document.querySelector('.dataset-controls .control-button')?.innerText==='Play stream'")
        call("Network.emulateNetworkConditions", {"offline": False, "latency": 600, "downloadThroughput": 800000, "uploadThroughput": 800000})
        click_play()
        wait_for("document.querySelector('.dataset-controls .control-button')?.innerText==='Pause stream'")
        wait_for("Number(document.querySelector('.playback-status')?.dataset.sample)>=173", timeout=20)
        assert evaluate("window.__playbackCheck.blanks") == 0, "Scene/chart was cleared or remounted during playback"
        screenshot("desktop-playing.png")

        # Pause during an in-flight response and ensure the committed frame stays put.
        wait_for("document.querySelector('.sample-control strong')?.innerText.split(' / ')[0]!==document.querySelector('.playback-status')?.dataset.sample", timeout=5)
        committed = evaluate("document.querySelector('.playback-status').dataset.sample")
        click_play()
        time.sleep(1)
        assert evaluate("document.querySelector('.playback-status').dataset.sample") == committed, "Pause accepted another in-flight sample"
        assert evaluate("document.querySelector('.sample-control strong').innerText.split(' / ')[0]") == committed, "Pause left slider ahead of readings"
        time.sleep(2)
        screenshot("paused-a.png", scene_only=True)
        time.sleep(.4)
        screenshot("paused-b.png", scene_only=True)
        changed_pixels, maximum_delta = screenshot_difference("paused-a.png", "paused-b.png")
        assert changed_pixels <= 5 and maximum_delta <= 5, "Process motion continues after Pause"
        evaluate("window.__playbackObserver.disconnect()")
        call("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})

        def seek(sample):
            evaluate(f"(()=>{{const x=document.getElementById('sample-seek');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(x,'{sample}');x.dispatchEvent(new Event('input',{{bubbles:true}}));x.dispatchEvent(new Event('change',{{bubbles:true}}));}})()")
            wait_for(f"document.querySelector('.playback-status')?.dataset.sample==='{sample}'")

        seek(1)
        assert "Unavailable" in evaluate("document.querySelector('.summary-strip').innerText"), "Early sample fabricated a pressure forecast"
        seek(959)
        click_play()
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='960' && document.querySelector('.dataset-controls .control-button')?.innerText==='Restart stream'")
        time.sleep(1)
        assert evaluate("document.querySelector('.playback-status').dataset.sample") == "960", "Run silently looped instead of ending"
        click_play()
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='1'")
        click_play()

        evaluate("(()=>{const x=[...document.querySelectorAll('.dataset-controls label')].find(x=>x.textContent.startsWith('PLAYBACK SPEED')).querySelector('select');x.value='2';x.dispatchEvent(new Event('change',{bubbles:true}))})()")
        click_play()
        wait_for("Number(document.querySelector('.playback-status')?.dataset.sample)>=2", timeout=5)
        click_play()
        committed = evaluate("document.querySelector('.playback-status').dataset.sample")
        call("Network.emulateNetworkConditions", {"offline": True, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        click_play()
        wait_for("document.querySelector('.error-banner')?.innerText.includes('Retry dataset')", timeout=8)
        assert evaluate("document.querySelector('.playback-status').dataset.sample") == committed, "Disconnected API cleared the last sample"
        assert evaluate("document.querySelectorAll('.asset-playback-cards button').length") == 3, "Disconnected API cleared equipment"
        call("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        evaluate("document.querySelector('.error-banner button').click()")
        wait_for("!document.querySelector('.error-banner') && document.querySelector('.connection-pill')?.innerText==='TEP dataset ready'")
        evaluate("(()=>{const x=[...document.querySelectorAll('.dataset-controls label')].find(x=>x.textContent.startsWith('SIMULATION RUN')).querySelector('select');x.value='2';x.dispatchEvent(new Event('change',{bubbles:true}))})()")
        wait_for("document.querySelector('.playback-status')?.dataset.run==='2'")
        selected_sample = evaluate("document.querySelector('.playback-status').dataset.sample")
        expected = json.load(urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/tep/dataset/state?sample={selected_sample}&partition=testing&fault=6&run=2"))
        shown_pressure = evaluate("document.querySelectorAll('.metric-grid strong')[1].innerText.split(' ')[0]")
        assert shown_pressure == f"{expected['assets'][0]['pressure_bar']:.2f}", "Displayed readings do not match selected dataset run"

        # Verify the actual mobile layout, including camera fit and both views.
        call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        call("Page.reload", {"ignoreCache": True})
        wait_for("document.querySelector('.playback-status')?.dataset.sample==='170'")
        assert evaluate("document.documentElement.scrollWidth<=innerWidth"), "Mobile page overflows horizontally"
        click_play()
        wait_for("document.querySelector('.scene')?.classList.contains('is-playing')")
        screenshot("mobile-playing.png")
        click_play()
        evaluate("[...document.querySelectorAll('.view-tabs button')].find(x=>x.textContent==='2D flow').click()")
        assert evaluate("getComputedStyle(document.querySelector('.flow-pulse')).animationPlayState") == "paused", "2D flow ignores Pause"
        click_play()
        assert evaluate("getComputedStyle(document.querySelector('.flow-pulse')).animationPlayState") == "running", "2D flow ignores Play"
        screenshot("mobile-2d-playing.png")
        click_play()
        assert not errors, f"Browser exceptions: {errors}"
        print(json.dumps({"status": "passed", "checks": ["slow-network no-flicker", "3D animation between samples", "pause cancels pending sample", "pause freezes motion", "early-model unavailable", "seek and run end/restart", "2x speed", "disconnect retains frame and retry recovers", "selected run matches dataset readings", "mobile layout", "2D play/pause", "no browser exceptions"], "artifacts": str(artifacts)}))


if __name__ == "__main__":
    main()
