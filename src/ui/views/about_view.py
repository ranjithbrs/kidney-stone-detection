"""About, Methodology, and Regulatory Limitations View."""

from __future__ import annotations

import streamlit as st


def render_about_view() -> None:
    """Render the About, Mathematical Methodology, and Regulatory Limitations interface."""
    st.markdown("## 📖 About NEFROAI-X: Methodology & Clinical Governance")

    st.markdown("""
    **NefroAI-X** is an investigational Clinical Decision Support System (CDSS) developed to replicate and
    enhance non-invasive screening, risk stratification, and progression modeling for Chronic Kidney Disease (CKD).
    """)

    # Three Core Pillars
    st.markdown("### 🔬 Mathematical Frameworks")

    with st.expander("1. Race-Free 2021 CKD-EPI Creatinine Equation", expanded=True):
        st.markdown("""
        Estimates Glomerular Filtration Rate (eGFR) per 2021 race-neutral clinical consensus (Inker et al., *NEJM* 2021):
        $$\\text{eGFR} = 142 \\times \\min\\left(\\frac{\\text{S}_{\\text{cr}}}{\\kappa}, 1\\right)^\\alpha \\times \\max\\left(\\frac{\\text{S}_{\\text{cr}}}{\\kappa}, 1\\right)^{-1.200} \\times 0.9938^{\\text{Age}} \\times [1.012 \\text{ if female}]$$
        - **Female:** $\\kappa = 0.7$, $\\alpha = -0.241$
        - **Male:** $\\kappa = 0.9$, $\\alpha = -0.302$
        - Replaces older equations with racial coefficients, ensuring unbiased physiological evaluation.
        """)

    with st.expander("2. KDIGO 2024 CGA Severity Staging Matrix", expanded=True):
        st.markdown("""
        Categorizes kidney disease using three independent diagnostic axes:
        - **C (Cause):** Etiological classification (e.g. Diabetic Nephropathy, Glomerulonephritis, Hypertensive Nephrosclerosis).
        - **G (GFR Category):** G1 ($\\ge 90$), G2 ($60-89$), G3a ($45-59$), G3b ($30-44$), G4 ($15-29$), G5 ($<15$ mL/min/1.73m²).
        - **A (Albuminuria Category):** A1 ($<30$), A2 ($30-300$), A3 ($>300$ mg/g uACR).
        - **Composite Risk Matrix:** 4-tier risk stratification (Low, Moderately Increased, High, Very High) determining recommended clinical monitoring intervals.
        """)

    with st.expander("3. Tangri 4-Variable Kidney Failure Risk Equation (KFRE)", expanded=True):
        st.markdown("""
        Estimates the 2-year and 5-year statistical risk of requiring Kidney Replacement Therapy (KRT / dialysis / transplant) per Tangri et al. (*JAMA* 2016):
        $$\\text{Risk}(t) = 1 - S_0(t)^{\\exp(\\text{LP})}$$
        $$\\text{LP} = -0.2201 \\times (\\text{Age}/10 - 7.036) + 0.2467 \\times (\\text{Male} - 0.5642) - 0.5567 \\times (\\text{eGFR}/5 - 7.222) + 0.4510 \\times (\\ln(\\text{uACR}) - 5.137)$$
        - Calibrated for non-North American cohorts ($S_0(2\\text{y}) = 0.9832, S_0(5\\text{y}) = 0.9365$) and North American cohorts ($S_0(2\\text{y}) = 0.9751, S_0(5\\text{y}) = 0.8996$).
        - **Validated Scope:** Confirmed CKD Stages G3–G5 (eGFR $10-60$ mL/min/1.73m²).
        """)

    st.markdown("---")
    st.markdown("### 🗃️ Datasets & Provenance Status")

    st.markdown("""
    | Dataset | Cohort Type | Sample Size | Primary Role in NefroAI-X | Access Governance |
    |---|---|:---:|---|---|
    | **UCI CKD (Dataset A)** | Clinical Case-Control | $N=400$ | Engine 1 Random Forest training | Public Open Research |
    | **NHANES 2017–2018** | Population Survey | $N=9,254$ | Engine 2 KDIGO validation & benchmarking | Public Epidemiological |
    | **CRIC Study Cohort** | Prospective Longitudinal | N/A | Engine 3 Survival ML model training | **RESTRICTED (NIDDK DUA Required)** |
    """)

    st.markdown("""
    > [!IMPORTANT]
    > **CRIC Access Boundary:** Model training on synthetic fixtures is strictly prohibited for clinical claims. Because CRIC longitudinal cohort data is not currently ingested under an approved Data Use Agreement, machine learning survival models (Cox PH and Random Survival Forest) are explicitly designated as **DEFERRED**.
    """)

    st.markdown("---")
    st.markdown("### ⚖️ Regulatory & Diagnostic Disclaimer")

    st.markdown("""
    **Investigational CDSS Notice:**  
    NefroAI-X is an investigational research software platform developed strictly for clinical decision support,
    triaging exploration, and mathematical education. It is **NOT** a certified Software as a Medical Device (SaMD)
    and has not received clearance or approval from the U.S. Food and Drug Administration (FDA), European Medicines
    Agency (EMA), or the Central Drugs Standard Control Organisation (CDSCO).

    1. **Not a Diagnostic Substitute:** Algorithmic estimates, risk probabilities, and classification tags do not constitute a definitive medical diagnosis.
    2. **Mandatory Physician Adjudication:** Final diagnostic determinations, differential evaluations, and therapeutic regimens must be directed exclusively by board-certified nephrologists and licensed clinical practitioners.
    3. **Chronicity Verification:** A single clinical examination or algorithmic assessment cannot substitute for the mandatory 3-month persistence criterion required under international clinical practice guidelines to establish true Chronic Kidney Disease.
    """)
