"""Patient Assessment Interface View."""

from __future__ import annotations

import streamlit as st

from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.ui.components.discrepancies import render_discrepancies
from src.ui.components.input_forms import render_patient_input_form
from src.ui.components.result_cards import (
    render_engine1_card,
    render_engine2_card,
    render_engine3_card,
)
from src.ui.components.visualizations import render_kdigo_matrix


@st.cache_resource
def get_assessment_engine() -> UnifiedAssessmentEngine:
    """Retrieve or initialize the cached UnifiedAssessmentEngine."""
    return UnifiedAssessmentEngine()


def render_assessment_view() -> None:
    """Render the interactive Patient Clinical Assessment interface."""
    st.markdown("## 🩺 Patient Clinical Diagnostic Assessment")
    st.markdown("""
    Enter patient clinical parameters or select a clinical preset below to execute available engines
    and generate a coordinated diagnostic assessment.
    """)

    engine = get_assessment_engine()

    # Render inputs
    request = render_patient_input_form()

    # Process assessment if form submitted
    if request is not None:
        with st.spinner("Executing unified clinical assessment across requested engines..."):
            response = engine.assess_patient(request)
            st.session_state.latest_unified_response = response
            st.session_state.latest_patient_request = request

    # Display active assessment results if available
    response = st.session_state.get("latest_unified_response")
    if response is not None:
        st.markdown("---")
        st.markdown(f"### 📊 Coordinated Clinical Assessment Results (ID: `{response.assessment_id}`)")

        # Demonstration Data Safety Warning
        if response.provenance.get("source") == "SYNTHETIC_DEMONSTRATION" or st.session_state.get("is_synthetic_demonstration", False):
            st.warning(
                "⚠️ **DEMONSTRATION RECORD WARNING**: This assessment was evaluated on an illustrative synthetic preset. "
                "The generated predictions and risk probabilities must NOT be cited as clinical performance evidence or used for diagnostic decisions."
            )

        # Overall Completeness and Status Banner
        comp = response.overall_completeness
        c_status = comp.get("status", "PARTIAL")
        has_crit = comp.get("has_critical_discrepancies", False)

        bcol1, bcol2, bcol3 = st.columns([1.5, 1, 1])
        with bcol1:
            st.metric("Engines Executed", f"{len(response.engines_executed)} of 3 Engines", f"Completeness: {comp.get('completeness_ratio', 0.0)*100:.0f}%")
        with bcol2:
            st.metric("Assessment Status", c_status)
        with bcol3:
            st.metric("Critical Discrepancies", "YES" if has_crit else "None", delta_color="inverse" if has_crit else "normal")

        # Cross-Engine Discrepancy Alerts
        render_discrepancies(response.clinical_discrepancies)

        # Tabbed Engine Results
        st.markdown("---")
        res_tab1, res_tab2, res_tab3 = st.tabs([
            "🩺 Engine 1: Screening Risk",
            "🔬 Engine 2: KDIGO Staging & Matrix",
            "📈 Engine 3: Progression & KFRE"
        ])

        with res_tab1:
            render_engine1_card(response.engine1_result)

        with res_tab2:
            render_engine2_card(response.engine2_result)
            if response.engine2_result and response.engine2_result.gfr_category:
                st.markdown("#### KDIGO Prognosis Heatmap")
                fig = render_kdigo_matrix(
                    gfr_cat=response.engine2_result.gfr_category,
                    alb_cat=response.engine2_result.albuminuria_category,
                )
                st.pyplot(fig)

        with res_tab3:
            render_engine3_card(response.engine3_result)

        # Quick link to report
        st.markdown("---")
        st.info("📄 **Report Ready**: A comprehensive medical summary report has been compiled for this assessment. Navigate to **📄 Assessment Report** in the sidebar to download as PDF, JSON, or CSV.")
    else:
        st.info("ℹ️ Enter patient laboratory data above and click **Execute Clinical Assessment** to run the evaluation.")
