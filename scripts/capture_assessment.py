import asyncio, json, base64, time, os, urllib.request, subprocess, websockets

ROOT = r"c:\Users\B Ranjith\Downloads\project"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_EXE):
    EDGE_EXE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

profile_dir = os.path.join(ROOT, ".edge_cdp_profile_9444")
os.makedirs(profile_dir, exist_ok=True)

st_proc = subprocess.Popen(
    [
        os.path.join(ROOT, ".venv", "Scripts", "streamlit.exe"), "run", "app_streamlit.py",
        "--server.headless=true", "--server.port=8501", "--server.address=127.0.0.1", "--browser.gatherUsageStats=false"
    ],
    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

for i in range(25):
    time.sleep(1)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=2) as r:
            if r.status == 200:
                print(f"Streamlit healthy in {i+1}s", flush=True)
                break
    except Exception:
        pass

browser_proc = subprocess.Popen(
    [
        EDGE_EXE, "--headless=new", "--remote-debugging-port=9444",
        f"--user-data-dir={profile_dir}", "--window-size=1400,1050", "--disable-gpu",
        "--no-first-run", "--no-default-browser-check", "--disable-sync", "about:blank"
    ],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

time.sleep(2)
req = urllib.request.urlopen("http://127.0.0.1:9444/json")
tabs = json.loads(req.read().decode("utf-8"))
ws_url = None
for tab in tabs:
    if tab.get("type") == "page" and tab.get("url") == "about:blank":
        ws_url = tab["webSocketDebuggerUrl"]
        break
if not ws_url:
    for tab in tabs:
        if tab.get("type") == "page" and "webSocketDebuggerUrl" in tab:
            ws_url = tab["webSocketDebuggerUrl"]
            break

msg_id = 0
async def send_cmd(ws, method, params=None, timeout=25):
    global msg_id
    msg_id += 1
    req_id = msg_id
    payload = {"id": req_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(raw)
            if data.get("id") == req_id:
                return data.get("result", {})
        except asyncio.TimeoutError:
            pass
    raise TimeoutError(f"Timeout waiting for response to {method}")

async def main():
    try:
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            # First warmup on home
            print("Warming up on home...", flush=True)
            await send_cmd(ws, "Page.navigate", {"url": "http://127.0.0.1:8501/?view=home"})
            await asyncio.sleep(5)
            
            # Now navigate to assessment
            print("Navigating to assessment...", flush=True)
            await send_cmd(ws, "Page.navigate", {"url": "http://127.0.0.1:8501/?view=assessment"})
            print("Waiting 12s for full assessment render...", flush=True)
            await asyncio.sleep(12)
            
            res = await send_cmd(ws, "Page.captureScreenshot", {"format": "png"})
            img_bytes = base64.b64decode(res["data"])
            out_path = os.path.join(ROOT, "docs", "images", "screenshot_real_assessment.png")
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            print(f"SUCCESS: Saved {out_path} ({len(img_bytes)/1024:.1f} KB)", flush=True)
    finally:
        browser_proc.terminate()
        st_proc.terminate()

asyncio.run(main())
