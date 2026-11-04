"""Explainable AI (XAI) & Clinical Findings View."""

from __future__ import annotations

import os
import streamlit as st

from src.ui.components.visualizations import render_feature_attributions_chart


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
        st.subheader("Individual Patient Decision Attribution")

        resp = st.session_state.get("latest_unified_response")
        if resp and resp.engine1_result and resp.engine1_result.feature_attributions:
            st.markdown(f"##### Active Patient (`{resp.patient_id}`) Biomarker Leverage Weights")
            f_chart = render_feature_attributions_chart(resp.engine1_result.feature_attributions)
            st.pyplot(f_chart)

            st.markdown("###### Detailed Feature Attribution Table:")
            attrib_data = [
                {"Biomarker": k, "Leverage Weight": f"{v.get('importance_weight', 0.0):.4f}", "Normalized Z-Score": f"{v.get('normalized_value', 0.0):+.2f}"}
                for k, v in resp.engine1_result.feature_attributions.items()
            ]
            st.dataframe(attrib_data, use_container_width=True)
        else:
            st.info("Run an assessment in **Patient Clinical Diagnosis** to view dynamic feature leverage weights for a specific patient.")

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
