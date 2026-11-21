# NEFROAI-X — Clinical Validation & Algorithmic Verification Report

**Document Version:** 1.0.0  
**Effective Date:** November 21, 2026  
**Clinical Scope:** Chronic Kidney Disease (CKD) Risk Screening, KDIGO Staging & Trajectory Modeling  
**Mandatory Clinical Disclaimer:** NEFROAI-X is an investigational Clinical Decision Support System (CDSS) for risk triaging and screening assistance. Software verification and mathematical unit tests do **NOT** constitute medical device clearance (FDA 510(k), CE mark) or substitute for prospective clinical trials and board-certified nephrologist clinical judgment.

---

## 1. Algorithmic Formulations & Clinical Standards

NEFROAI-X implements standard international clinical nephrology guidelines:

### 1.1 CKD-EPI 2021 Race-Free eGFR Formulation
In accordance with the 2021 National Kidney Foundation (NKF) and American Society of Nephrology (ASN) Task Force recommendations, glomerular filtration rate is calculated without race coefficients:

$$\text{eGFR} = 142 \times \min\left(\frac{S_{cr}}{\kappa}, 1\right)^\alpha \times \max\left(\frac{S_{cr}}{\kappa}, 1\right)^{-1.200} \times 0.9938^{\text{Age}} \times [1.012 \text{ if Female}]$$

Where:
- For **Females**: $\kappa = 0.7$, $\alpha = -0.241$
- For **Males**: $\kappa = 0.9$, $\alpha = -0.302$
- $S_{cr}$: Serum creatinine in $\text{mg/dL}$
- $\text{Age}$: Age in years

### 1.2 KDIGO 2024 CGA Severity Matrix
Patients are categorized according to Cause (C), GFR category (G), and Albuminuria category (A):

| GFR Stage | eGFR ($\text{mL/min/1.73m}^2$) | A1 ($<30\text{ mg/g}$) | A2 ($30\text{--}300\text{ mg/g}$) | A3 ($>300\text{ mg/g}$) |
|:---:|:---:|:---:|:---:|:---:|
| **G1** | $\ge 90$ | Low Risk (Green) | Moderate Risk (Yellow) | High Risk (Orange) |
| **G2** | $60\text{--}89$ | Low Risk (Green) | Moderate Risk (Yellow) | High Risk (Orange) |
| **G3a** | $45\text{--}59$ | Moderate Risk (Yellow) | High Risk (Orange) | Very High Risk (Red) |
| **G3b** | $30\text{--}44$ | High Risk (Orange) | Very High Risk (Red) | Very High Risk (Red) |
| **G4** | $15\text{--}29$ | Very High Risk (Red) | Very High Risk (Red) | Very High Risk (Red) |
| **G5** | $<15$ | Very High Risk (Red) | Very High Risk (Red) | Very High Risk (Red) |

### 1.3 Tangri 4-Variable Kidney Failure Risk Equation (KFRE)
For patients with CKD Stage 3–5 ($eGFR < 60\text{ mL/min/1.73m}^2$):

$$P(t) = 1 - S(t)^{\exp\left(\sum \beta_i (X_i - \bar{X}_i)\right)}$$

Where $X = (\text{Age}, \text{Sex}, eGFR, \ln(uACR))$. Baseline survival $S(2\text{yr}) = 0.9832$, $S(5\text{yr}) = 0.9365$ for non-North America calibration.

---

## 2. Independent Reference Case Verification

The following independently calculated clinical test cases were executed to verify mathematical fidelity:

| Test Case | Inputs | Expected Clinical Reference | Observed System Output | Concordance |
|---|---|---|---|:---:|
| **Case 1: Normal Male** | Age 60, Male, $S_{cr} = 0.8\text{ mg/dL}$ | $eGFR \approx 101.24\text{ mL/min}$ | $101.32\text{ mL/min/1.73m}^2$ | **CONCORDANT** |
| **Case 2: Advanced Male** | Age 64, Male, $S_{cr} = 2.4\text{ mg/dL}$ | $eGFR \approx 29.49\text{ mL/min}$ | $29.39\text{ mL/min/1.73m}^2$ | **CONCORDANT** |
| **Case 3: Young Normal Female** | Age 50, Female, $S_{cr} = 0.6\text{ mg/dL}$ | $eGFR \approx 109.28\text{ mL/min}$ | $109.28\text{ mL/min/1.73m}^2$ | **CONCORDANT** |
| **Case 4: Elderly Female** | Age 70, Female, $S_{cr} = 1.8\text{ mg/dL}$ | $eGFR \approx 29.80\text{ mL/min}$ | $29.94\text{ mL/min/1.73m}^2$ | **CONCORDANT** |
| **Case 5: Pediatric Safety Guard** | Age 16, Male, $S_{cr} = 1.1\text{ mg/dL}$ | Withhold CKD-EPI (Schwartz recommended) | Computation Withheld (`PEDIATRIC_EXCLUDED`) | **CONCORDANT** |
| **Case 6: KFRE 2-Yr & 5-Yr Risk** | Age 64, Male, $eGFR = 29.39, uACR = 380$ | 2-Yr: $\approx 6.4\%$, 5-Yr: $\approx 22.5\%$ | 2-Yr: $6.38\%$, 5-Yr: $22.51\%$ | **CONCORDANT** |
| **Case 7: KFRE eGFR Boundary Guard** | Age 45, Male, $eGFR = 85.0, uACR = 15$ | Withhold KFRE ($eGFR \ge 60$) | Withheld (`eGFR >= 60 mL/min`) | **CONCORDANT** |
| **Case 8: Chronicity Guard (<90d)** | 1 Visit ($S_{cr} = 2.4$) | Flag `DISC-03` (Unverified Chronicity) | `DISC-03` triggered (Confirmatory test needed) | **CONCORDANT** |
| **Case 9: Chronicity Guard ($\ge 90\text{d}$)** | 3 Visits spanning 380 days | Clear `DISC-03`, compute trajectory | Chronicity verified, OLS slope computed | **CONCORDANT** |
| **Case 10: Cross-Analyte Incoherence** | Hemo 7.0 g/dL, PCV 46% (Rule of 3 violation) | Flag `COH-01` / `DISC-09` (Data Discordance) | Alert `COH-01` + `DISC-09` raised | **CONCORDANT** |

---

## 3. Clinical Discrepancy & Safety Guardrails (DISC-01 to DISC-10)

The system computes non-compensatory clinical discrepancy checks across engines:

- `DISC-01`: Model predicts low risk, but eGFR indicates Stage G3b/G4/G5 (False Assurance Guard).
- `DISC-02`: Model predicts high risk, but eGFR is normal with no albuminuria (Over-Diagnosis Guard).
- `DISC-03`: Single cross-sectional visit with abnormal biomarkers lacks $\ge 90\text{d}$ proof of chronicity.
- `DISC-04`: Discordance between quantitative uACR and qualitative urine dipstick albumin.
- `DISC-05`: KFRE predicts high failure risk despite stable baseline eGFR.
- `DISC-06`: TreeSHAP and LIME feature attributions disagree on primary risk driver.
- `DISC-07`: Rapid eGFR decline ($>5\text{ mL/min/1.73m}^2/\text{yr}$) indicates progressive CKD or AKI.
- `DISC-08`: Clinical Reliability Index ($\text{CRI} < 0.60$) or Conformal Prediction epistemic uncertainty $\{0, 1\}$.
- `DISC-09`: Physiological cross-analyte coherence failure (Rule of Three, BUN/Creatinine ratio).
- `DISC-10`: Severe hypertension ($\text{SBP} \ge 180\text{ mmHg}$) co-occurring with acute renal biomarker shifts.

---

## 4. Formal Boundaries: Software Verification vs. Clinical Trials

```
+-------------------------------------------------------------------------------+
|                        CLINICAL VALIDATION BOUNDARY                           |
+-------------------------------------------------------------------------------+
| [WHAT SOFTWARE TESTS PROVE]                                                  |
| 1. Mathematical equations (CKD-EPI 2021, KFRE) match reference specifications.|
| 2. Feature vectors are aligned, normalized, and leak-free.                   |
| 3. Out-of-bounds, contradictory, and pediatric inputs trigger safety gates.   |
| 4. Deterministic repeatability and data persistence are maintained.          |
+-------------------------------------------------------------------------------+
| [WHAT SOFTWARE TESTS DO NOT PROVE (REQUIRES EXTERNAL CLINICAL VALIDATION)]     |
| 1. Diagnostic efficacy across heterogeneous racial/ethnic human populations.  |
| 2. Impact on clinician decision-making in real-world emergency or clinic EHRs.|
| 3. Reduction in ESRD progression or all-cause mortality in clinical practice.|
| 4. Regulatory compliance under FDA SaMD (Software as a Medical Device) or MDR.|
+-------------------------------------------------------------------------------+
```

### Recommendation for Clinical Deployment
Before deploying in active patient care environments:
1. Conduct an IRB-approved prospective observational clinical trial comparing NEFROAI-X triaging against standard nephrology referral pathways.
2. Validate against multi-institutional electronic health record (EHR) cohorts spanning diverse geographical demographics.
3. Establish formal integration with clinical laboratory information systems (LIS) to minimize manual transcription error.
