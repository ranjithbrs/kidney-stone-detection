# Phase 17: Candidate Invention Working Prototype Implementation & Verification Report

**Mechanism Designation**: Cross-Dataset Clinical Input Reliability and Prediction Validation Mechanism (CD-CIRPVM)  
**System Brand Name**: NephroGuard-AI Verification Engine  
**Implementation Modules**:  
- Engine Source: [`src/clinical_input_reliability_mechanism.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical_input_reliability_mechanism.py)  
- Test Suite: [`src/test_invention_prototype.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/test_invention_prototype.py)  
- Production Model Connected: [`models/clinical_pipeline.joblib`](file:///c:/Users/B%20Ranjith/Downloads/project/models/clinical_pipeline.joblib)  

---

## 1. Architectural Summary & Component Blueprint

```
                      Raw Patient Ingestion (EHR / FHIR / Tabular)
                                          │
                                          ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │ 1. Magnitude-Inferred Dimensional Reconciliation (MIDR Engine)              │
   │    • sc > 25.0 µmol/L    ──> sc / 88.42 (mg/dL)                            │
   │    • hemo > 25.0 g/L     ──> hemo / 10.0 (g/dL)                            │
   │    • 1.5 <= bgr < 35.0   ──> bgr * 18.018 (mg/dL)                          │
   │    • BUN flag active     ──> bu * 2.1428 (Whole Urea)                      │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
                                          ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │ 2. 14-Organ Physiological Viability Clamping & Quality Scoring (CRI)        │
   │    • Clamps negative / extreme sensor artifacts into physiological envelopes│
   │    • Intercepts IEEE-754 NaN and Inf values with safe defaults              │
   │    • Harmonizes dialect synonyms ('1', 'TRUE', 'present', 'norm')          │
   │    • Computes Clinical Reliability Index: CRI in [0.0, 1.0]                │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
             CRI < 0.60                                    CRI >= 0.60
                   │                                             │
                   ▼                                             ▼
       ┌────────────────────────┐                   ┌────────────────────────┐
       │ REJECT: UNRELIABLE     │                   │ 3. ML Inference Engine │
       │ Data Corrupted/Missing │                   │ 10-Consensus Biomarkers│
       │ Mandatory Re-Draw      │                   │ P(Healthy), P(CKD)     │
       └────────────────────────┘                   └───────────┬────────────┘
                                                                │
                                                                ▼
                                                    ┌────────────────────────┐
                                                    │ 4. Conformal Gate      │
                                                    │ Split Non-Conformity   │
                                                    │ Threshold: q_95 = 0.261│
                                                    └───────────┬────────────┘
                                                                │
                                   ┌────────────────────────────┴───────────────────────────┐
                                   │                                                        │
                         |C_alpha| = 1                                            |C_alpha| in {0, 2}
                                   │                                                        │
                                   ▼                                                        ▼
                       ┌────────────────────────┐                               ┌────────────────────────┐
                       │ DECISIVE PROCEED       │                               │ ABSTAIN: EPISTEMIC     │
                       │ 95% Certified Diagnosis│                               │ UNCERTAINTY            │
                       │ Triage Risk Categorized│                               │ Human Nephrologist     │
                       └────────────────────────┘                               │ Mandatory Consultation │
                                                                                └────────────────────────┘
```

---

## 2. Experimental Verification Across 5 Clinical Scenarios

The prototype was subjected to rigorous validation against the 5 requirements outlined in Phase 17:

| Test ID | Clinical Testing Scenario | Input Profile Description | CRI Score | Conformal Set | Gate Status | Final Decision | Status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: |
| **TEST 1A** | Compatible (Healthy Standard) | 100% complete standard US units, physiological normal limits | **1.00** | `[0]` | `DECISIVE_CONFORMAL_PASS` | **PROCEED** (Normal, Risk 0.0) | **PASSED** |
| **TEST 1B** | Compatible (CKD Standard) | Elevated creatinine, proteinuria, anemia, hypertension | **1.00** | `[1]` | `DECISIVE_CONFORMAL_PASS` | **PROCEED** (CKD, Risk 1.0) | **PASSED** |
| **TEST 2** | Incompatible Inputs | Sensor errors: `age = -15`, `bp = 380`, `sg = 1.999`, `sc = 95.0`, `bgr = 4500`, `hemo = NaN`, `pot = Inf` | **0.00** | `[0, 1]` | `REJECTED_UNRELIABLE_DATA` | **ABSTAIN** (Data Corrupted) | **PASSED** |
| **TEST 3A** | Missing Measurements | Empty record (`{}`) | **0.00** | `[0, 1]` | `REJECTED_UNRELIABLE_DATA` | **ABSTAIN** (Repeat Lab Needed) | **PASSED** |
| **TEST 3B** | Ultra-Sparse Measurements | Sparse record (`{"age": 55, "bp": 80}`) | **0.00** | `[0, 1]` | `REJECTED_UNRELIABLE_DATA` | **ABSTAIN** (12 Missing Features) | **PASSED** |
| **TEST 4A** | Inconsistent Units (UK SI Healthy) | `sc = 88.42 µmol/L`, `hemo = 150.0 g/L`, `bgr = 5.2 mmol/L`, boolean strings | **1.00** | `[0]` | `DECISIVE_CONFORMAL_PASS` | **PROCEED** (Normal, Reconciled) | **PASSED** |
| **TEST 4B** | Inconsistent Units (UK SI CKD) | `sc = 442.1 µmol/L`, `hemo = 80.0 g/L`, `bgr = 12.5 mmol/L`, boolean `htn="1"` | **1.00** | `[1]` | `DECISIVE_CONFORMAL_PASS` | **PROCEED** (CKD, Reconciled) | **PASSED** |
| **TEST 5** | Unreliable Predictions | Equivocal borderline patient: $P(\text{CKD}) = 0.58$, within epistemic boundary | **1.00** | `[0, 1]` | `REJECTED_EPISTEMIC_UNCERTAINTY` | **ABSTAIN** (Human Review Mandated) | **PASSED** |

---

## 3. Technical Implementation Details

### 3.1 Magnitude-Inferred Dimensional Reconciliation (MIDR)
Standard ML algorithms fail catastrophically when presented with international clinical units because serum creatinine in SI units ($88.42\ \mu\text{mol/L}$) is 88 times larger than conventional US units ($1.0\ \text{mg/dL}$).

MIDR exploits non-overlapping physiological separation:
- **Creatinine ($s_c$)**: Human serum creatinine in $\text{mg/dL}$ never exceeds $25.0\ \text{mg/dL}$ without mortality. Any reading $> 25.0$ represents $\mu\text{mol/L}$, automatically mapped via:
  $$\text{sc}_{\text{mg/dL}} = \frac{\text{sc}_{\mu\text{mol/L}}}{88.42}$$
- **Hemoglobin ($\text{hemo}$)**: Values in $\text{g/L}$ ($120 - 170\ \text{g/L}$) exceed $25.0\ \text{g/L}$, and are reconciled via:
  $$\text{hemo}_{\text{g/dL}} = \frac{\text{hemo}_{\text{g/L}}}{10.0}$$
- **Glucose ($\text{bgr}$)**: Values in $\text{mmol/L}$ ($3.5 - 30.0\ \text{mmol/L}$) fall in $[1.5, 35.0)$ and are converted via:
  $$\text{bgr}_{\text{mg/dL}} = \text{bgr}_{\text{mmol/L}} \times 18.018$$

### 3.2 Clinical Reliability Index (CRI)
Calculated dynamic score penalizing missing biomarkers, NaN/Inf intrusions, out-of-bounds sensor noise, and dialect discrepancies:
$$\text{CRI} = \max\left(0, 1.00 - \sum \Delta_{\text{missing}} - \sum \Delta_{\text{clamped}} - \sum \Delta_{\text{dialect}}\right)$$
If $\text{CRI} < 0.60$, inference halts immediately prior to model invocation, preventing silent hallucinations.

### 3.3 Inductive Conformal Non-Conformity Gate
Under calibration on the held-out validation cohort at significance $\alpha = 0.05$ (95% marginal coverage guarantee), the non-conformity threshold is:
$$\hat{q}_{95} = 0.261$$
For a new patient with model posterior probabilities $[\hat{P}_0, \hat{P}_1]$, the conformal prediction set is:
$$C_{\alpha}(x) = \left\{ y \in \{0, 1\} \;\middle|\; (1 - \hat{P}_y) \le \hat{q}_{95} \right\}$$
- When $\hat{P}_y \ge 1 - 0.261 = 0.739$, $|C_{\alpha}(x)| = 1 \implies$ **PROCEED** with single certified diagnosis.
- When $\hat{P}_y < 0.739$ for both classes (i.e. high epistemic uncertainty), $|C_{\alpha}(x)| = 2 \implies$ **ABSTAIN** and withhold automated diagnosis.

---

## 4. Distinction from Prior Art (NefroAI and Others)
- **NefroAI (Al Huda et al., IEEE Access 2024)**: Lacks dynamic unit reconciliation, lacks bounds clamping, and outputs a hard categorical label even when presented with incompatible units or complete noise.
- **Renalytix (US 11,462,328 B2)**: Requires physical proprietary blood biomarker assays (sTNFR1/2) and does not provide algorithmic cross-dataset compatibility or conformal abstention gates for tabular EHRs.
- **Candidate Invention (NephroGuard-AI / CD-CIRPVM)**: Entirely algorithmic software-implemented method operating upstream and downstream of any tabular clinical model, ensuring zero silent overconfidence and seamless multi-hospital EHR integration.
