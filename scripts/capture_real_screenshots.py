#!/usr/bin/env python3
"""
Capture genuine screenshots of the running Streamlit application using headless Edge.
Saves genuine screenshots into docs/images/:
  - screenshot_01_home_page.png
  - screenshot_02_unified_assessment.png
  - screenshot_03_longitudinal_view.png
  - screenshot_04_explainability_view.png
  - screenshot_05_report_view.png
  - screenshot_06_about_view.png
"""

import os
import sys
import time
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_IMAGES = os.path.join(ROOT, "docs", "images")
os.makedirs(DOCS_IMAGES, exist_ok=True)

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_EXE):
    EDGE_EXE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

STREAMLIT_EXE = os.path.join(ROOT, ".venv", "Scripts", "streamlit.exe")
APP_PY = os.path.join(ROOT, "app_streamlit.py")

print("Starting Streamlit application on http://localhost:8501...")
proc = subprocess.Popen(
    [
        STREAMLIT_EXE, "run", APP_PY,
        "--server.headless=true",
        "--server.port=8501",
        "--server.address=127.0.0.1",
        "--browser.gatherUsageStats=false"
    ],
    cwd=ROOT,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

try:
    # Poll for server health
    healthy = False
    for i in range(25):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://localhost:8501/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    healthy = True
                    print(f"Streamlit server healthy after {i+1} seconds!")
                    break
        except Exception:
            pass

    if not healthy:
        print("Error: Streamlit server failed to start or respond to health probe.")
        sys.exit(1)

    # Allow Streamlit internal components to settle
    time.sleep(3)

    pages = [
        ("screenshot_01_home_page.png", "http://localhost:8501/?view=home"),
        ("screenshot_02_unified_assessment.png", "http://localhost:8501/?view=assessment"),
        ("screenshot_03_longitudinal_view.png", "http://localhost:8501/?view=longitudinal"),
        ("screenshot_04_explainability_view.png", "http://localhost:8501/?view=explainability"),
        ("screenshot_05_report_view.png", "http://localhost:8501/?view=report"),
        ("screenshot_06_about_view.png", "http://localhost:8501/?view=about"),
    ]

    temp_profile = os.path.join(ROOT, ".edge_temp_profile")
    os.makedirs(temp_profile, exist_ok=True)

    for filename, url in pages:
        out_path = os.path.join(DOCS_IMAGES, filename)
        print(f"Capturing: {url} -> {filename}")
        cmd = [
            EDGE_EXE,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--user-data-dir={temp_profile}",
            "--hide-scrollbars",
            "--window-size=1280,1024",
            "--virtual-time-budget=4000",
            f"--screenshot={out_path}",
            url
        ]
        try:
            subprocess.run(cmd, check=True, timeout=20)
            if os.path.exists(out_path):
                size_kb = os.path.getsize(out_path) / 1024
                print(f"  OK: {filename} ({size_kb:.1f} KB)")
            else:
                print(f"  Warning: failed to produce {filename}")
        except Exception as e:
            print(f"  Error capturing {filename}: {e}")

finally:
    print("Terminating Streamlit server...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Streamlit server stopped cleanly.")
