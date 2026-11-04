# NEFROAI-X — Phase 6, Step 4: Survival Modelling & Competing-Risk Architecture

**Status:** IMPLEMENTED & VERIFIED  
**Component:** Engine 3 — Longitudinal Kidney Disease Progression Risk Prediction  
**Subpackage:** `src/clinical/survival/`  
**Test Suite Status:** 22/22 New Survival Tests Passing; 71/71 Total Engine 3 Tests Passing; 243/243 Full Repository Tests Passing

---

## 1. Executive Summary

Phase 6 Step 4 develops the survival-modelling and competing-risk architecture for **Engine 3 (Longitudinal Kidney Disease Progression Risk Prediction)**. 

While Step 3 established the published Tangri 4-variable Kidney Failure Risk Equation (KFRE) reference calculator, Step 4 builds the **cohort-ready survival modelling infrastructure** required to evaluate, tune, and benchmark empirical machine learning survival models against KFRE.

This architecture delivers five core production-grade components:
1. **Survival Dataset Contract & Invariants** (`src/clinical/survival/survival_contracts.py`):
   - Strongly-typed `SurvivalLandmarkRecord` and `SurvivalDataset` data structures.
   - Explicit event categorization: 0 = Right-Censored, 1 = Kidney Failure (KRT), 2 = Competing Death.
   - Comprehensive validation rejecting negative follow-up, events before landmark, contradictory event/censoring status, duplicate records, and feature temporal leakage.
   - Patient-level grouped train/test splitting ensuring zero patient overlap, alongside temporal cohort splitting.
2. **Modular Interpretable Cox Proportional Hazards Baseline** (`src/clinical/survival/cox_model.py`):
   - Native SciPy optimization of Cox partial log-likelihood with Breslow baseline cumulative hazard estimation.
   - Defensive checks detecting zero-variance features and near-perfect collinearity before fitting.
   - Computes hazard ratios ($\text{HR} = \exp(\beta)$), standard errors, z-scores, p-values, and 95% confidence intervals.
   - Predicts event-free survival and cumulative risk bounded strictly in $[0.0, 1.0]$.
3. **Random Survival Forest (RSF) Nonlinear Candidate** (`src/clinical/survival/rsf_model.py`):
   - Bootstrap ensemble of survival trees using log-rank splitting statistics and Nelson-Aalen / Kaplan-Meier leaf hazard estimators.
   - Fully deterministic and reproducible via explicit random seeds and hyperparameter configuration.
   - Computes out-of-bag (OOB) permutation feature importance (VIMP).
4. **Competing-Risk Data Pathway & Aalen-Johansen CIF** (`src/clinical/survival/competing_risk.py`):
   - Non-parametric Aalen-Johansen Cumulative Incidence Function (CIF) calculator accounting for competing death before kidney failure without bias.
   - Explicit `DeferredFineGrayEstimator` enforcing clinical AI safety: when `lifelines>=0.27.0` is unavailable, ordinary Cox PH or RSF are strictly prohibited from being substituted as competing-risk models.
5. **Time-Dependent Survival Evaluation Framework** (`src/clinical/survival/evaluation.py`):
   - Harrell's C-index and Uno's C-index with Inverse Probability of Censoring Weighting (IPCW).
   - Time-dependent cumulative/dynamic AUC at 2-year and 5-year horizons.
   - IPCW Brier score and risk quantile calibration assessment (expected vs. observed ratios).
   - Standardized `compare_models_with_kfre_on_cohort()` utility ensuring models are benchmarked on identical patient cohorts and landmark definitions.

---

## 2. Survival Dataset Contract & Invariants

### 2.1 Landmark Formulation

In longitudinal clinical cohorts, patients are monitored across multiple visits. Rather than fixing a single baseline at initial cohort entry, Engine 3 operates on **landmark observation dates** ($t_{\text{lm}}$):

$$\text{History: } [t_{\text{baseline}}, t_{\text{lm}}] \longrightarrow \text{Predictor Features } X(t_{\text{lm}}) \quad \Big| \quad \text{Follow-Up: } [t_{\text{lm}}, t_{\text{event}}] \longrightarrow \text{Outcome } (T, E)$$

### 2.2 Event & Censoring Classifications

| Event Code | `SurvivalEventType` Enum | Clinical Definition | Competing-Risk Status |
|:---:|:---|:---|:---|
| `0` | `RIGHT_CENSORED` | Patient completed study follow-up or was lost to follow-up without kidney failure or death. | Non-informative right censoring |
| `1` | `KIDNEY_FAILURE` | Primary outcome: initiation of maintenance dialysis, preemptive kidney transplant, or confirmed eGFR $< 15\text{ mL/min/1.73 m}^2$. | Primary endpoint |
| `2` | `COMPETING_DEATH` | Competing outcome: patient died prior to reaching kidney failure / KRT. | Competing event (precludes future KRT) |

### 2.3 Contract Validation Invariants

Any record violating any of the following invariants is rejected immediately with a `SurvivalDataValidationError`:
1. **Temporal Sequence**: $\text{baseline\_date} \le \text{landmark\_date} \le \text{follow\_up\_start\_date} \le \text{follow\_up\_end\_date}$.
2. **Non-Negative Duration**: $\text{follow\_up\_duration\_days} = (\text{follow\_up\_end\_date} - \text{follow\_up\_start\_date}).\text{days} \ge 0$.
3. **No Flag Contradictions**:
   - If `event_type == 0`: `is_censored == 1`, `event_kidney_failure == 0`, `event_death == 0`.
   - If `event_type == 1`: `is_censored == 0`, `event_kidney_failure == 1`, `event_death == 0`.
   - If `event_type == 2`: `is_censored == 0`, `event_kidney_failure == 0`, `event_death == 1`.
4. **Duplicate Rejection**: Duplicate `(patient_id, landmark_date)` records are strictly disallowed.
5. **Zero Temporal Leakage**: If `feature_timestamps` are provided, any timestamp $> \text{landmark\_date}$ triggers immediate exception.

---

## 3. Cox Proportional Hazards Model Architecture

### 3.1 Partial Log-Likelihood & Optimization

The cause-specific Cox Proportional Hazards model assumes the instantaneous hazard for patient $i$ is:

$$h(t | x_i) = h_0(t) \cdot \exp(x_i^T \beta)$$

The partial log-likelihood with an optional L2 ridge regularization penalty $\lambda \ge 0$ is:

$$\ell(\beta) = \sum_{i: E_i = 1} \left( x_i^T \beta - \ln \sum_{j \in R(T_i)} \exp(x_j^T \beta) \right) - \frac{\lambda}{2} \|\beta\|_2^2$$

where $R(T_i) = \{j : T_j \ge T_i\}$ is the risk set of individuals under observation immediately prior to time $T_i$.

Optimization is executed via SciPy's BFGS / L-BFGS-B algorithm with analytical gradients:

$$\nabla \ell(\beta) = \sum_{i: E_i = 1} \left( x_i - \frac{\sum_{j \in R(T_i)} x_j \exp(x_j^T \beta)}{\sum_{j \in R(T_i)} \exp(x_j^T \beta)} \right) - \lambda \beta$$

### 3.2 Breslow Baseline Cumulative Hazard

For each distinct event time $t_{(k)}$, the non-parametric Breslow baseline hazard increment is:

$$d\hat{H}_0(t_{(k)}) = \frac{d_{(k)}}{\sum_{j \in R(t_{(k)})} \exp(x_j^T \hat{\beta})}$$

Baseline survival is:

$$\hat{S}_0(t) = \exp\left(-\sum_{t_{(k)} \le t} d\hat{H}_0(t_{(k)})\right)$$

Predicted cumulative risk at horizon $t$ for patient $x$:

$$\text{Risk}(t | x) = 1 - \hat{S}_0(t)^{\exp(x^T \hat{\beta})}$$

### 3.3 Clinical Guardrails
> **CLINICAL INTERPRETATION NOTICE:**  
> - **Hazard Ratios (HR)** express instantaneous relative hazard rates, NOT direct cumulative probabilities of kidney failure. A hazard ratio of $2.0$ does NOT mean a patient has a $200\%$ or $2\times$ absolute probability of kidney failure by 2 years.
> - Cause-specific Cox PH treats competing deaths as right-censoring. In populations with high mortality (e.g. elderly diabetics), this can overestimate the true cumulative incidence of kidney failure.

---

## 4. Random Survival Forest (RSF) Candidate Architecture

### 4.1 Ensemble Structure
- **Bagging**: $B = \text{n\_estimators}$ survival trees fitted on bootstrap samples with replacement.
- **Node Splitting**: At each internal split, $m = \lfloor \sqrt{P} \rfloor$ features are evaluated to find the feature and threshold that maximizes the two-sample log-rank test statistic $|z|$.
- **Leaf Estimators**: Terminal nodes compute Nelson-Aalen cumulative hazard $\hat{H}_{\text{leaf}}(t)$ and Kaplan-Meier survival $\hat{S}_{\text{leaf}}(t)$.
- **Ensemble Aggregation**:
  $$\hat{S}_{\text{ensemble}}(t | x) = \frac{1}{B} \sum_{b=1}^B \hat{S}_b(t | x), \quad \text{Risk}(t | x) = 1 - \hat{S}_{\text{ensemble}}(t | x)$$

### 4.2 Out-of-Bag (OOB) Permutation Feature Importance (VIMP)
For each predictor $j$, feature values in the out-of-bag sample are permuted. The importance score is the increase in prediction error (Brier score / MSE at horizon $t$) relative to baseline unpermuted predictions.

---

## 5. Competing-Risk Handling & Fine-Gray Status

### 5.1 Aalen-Johansen Non-Parametric Cumulative Incidence Function (CIF)

When competing risks are present, the Aalen-Johansen estimator correctly quantifies the absolute probability of reaching kidney failure ($k=1$) before dying ($k=2$):

$$\hat{I}_1(t) = \sum_{t_{(l)} \le t} \hat{S}_{\text{overall}}(t_{(l-1)}) \cdot \frac{d_{1(l)}}{n_{(l)}}$$

where $\hat{S}_{\text{overall}}(t) = \prod_{t_{(l)} \le t} \left(1 - \frac{d_{1(l)} + d_{2(l)}}{n_{(l)}}\right)$ is overall survival from any event.

At all time points:

$$\hat{I}_1(t) + \hat{I}_2(t) + \hat{S}_{\text{overall}}(t) = 1.0$$

### 5.2 Fine-Gray Status & Dependency Blocker

| Component | Status | Technical Details / Blocker |
|:---|:---:|:---|
| **Competing Risk Contract** | **IMPLEMENTED** | Multi-state event typing (`SurvivalEventType`) in `survival_contracts.py`. |
| **Aalen-Johansen CIF** | **IMPLEMENTED** | Non-parametric CIF in `competing_risk.py`. |
| **Fine-Gray Data Pipeline** | **IMPLEMENTED** | `prepare_fine_gray_dataframe()` formats cohort into $(T, \epsilon, X)$ schema. |
| **Fine-Gray Subdistribution Model** | **DEFERRED** | Blocked: requires external package `lifelines>=0.27.0` (`lifelines.FineGrayFitter`). |

#### Explicit Safety Rule:
`DeferredFineGrayEstimator` raises `FineGrayDependencyUnavailableError` with explicit instructions. Cause-specific Cox regression or standard RSF are **strictly forbidden** from being approximated or labeled as competing-risk models, as doing so falsely treats competing mortality as non-informative right censoring and inflates kidney failure risk estimates.

---

## 6. Time-Dependent Evaluation Framework

The framework implements five standard survival evaluation metrics:
1. **Harrell's C-index**: Proportion of admissible pairs $(T_i < T_j, E_i = 1)$ where predicted risk is concordant ($\text{risk}_i > \text{risk}_j$).
2. **Uno's C-index**: Consistent C-index utilizing Inverse Probability of Censoring Weighting (IPCW) via Kaplan-Meier estimation of the censoring distribution $G(t)$.
3. **Time-Dependent Cumulative/Dynamic AUC**:
   $$\text{AUC}(t) = P(\text{Risk}_i > \text{Risk}_j \mid T_i \le t, E_i = 1, T_j > t)$$
4. **IPCW Brier Score**: Mean squared error between binary event status at horizon $t$ and predicted risk, weighted by $1/G(T_i)$ or $1/G(t)$.
5. **Quantile Risk Calibration**: Decile or quintile grouping computing mean predicted risk, observed event rate, Expected-to-Observed (E:O) ratio, and absolute calibration error.

---

## 7. CRIC Longitudinal Data Status & Access Restrictions

Inspection of the project environment confirms:
- **Local CRIC Availability**: **NOT PRESENT** in `datasets/` or any project subdirectory.
- **Governance Status**: The Chronic Renal Insufficiency Cohort (CRIC) dataset is a controlled-access resource governed by the NIDDK Central Repository (NIDDK-CR).
- **Access Requirements**: Requires formal Institutional Review Board (IRB) review, an executed Data Use Agreement (DUA), and formal credentialing via the NIDDK-CR portal.
- **Compliance Guarantee**: The system complies strictly with NIDDK restrictions. No unapproved web scraping or proxy access was attempted. The survival architecture is fully cohort-ready and will interface directly with CRIC upon data receipt.

---

## 8. Verification & Test Execution Summary

### 8.1 New Step 4 Unit Test Suites

| Test Suite File | Test Scope | Tests Run | Result |
|:---|:---|:---:|:---:|
| `tests/test_survival_contracts.py` | Event coding (0, 1, 2), contradictory flag rejection, negative follow-up, events before landmark, temporal leakage checks, duplicate patient-landmark rejection, patient-grouped split isolation, Aalen-Johansen CIF mathematical bounding, Fine-Gray deferred error. | 12 | **PASS** |
| `tests/test_survival_models_and_evaluation.py` | Cox PH input validation (non-positive durations, constant features, collinearity), coefficient estimation, hazard ratios, Breslow baseline, probability bounds, RSF deterministic reproducibility, RSF risk bounds and OOB VIMP, Harrell's C-index, Uno's IPCW C-index, time-dependent AUC, Brier score, quantile calibration, standardized KFRE comparison. | 10 | **PASS** |
| `tests/test_kfre_calculator.py` | Corrected reference tests: exact LP=0 risk check ($1 - S_0$), integer profile evaluation ($LP \approx 0.12714096$), independent term verification. | 14 | **PASS** |
| `tests/test_kidney_progression_engine.py` | Engine 3 prototype orchestration and landmark anchoring. | 6 | **PASS** |
| `tests/test_progression_features.py` | Longitudinal feature engineering and slope estimation. | 14 | **PASS** |
| `tests/test_longitudinal_simulator.py` | Deterministic longitudinal test simulator. | 15 | **PASS** |
| **Engine 3 Subtotal** | **All Phase 6 Engine 3 Modules** | **71** | **ALL PASS** (2.48s) |
| **Full Repository Suite** | **All Phase 1–6 Test Suites** | **243** | **ALL PASS** (32.03s) |

---

## 9. Protected Repository Asset Verification

Byte-level SHA-256 hashes of all protected baseline files were re-verified after test completion:

| Protected File Path | Expected Production SHA-256 | Current Working Copy SHA-256 | Status |
|:---|:---|:---|:---:|
| `models/clinical_pipeline.joblib` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | `9217fbbe3c74207f...` | **VERIFIED UNCHANGED** |
| `datasets/clinical/dataset_A_uci_ckd.csv` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | `147be021a0a1498d...` | **VERIFIED UNCHANGED** |
| `models/preprocessor_Dataset_A.joblib` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | `fae81c26a23117d4...` | **VERIFIED UNCHANGED** |
| `src/clinical_input_reliability_mechanism.py` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | `f250cfeb5629c4b3...` | **VERIFIED UNCHANGED** |

---

## 10. Implemented vs. Deferred Status

| Feature / Architectural Component | Implementation Status | Technical Location |
|:---|:---:|:---|
| **Survival Landmark Contract & Invariants** | **IMPLEMENTED** | `src/clinical/survival/survival_contracts.py` |
| **Competing Event Classification (0, 1, 2)** | **IMPLEMENTED** | `src/clinical/survival/survival_contracts.py` |
| **Patient-Grouped Train/Test Splitting** | **IMPLEMENTED** | `src/clinical/survival/survival_contracts.py` |
| **Temporal Cohort Splitting** | **IMPLEMENTED** | `src/clinical/survival/survival_contracts.py` |
| **Cause-Specific Cox Proportional Hazards Model** | **IMPLEMENTED** | `src/clinical/survival/cox_model.py` |
| **Breslow Baseline Cumulative Hazard Estimator** | **IMPLEMENTED** | `src/clinical/survival/cox_model.py` |
| **Random Survival Forest Ensemble & OOB VIMP** | **IMPLEMENTED** | `src/clinical/survival/rsf_model.py` |
| **Aalen-Johansen CIF Estimator** | **IMPLEMENTED** | `src/clinical/survival/competing_risk.py` |
| **Fine-Gray Data Preparation Pipeline** | **IMPLEMENTED** | `src/clinical/survival/competing_risk.py` |
| **Time-Dependent Evaluation (C-index, AUC, Brier)** | **IMPLEMENTED** | `src/clinical/survival/evaluation.py` |
| **Quantile Calibration Assessment** | **IMPLEMENTED** | `src/clinical/survival/evaluation.py` |
| **Standardized KFRE Comparison Framework** | **IMPLEMENTED** | `src/clinical/survival/evaluation.py` |
| **Corrected Step 3 Numerical KFRE Tests** | **IMPLEMENTED** | `tests/test_kfre_calculator.py` |
| **Parametric Fine-Gray Model Optimization** | **DEFERRED** | Requires external package `lifelines>=0.27.0`. |
| **Model Fitting on Real CRIC Cohort** | **DEFERRED** | Pending NIDDK Data Use Agreement (DUA) approval. |
| **Streamlit Progression Card UI Integration** | **DEFERRED** | Scheduled for Step 5. |

---

## 11. Requirements for Real-Cohort Model Training & Validation

When approved real-world longitudinal cohorts (e.g. CRIC) become available:
1. Ingest raw longitudinal laboratory encounters and map to `SurvivalLandmarkRecord`.
2. Anchor landmark time at 1 year post-enrollment ($t_{\text{lm}} = 1.0\text{ yr}$) to ensure sufficient retrospective observations for slope estimation.
3. Perform patient-level grouped 5-fold cross-validation (`patient_grouped_train_test_split()`) to tune Cox L2 penalties and RSF tree depth.
4. Fit cause-specific Cox PH and Random Survival Forest strictly on training partitions.
5. Benchmark against Tangri KFRE (`original_tangri`, `north_america`, `non_north_america`) on the identical held-out test cohort.
6. Evaluate Harrell's C-index, Uno's C-index, time-dependent AUC at 2 and 5 years, and IPCW Brier scores with 95% bootstrap confidence intervals.
