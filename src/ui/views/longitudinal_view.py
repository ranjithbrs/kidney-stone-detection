"""Longitudinal Kidney Assessment View."""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from src.clinical.egfr_calculator import calculate_egfr_ckd_epi_2021
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
)
from src.engines.kidney_progression_engine import KidneyProgressionEngine
from src.ui.components.visualizations import render_longitudinal_timeline


@st.cache_resource
def get_progression_engine() -> KidneyProgressionEngine:
    return KidneyProgressionEngine()


def render_longitudinal_view() -> None:
    """Render the Longitudinal Kidney Assessment and Trajectory interface."""
    st.markdown("## 📈 Longitudinal Kidney Assessment & Trajectory")
    st.markdown("""
    Evaluate kidney function progression across multiple dated visits. Computes empirical eGFR slope,
    estimates Linear Mixed-Effects (LMM) Empirical Bayes random slopes, and generates interactive filtration trajectories.
    """)

    prog_engine = get_progression_engine()

    # Session observations
    if "e3_observations" not in st.session_state:
        st.session_state.e3_observations = []

    # 1. Observation Import / Add Section
    tab_manual, tab_csv = st.tabs(["➕ Add Visit Manually", "📁 Import Visits via CSV"])

    with tab_manual:
        st.markdown("##### Add Clinical Observation")
        mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns([1.5, 1, 1, 1, 1])
        with mcol1:
            v_date = st.date_input("Visit Date", value=date.today())
        with mcol2:
            v_scr = st.number_input("Serum Creatinine [mg/dL]", min_value=0.2, max_value=25.0, value=1.4, step=0.1)
        with mcol3:
            v_uacr = st.number_input("uACR [mg/g]", min_value=1.0, max_value=4000.0, value=65.0, step=5.0)
        with mcol4:
            v_sbp = st.number_input("Systolic BP [mmHg]", min_value=60.0, max_value=240.0, value=128.0, step=2.0)
        with mcol5:
            st.markdown("<div style='padding-top: 1.7rem;'></div>", unsafe_allow_html=True)
            if st.button("Add Visit", use_container_width=True):
                st.session_state.e3_observations.append({
                    "date": v_date,
                    "scr": float(v_scr),
                    "uacr": float(v_uacr),
                    "sbp": float(v_sbp),
                })
                # Sort visits by date
                st.session_state.e3_observations.sort(key=lambda x: x["date"])
                st.success(f"Added visit for {v_date}!")
                st.rerun()

    with tab_csv:
        st.markdown("##### Upload Longitudinal Observations CSV")
        st.caption("Expected columns: `date` (YYYY-MM-DD), `serum_creatinine` (or `sc`), `uacr` (optional), `sbp` (optional). Max 5 MB, 500 rows.")
        uploaded_file = st.file_uploader("Select CSV file", type=["csv"])
        if uploaded_file is not None:
            # File security checks: size limit and file type
            MAX_UPLOAD_BYTES = 5 * 1024 * 1024
            MAX_ROWS = 500

            if uploaded_file.size > MAX_UPLOAD_BYTES:
                st.error(f"Security Alert: Uploaded file size ({uploaded_file.size / 1024 / 1024:.2f} MB) exceeds maximum limit of 5 MB.")
            elif not uploaded_file.name.lower().endswith(".csv"):
                st.error("Security Alert: Only .csv files are accepted.")
            else:
                try:
                    df_upload = pd.read_csv(uploaded_file, nrows=MAX_ROWS + 1)
                    if len(df_upload) > MAX_ROWS:
                        st.error(f"Security Alert: Uploaded CSV exceeds maximum row limit of {MAX_ROWS} rows.")
                    else:
                        st.dataframe(df_upload.head(5), use_container_width=True)

                        date_col = next((c for c in df_upload.columns if c.lower() in ["date", "timestamp", "visit_date"]), None)
                        scr_col = next((c for c in df_upload.columns if c.lower() in ["serum_creatinine", "sc", "scr", "lbxscr"]), None)
                        uacr_col = next((c for c in df_upload.columns if c.lower() in ["uacr", "urdact", "uacr_mg_g"]), None)
                        sbp_col = next((c for c in df_upload.columns if c.lower() in ["sbp", "systolic_bp", "bp"]), None)

                        if date_col and scr_col:
                            if st.button("Load Observations Into Active Session", type="primary"):
                                new_obs = []
                                for _, row in df_upload.iterrows():
                                    try:
                                        d_val = pd.to_datetime(row[date_col]).date()
                                        s_val = float(row[scr_col]) if pd.notna(row[scr_col]) else None
                                        u_val = float(row[uacr_col]) if uacr_col and pd.notna(row[uacr_col]) else None
                                        bp_val = float(row[sbp_col]) if sbp_col and pd.notna(row[sbp_col]) else None

                                        # Physiological boundary verification (0.2 - 25.0 mg/dL for SC)
                                        if s_val is not None and (0.2 <= s_val <= 25.0):
                                            if u_val is not None and not (0.1 <= u_val <= 10000.0):
                                                u_val = None
                                            if bp_val is not None and not (50.0 <= bp_val <= 260.0):
                                                bp_val = None
                                            new_obs.append({"date": d_val, "scr": s_val, "uacr": u_val, "sbp": bp_val})
                                    except Exception:
                                        continue
                                new_obs.sort(key=lambda x: x["date"])
                                st.session_state.e3_observations = new_obs
                                st.session_state.is_synthetic_demonstration = False
                                st.success(f"Successfully loaded and validated {len(new_obs)} longitudinal observations!")
                                st.rerun()
                        else:
                            st.error("Uploaded CSV must contain at least a date column and a serum creatinine column.")
                except Exception as ex:
                    st.error(f"Error parsing uploaded CSV: {ex}")

    st.markdown("---")

    # 2. Display Table of Current Visits
    visits = st.session_state.e3_observations
    st.markdown(f"### 📋 Recorded Longitudinal Visits ({len(visits)} Visits)")

    if not visits:
        st.info("No longitudinal observations currently in session. Use the controls above or select a preset in **Patient Clinical Diagnosis**.")
        return

    # Build display table with calculated eGFR
    table_rows = []
    age_eval = st.session_state.get("demo_age", 60.0)
    sex_eval = st.session_state.get("demo_sex", "male")

    for i, v in enumerate(visits):
        res_egfr = calculate_egfr_ckd_epi_2021(
            serum_creatinine=v.get("scr"),
            age=age_eval,
            sex=sex_eval,
        )
        egfr_val = res_egfr["egfr"]
        v["egfr"] = egfr_val
        table_rows.append({
            "Visit #": i + 1,
            "Date": str(v["date"]),
            "Creatinine (mg/dL)": v.get("scr"),
            "eGFR (mL/min/1.73m²)": f"{egfr_val:.1f}" if egfr_val else "N/A",
            "uACR (mg/g)": v.get("uacr") or "N/A",
            "Systolic BP (mmHg)": v.get("sbp") or "N/A",
        })

    tcol1, tcol2 = st.columns([3, 1])
    with tcol1:
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)
    with tcol2:
        if st.button("🗑️ Clear All Visits", use_container_width=True):
            st.session_state.e3_observations = []
            st.rerun()

    # 3. Landmark Filtering
    st.markdown("---")
    st.markdown("### ⏱️ Landmark Time-Cutoff & Anti-Leakage Gate")
    st.caption("Engine 3 enforces landmark cut-offs: observations after the landmark date are strictly quarantined from historical feature extraction.")

    min_date = visits[0]["date"]
    max_date = visits[-1]["date"]
    lm_date = st.date_input("Evaluation Landmark Cutoff Date", value=max_date, min_value=min_date, max_value=max_date + timedelta(days=365))

    # Convert to LongitudinalPatientRecord
    obs_objs = [
        ClinicalObservation(
            timestamp=datetime.combine(v["date"], datetime.min.time(), tzinfo=timezone.utc),
            serum_creatinine=v.get("scr"),
            egfr=v.get("egfr"),
            uacr=v.get("uacr"),
            systolic_bp=v.get("sbp"),
        )
        for v in visits
    ]
    pt_id = st.session_state.get("pt_id", "PT-LONGITUDINAL")
    rec = LongitudinalPatientRecord(
        patient_id=pt_id,
        age_baseline=age_eval,
        sex=sex_eval,
        observations=obs_objs,
        provenance="MANUAL_LONGITUDINAL_INPUT",
    )

    # 4. Trajectory Assessment
    lm_dt = datetime.combine(lm_date, datetime.min.time(), tzinfo=timezone.utc)
    with st.spinner("Calculating longitudinal progression trajectory..."):
        prog_res = prog_engine.assess_progression(record=rec, landmark_time=lm_dt)

    st.markdown("---")
    st.markdown("### 📊 Progression Trajectory Metrics")

    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        if prog_res.historical_egfr_slope is not None:
            st.metric("Historical OLS Slope", f"{prog_res.historical_egfr_slope:+.2f} mL/min/yr", prog_res.slope_status)
        else:
            st.info("OLS slope requires >= 2 visits spanning >= 90 days prior to landmark.")
    with mcol2:
        if prog_res.lmm_trajectory and prog_res.lmm_trajectory.is_eligible:
            st.metric("LMM BLUP Random Slope", f"{prog_res.lmm_trajectory.patient_slope:+.2f} mL/min/yr", f"SE: {prog_res.lmm_trajectory.slope_standard_error:.2f}")
        else:
            st.caption("LMM random slope requires >= 3 visits spanning >= 180 days.")
    with mcol3:
        if prog_res.kfre_result and prog_res.kfre_result.is_applicable:
            st.metric("KFRE 2-Yr Risk", f"{prog_res.kfre_result.risk_2year*100:.1f}%", f"5-Yr: {prog_res.kfre_result.risk_5year*100:.1f}%")
        else:
            st.caption("KFRE risk applies to CKD Stages G3-G5 (eGFR < 60 mL/min).")

    # 5. Interactive Timeline Visualization
    st.markdown("#### Interactive Longitudinal Trajectory Chart")
    t_fig = render_longitudinal_timeline(
        observations=visits,
        landmark_time=lm_dt,
        slope=prog_res.historical_egfr_slope,
        lmm_slope=prog_res.lmm_trajectory.patient_slope if prog_res.lmm_trajectory else None,
        figsize=(8.5, 5.0)
    )
    st.pyplot(t_fig)

    # Model Gating Notice
    st.markdown("""
    <div style="background-color: #f8fafc; border-left: 4px solid #64748b; padding: 0.6rem 0.9rem; border-radius: 4px; font-size: 0.85rem; color: #475569; margin-top: 1rem;">
        <b>⚠️ RESEARCH BOUNDARY:</b> Machine learning survival models (Cox PH and Random Survival Forests) are mathematically verified but remain explicitly gated (DEFERRED) pending CRIC cohort ingestion under an approved DUA.
    </div>
    """, unsafe_allow_html=True)
