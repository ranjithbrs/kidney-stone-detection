"""Patient Assessment Interface View."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.clinical.batch_screening import (
    MAX_BATCH_FILE_BYTES,
    MAX_BATCH_ROWS,
    get_sample_batch_csv,
    run_batch_clinical_screening,
)
from src.clinical.patient_store import ClinicalHistoryStore
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


def _render_batch_screening_tab(engine: UnifiedAssessmentEngine) -> None:
    """Render the Batch CKD Screening CSV upload, strict schema guard, and export tab."""
    st.markdown("### 📁 Batch CKD Cohort Screening (CSV Upload)")
    st.markdown("""
    Upload a cohort CSV containing routine hematology and urinalysis panels to run vectorized
    Engine 1 screening with **strict schema validation** and **CD-CIRPVM conformal reliability gating**.
    Incompatible datasets (e.g., kidney stone urinalysis or unrelated schemas) are rejected immediately.
    """)

    st.caption(
        "Required critical columns: `sc`, `al`, `hemo`. Recommended Top-10 consensus columns: "
        "`hemo, sg, pcv, rc, al, htn, sc, bu, dm, bgr` (plus optional `patient_id`). "
        "Max file size: 5 MB | Max rows: 500."
    )

    st.download_button(
        label="📄 Download Sample Cohort CSV Template",
        data=get_sample_batch_csv(),
        file_name="nefroai_sample_batch_screening.csv",
        mime="text/csv",
        help="Downloads a 4-row synthetic non-PII template demonstrating standard, SI-unit, and missing-critical records.",
    )

    uploaded_csv = st.file_uploader(
        "Select Patient Screening CSV File",
        type=["csv"],
        key="batch_ckd_csv_uploader",
    )

    if uploaded_csv is None:
        st.info("ℹ️ Upload a `.csv` patient screening cohort above or download the sample template to test batch inference.")
        return

    if uploaded_csv.size > MAX_BATCH_FILE_BYTES:
        st.error(
            f"⛔ **Security Boundary Triggered**: File size ({uploaded_csv.size / 1024 / 1024:.2f} MB) "
            f"exceeds maximum upload limit of 5 MB."
        )
        return

    if not uploaded_csv.name.lower().endswith(".csv"):
        st.error("⛔ **Security Boundary Triggered**: Only `.csv` files are accepted.")
        return

    pipeline = engine.get_pipeline()
    if pipeline is None:
        st.error("❌ Production screening pipeline (`models/clinical_pipeline.joblib`) could not be loaded.")
        return

    try:
        df_upload = pd.read_csv(uploaded_csv, nrows=MAX_BATCH_ROWS + 1)
    except Exception as ex:
        st.error(f"❌ Failed to parse uploaded CSV: {ex}")
        return

    with st.spinner("Validating schema and executing batch clinical screening..."):
        summary = run_batch_clinical_screening(
            df=df_upload,
            pipeline=pipeline,
            reliability_mechanism=engine.reliability_mechanism,
            max_rows=MAX_BATCH_ROWS,
        )

    if not summary.schema_valid:
        st.error(f"⛔ **Incompatible or Invalid Dataset Rejected**\n\n{summary.schema_message}")
        return

    st.success(
        f"✅ **Batch Screening Complete**: Processed {summary.total_rows} patient record(s) "
        f"(Calibrated Conformal Quantile q̂₉₅ = {summary.conformal_quantile:.3f})."
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Total Screened", summary.total_rows)
    with k2:
        st.metric("Predictions Available", summary.predictions_available + summary.incomplete_estimates)
    with k3:
        st.metric("High / Critical Risk", summary.high_or_critical_risk)
    with k4:
        st.metric("Pipeline / Conformal Abstains", f"{summary.abstained_rows} / {summary.conformal_abstentions}")
    with k5:
        st.metric("Mean CRI Score", f"{summary.mean_cri:.2f}")

    st.dataframe(summary.results_df, use_container_width=True)

    if getattr(summary, "drift_report", None):
        raw_dr = summary.drift_report
        dr = raw_dr.to_dict() if hasattr(raw_dr, "to_dict") else dict(raw_dr)
        st.markdown("#### 📡 Training-Anchored Covariate-Shift & Mahalanobis OOD Monitor")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.metric("Cohort Drift Status", dr.get("overall_drift_status", "UNKNOWN"))
        with d2:
            st.metric("Max PSI Score", f"{dr.get('max_psi', 0.0):.3f}", f"{len(dr.get('drifted_features', []))} drifted")
        with d3:
            ood_cnt = int(dr.get("ood_row_count", 0))
            st.metric("Mahalanobis OOD Rows", f"{ood_cnt} / {summary.total_rows}", f"p99 > {dr.get('mahalanobis_threshold_p99', 0.0):.2f}")
        with d4:
            st.metric("Reference Baseline", f"N={dr.get('reference_train_samples', 320)}", "Train Partition Only")

        if dr.get("overall_drift_status") == "SEVERE_COVARIATE_SHIFT" or dr.get("ood_row_count", 0) > 0:
            st.warning(
                f"⚠️ **Covariate Distribution Alert**: Drifted biomarkers={dr.get('drifted_features', [])}. "
                f"Elevated Mahalanobis distance or PSI > 0.25 indicates target cohort shift relative to UCI training distribution."
            )
        details = dr.get("feature_drift_details") or []
        if details:
            with st.expander("🔍 Feature-Level PSI & Two-Sample KS Shift Breakdown"):
                st.dataframe(pd.DataFrame(details), use_container_width=True)

    st.download_button(
        label="📥 Download Sanitized Batch Results (.csv)",
        data=summary.to_sanitized_csv(),
        file_name="nefroai_batch_screening_results.csv",
        mime="text/csv",
        type="primary",
    )


def _persist_assessment_snapshot(response, req_obj) -> None:
    """Save an assessment response cleanly to the local ClinicalHistoryStore."""
    store = ClinicalHistoryStore()
    owner = st.session_state.get("auth_username") or "guest_researcher"
    obs_dt = None
    sbp_val = None
    if req_obj and getattr(req_obj, "engine1_input", None):
        obs_dt = getattr(req_obj.engine1_input, "observation_date", None)
    if req_obj and getattr(req_obj, "engine3_input", None) and getattr(req_obj.engine3_input, "longitudinal_record", None):
        obs_list = req_obj.engine3_input.longitudinal_record.observations
        if obs_list:
            sbp_val = obs_list[-1].systolic_bp
    store.save_assessment(
        response,
        owner_username=owner,
        observation_date=str(obs_dt)[:10] if obs_dt else None,
        systolic_bp=sbp_val,
    )
    st.session_state[f"saved_{response.assessment_id}"] = True


def render_assessment_view() -> None:
    """Render the interactive Patient Clinical Assessment interface."""
    st.markdown("## 🩺 Patient Clinical Diagnostic Assessment")
    st.markdown("""
    Evaluate individual patients across all three clinical engines or upload a cohort CSV for
    schema-validated batch screening with CD-CIRPVM conformal safety gating.
    """)

    engine = get_assessment_engine()

    tab_single, tab_batch = st.tabs([
        "👤 Single-Patient Clinical Assessment",
        "📁 Batch CKD Screening (CSV)",
    ])

    with tab_single:
        # Render inputs
        request = render_patient_input_form()

        # Process assessment if form submitted
        if request is not None:
            with st.spinner("Executing unified clinical assessment across requested engines..."):
                response = engine.assess_patient(request)
                st.session_state.latest_unified_response = response
                st.session_state.latest_patient_request = request
                if st.session_state.get("auth_username"):
                    try:
                        _persist_assessment_snapshot(response, request)
                    except Exception:
                        pass

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

            # Safety-Max Clinical Action Arbitration State Machine Banner
            arb_detail = comp.get("arbitration_detail") or {}
            if arb_detail:
                arb_tier = arb_detail.get("tier", "ROUTINE_MONITORING")
                arb_rank = int(arb_detail.get("urgency_rank", 1))
                arb_action = arb_detail.get("recommended_action", "")
                arb_rule = arb_detail.get("safety_rule_applied", "SAFETY_MAX")
                arb_reasons = "; ".join(arb_detail.get("trigger_reasons", []))
                banner_txt = (
                    f"**🛡️ Safety-Max Arbitration Priority (`{arb_tier}` | Rule: `{arb_rule}`)**  \n"
                    f"{arb_action}"
                    + (f"  \n*Triggers:* {arb_reasons}" if arb_reasons else "")
                )
                if arb_rank >= 4:
                    st.error(f"🚨 {banner_txt}")
                elif arb_rank == 3:
                    st.warning(f"⚠️ {banner_txt}")
                elif arb_rank == 2:
                    st.info(f"ℹ️ {banner_txt}")
                else:
                    st.success(f"✅ {banner_txt}")

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

            # Persistence & Audit Vault Save Action
            st.markdown("---")
            scol1, scol2 = st.columns([1.4, 2.6])
            with scol1:
                if st.button("💾 Save Assessment to Patient History Vault", key=f"save_vault_{response.assessment_id}"):
                    try:
                        _persist_assessment_snapshot(response, st.session_state.get("latest_patient_request"))
                    except Exception as exc:
                        st.error(f"Unable to save assessment: {exc}")
            with scol2:
                att_sha = (response.provenance or {}).get("attestation_sha256", "")
                if st.session_state.get(f"saved_{response.assessment_id}"):
                    st.success(f"✅ Saved to Local Patient History Vault (`runs/local_cdss.db`) | Attestation `{att_sha[:16]}...`")
                elif att_sha:
                    st.caption(f"🔐 Provenance SHA-256 Attestation: `{att_sha}`")

            # Quick link to report
            st.markdown("---")
            st.info("📄 **Report Ready**: A comprehensive medical summary report has been compiled for this assessment. Navigate to **📄 Clinical Assessment Report** in the sidebar to download as PDF, JSON, or CSV.")
        else:
            st.info("ℹ️ Enter patient laboratory data above and click **Execute Clinical Assessment** to run the evaluation.")

    with tab_batch:
        _render_batch_screening_tab(engine)
