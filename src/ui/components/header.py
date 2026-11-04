"""Header component with persistent research-software disclaimers and status badges."""

from __future__ import annotations

import streamlit as st


def render_app_header() -> None:
    """Render the application branding, status badges, and persistent clinical disclaimer."""
    st.markdown("""
    <style>
        .app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.75rem;
            margin-bottom: 1rem;
        }
        .app-title-group h1 {
            font-size: 2.1rem;
            font-weight: 800;
            color: #0f4c81;
            margin: 0;
            line-height: 1.2;
        }
        .app-title-group p {
            font-size: 1.0rem;
            color: #475569;
            margin: 0.2rem 0 0 0;
        }
        .persistent-disclaimer-box {
            background-color: #fffbeb;
            border-left: 5px solid #d97706;
            color: #92400e;
            padding: 0.65rem 1rem;
            border-radius: 4px;
            font-size: 0.88rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .engine-badge {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            margin-right: 0.35rem;
        }
        .badge-online {
            background-color: #ecfdf5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }
        .badge-deferred {
            background-color: #f1f5f9;
            color: #475569;
            border: 1px solid #cbd5e1;
        }
        .badge-research {
            background-color: #eff6ff;
            color: #1e40af;
            border: 1px solid #bfdbfe;
        }
    </style>
    """, unsafe_allow_html=True)

    # Top title and badges
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("""
        <div class="app-title-group">
            <h1>NEFROAI-X</h1>
            <p>Unified Explainable Clinical Decision Support System for Renal Medicine</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="text-align: right; padding-top: 0.4rem;">
            <span class="engine-badge badge-research">🔬 RESEARCH SOFTWARE v7.0.0</span>
            <span class="engine-badge badge-online">E1: SCREENING ONLINE</span><br>
            <span class="engine-badge badge-online" style="margin-top: 0.25rem;">E2: KDIGO STAGING ONLINE</span>
            <span class="engine-badge badge-online" style="margin-top: 0.25rem;">E3: KFRE ONLINE</span>
            <span class="engine-badge badge-deferred" style="margin-top: 0.25rem;">SURVIVAL ML: DEFERRED</span>
        </div>
        """, unsafe_allow_html=True)

    # Persistent mandatory clinical safety disclaimer
    st.markdown("""
    <div class="persistent-disclaimer-box">
        <span>⚠️</span>
        <span><b>MANDATORY CLINICAL NOTICE:</b> RESEARCH SOFTWARE PROTOTYPE — NOT CLINICALLY VALIDATED FOR INDEPENDENT DIAGNOSIS. NOT INTENDED TO REPLACE PROFESSIONAL MEDICAL JUDGMENT OR PHYSICIAN CONSULTATION.</span>
    </div>
    """, unsafe_allow_html=True)
