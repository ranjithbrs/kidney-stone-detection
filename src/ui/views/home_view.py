"""Home / System Overview Landing View."""

from __future__ import annotations

import streamlit as st


def render_home_view() -> None:
    """Render the landing overview dashboard."""
    st.markdown("## 🏠 NEFROAI-X: Multimodal Renal Diagnostic & Progression Framework")
    st.markdown("""
    **NefroAI-X** is an investigational Clinical Decision Support System (CDSS) integrating three
    independently validated engines for non-invasive screening, clinical severity staging, and longitudinal
    progression risk prediction in Chronic Kidney Disease (CKD).
    """)

    # Three Engine Summary Cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid #0f4c81; border-radius: 8px; padding: 1rem; min-height: 250px;">
            <h4 style="color: #0f4c81; margin-top: 0;">🩺 Engine 1: Screening</h4>
            <p style="font-size: 0.88rem; color: #475569;">
                <b>Role:</b> Point-of-care risk triaging using 10 consensus routine hematological & urinalysis biomarkers.<br>
                <b>Model:</b> Champion Random Forest (Stratified 5-Fold Tuned).<br>
                <b>Dataset:</b> UCI Chronic Kidney Disease Cohort (N=400).<br>
                <b>Status:</b> <span style="color:#059669; font-weight:700;">ONLINE</span> (Calibrated Probability & Leverage Weights).
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid #059669; border-radius: 8px; padding: 1rem; min-height: 250px;">
            <h4 style="color: #059669; margin-top: 0;">🔬 Engine 2: KDIGO Staging</h4>
            <p style="font-size: 0.88rem; color: #475569;">
                <b>Role:</b> Quantitative KDIGO 2024 CGA severity staging and prognosis classification.<br>
                <b>Methodology:</b> Race-free CKD-EPI 2021 eGFR + continuous uACR categorization (A1-A3).<br>
                <b>Dataset:</b> NHANES 2017–2018 Population Cohort (N=9,254).<br>
                <b>Status:</b> <span style="color:#059669; font-weight:700;">ONLINE</span> (Certified Mathematical Guidelines).
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid #7c3aed; border-radius: 8px; padding: 1rem; min-height: 250px;">
            <h4 style="color: #7c3aed; margin-top: 0;">📈 Engine 3: Progression</h4>
            <p style="font-size: 0.88rem; color: #475569;">
                <b>Role:</b> Longitudinal trajectory estimation and 2-yr/5-yr Kidney Failure Risk (KFRE).<br>
                <b>Methodology:</b> OLS slope, LMM BLUP random slopes, Tangri 4-variable KFRE.<br>
                <b>Survival ML:</b> <span style="color:#64748b; font-weight:700;">DEFERRED (Pending CRIC DUA)</span>.<br>
                <b>Status:</b> <span style="color:#059669; font-weight:700;">ONLINE</span> (Trajectory & KFRE Reference).
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Architecture Overview Section
    st.subheader("System Architecture & Data Flow")
    st.markdown("""
    The framework processes patient measurements through an independent multi-engine pipeline with automated
    cross-engine discordance detection:
    """)

    st.code("""
    [Routine Urinalysis & Blood Labs] ──────► Engine 1 (Screening RF) ───────► Binary Risk & Triage Tier
    [Serum Creatinine + uACR Spot]   ──────► Engine 2 (KDIGO Staging) ──────► G1-G5 / A1-A3 CGA Matrix
    [Multi-Visit Historical Labs]    ──────► Engine 3 (Progression/KFRE) ───► eGFR Trajectory + KFRE 2y/5y
                                                        │
                                                        ▼
                                       [Cross-Engine Discrepancy Gate]
                                       • DISC-01: Screening Positive, No Staging
                                       • DISC-02: False Assurance Risk (CRITICAL)
                                       • DISC-03: Single Staging, Unproven Chronicity
                                       • DISC-04: Trajectory OK, Survival Deferred
                                       • DISC-05: KFRE Boundary Violation
                                       • DISC-06: Non-Concurrent Biomarkers (>30d)
                                       • DISC-07: Clinical History Conflict (HTN)
                                                        │
                                                        ▼
                                       [Unified Assessment Response]
                                       • Interactive Clinical Dashboard
                                       • Downloadable PDF / JSON / CSV Reports
    """, language="text")

    st.markdown("---")
    st.subheader("Dataset Provenance & Clinical Integrity Boundary")

    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown("""
        **Training & Validation Cohorts:**
        - **UCI Chronic Kidney Disease (Dataset A):** 400 clinical cases (250 CKD, 150 Normal) across 24 routine analytes. Protected baseline hash verified.
        - **NHANES 2017–2018 (Engine 2):** 9,254 unweighted population examination records with standardized laboratory harmonization.
        - **CRIC Longitudinal Cohort (Engine 3):** Access governed by NIDDK Central Repository DUA. Machine learning survival models remain explicitly deferred until cohort data is ingested under an approved agreement.
        """)

    with pcol2:
        st.markdown("""
        **Clinical Safety & Reliability Mandates:**
        - **Zero Silent Imputation:** Missing measurements are never substituted with healthy normal values (`sc=1.0`, `al=0`, `hemo=13.5`).
        - **Discordance Over Consensus:** Contradictions between binary screening and laboratory staging are prominently flagged.
        - **Cross-Sectional Caveat:** Single-timepoint staging is never presented as confirmed chronic kidney disease without proof of 90-day persistence.
        """)
