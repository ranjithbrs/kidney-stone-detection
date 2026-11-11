"""NEFROAI-X Unified Streamlit Clinical Decision Support Application.

Main entry point and navigation router coordinating 8 clinical views:
- System Overview
- Patient Clinical Assessment (Single + Batch CSV Screening)
- Longitudinal Kidney Assessment (Timeline, Trajectory, LMM, and KFRE)
- Explainability & Findings (Live TreeSHAP, LIME, Concordance & Counterfactuals)
- Clinical Assessment Report (PDF, JSON, CSV, Text)
- About & Clinical Governance
- Model Performance & Calibration
- Patient History & Audit Vault
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

from src.ui.components.auth import render_sidebar_account_widget
from src.ui.components.header import render_app_header
from src.ui.views.about_view import render_about_view
from src.ui.views.assessment_view import render_assessment_view
from src.ui.views.explainability_view import render_explainability_view
from src.ui.views.history_view import render_history_view
from src.ui.views.home_view import render_home_view
from src.ui.views.longitudinal_view import render_longitudinal_view
from src.ui.views.performance_view import render_performance_view
from src.ui.views.report_view import render_report_view


def main() -> None:
    """Main application layout and view router."""
    st.set_page_config(
        page_title="NEFROAI-X | Renal Clinical Decision Support System",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Render global SaaS styles, persistent header bar, and clinical safety notice
    render_app_header()

    # Sidebar Brand Block
    st.sidebar.markdown(
        """
        <div style="background: rgba(255,255,255,0.06); border: 1px solid rgba(148,163,184,0.18); border-radius: 12px; padding: 0.78rem 0.85rem; margin-bottom: 0.55rem;">
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <span style="font-size: 1.05rem; font-weight: 800; color: #ffffff; letter-spacing: -0.01em;">NEFROAI-X</span>
                <span style="background: rgba(56,189,248,0.2); color: #7dd3fc; font-size: 0.65rem; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 999px; border: 1px solid rgba(56,189,248,0.35);">CDSS</span>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem;">
                Early CKD Screening &amp; Multi-Engine Suite
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_sidebar_account_widget()
    st.sidebar.markdown("---")

    menu_options = [
        "🏠 System Overview",
        "🩺 Patient Clinical Assessment",
        "📈 Longitudinal Kidney Assessment",
        "🔍 Explainability & Findings (XAI)",
        "📄 Clinical Assessment Report",
        "📖 About & Clinical Governance",
        "📊 Model Performance & Calibration",
        "🗂️ Patient History & Audit Vault",
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
            "performance": 6,
            "calibration": 6,
            "history": 7,
            "vault": 7,
        }
        default_idx = view_map.get(str(query_view).lower().strip(), 0)

    selected_menu = st.sidebar.radio(
        "Navigation",
        menu_options,
        index=default_idx,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(148,163,184,0.16); border-radius: 10px; padding: 0.75rem 0.85rem; font-size: 0.77rem;">
            <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: #94a3b8; font-weight: 700; margin-bottom: 0.45rem;">Runtime Engine Health</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.28rem;"><span>E1 CKD Screening</span><span style="color:#34d399; font-weight:700;">● ONLINE</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.28rem;"><span>E2 KDIGO Staging</span><span style="color:#34d399; font-weight:700;">● ONLINE</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.28rem;"><span>E3 Trajectory</span><span style="color:#34d399; font-weight:700;">● ONLINE</span></div>
            <div style="display:flex; justify-content:space-between;"><span>Survival ML</span><span style="color:#94a3b8; font-weight:700;">○ DEFERRED</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        """
        <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.85rem; line-height: 1.4;">
            <b style="color:#cbd5e1;">Research Notice:</b> Investigational screening software; final decisions require licensed nephrologist judgment.
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    elif selected_menu == "📊 Model Performance & Calibration":
        render_performance_view()
    elif selected_menu == "🗂️ Patient History & Audit Vault":
        render_history_view()


if __name__ == "__main__":
    main()
