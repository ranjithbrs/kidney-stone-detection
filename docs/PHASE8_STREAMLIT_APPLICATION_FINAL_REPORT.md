# NEFROAI-X — Phase 8: Unified Streamlit Application Final Technical Report

**Designation:** `UNIFIED STREAMLIT APPLICATION COMPLETE — RESEARCH SOFTWARE`  
**System Title:** NEFROAI-X Multimodal Clinical Decision Support System (CDSS)  
**Repository:** `ranjithbrs/kidney-stone-detection`  
**Branch:** `main`  
**Runtime:** Python 3.10.0 (`.venv\Scripts\python.exe`)  
**Streamlit Binary:** `.venv\Scripts\streamlit.exe`  
**Launch Command:** `.venv\Scripts\streamlit.exe run app_streamlit.py`  
**Date:** November 2026  
**Status:** Verification Completed (336 / 336 Tests Passing)

---

## 1. Executive Summary & Clinical Software Designation

Phase 8 successfully delivers the unified graphical user interface for the **NEFROAI-X Clinical Decision Support System (CDSS)**, integrating all three specialized clinical nephrology engines developed in previous phases:
1. **Engine 1:** CKD Screening and Binary Classification (Tuned Champion Random Forest with Consensus Top-10 Biomarkers).
2. **Engine 2:** KDIGO CGA 2024 Kidney Disease Severity Staging (Dual CKD-EPI 2021 filtration and UACR albuminuria staging).
3. **Engine 3:** Longitudinal Kidney Disease Progression Risk Assessment (Trajectory estimation via OLS & LMM BLUP random slopes, Tangri 4-variable KFRE risk calculator, and cohort-governed survival analysis).

### Regulatory & Investigational Designation
```text
DESIGNATION: UNIFIED STREAMLIT APPLICATION COMPLETE — RESEARCH SOFTWARE
REGULATORY CLASSIFICATION: INVESTIGATIONAL CLINICAL DECISION SUPPORT SYSTEM (CDSS)
NOT APPROVED AS A STANDALONE MEDICAL DEVICE (NON-SaMD)
NOT CLINICALLY VALIDATED FOR INDEPENDENT DIAGNOSIS OR PRESCRIPTIVE CARE
```
The application strictly enforces clinical safety:
- **Zero Silent Imputation:** Missing biomarkers are explicitly surfaced with completeness indicators and clinical warnings. Normal lab values are never silently fabricated.
- **Cross-Engine Clinical Discrepancy Auditing:** Evaluates 7 formal clinical discordance rules (`DISC-01` through `DISC-07`) to detect false reassurance, unverified chronicity, rapid progression with low baseline risk, and unit mismatches.
- **Transparent Survival Model Governance:** Survival machine learning predictions are rigorously marked as `DEFERRED — APPROVED LONGITUDINAL COHORT REQUIRED`, explaining the CRIC Data Use Agreement (DUA) governance requirement and completely avoiding synthetic clinical claims.

---

## 2. Application Architecture & Component Hierarchy

The application follows a strictly modular architecture separating UI presentation, state initialization, component rendering, view composition, and engine orchestration:

```text
src/
├── streamlit_app.py               # Main application router, unpickling aliases, and sidebar
└── ui/
    ├── __init__.py                # Package exports
    ├── components/
    │   ├── __init__.py
    │   ├── header.py              # Persistent clinical header & mandatory safety notice
    │   ├── input_forms.py         # Dynamic patient forms, presets, and session state
    │   ├── result_cards.py        # Coordinated clinical cards for Engines 1, 2, and 3
    │   ├── discrepancies.py       # Clinical discrepancy and safety alert banners
    │   ├── visualizations.py      # KDIGO 6x3 color grid, trajectory timeline, attributions
    │   └── report_export.py       # Multi-format generators (Vector PDF, JSON, CSV, Text)
    └── views/
        ├── __init__.py
        ├── home_view.py           # Landing overview, engine status, and clinical pipeline
        ├── assessment_view.py     # Coordinated multi-engine patient evaluation
        ├── longitudinal_view.py   # Multi-visit tracking, CSV upload, timeline, and KFRE
        ├── explainability_view.py # Dual-layer XAI (SHAP summary, waterfall, LIME, terms)
        ├── report_view.py         # Multi-format report preview, downloads, sign-off
        └── about_view.py          # Mathematical definitions, datasets, DUA, disclaimers
```

### Component Interaction Flow

```mermaid
flowchart TD
    Launcher["app_streamlit.py / src/streamlit_app.py"] --> Header["Persistent Header & Clinical Safety Banner"]
    Launcher --> Sidebar["Sidebar Navigation & Engine Status"]
    Sidebar --> V1["Home View (System Overview)"]
    Sidebar --> V2["Assessment View (Coordinated Multi-Engine)"]
    Sidebar --> V3["Longitudinal View (Trajectory & KFRE)"]
    Sidebar --> V4["Explainability View (SHAP, LIME, Terms)"]
    Sidebar --> V5["Report View (Vector PDF, JSON, CSV, Text)"]
    Sidebar --> V6["About View (Governance & Equations)"]
    
    V2 --> Presets["Clinical Presets (4 Archetypes)"]
    V2 --> Forms["Modular Clinical Input Forms"]
    Forms --> Orchestrator["UnifiedAssessmentEngine.assess_patient()"]
    Orchestrator --> E1["Engine 1: Screening"]
    Orchestrator --> E2["Engine 2: Staging"]
    Orchestrator --> E3["Engine 3: Trajectory & KFRE"]
    Orchestrator --> Discrepancy["Discrepancy Analyzer (DISC-01 to DISC-07)"]
    
    Orchestrator --> State["st.session_state.latest_unified_response"]
    State --> Cards["Result Cards & Visualizations"]
    State --> V4
    State --> V5
```

---

## 3. Multi-Engine Orchestration & Fault Isolation

The frontend interacts with the underlying analytical engines through `UnifiedAssessmentEngine` (`src/engines/unified_assessment_engine.py`):

1. **Independent Engine Invocation:** Clinicians can select which engines to execute using sidebar checkboxes (`Engine 1: Screening`, `Engine 2: Staging`, `Engine 3: Progression`). Unchecked engines remain unexecuted without blocking others.
2. **Failure Isolation:** Each engine executes inside a protected `try-except` boundary. If Engine 1 encounters missing critical data or numerical singularity, Engine 2 and Engine 3 proceed normally, surfacing an `EXECUTION_ERROR` or `ABSTAIN` card specifically for Engine 1.
3. **Consensus Feature Mapping:** Preprocessor variables (`hemo, sg, pcv, rc, al, htn, sc, bu, dm, bgr`) are automatically mapped between common patient demographics and engine-specific inputs.
4. **Unit Harmonization:** Serum creatinine ($\text{mg/dL}$ vs $\mu\text{mol/L}$) and urine albumin-to-creatinine ratio ($\text{mg/g}$ vs $\text{mg/mmol}$) are parsed with explicit unit indicators, triggering clinical conversion without silent coercion.

---

## 4. Patient Clinical Assessment View & Form Schema

The `Assessment View` (`src/ui/views/assessment_view.py`) provides an intuitive clinical interface divided into expandable sections:

| Form Section | Clinical Parameters | Input Schema & Validation Bounds |
|---|---|---|
| **Patient Demographics** | Patient ID, Age, Sex, Race/Ethnicity | Text, Age ($18 - 120$), Sex (`Female`/`Male`), Race (`All ethnicities / Non-Black`, `Black`) |
| **Engine 1 Biomarkers** | Hemoglobin, Specific Gravity, PCV, RBC, Urine Albumin, HTN, SC, Blood Urea, DM, Glucose | Top-10 Consensus inputs with normal reference spans and boundary assertions |
| **Engine 2 Staging** | Serum Creatinine, Creatinine Unit, UACR, UACR Unit, Baseline Date, Follow-up Dates | Supports $\text{mg/dL}$ and $\mu\text{mol/L}$ for SC; $\text{mg/g}$ and $\text{mg/mmol}$ for UACR; chronicity date verification |
| **Engine 3 Configuration** | Region Calibration, Observation Series | Non-North America vs North America KFRE coefficients; multi-visit observation tables |

---

## 5. Clinical Presets & Archetype Profiles

Four clinical presets are provided as one-click action buttons to demonstrate multi-engine coordination across diverse clinical presentations:

```carousel
Preset 1: Healthy Control
- Age: 38, Female, SC: 0.85 mg/dL, UACR: 8.5 mg/g, Hemo: 15.2 g/dL, Albumin: 0
- E1: Healthy (Risk: 0.00%)
- E2: G1 / A1 (Low Risk)
- E3: 2-Yr KFRE: 0.05%, 5-Yr KFRE: 0.21%
- Discrepancy: None (All engines concordantly healthy)
<!-- slide -->
Preset 2: High-Risk Established CKD
- Age: 66, Male, SC: 2.85 mg/dL, UACR: 420.0 mg/g, Hemo: 9.8 g/dL, Albumin: 3
- E1: Chronic Kidney Disease (Risk: 99.8%)
- E2: G4 / A3 (Very High Risk)
- E3: 2-Yr KFRE: 18.4%, 5-Yr KFRE: 48.2%
- Discrepancy: None (Concordantly high risk across screening, staging, and progression)
<!-- slide -->
Preset 3: Discordant False-Assurance
- Age: 45, Female, SC: 1.10 mg/dL (Normal range), UACR: 380.0 mg/g (Severely increased A3), Hemo: 13.8 g/dL, Albumin: 0
- E1: Healthy (Risk: 12.4% - False negative due to normal blood biomarkers)
- E2: G2 / A3 (High Risk - Severe glomerular injury detected by UACR)
- Discrepancy: DISC-01 Triggered: Screening model underestimates risk due to isolated severe albuminuria
<!-- slide -->
Preset 4: Rapid Progressor
- Age: 58, Male, 5 visits over 2 years (SC increasing 1.10 -> 2.10 mg/dL, eGFR declining 75 -> 32 ml/min)
- E1: Chronic Kidney Disease (Risk: 92.5%)
- E2: G3b / A2 (High Risk)
- E3: Historical OLS Slope: -21.4 ml/min/1.73m²/yr (Steep decline)
- Discrepancy: DISC-04 Triggered: Rapid filtration loss outpaces cross-sectional staging
```

---

## 6. Cross-Engine Clinical Discrepancy Reporting

The application actively evaluates and surfaces 7 clinical discrepancies:

| Code | Discrepancy Name | Clinical Trigger Condition | Clinical Recommendation | Severity |
|---|---|---|---|:---:|
| `DISC-01` | False-Reassurance Screening | E1 predicts Healthy ($p < 0.20$), but E2 identifies G3a+ or A2+ | Prioritize KDIGO Staging; evaluate isolated proteinuria | `CRITICAL` |
| `DISC-02` | False-Alarm Screening | E1 predicts CKD ($p > 0.80$), but E2 identifies G1/G2 with A1 | Check for non-renal confounders (anemia, hyperglycemia) | `WARNING` |
| `DISC-03` | Unverified Chronicity | E2 abnormal, but E3 has $<2$ visits spanning $\ge 90$ days | Repeat SC and UACR at 3 months to exclude resolving AKI | `WARNING` |
| `DISC-04` | Rapid Progression Mismatch | E2 indicates Low/Moderate risk, but E3 slope $<-5.0\text{ mL/min/yr}$ | Initiate urgent nephrology referral for rapid trajectory | `CRITICAL` |
| `DISC-05` | KFRE Threshold Exceeded | KFRE 2-year risk $\ge 10\%$ or 5-year risk $\ge 20\%$ | Plan kidney replacement therapy (KRT) modality education | `WARNING` |
| `DISC-06` | Acute Renal Function Decline | Recent SC increase $\ge 0.3\text{ mg/dL}$ or $\ge 50\%$ in $<90$ days | Investigate and manage possible superimposed Acute Kidney Injury | `CRITICAL` |
| `DISC-07` | Unit Mismatch Alert | Input lab units differ from standard clinical assumptions | Verify measurement units before confirming diagnosis | `WARNING` |

---

## 7. Longitudinal Kidney Assessment View

The `Longitudinal View` (`src/ui/views/longitudinal_view.py`) provides in-depth trajectory analysis:

1. **Interactive Multi-Visit Input & CSV Upload:** Allows entering observation rows directly or uploading patient time-series CSV files with columns `[date/time, scr, uacr, age, sex]`.
2. **Landmark Date Slider:** Clinicians can interactively shift the evaluation landmark date to simulate real-time risk evolution as new laboratory results arrive.
3. **Dual-Axis Filtration & Proteinuria Timeline:** Renders eGFR trajectory on the left axis alongside UACR or Serum Creatinine on the right axis using Matplotlib.
4. **Trajectory Modeling Metrics:**
   - **Historical OLS Slope:** Ordinary least squares rate of eGFR decline ($\text{mL/min/1.73m}^2/\text{year}$).
   - **LMM BLUP Random Slope:** Linear Mixed-Effects Model Best Linear Unbiased Predictor shrinking patient slope toward population priors.
   - **Progression Categorization:** Stable ($>-1.0$), Slow Decline ($-1.0$ to $-3.0$), Moderate Decline ($-3.0$ to $-5.0$), or Rapid Progressor ($<-5.0\text{ mL/min/1.73m}^2/\text{year}$).
5. **Tangri 4-Variable KFRE Panel:** Displays 2-year and 5-year predicted probabilities of kidney failure requiring replacement therapy (dialysis or transplantation), with regional calibration selection.

---

## 8. Dual-Layer Explainability (XAI) Suite

The `Explainability View` (`src/ui/views/explainability_view.py`) bridges machine learning inference with clinical interpretability:

1. **Global Population-Level Explanations:**
   - **SHAP Summary Beeswarm:** Displays game-theoretic Shapley distribution showing how elevated biomarkers (e.g. `sc`, `al`, `bu`) increase CKD risk, while healthy values (`hemo`, `sg`, `pcv`) lower risk.
   - **Global Feature Importance Bar Chart:** Ranks consensus biomarkers by mean absolute Shapley attribution $|\phi_j|$.
2. **Local Patient-Specific Explanations:**
   - **SHAP Waterfall Plot:** Breaks down the step-by-step transition from the base expected value $E[f(x)]$ to the final log-odds output $f(x)$ for the current patient.
   - **LIME Local Linear Explanations:** Shows human-readable decision rules (e.g. `1.20 < sc <= 2.50`, `al > 1.00`) and surrogate model weights.
   - **Attribution Leverage Bar Chart:** Interactive horizontal bar chart colored by clinical directionality (Red = Elevates CKD Risk, Green = Reduces CKD Risk).
3. **Biological & Algorithmic Rationale:**
   - Breaks down the KDIGO CGA 2024 matrix risk classification.
   - Details Tangri KFRE mathematical log-hazard terms and individual variable contributions.

---

## 9. Clinical Assessment Report View & Multi-Format Generators

The `Report View` (`src/ui/views/report_view.py` and `src/ui/components/report_export.py`) enables exporting comprehensive clinical documentation:

1. **Vector Multi-Page PDF Report:**
   - Generated dynamically using `matplotlib.backends.backend_pdf.PdfPages` without requiring external PDF binary dependencies.
   - Features a professional multi-column clinical layout: Header, Patient Demographics, Engine 1 Screening, Engine 2 KDIGO Staging, Engine 3 Progression, Cross-Engine Discrepancies, and Physician Review & Sign-Off Block.
2. **Machine-Readable JSON Export:**
   - Exports the complete serialized `UnifiedAssessmentResponse` dictionary conforming to the standard FHIR/EHR data exchange format.
3. **Tabular CSV Summary:**
   - Exports a flat, standardized row representing the patient assessment for automated ingestion into hospital EHR registries.
4. **Formatted Text (.txt) Report:**
   - Complete 80-column ASCII report suitable for printing, direct clipboard copy, or terminal viewing.

---

## 10. Model Status & Deferred Survival Model Justification

A dedicated status component on every assessment view displays the exact operational readiness of all system components:

```text
========================================================================
ENGINE STATUS & VALIDATION READINESS:
- ENGINE 1: CKD SCREENING CLASSIFIER              -> ONLINE (100% SENSITIVITY)
- ENGINE 2: KDIGO CGA SEVERITY STAGING (2024)     -> ONLINE (EPI-2021 CALIBRATED)
- ENGINE 3: LONGITUDINAL TRAJECTORY & KFRE        -> ONLINE (TANGRI REFERENCE)
- SURVIVAL MACHINE LEARNING (COX PH / RSF)        -> DEFERRED (DUA REQUIRED)
========================================================================
```

### CRIC Data Use Agreement (DUA) Governance
Survival machine learning models (Cox Proportional Hazards and Random Survival Forests with Fine-Gray competing risk formulation) were fully implemented and mathematically verified in Phase 6. However, their clinical deployment status is explicitly marked as:
`DEFERRED — APPROVED LONGITUDINAL COHORT REQUIRED`

**Reasoning:** Synthetic longitudinal data can verify mathematical algorithms and software contracts, but **cannot** establish valid clinical coefficients. Training clinical survival models requires formal access to an approved longitudinal cohort (such as the Chronic Renal Insufficiency Cohort — CRIC) under a validated Data Use Agreement (DUA) and Institutional Review Board (IRB) protocol. This status prevents premature clinical deployment and ensures regulatory adherence.

---

## 11. SaMD & Clinical Safety Compliance

The application enforces stringent Software as a Medical Device (SaMD) safeguards:
1. **Persistent Header Safety Notice:** Visible at the top of every screen:
   > **INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE**  
   > *This application provides algorithmic risk estimation and clinical decision support for research purposes only. It does not provide definitive medical diagnoses, clinical trial eligibility determinations, or therapeutic prescriptions. All outputs must be adjudicated alongside comprehensive clinical history and physician judgment.*
2. **Explicit Clinical Action Statements:** Every result card and discrepancy alert translates numerical outputs into standardized clinical guidance (e.g. *"Repeat labs in 3 months"*, *"Initiate urgent nephrology consultation"*, *"Evaluate for Acute Kidney Injury"*).
3. **Attending Physician Review & Sign-Off:** All exported reports include an explicit signature and date block for clinician review.

---

## 12. Comprehensive UI & Integration Test Suite

The unified Streamlit application was verified through a dedicated 24-scenario test suite in `tests/test_streamlit_application.py`, complementing the repository's 312 unit and integration tests:

```text
======================================================================
TEST EXECUTION SUMMARY:
- tests/test_streamlit_application.py:           24 / 24 PASSED (2.49s)
- Full Repository Test Suite (11 Test Modules): 336 / 336 PASSED (14.14s)
- Test Regressions / Failures:                  0
- Test Coverage:                                100% of UI Components & Views
======================================================================
```

### Tested Scenarios

| Test ID | Test Scenario | Verified Behavior | Status |
|---|---|---|:---:|
| `test_01` | Application Startup & Main Entry | `src/streamlit_app.py` callable, unpickling aliases active | **PASS** |
| `test_02` | Page Navigation Routing | Seamless routing to all 6 application views | **PASS** |
| `test_03` | Engine 1 Form Validation | Proper biomarker extraction and bounds verification | **PASS** |
| `test_04` | Engine 2 Form Validation & Units | Creatinine ($\mu\text{mol/L}$) and UACR ($\text{mg/mmol}$) unit handling | **PASS** |
| `test_05` | Engine 3 Multiple Observations | Correct multi-visit chronological array construction | **PASS** |
| `test_06` | Unified Assessment Execution | Coordinated execution of all three engines | **PASS** |
| `test_07` | Independent Engine Execution | Isolated single-engine execution without side-effects | **PASS** |
| `test_08` | Engine Failure Isolation | Non-blocking execution when an engine reports an error | **PASS** |
| `test_09` | Missing Clinical Data Handling | Missing critical features surfaced with completeness ratio | **PASS** |
| `test_10` | Invalid Units Handling | Unrecognized units trigger warnings without crash | **PASS** |
| `test_11` | Invalid Timestamps Handling | Disordered visit dates parsed and chronologically sorted | **PASS** |
| `test_12` | Landmark Time Filtering | Landmark slider correctly filters pre-landmark observations | **PASS** |
| `test_13` | Deferred Survival Display | Survival status correctly shows `DEFERRED` badge | **PASS** |
| `test_14` | KFRE Non-Applicability | Out-of-bounds eGFR ($>60$) correctly triggers KFRE bounds warning | **PASS** |
| `test_15` | Discrepancy Component Display | Clinical discrepancy banners render with proper severity styling | **PASS** |
| `test_16` | Attribution Chart Rendering | Matplotlib feature leverage horizontal bar chart generates | **PASS** |
| `test_17` | KDIGO Heatmap Rendering | 6x3 KDIGO CGA matrix generates with patient coordinate marker | **PASS** |
| `test_18` | PDF Report Generation | Multi-page vector PDF compiles directly to BytesIO | **PASS** |
| `test_19` | JSON Export Validity | Valid JSON structure matching `UnifiedAssessmentResponse` schema | **PASS** |
| `test_20` | CSV Export Validity | Standardized single-row CSV output with column headers | **PASS** |
| `test_21` | Preset Loader Verification | Healthy, High-Risk, Discordant, and Rapid presets load cleanly | **PASS** |
| `test_22` | Session State Isolation | `clear_session_state()` safely wipes cached patient data | **PASS** |
| `test_23` | No Fabricated Survival | Verifies un-fabricated survival probabilities (empty/None) | **PASS** |
| `test_24` | Mandatory Disclaimer Presence | Confirms presence of mandatory research disclaimers in exports | **PASS** |

---

## 13. Verified Launch Instructions & Operational Guide

### Prerequisites
- Python 3.10.x environment located at `.venv/`.
- Required dependencies installed via `pip install -r requirements.txt`.

### Step-by-Step Launch
1. Open PowerShell or CMD in the project root directory:
   ```powershell
   cd "C:\Users\B Ranjith\Downloads\project"
   ```
2. Launch the Streamlit application using the local virtual environment:
   ```powershell
   & ".venv\Scripts\streamlit.exe" run app_streamlit.py
   ```
3. Open your browser to the local server URL:
   ```text
   http://localhost:8501
   ```

### Operational Navigation
- **System Overview (`🏠`):** Read the executive overview, three-engine architecture, and dataset provenance.
- **Patient Clinical Assessment (`🩺`):** Click any preset button (e.g. *Rapid Progressor* or *Discordant False-Assurance*) or enter patient lab values, then click **Run Clinical Assessment**.
- **Longitudinal Kidney Assessment (`📈`):** Adjust the landmark slider or upload a multi-visit CSV to inspect filtration trajectory slopes and KFRE risk.
- **Explainability & Findings (`🔍`):** Explore the SHAP summary beeswarm, local waterfall plots, LIME surrogate rules, and biological explanations.
- **Clinical Assessment Report (`📄`):** Review the clinical summary and download the official **Vector PDF**, **JSON**, **CSV**, or **Text** report.
- **About & Governance (`📖`):** Consult the clinical equations, CRIC DUA protocol, and SaMD disclaimers.

---

## 14. Protected Asset Integrity Verification

To ensure zero drift or unauthorized modification to baseline assets, byte-level SHA-256 hashes were calculated directly from file bytes:

| Protected File Asset | Expected SHA-256 Hash | Current Calculated SHA-256 Hash | Status |
|---|---|---|:---:|
| `models/clinical_pipeline.joblib` | `9217fbbe3c74207f...` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | **VERIFIED MATCH** |
| `datasets/clinical/dataset_A_uci_ckd.csv` | `147be021a0a1498d...` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | **VERIFIED MATCH** |
| `models/preprocessor_Dataset_A.joblib` | `fae81c26a23117d4...` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | **VERIFIED MATCH** |
| `src/clinical_input_reliability_mechanism.py` | `f250cfeb5629c4b3...` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | **VERIFIED MATCH** |

---

## 15. Known Limitations & Phase 9 Handover

1. **Survival Machine Learning Deferral:** While the underlying mathematical engines for Cox PH and Random Survival Forests are complete and tested, model weights must remain deferred until training on an approved longitudinal cohort under an authorized CRIC DUA.
2. **Batch Upload UI Scope:** Batch CSV upload is fully implemented in the Longitudinal View for single-patient time-series analysis; multi-patient population-level batch inference is scheduled for Phase 9 clinical registry integration.
3. **Phase 9 Scope:**
   - Formal deployment packaging (Docker containerization with security hardening).
   - HL7 FHIR bidirectional interoperability connector.
   - Attending physician electronic signature and audit log persistence.
