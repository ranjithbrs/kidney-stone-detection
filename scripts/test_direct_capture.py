import os, sys, time, subprocess, urllib.request

ROOT = r"c:\Users\B Ranjith\Downloads\project"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_EXE):
    EDGE_EXE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

profile_dir = os.path.join(ROOT, ".edge_test_profile2")
os.makedirs(profile_dir, exist_ok=True)

# 1. Start Streamlit
st_proc = subprocess.Popen(
    [
        os.path.join(ROOT, ".venv", "Scripts", "streamlit.exe"), "run", "app_streamlit.py",
        "--server.headless=true", "--server.port=8501", "--server.address=127.0.0.1", "--browser.gatherUsageStats=false"
    ],
    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

# Wait for Streamlit
for i in range(25):
    time.sleep(1)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=2) as r:
            if r.status == 200:
                print(f"Streamlit healthy in {i+1}s", flush=True)
                break
    except Exception:
        pass

out_png = os.path.join(ROOT, "docs", "images", "direct_test.png")
if os.path.exists(out_png):
    os.remove(out_png)

# Run Edge without virtual-time-budget
cmd = [
    EDGE_EXE,
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--window-size=1440,1080",
    f"--user-data-dir={profile_dir}",
    f"--screenshot={out_png}",
    "http://127.0.0.1:8501/?view=assessment"
]
print("Running Edge...", flush=True)
res = subprocess.run(cmd, timeout=30)
print("Edge finished with code:", res.returncode, flush=True)
st_proc.terminate()

if os.path.exists(out_png):
    size_kb = os.path.getsize(out_png) / 1024
    print(f"Produced direct_test.png: {size_kb:.1f} KB", flush=True)
else:
    print("Failed to produce direct_test.png", flush=True)
