"""Patient clinical data input forms, preset management, and session handlers."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from src.clinical.assessment_contracts import (
    Demographics,
    Engine1ScreeningInput,
    Engine2SeverityInput,
    Engine3ProgressionInput,
    PatientAssessmentRequest,
    ProvenanceSource,
)
from src.clinical.kfre_calculator import KFRECalibrationProfile, KFREInput
from src.clinical.progression_features import ClinicalObservation, LongitudinalPatientRecord


def initialize_session_state() -> None:
    """Initialize clinical form defaults in session state if not present."""
    defaults = {
        "pt_id": "PT-CLINICAL-001",
        "demo_age": 60.0,
        "demo_sex": "male",
        # Engine 1 features
        "e1_hemo": 14.2,
        "e1_sg": 1.020,
        "e1_pcv": 42.0,
        "e1_sc": 1.1,
        "e1_rc": 4.8,
        "e1_al": 0,
        "e1_bu": 28.0,
        "e1_bgr": 105.0,
        "e1_htn": "no",
        "e1_dm": "no",
        # Engine 2 features
        "e2_scr": 1.1,
        "e2_scr_unit": "mg/dL",
        "e2_uacr": 25.0,
        "e2_uacr_unit": "mg/g",
        "e2_date_scr": date(2023, 6, 1),
        "e2_date_uacr": date(2023, 6, 1),
        # Engine 3 features
        "e3_kfre_calib": KFRECalibrationProfile.NON_NORTH_AMERICA.value,
        "e3_observations": [],
        # Engine execution toggles
        "run_e1": True,
        "run_e2": True,
        "run_e3": True,
        # Active result cache
        "latest_unified_response": None,
        "latest_patient_request": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def load_preset(preset_type: str) -> None:
    """Apply standard clinical preset values to the session state."""
    today = date(2023, 6, 1)
    st.session_state.is_synthetic_demonstration = True
    st.session_state.preset_label = preset_type

    if preset_type == "healthy":
        st.session_state.pt_id = "PT-HEALTHY-REF"
        st.session_state.demo_age = 42.0
        st.session_state.demo_sex = "male"
        st.session_state.e1_hemo = 15.2
        st.session_state.e1_sg = 1.025
        st.session_state.e1_pcv = 45.0
        st.session_state.e1_sc = 0.85
        st.session_state.e1_rc = 5.2
        st.session_state.e1_al = 0
        st.session_state.e1_bu = 22.0
        st.session_state.e1_bgr = 95.0
        st.session_state.e1_htn = "no"
        st.session_state.e1_dm = "no"
        st.session_state.e2_scr = 0.85
        st.session_state.e2_scr_unit = "mg/dL"
        st.session_state.e2_uacr = 12.0
        st.session_state.e2_uacr_unit = "mg/g"
        st.session_state.e2_date_scr = today
        st.session_state.e2_date_uacr = today
        st.session_state.e3_observations = [
            {"date": today - timedelta(days=360), "scr": 0.82, "uacr": 10.0, "sbp": 118.0},
            {"date": today - timedelta(days=180), "scr": 0.84, "uacr": 12.0, "sbp": 120.0},
            {"date": today, "scr": 0.85, "uacr": 12.0, "sbp": 118.0},
        ]

    elif preset_type == "high_risk_ckd":
        st.session_state.pt_id = "PT-HIGH-RISK-CKD"
        st.session_state.demo_age = 64.0
        st.session_state.demo_sex = "male"
        st.session_state.e1_hemo = 9.8
        st.session_state.e1_sg = 1.012
        st.session_state.e1_pcv = 30.0
        st.session_state.e1_sc = 2.4
        st.session_state.e1_rc = 3.3
        st.session_state.e1_al = 3
        st.session_state.e1_bu = 72.0
        st.session_state.e1_bgr = 185.0
        st.session_state.e1_htn = "yes"
        st.session_state.e1_dm = "yes"
        st.session_state.e2_scr = 2.4
        st.session_state.e2_scr_unit = "mg/dL"
        st.session_state.e2_uacr = 380.0
        st.session_state.e2_uacr_unit = "mg/g"
        st.session_state.e2_date_scr = today
        st.session_state.e2_date_uacr = today
        st.session_state.e3_observations = [
            {"date": today - timedelta(days=360), "scr": 1.9, "uacr": 220.0, "sbp": 142.0},
            {"date": today - timedelta(days=180), "scr": 2.1, "uacr": 310.0, "sbp": 148.0},
            {"date": today, "scr": 2.4, "uacr": 380.0, "sbp": 152.0},
        ]

    elif preset_type == "discordant_false_assurance":
        st.session_state.pt_id = "PT-DISCORDANT-001"
        st.session_state.demo_age = 48.0
        st.session_state.demo_sex = "female"
        # Normal blood counts / dipstick -> Engine 1 predicts Healthy
        st.session_state.e1_hemo = 14.5
        st.session_state.e1_sg = 1.020
        st.session_state.e1_pcv = 43.0
        st.session_state.e1_sc = 1.4
        st.session_state.e1_rc = 4.9
        st.session_state.e1_al = 0
        st.session_state.e1_bu = 24.0
        st.session_state.e1_bgr = 95.0
        st.session_state.e1_htn = "no"
        st.session_state.e1_dm = "no"
        # Objective labs show elevated creatinine and severe albuminuria -> Engine 2 shows G3b/A3
        st.session_state.e2_scr = 1.4
        st.session_state.e2_scr_unit = "mg/dL"
        st.session_state.e2_uacr = 420.0
        st.session_state.e2_uacr_unit = "mg/g"
        st.session_state.e2_date_scr = today
        st.session_state.e2_date_uacr = today
        st.session_state.e3_observations = []

    elif preset_type == "rapid_progressor":
        st.session_state.pt_id = "PT-RAPID-PROGRESSOR"
        st.session_state.demo_age = 68.0
        st.session_state.demo_sex = "female"
        st.session_state.e1_hemo = 10.5
        st.session_state.e1_sg = 1.015
        st.session_state.e1_pcv = 32.0
        st.session_state.e1_sc = 2.8
        st.session_state.e1_rc = 3.5
        st.session_state.e1_al = 2
        st.session_state.e1_bu = 68.0
        st.session_state.e1_bgr = 140.0
        st.session_state.e1_htn = "yes"
        st.session_state.e1_dm = "yes"
        st.session_state.e2_scr = 2.8
        st.session_state.e2_scr_unit = "mg/dL"
        st.session_state.e2_uacr = 280.0
        st.session_state.e2_uacr_unit = "mg/g"
        st.session_state.e2_date_scr = today
        st.session_state.e2_date_uacr = today
        # Longitudinal steep decline
        st.session_state.e3_observations = [
            {"date": today - timedelta(days=720), "scr": 1.2, "uacr": 90.0, "sbp": 136.0},
            {"date": today - timedelta(days=540), "scr": 1.5, "uacr": 140.0, "sbp": 140.0},
            {"date": today - timedelta(days=360), "scr": 1.9, "uacr": 210.0, "sbp": 145.0},
            {"date": today - timedelta(days=180), "scr": 2.3, "uacr": 240.0, "sbp": 150.0},
            {"date": today, "scr": 2.8, "uacr": 280.0, "sbp": 156.0},
        ]


def clear_session_state() -> None:
    """Clear patient record and evaluation cache from session state."""
    keys_to_clear = [
        "latest_unified_response", "latest_patient_request", "e3_observations"
    ]
    for k in keys_to_clear:
        if k in st.session_state:
            st.session_state[k] = None if k != "e3_observations" else []
    st.session_state.is_synthetic_demonstration = False
    st.session_state.preset_label = None


def render_preset_buttons() -> None:
    """Render clinical preset selector buttons."""
    st.markdown("#### ⚡ Clinical Demonstration Presets")
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 0.8])
    with col1:
        if st.button("🟢 Healthy Cohort", help="Loads normal screening biomarkers and baseline eGFR"):
            load_preset("healthy")
            st.rerun()
    with col2:
        if st.button("🔴 High-Risk CKD", help="Loads progressive diabetic nephropathy with severe proteinuria"):
            load_preset("high_risk_ckd")
            st.rerun()
    with col3:
        if st.button("⚠️ Discordant Case", help="Demonstrates False Assurance Risk (Engine 1 Healthy vs Engine 2 G3b/A3)"):
            load_preset("discordant_false_assurance")
            st.rerun()
    with col4:
        if st.button("📉 Rapid Progressor", help="Loads 5-visit 2-year longitudinal trajectory with steep eGFR decline"):
            load_preset("rapid_progressor")
            st.rerun()
    with col5:
        if st.button("🔄 Reset Data", help="Clears patient inputs and cached evaluation results"):
            clear_session_state()
            initialize_session_state()
            st.rerun()


def render_patient_input_form() -> Optional[PatientAssessmentRequest]:
    """Render the primary patient assessment form and construct PatientAssessmentRequest."""
    initialize_session_state()
    render_preset_buttons()

    # Synthetic Demonstration Safety Banner
    if st.session_state.get("is_synthetic_demonstration", False):
        st.warning(
            f"⚠️ **DEMONSTRATION RECORD ACTIVE (`{st.session_state.get('preset_label', 'preset')}`)**: "
            "This patient profile was loaded from an illustrative synthetic archetype for software testing and demonstration. "
            "It does NOT represent a real patient and must NOT be used for clinical decision-making or performance claims."
        )

    st.markdown("---")
    st.markdown("### 📋 Patient Demographics & Engine Selection")

    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        pt_id = st.text_input("Pseudonymous Patient ID", value=st.session_state.pt_id, help="De-identified patient reference; avoid patient PII.")
    with dcol2:
        age_val = st.number_input("Patient Age (Years)", min_value=18.0, max_value=115.0, value=float(st.session_state.demo_age), step=1.0)
    with dcol3:
        sex_idx = 0 if st.session_state.demo_sex == "male" else 1
        sex_val = st.selectbox("Biological Sex", ["male", "female"], index=sex_idx, help="Required for CKD-EPI 2021 equation and KFRE.")

    st.markdown("##### Target Clinical Engines to Execute:")
    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        run_e1 = st.checkbox("🩺 Engine 1: Screening & Binary Risk", value=st.session_state.run_e1)
    with tcol2:
        run_e2 = st.checkbox("🔬 Engine 2: KDIGO CGA Severity Staging", value=st.session_state.run_e2)
    with tcol3:
        run_e3 = st.checkbox("📈 Engine 3: Longitudinal Progression & KFRE", value=st.session_state.run_e3)

    # Sync back to session state
    st.session_state.pt_id = pt_id
    st.session_state.demo_age = age_val
    st.session_state.demo_sex = sex_val
    st.session_state.run_e1 = run_e1
    st.session_state.run_e2 = run_e2
    st.session_state.run_e3 = run_e3

    st.markdown("---")

    # Engine-specific tabbed input layout
    tab_e1, tab_e2, tab_e3 = st.tabs([
        "Engine 1: Screening Panel",
        "Engine 2: Staging Panel (Creatinine & uACR)",
        "Engine 3: Progression & KFRE Parameters"
    ])

    with tab_e1:
        st.markdown("##### 10 Consensus Renal Biomarkers (Huda et al. Hybrid Selection)")
        e1_c1, e1_c2 = st.columns(2)
        with e1_c1:
            hemo = st.number_input("Hemoglobin [g/dL] (hemo)", min_value=2.5, max_value=20.0, value=float(st.session_state.e1_hemo), step=0.1, help="Critical biomarker. Normal: 12.0 - 17.5 g/dL")
            sc_e1 = st.number_input("Serum Creatinine [mg/dL] (sc)", min_value=0.2, max_value=25.0, value=float(st.session_state.e1_sc), step=0.1, help="Critical biomarker. Normal: 0.6 - 1.2 mg/dL")
            al = st.selectbox("Urinary Albumin Dipstick [0-5] (al)", [0, 1, 2, 3, 4, 5], index=int(st.session_state.e1_al), help="Critical biomarker. 0 = Negative, 1-5 = Proteinuria grade")
            sg = st.selectbox("Urine Specific Gravity (sg)", [1.005, 1.010, 1.015, 1.020, 1.025], index=[1.005, 1.010, 1.015, 1.020, 1.025].index(st.session_state.e1_sg))
            pcv = st.number_input("Packed Cell Volume / Hct [%] (pcv)", min_value=10.0, max_value=60.0, value=float(st.session_state.e1_pcv), step=1.0)
        with e1_c2:
            rc = st.number_input("Red Blood Cell Count [M/mcL] (rc)", min_value=1.5, max_value=8.0, value=float(st.session_state.e1_rc), step=0.1)
            bu = st.number_input("Blood Urea [mg/dL] (bu)", min_value=5.0, max_value=350.0, value=float(st.session_state.e1_bu), step=1.0)
            bgr = st.number_input("Blood Glucose Random [mg/dL] (bgr)", min_value=40.0, max_value=500.0, value=float(st.session_state.e1_bgr), step=1.0)
            htn = st.selectbox("Hypertension History (htn)", ["no", "yes"], index=0 if st.session_state.e1_htn == "no" else 1)
            dm = st.selectbox("Diabetes Mellitus History (dm)", ["no", "yes"], index=0 if st.session_state.e1_dm == "no" else 1)

    with tab_e2:
        st.markdown("##### Quantitative Filtration & Albuminuria Staging Markers")
        e2_c1, e2_c2 = st.columns(2)
        with e2_c1:
            scr_val = st.number_input("Serum Creatinine (Staging)", min_value=0.1, max_value=30.0, value=float(st.session_state.e2_scr), step=0.1)
            scr_unit = st.selectbox("Creatinine Unit", ["mg/dL", "µmol/L"], index=0 if st.session_state.e2_scr_unit == "mg/dL" else 1)
            date_scr = st.date_input("Creatinine Observation Date", value=st.session_state.e2_date_scr)
        with e2_c2:
            uacr_val = st.number_input("Urine Albumin-to-Creatinine Ratio (uACR)", min_value=0.1, max_value=5000.0, value=float(st.session_state.e2_uacr), step=5.0)
            uacr_unit = st.selectbox("uACR Unit", ["mg/g", "mg/mmol"], index=0 if st.session_state.e2_uacr_unit == "mg/g" else 1)
            date_uacr = st.date_input("uACR Observation Date", value=st.session_state.e2_date_uacr)

    with tab_e3:
        st.markdown("##### Tangri 4-Variable KFRE Calibration & Multi-Visit Record")
        kfre_calib = st.selectbox(
            "KFRE Regional Calibration Profile",
            [KFRECalibrationProfile.NON_NORTH_AMERICA.value, KFRECalibrationProfile.NORTH_AMERICA.value, KFRECalibrationProfile.ORIGINAL_TANGRI.value],
            index=0,
            help="Default is non_north_america per KDIGO 2024 international guidance."
        )

        obs_count = len(st.session_state.e3_observations)
        if obs_count > 0:
            st.info(f"📊 **Longitudinal Observation History**: {obs_count} visits loaded. Visit details can be inspected and expanded in the **Longitudinal Kidney Assessment** tab.")
        else:
            st.caption("No multi-visit historical observations currently loaded. (A single-timepoint index KFRE risk will be estimated from current age, sex, eGFR, and uACR).")

    # Submission button
    st.markdown("---")
    submitted = st.button("🔬 Execute Clinical Assessment", type="primary", use_container_width=True)

    if submitted:
        prov = (
            ProvenanceSource.SYNTHETIC_DEMONSTRATION.value
            if st.session_state.get("is_synthetic_demonstration", False)
            else ProvenanceSource.MANUAL_ENTRY.value
        )

        # Build requested list
        req_engines = []
        if run_e1: req_engines.append("engine1")
        if run_e2: req_engines.append("engine2")
        if run_e3: req_engines.append("engine3")

        # Assemble Engine 1 input
        e1_input = Engine1ScreeningInput(
            biomarkers={
                "hemo": hemo, "sg": sg, "pcv": pcv, "sc": sc_e1, "rc": rc,
                "al": al, "bu": bu, "bgr": bgr, "htn": htn, "dm": dm,
                "age": age_val,
            },
            observation_date=datetime.combine(date_scr, datetime.min.time(), tzinfo=timezone.utc),
            provenance=prov,
        )

        # Assemble Engine 2 input
        e2_input = Engine2SeverityInput(
            serum_creatinine=scr_val,
            serum_creatinine_unit=scr_unit,
            uacr=uacr_val,
            uacr_unit=uacr_unit,
            age=age_val,
            sex=sex_val,
            observation_date_scr=datetime.combine(date_scr, datetime.min.time(), tzinfo=timezone.utc),
            observation_date_uacr=datetime.combine(date_uacr, datetime.min.time(), tzinfo=timezone.utc),
            provenance=prov,
        )

        # Assemble Engine 3 input
        e3_input = None
        if run_e3:
            obs_list = []
            for obs in st.session_state.e3_observations:
                obs_dt = obs["date"]
                if isinstance(obs_dt, date) and not isinstance(obs_dt, datetime):
                    obs_dt = datetime.combine(obs_dt, datetime.min.time(), tzinfo=timezone.utc)
                obs_list.append(ClinicalObservation(
                    timestamp=obs_dt,
                    serum_creatinine=obs.get("scr"),
                    uacr=obs.get("uacr"),
                    systolic_bp=obs.get("sbp"),
                ))

            rec = None
            if len(obs_list) > 0:
                rec = LongitudinalPatientRecord(
                    patient_id=pt_id,
                    age_baseline=age_val,
                    sex=sex_val,
                    observations=obs_list,
                    provenance=prov,
                )

            e3_input = Engine3ProgressionInput(
                longitudinal_record=rec,
                kfre_calibration=kfre_calib,
                provenance=prov,
            )

        request = PatientAssessmentRequest(
            patient_id=pt_id,
            assessment_timestamp=datetime.now(timezone.utc),
            demographics=Demographics(age=age_val, sex=sex_val),
            engine1_input=e1_input,
            engine2_input=e2_input,
            engine3_input=e3_input,
            requested_engines=req_engines,
            provenance=prov,
        )
        return request

    return None
