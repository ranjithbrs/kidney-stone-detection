# NEFROAI-X — Phase 5, Step 2: Engine 2 Clinical CKD Severity Assessment & KDIGO CGA Staging

**Framework:** NEFROAI-X — Advanced Explainable Hybrid AI Framework for Kidney Disease  
**Engine:** Engine 2 — Clinical Severity Assessment & KDIGO CGA Staging  
**Issuing Authority:** Clinical Machine Learning & Nephrology AI Engineering Core  
**Publication Date:** November 2026 (Revised & Certified)  
**Execution Environment:** Python 3.10.0 (`.venv\Scripts\python.exe`)  
**Data Cycle:** NHANES 2017–2018 (Continuous National Health and Nutrition Examination Survey)

---

## 1. Executive Summary & Clinical Mission

NEFROAI-X introduces a three-engine clinical decision support architecture:
1. **Engine 1**: Routine CKD screening and classification (UCI CKD ground truth; $N = 400$).
2. **Engine 2**: Clinical CKD severity assessment and KDIGO CGA staging (NHANES 2017–2018 cohort; $N = 9,254$).
3. **Engine 3**: Longitudinal progression risk prediction (Prospective cohorts; e.g. KPMP, CRIC).

This document certifies the formal implementation and verification of **Engine 2**. Engine 2 calculates kidney filtration estimates using the official race-free **2021 CKD-EPI creatinine equation**, stratifies filtration into KDIGO GFR categories (**G1 to G5**), classifies urine albumin-to-creatinine ratio (UACR) into albuminuria categories (**A1 to A3**), and combines them into a **KDIGO CGA composite risk assessment** (**Low, Moderately Increased, High, Very High Risk**).

Engine 2 operates completely independently of Engine 1 and enforces clinical safeguards preventing label manufacturing, silent imputation, and unconfirmed chronic diagnostic assertions from single-timepoint cross-sectional data.

---

## 2. Mathematical Formulation: Race-Free 2021 CKD-EPI Creatinine Equation

Inker et al. (*N Engl J Med* 2021; 385:1737-1749) developed and validated the race-free 2021 CKD-EPI creatinine equation to provide unbiased, accurate filtration estimates without race terms:

$$\text{eGFR} = 142 \times \min\left(\frac{S_{cr}}{\kappa}, 1.0\right)^\alpha \times \max\left(\frac{S_{cr}}{\kappa}, 1.0\right)^{-1.200} \times 0.9938^{\text{Age}} \times [1.012 \text{ if Female}]$$

### 2.1 Parameter Matrix
| Parameter | Female ($RIAGENDR = 2$) | Male ($RIAGENDR = 1$) | Methodological Clinical Role |
|---|:---:|:---:|---|
| **$\kappa$ (kappa)** | $0.7\text{ mg/dL}$ | $0.9\text{ mg/dL}$ | Mean healthy population baseline serum creatinine |
| **$\alpha$ (alpha)** | $-0.241$ | $-0.302$ | Power exponent for low/normal creatinine concentrations |
| **High Power** | $-1.200$ | $-1.200$ | Power exponent for elevated creatinine concentrations |
| **Age Power** | $0.9938^{\text{Age}}$ | $0.9938^{\text{Age}}$ | Physiological age-related filtration decline ($~0.62\%$ per year) |
| **Sex Factor** | $1.012$ | $1.000$ | Empirical adjustment for female muscle mass / creatinine generation |

### 2.2 Independent Numerical Reference Case Verification
The implementation was verified against authoritative references from the National Kidney Foundation (NKF) and published trial datasets:

| Patient Profile | Input Serum Creatinine ($S_{cr}$) | Age | Sex | Standard Formula Reference | Engine 2 Output | Absolute Delta | Verification Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Young Female Baseline** | $0.70\text{ mg/dL}$ | $20\text{ yr}$ | Female | $126.90\text{ mL/min/1.73 m}^2$ | $126.90\text{ mL/min/1.73 m}^2$ | $< 0.001$ | **PASSED** |
| **Older Female Elevated** | $1.40\text{ mg/dL}$ | $60\text{ yr}$ | Female | $43.07\text{ mL/min/1.73 m}^2$ | $43.07\text{ mL/min/1.73 m}^2$ | $< 0.001$ | **PASSED** |
| **Elderly Female Normal** | $0.60\text{ mg/dL}$ | $65\text{ yr}$ | Female | $99.55\text{ mL/min/1.73 m}^2$ | $99.55\text{ mL/min/1.73 m}^2$ | $< 0.001$ | **PASSED** |
| **Young Male Baseline** | $0.90\text{ mg/dL}$ | $20\text{ yr}$ | Male | $125.40\text{ mL/min/1.73 m}^2$ | $125.40\text{ mL/min/1.73 m}^2$ | $< 0.001$ | **PASSED** |
| **Older Male Impaired** | $1.80\text{ mg/dL}$ | $60\text{ yr}$ | Male | $42.56\text{ mL/min/1.73 m}^2$ | $42.56\text{ mL/min/1.73 m}^2$ | $< 0.001$ | **PASSED** |
| **Middle-Aged Male Normal** | $0.80\text{ mg/dL}$ | $50\text{ yr}$ | Male | $107.82\text{ mL/min/1.73 m}^2$ | $107.82\text{ mL/min/1.73 m}^2$ | $< 0.001$ | **PASSED** |

---

## 3. KDIGO Staging & CGA Composite Risk Matrix

### 3.1 GFR Categories (G1 to G5)
Categories strictly adhere to KDIGO 2012 / 2024 Clinical Practice Guidelines:

| Category | Description | eGFR Operating Range ($\text{mL/min/1.73 m}^2$) | Strict Boundary Test Points | Clinical Action & Guidance |
|:---:|---|:---:|:---:|---|
| **G1** | Normal or high | $\ge 90.0$ | $90.00 \to \text{G1}$; $120.0 \to \text{G1}$ | Normal filtration; evaluate markers of structural kidney damage. |
| **G2** | Mildly decreased | $60.0 - 89.99$ | $60.00 \to \text{G2}$; $89.99 \to \text{G2}$ | Mild reduction; may reflect physiological senescence in age $>65$. |
| **G3a** | Mildly to moderately decreased | $45.0 - 59.99$ | $45.00 \to \text{G3a}$; $59.99 \to \text{G3a}$ | Warrants cardiovascular risk management and monitoring. |
| **G3b** | Moderately to severely decreased | $30.0 - 44.99$ | $30.00 \to \text{G3b}$; $44.99 \to \text{G3b}$ | Monitor metabolic complications (anemia, hyperkalemia, MBD). |
| **G4** | Severely decreased | $15.0 - 29.99$ | $15.00 \to \text{G4}$; $29.99 \to \text{G4}$ | Preparation for kidney replacement therapy (KRT / transplant). |
| **G5** | Kidney failure | $< 15.0$ | $14.99 \to \text{G5}$; $5.00 \to \text{G5}$ | Kidney failure; active planning or initiation of renal replacement. |

*Safety Invariant*: Missing or non-finite eGFR values strictly return `category: None` and `status: "MISSING_INPUT"`. The engine **never** converts missing measurements to G1.

---

### 3.2 Albuminuria Categories (A1 to A3)
Calculated using the official published continuous Urine Albumin-to-Creatinine Ratio (`URDACT` in $\text{mg/g}$):

| Category | Description | UACR Operating Range ($\text{mg/g}$) | Boundary Verification Test Points | Clinical Relevance |
|:---:|---|:---:|:---:|---|
| **A1** | Normal to mildly increased | $< 30.00$ | $0.00 \to \text{A1}$; $29.99 \to \text{A1}$ | Baseline physiological podocyte integrity. |
| **A2** | Moderately increased | $30.00 - 300.00$ | $30.00 \to \text{A2}$; $300.00 \to \text{A2}$ | Early diabetic / hypertensive microvascular podocyte injury. |
| **A3** | Severely increased | $> 300.00$ | $300.01 \to \text{A3}$; $2500.00 \to \text{A3}$ | Overt nephropathy / macroalbuminuria; high progression hazard. |

*Safety Invariant*: Missing UACR returns `category: None`. The engine **never** defaults missing albuminuria to A1.

---

### 3.3 KDIGO CGA Composite Risk Grid (4-Tier Risk Matrix)

The composite risk grid integrates **Cause (C)**, **GFR Category (G)**, and **Albuminuria Category (A)**:

| GFR Category | Albuminuria A1 ($< 30\text{ mg/g}$) | Albuminuria A2 ($30 - 300\text{ mg/g}$) | Albuminuria A3 ($> 300\text{ mg/g}$) |
|:---:|:---:|:---:|:---:|
| **G1** ($\ge 90$) | **Low Risk** (Green, Tier 1) | **Moderately Increased Risk** (Yellow, Tier 2) | **High Risk** (Orange, Tier 3) |
| **G2** ($60 - 89$) | **Low Risk** (Green, Tier 1) | **Moderately Increased Risk** (Yellow, Tier 2) | **High Risk** (Orange, Tier 3) |
| **G3a** ($45 - 59$) | **Moderately Increased Risk** (Yellow, Tier 2) | **High Risk** (Orange, Tier 3) | **Very High Risk** (Red, Tier 4) |
| **G3b** ($30 - 44$) | **High Risk** (Orange, Tier 3) | **Very High Risk** (Red, Tier 4) | **Very High Risk** (Red, Tier 4) |
| **G4** ($15 - 29$) | **Very High Risk** (Red, Tier 4) | **Very High Risk** (Red, Tier 4) | **Very High Risk** (Red, Tier 4) |
| **G5** ($< 15$) | **Very High Risk** (Red, Tier 4) | **Very High Risk** (Red, Tier 4) | **Very High Risk** (Red, Tier 4) |

---

## 4. Clinical Governance & Chronicity Safeguards

A central failure mode in observational healthcare machine learning is equating a single abnormal laboratory measurement with a definitive chronic disease diagnosis. NEFROAI-X enforces three mandatory clinical boundaries:

1. **Chronicity Requirement**:
   - KDIGO clinical practice guidelines explicitly mandate that abnormalities of kidney structure or function must be documented for **$\ge 3\text{ months}$** to diagnose Chronic Kidney Disease.
   - NHANES is an observational, single-visit cross-sectional survey. A transiently elevated creatinine or albuminuria at a single timepoint can be induced by Acute Kidney Injury (AKI), fever, strenuous exercise, volume contraction, or dietary protein load.
   - **Engine Guard**: All Engine 2 outputs set `chronicity_confirmed: False` and attach a mandatory legal/clinical disclaimer.
2. **Etiology ("Cause / C") Boundaries**:
   - Cause classification cannot be inferred from numerical creatinine and UACR alone.
   - **Engine Guard**: In cross-sectional cohorts, Cause is explicitly reported as `UNAVAILABLE_CROSS_SECTIONAL` unless substantiated by independent clinical adjudication.
3. **Incomplete Panel Rejection**:
   - If either eGFR or UACR is unavailable, composite KDIGO risk staging is with withheld (`status: "INCOMPLETE"`, `composite_risk_level: None`).

---

## 5. NHANES 2017–2018 Cohort Severity Distribution ($N = 5,069$)

Executing Engine 2 across the harmonized NHANES 2017–2018 adult dataset reproduces the verified Phase 5 Step 1 cohort numbers and establishes the empirical baseline:

### 5.1 Cohort Denominators
- **Total Sampled Cohort**: $N = 9,254$
- **Total Sampled Adult Population Denominator**: $N = 5,863$ ($100.00\%$ of adults)
- **MEC-Examined Adult Denominator**: $N = 5,540$ ($94.49\%$ of adults)
- **Interview-Only Adult Denominator**: $N = 323$ ($5.51\%$ of adults; excluded from laboratory staging)
- **Pediatric Denominator** ($< 18$ at Exam): $N = 3,391$ (excluded from adult staging)
- **Complete Adult Laboratory Severity Records**: **$N = 5,069$**
  - **Retention of Sampled Adults**: **$86.46\%$** ($\frac{5,069}{5,863}$)
  - **Retention of MEC-Examined Adults**: **$91.50\%$** ($\frac{5,069}{5,540}$)
  - **Share of Total Population Sample**: **$54.78\%$** ($\frac{5,069}{9,254}$)

---

### 5.2 Empirical KDIGO Grid Cross-Tabulation ($6 \times 3$ Matrix)

| GFR Category | Albuminuria A1 ($< 30\text{ mg/g}$) | Albuminuria A2 ($30 - 300\text{ mg/g}$) | Albuminuria A3 ($> 300\text{ mg/g}$) | GFR Total Count | % of Complete Cohort ($N = 5,069$) |
|---|:---:|:---:|:---:|:---:|:---:|
| **G1** ($\ge 90$) | 2,878 | 273 | 34 | **3,185** | 62.83% |
| **G2** ($60 - 89$) | 1,250 | 189 | 34 | **1,473** | 29.06% |
| **G3a** ($45 - 59$) | 196 | 57 | 15 | **268** | 5.29% |
| **G3b** ($30 - 44$) | 51 | 35 | 16 | **102** | 2.01% |
| **G4** ($15 - 29$) | 6 | 12 | 14 | **32** | 0.63% |
| **G5** ($< 15$) | 0 | 2 | 7 | **9** | 0.18% |
| **Albuminuria Total Count** | **4,381** | **568** | **120** | **5,069** | **100.00%** |
| **% of Complete Cohort** | **86.43%** | **11.21%** | **2.37%** | **100.00%** | — |

---

### 5.3 Composite KDIGO Risk Stratification

| KDIGO Composite Risk Level | Risk Color Tier | Participant Count | % of Complete Adult Cohort ($N = 5,069$) | Clinical Triage Recommendation |
|---|:---:|:---:|:---:|---|
| **Low Risk** | Green (Tier 1) | **4,128** | **81.44%** | Routine preventive screening; blood pressure & glycemic monitoring. |
| **Moderately Increased Risk** | Yellow (Tier 2) | **658** | **12.98%** | Repeat laboratory panel in 3–6 months to establish chronicity; evaluate SGLT2i / ACEi. |
| **High Risk** | Orange (Tier 3) | **176** | **3.47%** | Comprehensive nephrology evaluation; close monitoring of eGFR trajectory; cardiovascular risk minimization. |
| **Very High Risk** | Red (Tier 4) | **107** | **2.11%** | Urgent multidisciplinary nephrology management; metabolic complication treatment; KRT planning. |
| **Total Complete Cases** | — | **5,069** | **100.00%** | — |

---

## 6. Architecture & Code Structure

The implementation follows a modular architecture separating mathematical estimation, categorical thresholding, and cohort processing:

```text
src/
├── clinical/
│   ├── __init__.py               # Exports calculators and staging engines
│   ├── egfr_calculator.py        # Race-free 2021 CKD-EPI creatinine equation
│   └── kdigo_staging.py          # KDIGO GFR, Albuminuria, and 4-tier CGA risk matrix
├── engines/
│   ├── __init__.py               # Exports primary engine classes
│   └── kidney_severity_engine.py # KidneySeverityEngine (Patient & Cohort assessment)
tests/
└── test_kidney_severity_engine.py# 16 comprehensive automated unit & regression tests
```

---

## 7. Quality Assurance & Regression Verification

### 7.1 Automated Test Execution
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
- **Total Tests Discovered & Executed**: **170 tests** across the entire repository.
- **Pass Rate**: **100% (170 passed, 0 failures, 0 errors)** in $13.52\text{ s}$.
- **New Engine 2 Tests**: 16 dedicated tests in `tests/test_kidney_severity_engine.py` covering male/female reference calculations, boundary transitions, pediatric exclusion, missingness, interview-only exclusion, and NHANES cohort ground truth.

### 7.2 Data Integrity & Protected Assets
- `models/clinical_pipeline.joblib`: SHA-256 `9217fbbe...` (verified **untouched**; Engine 1 unchanged).
- `datasets/clinical/dataset_A_uci_ckd.csv`: SHA-256 `147be021...` (verified **untouched**; UCI screening data unchanged).
- `git diff --check`: Exit code `0` (clean; no whitespace, patch, or merge issues).
- No Git commits or pushes were executed.
