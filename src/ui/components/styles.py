"""Global Clinical SaaS UI Design System (CSS injection) for NEFROAI-X."""

from __future__ import annotations

import streamlit as st


def inject_professional_styles() -> None:
    """Inject modern SaaS clinical web-application typography, layout, sidebar, and card CSS."""
    st.markdown(
        """
        <style>
        :root {
            --nx-navy: #0b1f3a;
            --nx-navy-mid: #0f2942;
            --nx-primary: #0f4c81;
            --nx-teal: #0e7490;
            --nx-sky: #0284c7;
            --nx-emerald: #059669;
            --nx-amber: #d97706;
            --nx-red: #dc2626;
            --nx-bg: #f1f5f9;
            --nx-surface: #ffffff;
            --nx-border: #e2e8f0;
            --nx-text: #0f172a;
            --nx-muted: #475569;
            --nx-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
            --nx-shadow-md: 0 4px 16px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.04);
        }

        html, body, [class*="css"], .stApp {
            font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
            color: var(--nx-text);
        }

        .stApp {
            background-color: var(--nx-bg);
        }

        [data-testid="stHeader"] {
            background: rgba(241, 245, 249, 0.85);
            backdrop-filter: blur(8px);
        }

        .main .block-container,
        [data-testid="stAppViewBlockContainer"] {
            padding-top: 1.4rem !important;
            padding-bottom: 2.2rem !important;
            max-width: 1380px !important;
        }

        h1, h2, h3, h4 {
            color: var(--nx-navy-mid);
            letter-spacing: -0.015em;
            font-weight: 700;
        }
        h2 {
            font-size: 1.42rem !important;
            margin-top: 0.15rem !important;
            margin-bottom: 0.45rem !important;
        }
        h3 {
            font-size: 1.12rem !important;
            margin-top: 0.35rem !important;
            margin-bottom: 0.35rem !important;
        }
        code, pre {
            font-family: 'Cascadia Code', 'Consolas', ui-monospace, SFMono-Regular, monospace !important;
        }

        /* ================== SIDEBAR (Dark Clinical Navy SaaS Navigation) ================== */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #09182e 0%, #0f2942 62%, #13314f 100%) !important;
            border-right: 1px solid rgba(148, 163, 184, 0.16);
        }
        [data-testid="stSidebar"] * {
            color: #e2e8f0;
        }
        [data-testid="stSidebar"] hr {
            border-color: rgba(148, 163, 184, 0.18) !important;
            margin: 0.75rem 0 !important;
        }

        /* Transform Streamlit 1.65 radio items into sleek SaaS pill nav buttons */
        [data-testid="stSidebar"] [role="radiogroup"] {
            gap: 0.25rem !important;
        }
        [data-testid="stSidebar"] label[data-testid="stRadioOption"] {
            background: transparent !important;
            border: 1px solid transparent !important;
            border-radius: 9px !important;
            padding: 0.48rem 0.72rem !important;
            margin: 0 !important;
            width: 100% !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
        }
        /* Hide native circular radio ring div in Streamlit 1.65 */
        [data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child {
            display: none !important;
        }
        [data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover {
            background: rgba(56, 189, 248, 0.12) !important;
            border-color: rgba(56, 189, 248, 0.28) !important;
        }
        [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) {
            background: linear-gradient(90deg, rgba(14, 165, 233, 0.24) 0%, rgba(14, 116, 144, 0.18) 100%) !important;
            border: 1px solid rgba(56, 189, 248, 0.55) !important;
            box-shadow: inset 3px 0 0 #38bdf8, 0 2px 8px rgba(2, 6, 23, 0.25) !important;
        }
        [data-testid="stSidebar"] label[data-testid="stRadioOption"] p {
            font-size: 0.87rem !important;
            font-weight: 500 !important;
            color: #cbd5e1 !important;
            line-height: 1.28 !important;
            margin: 0 !important;
        }
        [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) p {
            color: #ffffff !important;
            font-weight: 700 !important;
        }

        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            font-size: 0.70rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            color: #94a3b8 !important;
            font-weight: 700 !important;
            margin-bottom: 0.35rem !important;
        }

        /* ================== METRIC KPI SURFACE CARDS ================== */
        [data-testid="stMetric"] {
            background: var(--nx-surface) !important;
            border: 1px solid var(--nx-border) !important;
            border-radius: 12px !important;
            padding: 0.8rem 0.95rem !important;
            min-height: 108px !important;
            box-shadow: var(--nx-shadow-sm) !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
        }
        [data-testid="stMetricLabel"] p {
            font-size: 0.74rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
            color: var(--nx-muted) !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.28rem !important;
            font-weight: 800 !important;
            color: var(--nx-navy-mid) !important;
            font-variant-numeric: tabular-nums !important;
        }

        /* ================== SEGMENTED SAAS TABS ================== */
        [data-testid="stTabs"] [role="tablist"] {
            background: #e2e8f0 !important;
            padding: 5px 6px !important;
            border-radius: 10px !important;
            gap: 6px !important;
            border-bottom: none !important;
        }
        [data-testid="stTabs"] button[role="tab"] {
            border-radius: 8px !important;
            padding: 0.45rem 1.0rem !important;
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: #475569 !important;
            background: transparent !important;
            border: none !important;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: #ffffff !important;
            color: #0f2942 !important;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.12) !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"],
        [data-testid="stTabs"] [data-baseweb="tab-border"] {
            display: none !important;
        }

        /* ================== BUTTONS & DOWNLOADS ================== */
        .stButton > button, .stDownloadButton > button {
            border-radius: 9px !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
            padding: 0.48rem 0.9rem !important;
            border: 1px solid #cbd5e1 !important;
            background: #ffffff !important;
            color: #0f2942 !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
            transition: all 0.15s ease !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: #0284c7 !important;
            color: #0f4c81 !important;
            background: #f0f9ff !important;
            transform: translateY(-1px);
            box-shadow: 0 3px 8px rgba(2, 132, 199, 0.12) !important;
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0f4c81 0%, #0e7490 100%) !important;
            color: #ffffff !important;
            border: none !important;
            box-shadow: 0 3px 10px rgba(15, 76, 129, 0.25) !important;
        }
        .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #0b3a63 0%, #0c637a 100%) !important;
            color: #ffffff !important;
            box-shadow: 0 5px 14px rgba(15, 76, 129, 0.35) !important;
        }

        /* ================== SIDEBAR BUTTONS (Dark Glass Theme) ================== */
        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255, 255, 255, 0.08) !important;
            color: #ffffff !important;
            border: 1px solid rgba(148, 163, 184, 0.30) !important;
            border-radius: 8px !important;
            font-size: 0.80rem !important;
            font-weight: 600 !important;
            padding: 0.36rem 0.6rem !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(56, 189, 248, 0.22) !important;
            border-color: rgba(56, 189, 248, 0.65) !important;
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0284c7 0%, #0e7490 100%) !important;
            border-color: rgba(125, 211, 252, 0.45) !important;
            color: #ffffff !important;
        }

        /* ================== INPUTS, FORMS, EXPANDERS & DATAFRAMES ================== */
        [data-testid="stExpander"], [data-testid="stForm"] {
            background: #ffffff !important;
            border: 1px solid var(--nx-border) !important;
            border-radius: 12px !important;
            box-shadow: var(--nx-shadow-sm) !important;
        }
        [data-testid="stDataFrame"], [data-testid="stAlert"] {
            border-radius: 10px !important;
        }
        [data-testid="stTextInputRootElement"],
        [data-testid="stNumberInputContainer"],
        [data-baseweb="select"] > div,
        [data-testid="stDateInput"] > div > div {
            border: 1.5px solid #cbd5e1 !important;
            box-shadow: inset 0 0 0 1px rgba(203, 213, 225, 0.5) !important;
            border-radius: 8px !important;
            background-color: #f8fafc !important;
        }
        [data-testid="stTextInputRootElement"] [data-baseweb="input"],
        [data-testid="stTextInputRootElement"] [data-baseweb="base-input"],
        [data-testid="stNumberInputContainer"] [data-baseweb="input"],
        [data-testid="stNumberInputContainer"] [data-baseweb="base-input"] {
            background-color: transparent !important;
            border: none !important;
        }
        [data-testid="stTextInputRootElement"]:focus-within,
        [data-testid="stNumberInputContainer"]:focus-within,
        [data-baseweb="select"] > div:focus-within {
            border-color: #0284c7 !important;
            background-color: #ffffff !important;
            box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.16) !important;
        }
        .stNumberInput input, .stTextInput input {
            background-color: transparent !important;
            color: #0f172a !important;
        }

        .nx-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.15rem 1.25rem;
            box-shadow: var(--nx-shadow-md);
        }
        .nx-section-title {
            font-size: 1.06rem;
            font-weight: 700;
            color: #0f2942;
            margin: 0 0 0.2rem 0;
        }
        .nx-section-sub {
            font-size: 0.85rem;
            color: #475569;
            margin: 0 0 0.8rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
