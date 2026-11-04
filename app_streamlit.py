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

# Import and invoke main application
import src.streamlit_app as app

if __name__ == "__main__":
    app.main()
