# NEFROAI-X — Phase 6, Step 3: KFRE Reference Calculator & Kidney Progression Engine Prototype

**Status:** IMPLEMENTED & VERIFIED  
**Component:** Engine 3 — Longitudinal Kidney Disease Progression Risk Prediction  
**Module Paths:**
- `src/clinical/kfre_calculator.py`
- `src/engines/kidney_progression_engine.py`
- `tests/test_kfre_calculator.py`
- `tests/test_kidney_progression_engine.py`  
**Test Suite Status:** 18/18 New Tests Passing; 47/47 Engine 3 Tests Passing; 219/219 Full Repository Tests Passing

---

## 1. Executive Summary

Phase 6 Step 3 implements the foundational risk-prediction component of **Engine 3 (Longitudinal Kidney Disease Progression Risk Prediction)** for the NefroAI-X Clinical Decision Support System (CDSS). 

Engine 3 addresses a core clinical requirement beyond static screening (Engine 1) and cross-sectional staging (Engine 2): **quantifying the individualized future risk of progression to kidney failure** requiring kidney replacement therapy (KRT: chronic dialysis or preemptive kidney transplantation).

This step delivers two core production-grade modules:
1. **Tangri 4-Variable Kidney Failure Risk Equation (KFRE) Reference Calculator** (`src/clinical/kfre_calculator.py`):
   - High-fidelity implementation of the published, multinational-validated Tangri 4-variable equation (JAMA 2011, JAMA 2016).
   - Computes 2-year and 5-year individualized probabilities of progression to kidney failure.
   - Supports 3 explicit regional calibration baseline-survival profiles (`original_tangri`, `north_america`, `non_north_america`).
   - Strict applicability gating: explicitly restricted to CKD Stages G3–G5 ($\text{eGFR} < 60.0\text{ mL/min/1.73 m}^2$).
   - Defensive clinical boundary validation (age $\ge 18$, $\text{ACR} > 0$, $\text{eGFR} > 0$, rejection of missing/corrupted/NaN values).
2. **Kidney Progression Engine Prototype** (`src/engines/kidney_progression_engine.py`):
   - High-level orchestrator integrating longitudinal feature extraction (`extract_progression_features`) with static risk estimation (`calculate_kfre`).
   - Strict architectural separation: static KFRE applicability is decoupled from longitudinal trajectory availability, guaranteeing that longitudinal abstention does not suppress an independently valid KFRE calculation, and missing KFRE inputs do not corrupt longitudinal feature extraction.
   - Explicit clinical provenance, data completeness metrics, and zero-temporal-leakage guarantees.

---

## 2. Mathematical Formulation: Tangri 4-Variable KFRE

The Tangri 4-variable equation predicts the probability of kidney failure within a defined time horizon ($t \in \{2, 5\}\text{ years}$) based on four routine clinical variables:
- **Age** ($\text{years}$)
- **Sex** (encoded: $\text{male} = 1, \text{female} = 0$)
- **eGFR** ($\text{mL/min/1.73 m}^2$, calculated via CKD-EPI 2021)
- **Urine Albumin-to-Creatinine Ratio (UACR)** ($\text{mg/g}$)

### 2.1 Centered Linear Predictor ($\text{LP}$)

The linear predictor $\text{LP}$ is computed from centered and scaled variables as established by Tangri et al. (JAMA 2011, 2016):

$$\text{LP} = \beta_{\text{age}} \cdot \left(\frac{\text{age}}{10} - \mu_{\text{age}}\right) + \beta_{\text{sex}} \cdot (\text{male} - \mu_{\text{sex}}) + \beta_{\text{egfr}} \cdot \left(\frac{\text{eGFR}}{5} - \mu_{\text{egfr}}\right) + \beta_{\text{acr}} \cdot (\ln(\text{ACR}) - \mu_{\text{acr}})$$

Using the published regression coefficients and centering constants:

$$\begin{aligned}
\text{LP} &= -0.2201 \cdot \left(\frac{\text{age}}{10} - 7.036\right) \\
&\quad + 0.2467 \cdot (\text{male} - 0.5642) \\
&\quad - 0.5567 \cdot \left(\frac{\text{eGFR}}{5} - 7.222\right) \\
&\quad + 0.4510 \cdot (\ln(\text{ACR}) - 5.137)
\end{aligned}$$

#### Clinical Interpretation of Coefficients:
- **Age ($\beta = -0.2201$)**: Negative coefficient. Holding other markers equal, older patients exhibit lower relative hazard of reaching ESRD prior to competing mortality.
- **Male Sex ($\beta = +0.2467$)**: Positive coefficient. Male patients exhibit a higher rate of progression.
- **eGFR ($\beta = -0.5567$)**: Negative coefficient. Lower baseline eGFR steeply increases progression hazard.
- **$\ln(\text{ACR})$ ($\beta = +0.4510$)**: Positive coefficient. Logarithmic increases in albuminuria strongly accelerate renal filtration breakdown.

### 2.2 Baseline Survival Probabilities & Risk Formulation

The individual risk of progressing to kidney failure within horizon $t$ is calculated via the Cox proportional hazards transformation:

$$\text{Risk}(t) = 1 - S_0(t)^{\exp(\text{LP})}$$

where $S_0(t)$ is the baseline event-free survival probability at time horizon $t$.

---

## 3. Calibration Profiles & Regional Baselines

Baseline event rates vary substantially across health systems and geographic populations due to background mortality, screening practices, and healthcare access. NefroAI-X implements the three official published calibration baseline sets from Tangri et al. (JAMA 2016 eAppendix 2):

| Profile Name | Geographic / Cohort Context | $S_0(2\text{yr})$ | $S_0(5\text{yr})$ | Baseline 2-Yr Risk at Centering ($\text{LP}=0$) | Baseline 5-Yr Risk at Centering ($\text{LP}=0$) |
|:---|:---|:---:|:---:|:---:|:---:|
| `original_tangri` | Canadian Development Cohort (JAMA 2011) | $0.9750$ | $0.9240$ | $2.50\%$ | $7.60\%$ |
| `north_america` | North American Validation Meta-Analysis (JAMA 2016) | $0.9751$ | $0.8996$ | $2.49\%$ | $10.04\%$ |
| `non_north_america` | International Validation Meta-Analysis (JAMA 2016) | $0.9832$ | $0.9365$ | $1.68\%$ | $6.35\%$ |

### 3.1 Critical Clinical Calibration Warning
> **IMPORTANT CLINICAL GOVERNANCE NOTICE:**  
> The `non_north_america` profile represents a multinational pooled cohort from Europe, the United Kingdom, Australasia, and Asia (predominantly high-income healthcare jurisdictions in the JAMA 2016 meta-analysis).  
> **It is NOT an India-specific calibrated model.**  
> South Asian populations may exhibit different progression dynamics due to diabetic kidney disease phenotypes and environmental factors. In the absence of an officially published, independently validated Indian cohort recalibration, NefroAI-X defaults to `north_america` as recommended by international guidelines, provides `non_north_america` and `original_tangri` as explicit options, and surfaces this limitation in all clinical reports and API outputs.

---

## 4. Input Bounds, Applicability Scope & G1–G2 Gate

### 4.1 Strict Input Validation Rules

The calculator strictly verifies all clinical parameters before computing risk. If any rule is violated, calculation is rejected (`is_valid=False`, risk values set to `None`, descriptive reason recorded):

| Variable | Required Type / Range | Units | Validation Failure Consequence |
|:---|:---|:---:|:---|
| `age` | $18.0 \le \text{age} \le 120.0$ | Years | Rejected (pediatric formula required; adult KFRE invalid) |
| `sex` | `male`, `m`, `female`, `f` (case-insensitive) | Categorical | Rejected if unmappable |
| `eGFR` | $\text{Finite float} > 0.0$ | $\text{mL/min/1.73 m}^2$ | Rejected if $\le 0$, NaN, or infinite |
| `uacr` | $\text{Finite float} > 0.0$ | $\text{mg/g}$ | Rejected if $\le 0$ ($\ln(0)$ is undefined), NaN, or infinite |
| Missingness | None permitted in KFRE inputs | — | Rejected (no silent imputation permitted) |

### 4.2 Applicability Scope: CKD G3–G5 Only ($\text{eGFR} < 60.0$)

The Tangri equation was derived and validated exclusively in patients with confirmed Chronic Kidney Disease Stages G3a, G3b, G4, and G5 ($\text{eGFR} < 60.0\text{ mL/min/1.73 m}^2$).

**Why CKD Stages G1–G2 are Out-of-Scope:**
1. In populations with preserved eGFR ($\ge 60\text{ mL/min/1.73 m}^2$), the competing risk of non-renal cardiovascular mortality and non-progression vastly dominates.
2. The linear predictor in G1–G2 yields negative $\text{LP}$ values that extrapolated mathematical hazard models outside their validated domain, producing misleadingly low risks that may give clinicians a false sense of security in the presence of severe proteinuria (A3).
3. International clinical guidelines (KDIGO 2024 Section 1.4) state that risk prediction tools developed for CKD G3–G5 should not be applied to G1–G2.

**System Behavior on G1–G2 Patients:**
- If $\text{eGFR} \ge 60.0\text{ mL/min/1.73 m}^2$, the calculator outputs:
  - `is_valid = True` (the inputs are physiologically valid)
  - `is_applicable = False` (the patient is clinically outside KFRE target population)
  - `applicability_status = "OUT_OF_SCOPE_GFR_STAGE_G1_G2"`
  - `risk_2year = None`
  - `risk_5year = None`
  - `linear_predictor = None`
  - `clinical_warning = "KFRE is validated exclusively for CKD Stages G3-G5 (eGFR < 60 mL/min/1.73 m^2). Patients with eGFR >= 60 are out-of-scope."`

---

## 5. Architectural Design: KidneyProgressionEngine

`KidneyProgressionEngine` (`src/engines/kidney_progression_engine.py`) coordinates the dual capabilities of Engine 3:
1. **Longitudinal Trajectory Extraction**: Slope estimation, acute decline detection, visit spacing, and trajectory stability.
2. **KFRE Static Progression Risk Estimation**: 2-year and 5-year kidney failure risk estimation.

```
+-----------------------------------------------------------------------------------------+
|                                KidneyProgressionEngine                                  |
+-----------------------------------------------------------------------------------------+
                                   |
         +-------------------------+-------------------------+
         |                                                   |
         v                                                   v
+--------------------------------+          +----------------------------------+
| extract_progression_features() |          |         calculate_kfre()         |
+--------------------------------+          +----------------------------------+
| - Landmark date anchoring      |          | - Age, Sex, eGFR, UACR           |
| - eGFR / SCr OLS & robust slope|          | - Centering vector subtraction   |
| - Rapid decline categorization |          | - Regional calibration baseline  |
| - Abstains if visits < 2 or    |          | - Applicable only if eGFR < 60   |
|   time span < 90 days          |          | - Out-of-scope gate if eGFR >= 60|
+--------------------------------+          +----------------------------------+
         |                                                   |
         +-------------------------+-------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------------------------+
|                                ProgressionEngineResult                                  |
| - longitudinal_features: Optional[ProgressionFeatures]                                  |
| - kfre_result: Optional[KFREResult]                                                     |
| - landmark_date: Optional[date]                                                         |
| - overall_status: "SUCCESS" | "PARTIAL_LONGITUDINAL_ONLY" | "PARTIAL_KFRE_ONLY" | ...   |
| - provenance & clinical disclaimer                                                      |
+-----------------------------------------------------------------------------------------+
```

### 5.1 Decoupled Orchestration & Zero-Leakage Invariants
- **Independent Evaluation**: Longitudinal feature abstention (e.g., patient has only 1 visit or visits span $< 90$ days) does **not** invalidate an independently provided, clinically complete KFRE calculation.
- **Asynchronous Lab Handling**: Longitudinal eGFR tracking and spot urine ACR are frequently measured asynchronously. The engine allows providing explicit KFRE index inputs alongside or in place of the latest longitudinal record.
- **Landmark Anchoring**: When longitudinal records are provided, the landmark observation date is preserved, ensuring all feature extractions represent retrospective history up to that exact date with zero future leakage.

---

## 6. Verification & Test Suite Summary

### 6.1 Unit & Integration Test Breakdown

| Test Suite File | Test Scope | Tests Run | Result |
|:---|:---|:---:|:---:|
| `tests/test_kfre_calculator.py` | Centering profile, integer profile, sex encoding, calibration baselines, pediatric rejection, non-positive ACR rejection, G1–G2 applicability gate, monotonic risk ordering, bounded probabilities ($[0, 1]$) | 12 | **PASS** |
| `tests/test_kidney_progression_engine.py` | Full end-to-end orchestration, landmark date preservation, longitudinal abstention with valid KFRE, missing KFRE inputs, out-of-scope eGFR gating, clinical disclaimer integrity | 6 | **PASS** |
| `tests/test_progression_features.py` | Step 2 longitudinal slope calculation, acute decline, OLS vs robust, minimum visit constraints | 14 | **PASS** |
| `tests/test_longitudinal_simulator.py` | Step 2 deterministic longitudinal simulation, trajectory types, reproducible seed generation | 15 | **PASS** |
| **Engine 3 Subtotal** | **All Phase 6 Engine 3 Modules** | **47** | **ALL PASS** |
| **Full Repository Suite** | **All Phase 1–6 Test Suites** | **219** | **ALL PASS** (12.7s) |

### 6.2 Reference Numerical Test Verification

#### Test Profile 1: Mathematical Centering Vector ($\text{LP} = 0.0$)
- **Parameters**: $\text{Age} = 70.36\text{ yr}$, $\text{Male} = 0.5642$, $\text{eGFR} = 36.11\text{ mL/min/1.73 m}^2$, $\text{ACR} = \exp(5.137) \approx 170.2044\text{ mg/g}$.
- **Result**: $\text{LP} = 0.000000$.
- **Risks**:
  - `original_tangri`: 2-yr $= 2.500\%$, 5-yr $= 7.600\%$
  - `north_america`: 2-yr $= 2.490\%$, 5-yr $= 10.040\%$
  - `non_north_america`: 2-yr $= 1.680\%$, 5-yr $= 6.350\%$

#### Test Profile 2: Clinical Integer Vector
- **Parameters**: $\text{Age} = 70\text{ yr}$, $\text{Male} = 1$, $\text{eGFR} = 36.0\text{ mL/min/1.73 m}^2$, $\text{ACR} = 170.0\text{ mg/g}$.
- **Result**: $\text{LP} = 0.12714$.
- **Risks (`north_america`)**:
  - 2-year risk $= 2.818\%$
  - 5-year risk $= 11.321\%$

---

## 7. Protected Repository Asset Verification

Prior to and following the Step 3 implementation, all protected production artifacts and baseline data files were verified via SHA-256 byte-level checksums:

| Protected Asset | Expected SHA-256 Checksum | Observed SHA-256 Checksum | Verification Status |
|:---|:---|:---|:---:|
| `models/clinical_pipeline.joblib` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | `9217fbbe3c74207f...` | **MATCH (UNTOUCHED)** |
| `datasets/clinical/dataset_A_uci_ckd.csv` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | `147be021a0a1498d...` | **MATCH (UNTOUCHED)** |
| `models/preprocessor_Dataset_A.joblib` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | `fae81c26a23117d4...` | **MATCH (UNTOUCHED)** |
| `src/clinical_input_reliability_mechanism.py` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | `f250cfeb5629c4b3...` | **MATCH (UNTOUCHED)** |

---

## 8. Clinical, Ethical, and Regulatory Limitations

1. **Investigational CDSS Status**: This software prototype is designed strictly for research, academic evaluation, and preliminary risk stratification. It does not possess FDA 510(k), CE mark, or CDSCO clearance as a medical device.
2. **Non-Infallibility**: KFRE risk estimates reflect population-level statistical hazard equations. Individual trajectory may deviate substantially due to acute kidney injury (AKI), glomerulonephritis flares, medication changes (e.g. SGLT2i, RAS inhibitors), or cardiovascular events.
3. **Dialysis Scheduling**: A high KFRE 2-year risk (e.g. $> 40\%$) indicates strong indication for nephrology referral, vascular access planning, and transplant workup; it must never be used autonomously to initiate dialysis without clinical nephrological consultation.

---

## 9. References

1. **Tangri N, Stevens LA, Griffith J, et al.** *A predictive model for progression of chronic kidney disease to kidney failure.* **JAMA**. 2011;305(15):1553–1559. doi:10.1001/jama.2011.451
2. **Tangri N, Grams ME, Levey AS, et al.** *Multinational Assessment of Accuracy of Equations for Predicting Risk of Kidney Failure: A Meta-analysis.* **JAMA**. 2016;315(2):164–174. doi:10.1001/jama.2016.12242
3. **KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease.** *Kidney International Supplements*. 2024;105(4S):S117–S314.
