"""Header component with modern SaaS navigation bar, engine status pills, and persistent clinical disclaimer."""

from __future__ import annotations

import html

import streamlit as st

from src.ui.components.styles import inject_professional_styles


def render_app_header() -> None:
    """Render global SaaS design styles, top clinical navbar, status pills, and safety notice."""
    inject_professional_styles()

    active_user = st.session_state.get("auth_username")
    if active_user:
        user_badge_html = (
            f'<span class="nx-pill nx-pill-live"><span class="nx-dot-green"></span> @{html.escape(str(active_user))}</span>'
        )
    else:
        user_badge_html = '<span class="nx-pill nx-pill-muted">GUEST SESSION</span>'

    header_html = """
        <style>
        .nx-topbar {
            background: linear-gradient(135deg, #0b1f3a 0%, #0f4c81 58%, #0e7490 100%);
            border-radius: 14px;
            padding: 0.85rem 1.25rem;
            margin-bottom: 0.55rem;
            display: flex;
            flex-wrap: nowrap;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            box-shadow: 0 8px 24px rgba(11, 31, 58, 0.14);
            border: 1px solid rgba(56, 189, 248, 0.22);
        }
        @media (max-width: 1120px) {
            .nx-topbar { flex-wrap: wrap; }
        }
        .nx-brand-wrap {
            display: flex;
            align-items: center;
            gap: 0.72rem;
            flex: 0 1 auto;
        }
        .nx-logo-badge {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.28);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .nx-brand-title {
            margin: 0;
            font-size: 1.42rem;
            font-weight: 800;
            color: #ffffff !important;
            letter-spacing: -0.02em;
            line-height: 1.1;
        }
        .nx-brand-sub {
            margin: 0.15rem 0 0 0;
            font-size: 0.80rem;
            color: #cbd5e1 !important;
            font-weight: 500;
        }
        .nx-pill-row {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.35rem;
            justify-content: flex-end;
        }
        .nx-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.32rem;
            padding: 0.22rem 0.56rem;
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            white-space: nowrap;
        }
        .nx-pill-live {
            background: rgba(16, 185, 129, 0.18);
            color: #d1fae5 !important;
            border: 1px solid rgba(52, 211, 153, 0.45);
        }
        .nx-pill-ver {
            background: rgba(255, 255, 255, 0.14);
            color: #f8fafc !important;
            border: 1px solid rgba(255, 255, 255, 0.28);
        }
        .nx-pill-muted {
            background: rgba(148, 163, 184, 0.16);
            color: #cbd5e1 !important;
            border: 1px solid rgba(148, 163, 184, 0.32);
        }
        .nx-dot-green {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #34d399;
            display: inline-block;
        }
        .nx-disclaimer-strip {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-left: 4px solid #d97706;
            border-radius: 10px;
            padding: 0.55rem 0.95rem;
            margin-bottom: 1.15rem;
            display: flex;
            align-items: center;
            gap: 0.6rem;
            font-size: 0.80rem;
            font-weight: 600;
            color: #92400e;
            box-shadow: 0 1px 2px rgba(217, 119, 6, 0.06);
        }
        </style>

        <div class="nx-topbar">
            <div class="nx-brand-wrap">
                <div class="nx-logo-badge">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2L4 5v6c0 5.55 3.42 10.74 8 12 4.58-1.26 8-6.45 8-12V5l-8-3z"/>
                        <path d="M9 12l2 2 4-4"/>
                    </svg>
                </div>
                <div>
                    <div class="nx-brand-title">NEFROAI-X</div>
                    <div class="nx-brand-sub">Early CKD Screening, KDIGO Staging &amp; Progression Suite</div>
                </div>
            </div>
            <div class="nx-pill-row">
                <span class="nx-pill nx-pill-ver">CDSS v1.0</span>
                <span class="nx-pill nx-pill-live"><span class="nx-dot-green"></span> E1–E3 ONLINE</span>
                <span class="nx-pill nx-pill-muted">SURVIVAL ML: DEFERRED</span>
                __USER_BADGE_HTML__
            </div>
        </div>

        <div class="nx-disclaimer-strip">
            <span style="font-size: 1rem;">⚠️</span>
            <span><b>MANDATORY CLINICAL NOTICE:</b> RESEARCH SOFTWARE PROTOTYPE — NOT CLINICALLY VALIDATED FOR INDEPENDENT DIAGNOSIS. NOT INTENDED TO REPLACE PROFESSIONAL MEDICAL JUDGMENT OR PHYSICIAN CONSULTATION.</span>
        </div>
        """.replace("__USER_BADGE_HTML__", user_badge_html)
    st.markdown(header_html, unsafe_allow_html=True)
