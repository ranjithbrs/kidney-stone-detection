# NEFROAI-X — Phase 6, Step 5: Survival Algorithm Verification, Competing-Risk Evaluation & Cohort Readiness

**Status:** IMPLEMENTED & MATHEMATICALLY VERIFIED  
**Component:** Engine 3 — Longitudinal Kidney Disease Progression Risk Prediction  
**Subpackage:** `src/clinical/survival/`  
**Test Suite Status:** 18/18 New Verification Tests Passing; 89/89 Engine 3 Tests Passing; 261/261 Full Repository Tests Passing

---

## 1. Executive Summary

Phase 6 Step 5 performs a rigorous statistical verification, mathematical validation, and cohort-readiness audit of the survival analysis algorithms developed in Step 4.

The primary objective was to independently establish whether the custom algorithms (Cox Proportional Hazards, Random Survival Forest, Aalen–Johansen Cumulative Incidence Function, and Time-Dependent Evaluation framework) adhere to published mathematical formulas, handle edge cases correctly (ties, zero events, all-censored, competing risks), and preserve clinical AI safety boundaries.

### Summary of Component Statuses

| Component | Status Label | Verification Method |
|:---|:---:|:---|
| **Cox PH Likelihood & Breslow Tie Handling** | **MATHEMATICALLY VERIFIED** | Hand-calculated analytical log-likelihood ($\ell = -\ln 80$), gradient ($+0.9$), information ($2.365$). |
| **Cox Observed Information Matrix & SEs** | **MATHEMATICALLY VERIFIED** | Analytical second-moment Hessian $I(\hat{\beta})^{-1}$ with singular matrix rejection. |
| **Breslow Cumulative Baseline Hazard** | **MATHEMATICALLY VERIFIED** | Exact step-down increments; verified monotonic non-decreasing hazard and non-increasing survival. |
| **RSF Log-Rank Splitting & Leaf Estimators** | **MATHEMATICALLY VERIFIED** | Exact hypergeometric log-rank score derivation; Nelson-Aalen hazard & Kaplan-Meier leaf tests. |
| **RSF Out-Of-Bag (OOB) Permutation VIMP** | **MATHEMATICALLY VERIFIED** | True OOB evaluation strictly isolating in-bag training observations; signal vs noise verification. |
| **Aalen–Johansen Competing-Risk CIF** | **MATHEMATICALLY VERIFIED** | Exact 4-patient hand derivation; verified $\text{CIF}_1(t) + \text{CIF}_2(t) + S(t) = 1.0$ identity with ties. |
| **Fine-Gray Subdistribution Model** | **DEFERRED** | Documented dependency blocker (`lifelines>=0.27.0` not installed); no unsafe Cox/RSF proxy substitution. |
| **Time-Dependent Discrimination & Brier** | **MATHEMATICALLY VERIFIED** | Exact concordance fixtures ($C=1.0$ and $C=0.0$), dynamic AUC, and IPCW Brier score. |
| **Risk Quantile Calibration & Slope/Intercept** | **MATHEMATICALLY VERIFIED** | Binned Kaplan-Meier observed event rates with Greenwood SEs and logistic calibration slope/intercept. |
| **Standardized KFRE Cohort Comparison** | **MATHEMATICALLY VERIFIED** | Strict filtering for KFRE-eligible patients ($eGFR < 60$), explicit reporting of excluded ineligibles without silent imputation. |
| **Clinical Progression Model Training** | **BLOCKED PENDING REAL COHORT** | CRIC longitudinal data unavailable locally; no training permitted on synthetic simulator. |
| **Clinical Decision Support System (SaMD)** | **NOT CLINICALLY EVALUATED** | Research prototype software; SaMD regulatory clearance and clinical efficacy not evaluated. |

---

## 2. Defects Identified & Corrections Made

During this audit, three mathematical and operational defects were identified and corrected:

### Defect 1: Breslow Tie Handling in Cox Partial Log-Likelihood
- **Issue:** The initial implementation sorted follow-up times ascending and used `np.cumsum` from right to left without grouping tied event times. When multiple events occurred at the exact same timestamp ($t_1 = t_2$), the second event's risk set incorrectly excluded the first event, violating Breslow's tie specification.
- **Correction:** Implemented explicit grouping by distinct event times $\tau_k$. Used `np.searchsorted(t_sorted, tau_k, side="left")` to find the exact start index of the shared risk set $R(\tau_k)$. All $d_k$ tied events at $\tau_k$ now share the exact same risk set denominator and weighted covariate sum.
- **Verification:** Verified against an exact analytical 5-patient tied fixture ($t = [1, 2, 2, 3, 4]$, events at $t=1, 2, 2, 4$), confirming $\ell(0) = -\ln(80) \approx -4.38203$, gradient $= +0.9$, and observed information $= 2.365$.

### Defect 2: In-Bag Contamination in RSF Variable Importance (VIMP)
- **Issue:** RSF `compute_feature_importance` previously evaluated the ensemble across the entire dataset `X_arr`, contaminating out-of-bag feature importance with in-bag training observations.
- **Correction:** Rewrote `compute_feature_importance` to strictly isolate $\text{OOB}_b$ sample indices for each tree $b$. Permutations are applied strictly within $\text{OOB}_b$, and the baseline versus permuted prediction error is averaged only across trees where the sample was genuinely out-of-bag.
- **Verification:** Verified on a signal-versus-noise fixture that informative markers receive positive importance while random noise receives zero/near-zero importance.

### Defect 3: Silent Risk Imputation in KFRE Cohort Comparison
- **Issue:** `compare_models_with_kfre_on_cohort()` previously assigned a hardcoded risk of `0.001` to patients with $\text{eGFR} \ge 60\text{ mL/min/1.73 m}^2$ (CKD G1–G2), silently imputing risk for clinically out-of-scope individuals.
- **Correction:** Replaced silent imputation with strict eligibility filtering. All patients with $\text{eGFR} \ge 60$, pediatric age, or missing/non-positive ACR are excluded from the comparison, the count of excluded ineligibles is explicitly recorded (`n_ineligible_excluded`), and survival models and KFRE are benchmarked on the identical eligible partition.
- **Verification:** Unit test `test_18_kfre_cohort_and_horizon_consistency` confirms that ineligible patients are excluded without imputation.

---

## 3. Verified Algorithm Details

### 3.1 Cox Proportional Hazards Model
- **Likelihood Equation:**
  $$\ell(\beta) = \sum_{k=1}^K \left[ \sum_{i \in D_k} x_i^T \beta - d_k \ln \sum_{j \in R(\tau_k)} \exp(x_j^T \beta) \right] - \frac{\lambda}{2} \|\beta\|_2^2$$
- **Gradient Equation:**
  $$\nabla \ell(\beta) = \sum_{k=1}^K \left[ \sum_{i \in D_k} x_i - d_k \frac{S_1(\tau_k)}{S_0(\tau_k)} \right] - \lambda \beta$$
- **Observed Information Matrix:**
  $$I(\beta) = \sum_{k=1}^K d_k \left[ \frac{S_2(\tau_k)}{S_0(\tau_k)} - \left(\frac{S_1(\tau_k)}{S_0(\tau_k)}\right) \left(\frac{S_1(\tau_k)}{S_0(\tau_k)}\right)^T \right] + \lambda I$$
- **Standard Errors:** $\text{SE}(\hat{\beta}_j) = \sqrt{[I(\hat{\beta})^{-1}]_{jj}}$. Optimization non-convergence or information matrix singularity ($\text{cond} > 10^{12}$) raises `SurvivalModelError` immediately, preventing invalid statistical inferences.
- **Baseline Cumulative Hazard:**
  $$\hat{H}_0(t) = \sum_{\tau_k \le t} \frac{d_k}{\sum_{j \in R(\tau_k)} \exp(x_j^T \hat{\beta})}, \quad \hat{S}_0(t) = \exp(-\hat{H}_0(t))$$

### 3.2 Random Survival Forest (RSF)
- **Model Type:** Explicitly classified as `cause_specific_survival`.
- **Log-Rank Splitting:** Two-sample log-rank test statistic $|z|$ computed via exact hypergeometric variance:
  $$z = \frac{\sum_i (d_{1i} - n_{1i} \frac{d_i}{n_i})}{\sqrt{\sum_i \frac{n_{1i} n_{2i} d_i (n_i - d_i)}{n_i^2 (n_i - 1)}}}$$
- **Terminal Leaves:** Step-down Kaplan-Meier survival $\hat{S}_{\text{leaf}}(t) = \prod_{t_k \le t} (1 - d_k / n_k)$ and Nelson-Aalen cumulative hazard $\hat{H}_{\text{leaf}}(t) = \sum_{t_k \le t} d_k / n_k$.
- **Ensemble Aggregation:** $\hat{S}(t | x) = \frac{1}{B} \sum_{b=1}^B \hat{S}_b(t | x)$, $\text{Risk}(t | x) = 1 - \hat{S}(t | x)$, bounded in $[0, 1]$.

### 3.3 Aalen–Johansen Competing-Risk Cumulative Incidence
- **Non-Parametric Estimation:**
  $$\hat{I}_1(t) = \sum_{\tau_k \le t} \hat{S}_{\text{overall}}(\tau_{k-1}) \cdot \frac{d_{1k}}{n_k}$$
  where $\hat{S}_{\text{overall}}(t) = \prod_{\tau_k \le t} (1 - \frac{d_{1k} + d_{2k}}{n_k})$.
- **Mathematical Identity:** $\hat{I}_{\text{kf}}(t) + \hat{I}_{\text{death}}(t) + \hat{S}_{\text{overall}}(t) = 1.0$ holds within $10^{-5}$ floating tolerance across all time horizons, even with simultaneous tied events.

---

## 4. Competing-Risk Interpretation Boundaries

To prevent clinical misinterpretation, four distinct survival concepts are strictly demarcated:

1. **Aalen–Johansen Estimator:** Non-parametric population-level CIF estimator. It does not accept individual patient covariates and cannot provide individualized predictions.
2. **Cause-Specific Cox Model:** Models instantaneous hazard $h_k(t | x)$. Competing events (death) are removed from the risk set at death. It evaluates relative hazard, NOT subdistribution cumulative incidence.
3. **Fine–Gray Model:** Models the subdistribution hazard $\bar{h}_k(t | x)$ directly. **Currently DEFERRED** pending external library `lifelines>=0.27.0`. Standard Cox PH and RSF are strictly prohibited from being substituted as competing-risk models.
4. **Personalized Competing-Risk Prediction:** Requires a fitted subdistribution hazard or multi-state model. Marked as **DEFERRED**. Ordinary Kaplan-Meier failure probabilities ($1 - S_{\text{KM}}$) are NEVER used as substitutes for cumulative incidence under competing risks.

---

## 5. Evaluation Framework Upgrades

1. **Discrimination Estimands:**
   - Cause-Specific Harrell's C-index: Pairs $(T_i < T_j, E_i = 1)$ evaluated by relative risk score; competing deaths censored at death date.
   - Cause-Specific Uno's C-index: Incorporates Inverse Probability of Censoring Weighting (IPCW) via censoring distribution $G(t)$.
2. **Time-Dependent Dynamic AUC:**
   - Evaluated at $t \in \{2, 5\}\text{ years}$.
   - Cases: Experienced primary kidney failure at or before $t$ ($T_i \le t, E_i = 1$).
   - Controls: Remained alive and event-free beyond $t$ ($T_j > t$).
3. **IPCW Brier Score:** Mean squared prediction error at horizon $t$ adjusted for right-censoring weights $1/G(T_i)$ and $1/G(t)$.
4. **Quantile Calibration:**
   - Replaced naive complete-case proportion with non-parametric Kaplan-Meier observed event rate within each quantile group, accounting for internal right-censoring.
   - Computes Greenwood standard errors and 95% confidence intervals.
   - Computes logistic calibration slope and intercept via logit regression: $\text{logit}(P(Y=1)) = \alpha + \beta \cdot \text{logit}(\hat{p})$. Ideal: $\alpha = 0.0, \beta = 1.0$.

---

## 6. CRIC Longitudinal Data Readiness & Access Governance

| Item | Status / Finding | Governance & Implementation Details |
|:---|:---:|:---|
| **Local Availability** | **NOT PRESENT** | Confirmed absent from `datasets/` and all project subdirectories. |
| **Governance Entity** | NIDDK Central Repository (NIDDK-CR) | Controlled-access repository requiring institutional credentialing. |
| **Access Requirements** | Blocked | Requires IRB protocol approval and an executed Data Use Agreement (DUA). |
| **Required Biomarker Fields** | Pre-specified | Repeated serum creatinine (`LBXSCR`), UACR (`URDACT`), eGFR. |
| **Required Outcome Fields** | Pre-specified | Maintenance dialysis start date, kidney transplant date, all-cause death date. |
| **Training Mandate** | **BLOCKED** | In accordance with clinical AI ethics, no survival models are trained on simulator data. |

---

## 7. Verification Test Execution Summary

```powershell
# 1. New Survival Statistical Verification Suite
.venv\Scripts\python.exe -m unittest tests/test_survival_statistical_verification.py
# Result: 18 / 18 PASS in 0.633s

# 2. All Engine 3 Test Suites
.venv\Scripts\python.exe -m unittest tests/test_survival_contracts.py tests/test_survival_models_and_evaluation.py tests/test_survival_statistical_verification.py tests/test_kfre_calculator.py tests/test_kidney_progression_engine.py tests/test_progression_features.py tests/test_longitudinal_simulator.py
# Result: 89 / 89 PASS in 3.239s

# 3. Full Repository Regression Suite
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
# Result: 261 / 261 PASS in 35.627s
```

All 261 tests pass with zero errors and zero failures.

---

## 8. Protected Repository Asset Verification

Byte-level SHA-256 hashes of all protected files remain identical to baseline:

| Protected File Path | Expected Production SHA-256 | Current Working Copy SHA-256 | Status |
|:---|:---|:---|:---:|
| `models/clinical_pipeline.joblib` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | **VERIFIED UNCHANGED** |
| `datasets/clinical/dataset_A_uci_ckd.csv` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | **VERIFIED UNCHANGED** |
| `models/preprocessor_Dataset_A.joblib` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | **VERIFIED UNCHANGED** |
| `src/clinical_input_reliability_mechanism.py` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | **VERIFIED UNCHANGED** |

---

## 9. Remaining Limitations

1. **Parametric Fine-Gray Estimator Deferred:** Direct modeling of the subdistribution hazard requires external library `lifelines>=0.27.0`.
2. **Absence of Real Empirical Validation:** Predictive accuracy metrics (e.g. C-index $> 0.80$) cannot be reported without access to an approved real-world longitudinal cohort.
3. **Streamlit UI Deferred:** Engine 3 progression and survival visual cards will be wired in Phase 6 Step 6.
