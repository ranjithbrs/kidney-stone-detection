"""
Streamlit Web Application Root Launcher for NefroAI Kidney Diagnostic System
Run with:
    streamlit run app_streamlit.py
or:
    .venv\Scripts\streamlit run app_streamlit.py
"""

import os
import sys

# Ensure src/ and root are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Execute the main Streamlit application
streamlit_app_path = os.path.join(SRC_DIR, "streamlit_app.py")

with open(streamlit_app_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), streamlit_app_path, "exec")
    exec(code, globals())
