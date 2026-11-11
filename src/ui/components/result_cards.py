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
    if e1.status in [EngineStatus.ABSTAINED.value, "ABSTAIN_MISSING_CRITICAL_FEATURES", "REJECTED_INVALID_SCHEMA", "ABSTAIN_INVALID_INPUT_MEASUREMENT", "ABSTAIN_OUT_OF_DOMAIN_MEASUREMENT", EngineStatus.EXECUTION_ERROR.value]:
        st.warning(f"⚠️ **Automated Screening Withheld ({e1.status})**\n\n{e1.abstention_reason or 'Critical biomarker safety requirement not met.'}")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Consensus Panel Completeness", f"{e1.data_completeness_ratio * 100:.1f}%")
        with m2:
            st.metric("Missing Biomarkers", ", ".join(e1.missing_features) if e1.missing_features else "None")
        with m3:
            cri_txt = f"{e1.clinical_reliability_index:.2f}" if e1.clinical_reliability_index is not None else "N/A"
            st.metric("Clinical Reliability Index (CRI)", cri_txt)
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

    # CD-CIRPVM Reliability & Conformal Prediction Gate Panel
    if e1.clinical_reliability_index is not None or e1.conformal_gate_decision is not None:
        st.markdown("---")
        st.markdown("#### 🛡️ CD-CIRPVM Conformal Reliability & Safety Gate")
        gcol1, gcol2, gcol3 = st.columns(3)

        cri_val = e1.clinical_reliability_index if e1.clinical_reliability_index is not None else 0.0
        cov_pct = int(round((e1.conformal_coverage_target or 0.95) * 100))
        class_labels = {0: "Healthy (0)", 1: "CKD (1)"}
        cset_str = (
            "{" + ", ".join(class_labels.get(c, str(c)) for c in e1.conformal_set) + "}"
            if e1.conformal_set is not None
            else "N/A"
        )

        with gcol1:
            st.metric(
                "Clinical Reliability Index (CRI)",
                f"{cri_val:.2f} / 1.00",
                "Above 0.60 threshold" if cri_val >= 0.60 else "Below 0.60 threshold",
            )
            st.progress(min(max(cri_val, 0.0), 1.0))

        with gcol2:
            q_str = f"q̂={e1.conformal_quantile:.3f}" if e1.conformal_quantile is not None else "Calibrated"
            st.metric(f"Conformal Prediction Set ({cov_pct}%)", cset_str, q_str)

        with gcol3:
            gate_dec = e1.conformal_gate_decision or "N/A"
            gate_stat = e1.conformal_gate_status or ""
            st.metric("CD-CIRPVM Gate Decision", gate_dec, gate_stat)

        if e1.conformal_gate_decision == "ABSTAIN":
            st.warning(
                f"⚠️ **CD-CIRPVM Advises Human Review (`{e1.conformal_gate_status}`)**: "
                f"Conformal prediction set `{cset_str}` indicates boundary uncertainty or low data reliability "
                f"(CRI={cri_val:.2f}). Confirm laboratory measurements and obtain physician adjudication."
            )
        elif e1.conformal_calibration_method:
            st.caption(
                f"Dynamic conformal calibration: `{e1.conformal_calibration_method}` "
                f"(q̂ = {e1.conformal_quantile:.3f}, target coverage {cov_pct}%, fitted strictly on training partition)."
            )

        if e1.unit_reconciliation_audit or e1.bounds_clamping_audit:
            with st.expander("🔍 Unit Reconciliation (MIDR) & Physiological Bounds Audit"):
                if e1.unit_reconciliation_audit:
                    st.markdown("**Detected Non-Standard / SI Unit Conversions:**")
                    st.json(e1.unit_reconciliation_audit)
                if e1.bounds_clamping_audit:
                    st.markdown("**Reliability & Bounds Notes:**")
                    st.json(e1.bounds_clamping_audit)

    # 4-Family Stacking Ensemble Disagreement & Mondrian Class-Conditional Conformal Set
    if e1.stacking_probability is not None or e1.mondrian_conformal_set is not None:
        st.markdown("#### 🤝 Multi-Architecture Consensus & Class-Conditional Conformal Set")
        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            if e1.stacking_probability is not None:
                st.metric(
                    "4-Family Stacking Ensemble Risk",
                    f"{e1.stacking_probability * 100:.1f}%",
                    "LR Meta-Learner (RF + XGB + SVM + MLP)",
                )
            else:
                st.metric("4-Family Stacking Ensemble Risk", "N/A")
        with mcol2:
            if e1.ensemble_disagreement_spread is not None:
                dis_label = "Cross-Model Divergence" if e1.has_architecture_disagreement else "Architectures Aligned"
                st.metric(
                    "Cross-Architecture Spread",
                    f"{e1.ensemble_disagreement_spread * 100:.1f}%",
                    dis_label,
                )
            else:
                st.metric("Cross-Architecture Spread", "N/A")
        with mcol3:
            if e1.mondrian_conformal_set is not None:
                m_labels = {0: "Healthy", 1: "CKD"}
                m_str = "{" + ", ".join(m_labels.get(c, str(c)) for c in e1.mondrian_conformal_set) + "}" if e1.mondrian_conformal_set else "{Empty}"
                mq = e1.mondrian_quantiles or {}
                mq_str = (
                    f"q₀={mq.get('q_healthy', 0.0):.2f} | q₁={mq.get('q_ckd', 0.0):.2f}"
                    if mq
                    else "Class-Conditional"
                )
                st.metric("Mondrian Conformal Set (95%)", m_str, mq_str)
            else:
                st.metric("Mondrian Conformal Set (95%)", "N/A")

        if e1.has_architecture_disagreement:
            st.warning(
                f"⚠️ **Architecture Disagreement Gate Triggered**: Base learners (RF, XGBoost, SVM-RBF, MLP) "
                f"exhibit a spread of {e1.ensemble_disagreement_spread * 100:.1f}% or split classification votes. "
                f"Review cross-family probabilities below."
            )
        if e1.stacking_base_probabilities:
            with st.expander("📐 Base Learner Risk Probabilities (RF / XGBoost / SVM-RBF / MLP)"):
                st.json({k: round(float(v), 4) for k, v in e1.stacking_base_probabilities.items()})

    # Cross-Analyte Physiological & Stoichiometric Coherence Verifier
    if e1.coherence_audit:
        st.markdown("#### 🧪 Cross-Analyte Physiological Coherence Audit (`COH-01`–`04`)")
        coh = e1.coherence_audit
        if coh.get("is_coherent", True):
            st.success(
                f"✅ **Analytes Physiologically Coherent** (Coherence Score: `{coh.get('coherence_score', 1.0):.2f}` | "
                f"{coh.get('checks_evaluated', 0)} invariant checks passed)."
            )
        else:
            st.error(
                f"⛔ **Cross-Analyte Coherence Contradiction Detected** "
                f"(Score: `{coh.get('coherence_score', 0.0):.2f}` | CRI Penalty: `-{coh.get('total_cri_penalty', 0.0):.2f}`)"
            )
            for finding in coh.get("findings", []):
                st.markdown(
                    f"- **`{finding.get('check_id')}` — {finding.get('title')}** (`{finding.get('severity')}`): "
                    f"{finding.get('observed_detail')} *(Expected: {finding.get('expected_invariant')})*  \n"
                    f"  *Action:* {finding.get('clinical_action')}"
                )


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

    # AKI-vs-CKD Velocity Disambiguation & Expanding-Window Trajectory Backtest
    if e3.chronicity_aki_assessment or e3.trajectory_backtest:
        st.markdown("---")
        col_aki, col_bt = st.columns(2)
        with col_aki:
            st.markdown("#### ⚡ Chronicity vs. Acute Velocity (AKI Guard)")
            aki = e3.chronicity_aki_assessment or {}
            aki_status = aki.get("status", "UNKNOWN")
            if aki.get("acute_spike_detected"):
                st.error(f"🚨 **`{aki_status}`** — {aki.get('summary', '')}")
            elif aki.get("chronic_persistence_confirmed"):
                st.success(f"✅ **`{aki_status}`** — {aki.get('summary', '')}")
            else:
                st.info(f"ℹ️ **`{aki_status}`** — {aki.get('summary', '')}")
        with col_bt:
            st.markdown("#### 📉 Expanding-Window eGFR Trajectory Backtest")
            bt = e3.trajectory_backtest or {}
            if bt.get("eligible"):
                b1, b2, b3 = st.columns(3)
                with b1:
                    st.metric("Walk-Forward MAE", f"{bt.get('mae', 0.0):.2f}")
                with b2:
                    st.metric("Walk-Forward RMSE", f"{bt.get('rmse', 0.0):.2f}")
                with b3:
                    r2_val = bt.get("r2")
                    st.metric("Out-of-Time R²", f"{r2_val:.3f}" if r2_val is not None else "N/A")
                st.caption(f"Evaluated across {bt.get('evaluated_steps', 0)} historical walk-forward step(s).")
            else:
                st.caption(bt.get("reason", "Requires >= 3 dated eGFR observations for walk-forward backtest."))

    st.markdown("---")
    # Machine Learning Survival Models Gating Notice
    st.markdown("""
    <div style="background-color: #f1f5f9; border-left: 4px solid #64748b; padding: 0.6rem 0.9rem; border-radius: 4px; font-size: 0.85rem; color: #334155;">
        <b>🔬 SURVIVAL MODEL INFERENCE:</b> <span style="background-color: #e2e8f0; padding: 0.15rem 0.4rem; border-radius: 3px; font-weight: 700;">DEFERRED — APPROVED LONGITUDINAL COHORT REQUIRED</span><br>
        Machine learning survival models (Semi-parametric Cox Proportional Hazards and Random Survival Forests) are mathematically verified but withheld for clinical patient predictions pending formal CRIC cohort ingestion under an approved NIDDK Data Use Agreement. Synthetic simulator fixtures are never used for clinical inference.
    </div>
    """, unsafe_allow_html=True)
