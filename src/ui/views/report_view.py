"""Assessment Report Preview & Export View."""

from __future__ import annotations

from datetime import datetime
import streamlit as st

from src.ui.components.report_export import (
    generate_csv_export,
    generate_json_export,
    generate_pdf_report,
    generate_text_report,
)


def render_report_view() -> None:
    """Render the clinical report preview and multi-format export interface."""
    st.markdown("## 📄 Clinical Assessment Report Generator")
    st.markdown("""
    Generate, preview, and download formal timestamped clinical evaluation reports
    in PDF, JSON, CSV, and text formats.
    """)

    resp = st.session_state.get("latest_unified_response")
    visits = st.session_state.get("e3_observations", [])

    if resp is None:
        st.info("ℹ️ No patient assessment has been executed in the current session. Go to **🩺 Patient Clinical Diagnosis**, enter values or select a preset, and execute an assessment.")
        return

    st.success(f"✅ Assessment found for patient `{resp.patient_id}` (ID: `{resp.assessment_id}`).")

    # Synthetic Demonstration Warning Banner
    if resp.provenance.get("source") == "SYNTHETIC_DEMONSTRATION" or st.session_state.get("is_synthetic_demonstration", False):
        st.warning(
            "⚠️ **SYNTHETIC DEMONSTRATION NOTICE**: This report documents an illustrative demonstration preset. "
            "It does NOT represent a real patient and must NOT be filed in an actual medical record."
        )

    # Generate Exports
    txt_content = generate_text_report(resp)
    json_content = generate_json_export(resp)
    csv_content = generate_csv_export(resp)
    pdf_bytes = generate_pdf_report(resp, observations=visits)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"nefroai_assessment_{resp.patient_id}_{timestamp_str}"

    # Download Buttons Grid
    st.markdown("### 💾 Export Assessment Report")
    dcol1, dcol2, dcol3, dcol4 = st.columns(4)

    with dcol1:
        st.download_button(
            label="📑 Download PDF Report",
            data=pdf_bytes,
            file_name=f"{base_filename}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )

    with dcol2:
        st.download_button(
            label="📦 Download JSON Data",
            data=json_content,
            file_name=f"{base_filename}.json",
            mime="application/json",
            use_container_width=True,
        )

    with dcol3:
        st.download_button(
            label="📊 Download CSV Table",
            data=csv_content,
            file_name=f"{base_filename}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with dcol4:
        st.download_button(
            label="📝 Download Text Report",
            data=txt_content,
            file_name=f"{base_filename}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("### 📋 Formatted Medical Report Preview")
    st.code(txt_content, language="text")
