"""Explainable AI (XAI) & Clinical Findings View."""

from __future__ import annotations

import os
import matplotlib.pyplot as plt
import streamlit as st

from src.clinical.xai_live import (
    compute_live_lime,
    compute_live_treeshap,
    compute_xai_concordance,
    generate_clinical_counterfactuals,
)
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.ui.components.visualizations import (
    render_feature_attributions_chart,
    render_live_treeshap_waterfall,
)


@st.cache_resource
def _get_explainability_engine() -> UnifiedAssessmentEngine:
    """Retrieve cached UnifiedAssessmentEngine to access the production pipeline."""
    return UnifiedAssessmentEngine()


def render_explainability_view() -> None:
    """Render the multi-level Explainability and Clinical Rationale interface."""
    st.markdown("## 🔍 Explainability & Clinical Findings (XAI)")
    st.markdown("""
    Deciphering the decision boundaries, physiological biomarkers, and algorithmic mechanisms
    powering the three clinical engines.
    """)

    # Scientific Caution Alert
    st.markdown("""
    <div style="background-color: #f1f5f9; border-left: 4px solid #0f4c81; padding: 0.6rem 0.9rem; border-radius: 4px; font-size: 0.85rem; color: #334155; margin-bottom: 1.25rem;">
        <b>⚠️ CLINICAL XAI INTERPRETATION NOTICE:</b> Algorithmic feature attributions (SHAP and leverage weights) indicate the relative statistical contribution of an analyte to the model's output prediction. They do NOT establish pathological etiology or clinical causality.
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📊 Global Biomarker Dynamics",
        "🎯 Local Patient Attributions",
        "🔬 Clinical Staging & KFRE Rationale"
    ])

    with tab1:
        st.subheader("Population-Level SHAP Interpretability (Dataset A)")
        st.markdown("""
        Evaluated across all 400 patient records using game-theoretic Shapley values (`shap.TreeExplainer`).
        - **Red dots**: High biomarker measurement in patient.
        - **Blue dots**: Low biomarker measurement in patient.
        - **Right of axis**: Pushes model probability towards Chronic Kidney Disease.
        """)

        beeswarm_img = "runs/explainability/plots/shap_summary_beeswarm.png"
        bar_img = "runs/explainability/plots/shap_importance_bar.png"

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if os.path.exists(beeswarm_img):
                st.image(beeswarm_img, caption="SHAP Summary Beeswarm Plot (UCI Cohort)", use_container_width=True)
            else:
                st.info("Beeswarm plot not generated.")
        with bcol2:
            if os.path.exists(bar_img):
                st.image(bar_img, caption="Mean Absolute Shapley Feature Importance", use_container_width=True)
            else:
                st.info("Feature importance bar plot not generated.")

    with tab2:
        st.subheader("Individual Patient Decision Attribution (Live TreeSHAP)")

        resp = st.session_state.get("latest_unified_response")
        req = st.session_state.get("latest_patient_request")

        if resp and resp.engine1_result:
            e1 = resp.engine1_result
            if e1.risk_probability is not None and e1.sanitized_inputs:
                pipeline_obj = _get_explainability_engine().get_pipeline()
                biomarker_payload = dict(e1.sanitized_inputs)
                if req is not None and getattr(req, "patient_id", None) == resp.patient_id:
                    e1_in = getattr(req, "engine1_input", None)
                    if e1_in is not None and hasattr(e1_in, "biomarkers") and e1_in.biomarkers:
                        biomarker_payload = dict(e1_in.biomarkers)

                shap_res = compute_live_treeshap(pipeline_obj, biomarker_payload) if pipeline_obj else None

                if shap_res is not None:
                    st.markdown(f"##### Active Patient (`{resp.patient_id}`) — Exact `shap.TreeExplainer` Attribution")
                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        st.metric("Base Expected Risk E[f(X)]", f"{shap_res.base_value * 100:.2f}%")
                    with sc2:
                        st.metric("Predicted CKD Risk f(x)", f"{shap_res.predicted_probability * 100:.2f}%")
                    with sc3:
                        st.metric("SHAP Additivity Residual", f"{shap_res.additivity_error:.2e}")

                    wf_fig = render_live_treeshap_waterfall(shap_res, patient_id=resp.patient_id)
                    st.pyplot(wf_fig)
                    plt.close(wf_fig)

                    st.markdown("###### Exact Game-Theoretic Shapley Values (φᵢ):")
                    shap_rows = [
                        {
                            "Biomarker": d["label"],
                            "Clinical Value": str(d["clinical_value"]),
                            "Shapley φᵢ": f"{d['shap_value']:+.4f}",
                            "Attribution Direction": d["direction"],
                            "Normalized Z-Score": f"{d['normalized_z']:+.2f}",
                        }
                        for d in shap_res.top_drivers
                    ]
                    st.dataframe(shap_rows, use_container_width=True)

                    # Live LIME Surrogate & Cross-XAI Concordance Audit (SHAP vs LIME vs KDIGO)
                    st.markdown("---")
                    st.markdown("##### ⚖️ Live LIME Surrogate & Cross-XAI Concordance Auditor")
                    uacr_ctx = getattr(resp.engine2_result, "uacr", None) if resp.engine2_result else None
                    lime_res = compute_live_lime(pipeline_obj, biomarker_payload)
                    conc_res = compute_xai_concordance(shap_res, lime_res, uacr_mg_g=uacr_ctx) if lime_res else None

                    if conc_res is not None:
                        cc1, cc2, cc3, cc4 = st.columns(4)
                        with cc1:
                            st.metric("Concordance Status", conc_res.concordance_status)
                        with cc2:
                            rho_str = f"{conc_res.spearman_rank_corr:+.3f}" if conc_res.spearman_rank_corr is not None else "N/A"
                            st.metric("Spearman Rank ρ", rho_str, "SHAP vs. LIME |φ|")
                        with cc3:
                            st.metric("Top-3 Driver Overlap", f"{conc_res.top3_overlap_count} / 3", f"SHAP: {', '.join(conc_res.top3_shap_features)}")
                        with cc4:
                            st.metric("Sign Agreement", f"{conc_res.sign_agreement_ratio * 100:.0f}%", conc_res.kdigo_marker_alignment)

                    if lime_res is not None:
                        with st.expander("📋 Live LIME Local Linear Surrogate Decision Rules"):
                            st.caption(
                                f"Surrogate intercept={lime_res.intercept:+.4f} | "
                                f"Target RF probability={lime_res.predicted_probability * 100:.1f}%"
                            )
                            st.dataframe(
                                [
                                    {
                                        "Local Discretized Rule": r["rule"],
                                        "LIME Linear Weight": f"{r['weight']:+.4f}",
                                        "Effect": "Increases CKD Risk" if r["weight"] > 0 else "Decreases CKD Risk",
                                    }
                                    for r in lime_res.rules
                                ],
                                use_container_width=True,
                            )

                    # Interactive Physiologically-Constrained Counterfactual Recourse Simulator
                    st.markdown("---")
                    st.markdown("##### 🧭 Physiologically-Constrained Counterfactual \"What-If\" Recourse Simulator")
                    st.caption(
                        "Explores minimal clinically plausible shifts within physiological bounds (excluding immutable "
                        "features `age`, `sex`, `htn`, `dm`) constrained by calibrated conformal risk sets."
                    )
                    cf_col1, cf_col2 = st.columns(2)
                    with cf_col1:
                        target_risk_pct = st.slider(
                            "Target Maximum CKD Risk (%)",
                            min_value=5,
                            max_value=45,
                            value=20,
                            step=5,
                            key="cf_target_risk_pct",
                        )
                    with cf_col2:
                        max_changes_val = st.selectbox(
                            "Maximum Concurrent Biomarker Shifts",
                            options=[1, 2, 3],
                            index=1,
                            key="cf_max_changes",
                        )

                    cf_res = generate_clinical_counterfactuals(
                        pipeline_obj,
                        biomarker_payload,
                        target_max_risk=float(target_risk_pct) / 100.0,
                        max_changes=int(max_changes_val),
                    )
                    if cf_res is not None:
                        mcf1, mcf2, mcf3 = st.columns(3)
                        with mcf1:
                            st.metric("Current Predicted Risk", f"{cf_res.initial_probability * 100:.1f}%", f"Conformal Set {cf_res.initial_conformal_set}")
                        with mcf2:
                            st.metric("Simulated Counterfactual Risk", f"{cf_res.target_probability * 100:.1f}%", f"Conformal Set {cf_res.target_conformal_set}")
                        with mcf3:
                            st.metric("Target Threshold Reached", "YES" if cf_res.target_achieved else "PARTIAL REDUCTION", f"Goal <= {target_risk_pct}%")

                        if cf_res.suggested_shifts:
                            st.dataframe(
                                [
                                    {
                                        "Modifiable Biomarker": s["label"],
                                        "Feature Key": s["feature"],
                                        "Current Value": str(s["current_value"]),
                                        "Target Simulated Value": str(s["target_value"]),
                                    }
                                    for s in cf_res.suggested_shifts
                                ],
                                use_container_width=True,
                            )
                        st.info(
                            f"ℹ️ **Recourse Simulation Note**: {cf_res.notes} "
                            f"(Immutable features locked: `{', '.join(cf_res.locked_immutable_features)}`). "
                            "*Counterfactual simulations illustrate model sensitivity boundaries, not therapeutic prescriptions.*"
                        )
                else:
                    st.info("Live TreeSHAP waterfall requires a tree-ensemble pipeline (`RandomForestClassifier`).")
            else:
                st.warning(
                    f"⚠️ Live TreeSHAP waterfall withheld for patient `{resp.patient_id}` "
                    f"(Engine 1 status: `{e1.status}`)."
                )

            if e1.feature_attributions:
                with st.expander("📊 Global Model Feature Importance (Random Forest Gini / MDI Heuristic)"):
                    st.caption(
                        "Note: Gini/MDI weights below measure global training-split impurity reduction across the Random Forest, "
                        "not patient-specific Shapley attributions."
                    )
                    f_chart = render_feature_attributions_chart(e1.feature_attributions)
                    st.pyplot(f_chart)
                    plt.close(f_chart)
        else:
            st.info("Run an assessment in **🩺 Patient Clinical Assessment** to generate a live TreeSHAP waterfall for a specific patient.")

        st.markdown("---")
        st.subheader("Baseline Benchmark Case Study (Patient #0)")
        p0_waterfall = "runs/explainability/plots/patient_0_shap_waterfall.png"
        p0_lime = "runs/explainability/plots/patient_0_lime_bar.png"

        lcol1, lcol2 = st.columns(2)
        with lcol1:
            if os.path.exists(p0_waterfall):
                st.image(p0_waterfall, caption="Patient #0 SHAP Waterfall Attribution", use_container_width=True)
        with lcol2:
            if os.path.exists(p0_lime):
                st.image(p0_lime, caption="Patient #0 Local LIME Surrogate Rule Breakdown", use_container_width=True)

    with tab3:
        st.subheader("Clinical Staging & KFRE Mathematical Terms")
        st.markdown("""
        **1. KDIGO CGA Staging Logic:**
        - **eGFR Calculation:** Race-free 2021 CKD-EPI equation using standardized serum creatinine.
        - **GFR Category:** Stratified into 6 prognostic tiers (G1 to G5).
        - **Albuminuria Category:** Stratified into 3 tiers based on continuous uACR (A1: <30, A2: 30-300, A3: >300 mg/g).
        - **Composite Risk:** Mapped to the KDIGO 4-tier matrix (Low, Moderately Increased, High, Very High).
        """)

        st.markdown("""
        **2. Tangri 4-Variable KFRE Linear Predictor Decomposition:**
        $$\\text{LP} = -0.2201 \\times (\\text{Age}/10 - 7.036) + 0.2467 \\times (\\text{Male} - 0.5642) - 0.5567 \\times (\\text{eGFR}/5 - 7.222) + 0.4510 \\times (\\ln(\\text{uACR}) - 5.137)$$
        
        - **Age Term:** Negative coefficient reflects competing mortality in older populations.
        - **Sex Term:** Male biological sex carries slightly higher progression hazard.
        - **eGFR Term:** Depleted baseline filtration exponentially accelerates kidney failure risk.
        - **uACR Term:** Logarithmic albuminuria drives glomerular barrier breakdown.
        """)
