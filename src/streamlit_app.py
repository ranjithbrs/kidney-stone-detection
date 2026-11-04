"""NEFROAI-X Unified Streamlit Clinical Decision Support Application.

Main entry point and navigation router coordinating:
- Home / System Overview
- Patient Clinical Assessment (Unified Multi-Engine Evaluation)
- Longitudinal Kidney Assessment (Timeline, Trajectory, LMM, and KFRE)
- Explainability & Clinical Findings (SHAP, LIME, and Decision Logic)
- Clinical Report Export (PDF, JSON, CSV, Text)
- About & Regulatory Governance (Methodology, Datasets, and Disclaimers)
"""

from __future__ import annotations

import os
import sys

# Ensure src/ and project root are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup unpickling aliases for production pipeline
import src.pipeline as _pipe_mod
import src.preprocessing as _prep_mod
sys.modules.setdefault("pipeline", _pipe_mod)
sys.modules.setdefault("preprocessing", _prep_mod)

import streamlit as st

from src.ui.components.header import render_app_header
from src.ui.views.about_view import render_about_view
from src.ui.views.assessment_view import render_assessment_view
from src.ui.views.explainability_view import render_explainability_view
from src.ui.views.home_view import render_home_view
from src.ui.views.longitudinal_view import render_longitudinal_view
from src.ui.views.report_view import render_report_view


def main() -> None:
    """Main application layout and view router."""
    st.set_page_config(
        page_title="NEFROAI-X | Renal Clinical Decision Support System",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Render persistent header and mandatory clinical safety banner
    render_app_header()

    # Sidebar Navigation
    st.sidebar.title("NEFROAI-X CDSS")
    st.sidebar.caption("Research Decision Support Prototype")

    menu_options = [
        "🏠 System Overview",
        "🩺 Patient Clinical Assessment",
        "📈 Longitudinal Kidney Assessment",
        "🔍 Explainability & Findings (XAI)",
        "📄 Clinical Assessment Report",
        "📖 About & Clinical Governance"
    ]

    default_idx = 0
    query_view = st.query_params.get("view", "")
    if query_view:
        view_map = {
            "home": 0,
            "overview": 0,
            "assessment": 1,
            "patient": 1,
            "longitudinal": 2,
            "trajectory": 2,
            "explainability": 3,
            "xai": 3,
            "report": 4,
            "export": 4,
            "about": 5,
            "governance": 5,
        }
        default_idx = view_map.get(str(query_view).lower().strip(), 0)

    selected_menu = st.sidebar.radio(
        "Navigation",
        menu_options,
        index=default_idx,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Engine Status:**
    - 🩺 **E1 Screening:** `ONLINE`
    - 🔬 **E2 Staging:** `ONLINE`
    - 📈 **E3 Trajectory:** `ONLINE`
    - ⏳ **Survival ML:** `DEFERRED`
    """)

    st.sidebar.markdown("---")
    st.sidebar.caption("""
    **Disclaimer:** Investigational research software. Not certified as a diagnostic medical device. Final clinical judgment requires board-certified physician adjudication.
    """)

    # Route to selected view
    if selected_menu == "🏠 System Overview":
        render_home_view()
    elif selected_menu == "🩺 Patient Clinical Assessment":
        render_assessment_view()
    elif selected_menu == "📈 Longitudinal Kidney Assessment":
        render_longitudinal_view()
    elif selected_menu == "🔍 Explainability & Findings (XAI)":
        render_explainability_view()
    elif selected_menu == "📄 Clinical Assessment Report":
        render_report_view()
    elif selected_menu == "📖 About & Clinical Governance":
        render_about_view()


if __name__ == "__main__":
    main()
