"""Engine result display cards with color-coded triage, KDIGO matrices, and reliability gauges."""

from __future__ import annotations

import streamlit as st

from src.clinical.assessment_contracts import (
    Engine1Result,
    Engine2Result,
    Engine3Result,
    EngineStatus,
)


def render_engine1_card(e1: Optional[Engine1Result]) -> None:
    """Render structured evaluation card for Engine 1 (Screening & Binary Classification)."""
    st.markdown("### 🩺 Engine 1: Screening & Binary Risk (Random Forest)")

    if e1 is None:
        st.info("ℹ️ Engine 1 was not executed or not requested for this evaluation.")
        return

    # Check abstention or failure
    if e1.status in [EngineStatus.ABSTAINED.value, "ABSTAIN_MISSING_CRITICAL_FEATURES", "REJECTED_INVALID_SCHEMA", EngineStatus.EXECUTION_ERROR.value]:
        st.warning(f"⚠️ **Automated Screening Withheld ({e1.status})**\n\n{e1.abstention_reason or 'Critical biomarker safety requirement not met.'}")
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Consensus Panel Completeness", f"{e1.data_completeness_ratio * 100:.1f}%")
        with m2:
            st.metric("Missing Biomarkers", ", ".join(e1.missing_features) if e1.missing_features else "None")
        return

    # Valid prediction display
    prob_pct = (e1.risk_probability * 100) if e1.risk_probability is not None else 0.0
    conf_pct = (e1.confidence_score * 100) if e1.confidence_score is not None else 0.0

    rcol1, rcol2 = st.columns([1.4, 1.6])
    with rcol1:
        if e1.diagnostic_class == 1:
            st.markdown(f"""
            <div style="background-color: #fef2f2; border-left: 5px solid #ef4444; padding: 1rem; border-radius: 6px;">
                <h4 style="color: #b91c1c; margin-top: 0;">⚠️ {e1.diagnosis}</h4>
                <p style="font-size: 1.1rem; margin-bottom: 0.3rem;"><b>Predicted Risk:</b> {prob_pct:.1f}%</p>
                <p style="margin-bottom: 0.2rem;"><b>Triage Tier:</b> {e1.risk_category}</p>
                <p style="font-size: 0.85rem; color: #7f1d1d; margin: 0;">Consensus model indicates elevated screening risk. Comprehensive laboratory confirmation and clinical adjudication required.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #ecfdf5; border-left: 5px solid #10b981; padding: 1rem; border-radius: 6px;">
                <h4 style="color: #047857; margin-top: 0;">✅ {e1.diagnosis}</h4>
                <p style="font-size: 1.1rem; margin-bottom: 0.3rem;"><b>Predicted Risk:</b> {prob_pct:.1f}%</p>
                <p style="margin-bottom: 0.2rem;"><b>Triage Tier:</b> {e1.risk_category}</p>
                <p style="font-size: 0.85rem; color: #065f46; margin: 0;">Screening panel indicates low probability of CKD based on the evaluated biomarkers.</p>
            </div>
            """, unsafe_allow_html=True)

        st.progress(min(max(prob_pct / 100.0, 0.0), 1.0))

    with rcol2:
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Model Confidence", f"{conf_pct:.1f}%")
            st.metric("Consensus Completeness", f"{e1.data_completeness_ratio * 100:.1f}%")
        with m2:
            st.metric("Model Version", e1.model_version)
            st.metric("Full Panel Completeness", f"{e1.full_panel_completeness_ratio * 100:.1f}%")

        if e1.imputed_features:
            st.caption(f"ℹ️ Non-critical features estimated via training medians: `{e1.imputed_features}`")


def render_engine2_card(e2: Optional[Engine2Result]) -> None:
    """Render structured evaluation card for Engine 2 (KDIGO CGA Severity Staging)."""
    st.markdown("### 🔬 Engine 2: KDIGO CGA Severity Staging (2024 Framework)")

    if e2 is None:
        st.info("ℹ️ Engine 2 was not executed or not requested for this evaluation.")
        return

    if e2.status == EngineStatus.EXECUTION_ERROR.value:
        st.error(f"❌ Engine 2 encountered an execution error. Check input formats.")
        return

    # Metrics row
    c1, c2, c3 = st.columns(3)
    with c1:
        egfr_display = f"{e2.egfr:.1f} mL/min/1.73m²" if e2.egfr is not None else "N/A"
        st.metric("Filtration Rate (eGFR)", egfr_display, f"{e2.gfr_category or 'Unclassified'}: {e2.gfr_description or ''}")
        st.caption("Equation: CKD-EPI 2021 (Race-Free Creatinine)")

    with c2:
        uacr_display = f"{e2.uacr:.1f} mg/g" if e2.uacr is not None else "N/A"
        st.metric("Albuminuria (uACR)", uacr_display, f"{e2.albuminuria_category or 'Unclassified'}: {e2.albuminuria_description or ''}")
        st.caption("Standard Thresholds: A1 (<30), A2 (30-300), A3 (>300)")

    with c3:
        st.metric("KDIGO CGA Stage", e2.cga_string or "Incomplete", e2.composite_risk_level or "Unclassified")
        tier_color = e2.risk_color or "#64748b"
        st.markdown(f"""
        <div style="background-color: {tier_color}20; border-left: 4px solid {tier_color}; padding: 0.35rem 0.6rem; border-radius: 4px; font-weight: 700; color: {tier_color}; font-size: 0.85rem;">
            Risk Tier: {e2.risk_tier or 'Unclassified'}
        </div>
        """, unsafe_allow_html=True)

    # Clinical Governance Notice
    st.markdown("""
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.84rem; color: #475569; margin-top: 0.75rem;">
        <b>⚠️ KDIGO CHRONICITY REQUIREMENT:</b> Diagnosis of Chronic Kidney Disease requires persistence of abnormalities (>3 months). Cross-sectional single-timepoint staging cannot exclude resolving Acute Kidney Injury (AKI) or transient functional proteinuria.
    </div>
    """, unsafe_allow_html=True)


def render_engine3_card(e3: Optional[Engine3Result]) -> None:
    """Render structured evaluation card for Engine 3 (Progression, LMM, and KFRE)."""
    st.markdown("### 📈 Engine 3: Longitudinal Progression & KFRE Risk")

    if e3 is None:
        st.info("ℹ️ Engine 3 was not executed or not requested for this evaluation.")
        return

    if e3.status == EngineStatus.EXECUTION_ERROR.value:
        st.error(f"❌ Engine 3 encountered an execution error. Check visit records.")
        return

    # Two columns: Trajectory and KFRE
    col_traj, col_kfre = st.columns(2)

    with col_traj:
        st.markdown("#### eGFR Filtration Trajectory")
        if e3.historical_egfr_slope is not None:
            st.metric(
                "Descriptive OLS Slope",
                f"{e3.historical_egfr_slope:+.2f} mL/min/1.73m²/yr",
                e3.slope_status
            )
        else:
            st.info("Descriptive OLS slope requires >= 2 valid visits spanning >= 90 days.")

        if e3.lmm_annual_slope is not None:
            ci_str = f"95% CI: [{e3.lmm_slope_ci_lower:+.2f}, {e3.lmm_slope_ci_upper:+.2f}]" if e3.lmm_slope_ci_lower is not None else ""
            st.metric(
                "LMM BLUP Random Slope",
                f"{e3.lmm_annual_slope:+.2f} mL/min/1.73m²/yr",
                ci_str
            )
            st.caption(f"Status: {e3.lmm_status}")
        else:
            st.caption("Population LMM random slope requires >= 3 visits spanning >= 180 days.")

    with col_kfre:
        st.markdown("#### Tangri 4-Variable KFRE Reference Risks")
        if e3.kfre_2year_risk is not None:
            kc1, kc2 = st.columns(2)
            with kc1:
                st.metric("2-Year Kidney Failure Risk", f"{e3.kfre_2year_risk * 100:.1f}%")
            with kc2:
                st.metric("5-Year Kidney Failure Risk", f"{e3.kfre_5year_risk * 100:.1f}%")
            st.caption(f"Calibration Profile: `{e3.kfre_calibration_profile}` (Applicable: {e3.kfre_is_applicable})")
        else:
            if not e3.kfre_is_applicable and e3.kfre_applicability_explanation:
                st.warning(f"⚠️ **KFRE Risk Withheld**: {e3.kfre_applicability_explanation}")
            else:
                st.info("KFRE calculation requires age, sex, eGFR, and uACR.")

    st.markdown("---")
    # Machine Learning Survival Models Gating Notice
    st.markdown("""
    <div style="background-color: #f1f5f9; border-left: 4px solid #64748b; padding: 0.6rem 0.9rem; border-radius: 4px; font-size: 0.85rem; color: #334155;">
        <b>🔬 SURVIVAL MODEL INFERENCE:</b> <span style="background-color: #e2e8f0; padding: 0.15rem 0.4rem; border-radius: 3px; font-weight: 700;">DEFERRED — APPROVED LONGITUDINAL COHORT REQUIRED</span><br>
        Machine learning survival models (Semi-parametric Cox Proportional Hazards and Random Survival Forests) are mathematically verified but withheld for clinical patient predictions pending formal CRIC cohort ingestion under an approved NIDDK Data Use Agreement. Synthetic simulator fixtures are never used for clinical inference.
    </div>
    """, unsafe_allow_html=True)
