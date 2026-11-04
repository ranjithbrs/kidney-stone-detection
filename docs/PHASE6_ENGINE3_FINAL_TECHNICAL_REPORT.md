# NEFROAI-X — Phase 6: Engine 3 Final Technical Report
## Longitudinal Kidney Disease Progression Risk Prediction Subsystem

**Subsystem Status:** SOFTWARE ENGINEERING COMPLETE — RESEARCH PROTOTYPE  
**Clinical Validation Status:** BLOCKED — APPROVED LONGITUDINAL COHORT REQUIRED  
**Regulatory Status:** Investigational Clinical Decision Support System (CDSS) — Not Cleared for Definitive Diagnosis  
**Repository:** `ranjithbrs/kidney-stone-detection`  
**Base Commit:** `64b831a`  
**Environment:** Python 3.10.0 (`.venv\Scripts\python.exe`)

---

## 1. Complete Engine 3 Architecture

Engine 3 provides an end-to-end research subsystem for evaluating future kidney function deterioration over multi-year horizons (2-year and 5-year). It unites time-aware laboratory observation history, descriptive and mixed-effects filtration trajectories, established baseline risk equations, survival analysis, and competing-risk cumulative incidence.

```
+-------------------------------------------------------------------------------------------------------+
|                                    NEFROAI-X ENGINE 3 ARCHITECTURE                                    |
+-------------------------------------------------------------------------------------------------------+

        +-----------------------------------+        +-----------------------------------+
        |   Longitudinal Clinical Records   |        |    Explicit Index KFRE Inputs     |
        |  (Patient History / EHR / CRIC)   |        |       (Age, Sex, eGFR, UACR)      |
        +-----------------+-----------------+        +-----------------+-----------------+
                          |                                            |
                          v                                            v
        +-----------------------------------+        +-----------------------------------+
        |  Chronology & Landmarking Guard   |        |   Tangri 4-Variable Calculator    |
        |  (Strict Landmarking <= t_lm)     |        |   (Regional Calibration Profiles) |
        +-----------------+-----------------+        +-----------------+-----------------+
                          |                                            |
                          v                                            |
        +-----------------------------------+                          |
        | Time-Aware Feature Extractor      |                          |
        | (KDIGO 90d Sufficiency Gate)      |                          |
        +--------+-----------------+--------+                          |
                 |                 |                                   |
                 v                 v                                   |
        +----------------+ +----------------+                          |
        |   OLS Slope    | | Population LMM |                          |
        |  (Descriptive) | | (Empirical     |                          |
        |                | |  Bayes BLUP)   |                          |
        +--------+-------+ +-------+--------+                          |
                 |                 |                                   |
                 +--------+--------+                                   |
                          |                                            |
                          v                                            v
        +--------------------------------------------------------------+----------------+
        |                 KIDNEY PROGRESSION ENGINE ORCHESTRATOR                        |
        |               (src/engines/kidney_progression_engine.py)                      |
        +-------------------------------+-----------------------------------------------+
                                        |
      +---------------------------------+---------------------------------+
      |                                 |                                 |
      v                                 v                                 v
+-----------------------+     +-----------------------+     +---------------------------+
| Survival Inference    |     | Competing-Risk Engine |     | Clinical Reliability Gate |
| - Cause-Specific Cox  |     | - Aalen-Johansen CIF  |     | - CD-CIRPVM CRI Scoring   |
| - Random Survival     |     | - Cause-Specific CIF  |     | - Conformal Abstention    |
|   Forest (RSF)        |     |   Hazard Integration  |     | - Physiological Clamping  |
+-----------+-----------+     +-----------+-----------+     +-------------+-------------+
            |                             |                               |
            +-----------------------------+-------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |       ProgressionEngineResult         |
                      | - Longitudinal Trajectory & LMM       |
                      | - KFRE Baseline Risk (2y, 5y)         |
                      | - Competing-Risk Profile              |
                      | - Clinical Reliability Index (CRI)    |
                      | - Risk Factor Attributions            |
                      | - Selective Abstention Verdict        |
                      +---------------------------------------+
```

---

## 2. Data Flow & Module Responsibilities

| Module Path | Primary Responsibility | Clinical/Algorithmic Role |
|---|---|---|
| [`src/engines/kidney_progression_engine.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/engines/kidney_progression_engine.py) | Engine Orchestrator | Coordinates observation validation, trajectory estimation, KFRE reference calculation, survival inference, and reliability checks into a unified result contract. |
| [`src/data_sources/longitudinal_loader.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/data_sources/longitudinal_loader.py) | Cohort Ingestion & Landmarking | Standardizes longitudinal visits, enforces biological bounds, performs leak-free landmark cohort extraction, and provides the CRIC ingestion interface. |
| [`src/clinical/progression_features.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/progression_features.py) | Feature Engineering | Extracts KDIGO-compliant longitudinal features (eGFR delta, UACR progression ratio, hemodynamic variability) and enforces KDIGO 90-day chronicity gates. |
| [`src/clinical/lmm_trajectory.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/lmm_trajectory.py) | Mixed-Effects Trajectory Modeling | Fits population linear mixed-effects models and estimates patient-specific Empirical Bayes (BLUP) random slopes with 95% confidence intervals. |
| [`src/clinical/kfre_calculator.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/kfre_calculator.py) | KFRE Reference Calculation | Computes Tangri 4-variable failure risk over 2- and 5-year horizons with regional calibration profiles (North America, non-North America, original Tangri). |
| [`src/clinical/survival/survival_contracts.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/survival_contracts.py) | Survival Contracts & Splits | Implements `SurvivalLandmarkRecord`, `SurvivalDataset`, and patient-grouped / temporal train-test partitioning. |
| [`src/clinical/survival/cox_model.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/cox_model.py) | Cause-Specific Cox PH | Interpretable proportional hazards baseline with exact Breslow tied-event partial likelihood, ridge regularization, and baseline cumulative hazard. |
| [`src/clinical/survival/rsf_model.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/rsf_model.py) | Random Survival Forest | Non-linear ensemble candidate with log-rank split criteria, Nelson–Aalen ensemble cumulative hazard, and out-of-bag variable importance (VIMP). |
| [`src/clinical/survival/competing_risk.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/competing_risk.py) | Competing-Risk Architecture | Non-parametric Aalen–Johansen population CIF, cause-specific hazard integration for personalized CIF, and Fine-Gray dependency blockers. |
| [`src/clinical/survival/evaluation.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/evaluation.py) | Survival Evaluation & Calibration | Harrell/Uno C-index, dynamic cumulative AUC, IPCW Brier score, Aalen–Johansen quantile calibration, and jackknife pseudo-observation regression. |
| [`src/data_sources/longitudinal_simulator.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/data_sources/longitudinal_simulator.py) | Deterministic Test Simulator | Generates controlled mathematical test fixtures with explicit provenance tags (`SYNTHETIC_TEST_FIXTURE_NEFROAI_X`). |

---

## 3. Longitudinal Data Contracts

Defined in [`src/data_sources/longitudinal_loader.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/data_sources/longitudinal_loader.py):

- **`LongitudinalVisit`**: Represents a single clinical encounter.
  - Mandatory: `visit_id`, `patient_id`, `timestamp`.
  - Continuous analytes: `serum_creatinine`, `egfr`, `uacr`, `systolic_bp`, `diastolic_bp`, `hba1c`, `serum_glucose`.
  - Covariates: Arbitrary dictionary for concomitant medications or comorbidities.
  - Quality tracking: `is_valid`, `validation_warnings`.
- **`LongitudinalPatientHistory`**: Full chronological patient history.
  - `patient_id`, `baseline_age`, `sex`, `diabetes_history`, `hypertension_history`.
  - `visits`: Monotonically ordered list of `LongitudinalVisit`.
  - `event_type`: Primary outcome (0 = Right-Censored, 1 = Kidney Failure, 2 = Competing Death).
  - `follow_up_duration_years`: Total follow-up from baseline.
  - Method `to_progression_record()`: Seamlessly transforms to `LongitudinalPatientRecord` for feature extraction.
- **`LongitudinalCohort`**: Multi-patient collection.
  - Method `create_landmark_survival_dataset(landmark_time, followup_horizon_years, min_prior_observations)`: Filters strictly $\le \text{landmark\_time}$ and builds a leak-free `SurvivalDataset` with forward prospective survival targets.

---

## 4. Feature Engineering & Quality Controls

Implemented in [`src/clinical/progression_features.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/progression_features.py):

1. **Chronology Validation**: Duplicate timestamps and non-monotonic sequences trigger structured abstention (`NON_MONOTONIC_TIMESTAMPS`).
2. **KDIGO 90-Day Sufficiency Gate**: Minimum 2 observations spanning $\ge 90$ days required to differentiate chronic progression from acute kidney injury (AKI).
3. **On-the-Fly eGFR Calculation**: If `egfr` is missing but `serum_creatinine` is valid, calculated dynamically using CKD-EPI 2021 race-free equation.
4. **Descriptive eGFR Trajectory**:
   - `egfr_historical_slope`: Ordinary Least Squares (OLS) annual rate of decline (requires $\ge 3$ valid points spanning $\ge 365$ days).
   - `egfr_recent_slope`: Trajectory over the most recent 12–24 months.
   - `egfr_recent_acceleration`: Change in slope between early and recent observation windows.
   - `egfr_variability_cv`: Coefficient of variation of eGFR values.
5. **Albuminuria Exposure**:
   - `uacr_time_weighted_mean`: Trapezoidal integration over time intervals.
   - `uacr_progression_ratio`: Ratio of latest UACR to baseline UACR.

---

## 5. eGFR Trajectory Methodology: Descriptive OLS vs Population LMM

Engine 3 provides two complementary trajectory models:

| Dimension | Descriptive OLS Slope | Population Linear Mixed-Effects Model (LMM) |
|---|---|---|
| **Primary File** | `src/clinical/progression_features.py` | `src/clinical/lmm_trajectory.py` |
| **Model Type** | Independent univariate ordinary least squares | Repeated-measures random intercept & random slope |
| **Equation** | $\min \sum_j (y_{ij} - (\alpha_i + \beta_i t_{ij}))^2$ | $y_{ij} = (\beta_0 + u_{0i}) + (\beta_1 + u_{1i}) t_{ij} + \varepsilon_{ij}$ |
| **Shrinkage** | None (noisy with few points) | Empirical Bayes (BLUP) shrinkage towards population mean |
| **Uncertainty** | Residual standard error (if $n \ge 3$) | Standard error and 95% prediction interval: $[\hat{\beta}_1 + \hat{u}_{1i} \pm 1.96 \cdot \text{SE}]$ |
| **Eligibility** | $\ge 3$ visits spanning $\ge 365$ days | $\ge 3$ visits spanning $\ge 180$ days |
| **Ineligible Action** | Abstains on slope (`INSUFFICIENT_POINTS`) | Shrinks to population fixed slope with wide uncertainty interval |

---

## 6. Tangri 4-Variable KFRE Reference Methodology

Implemented in [`src/clinical/kfre_calculator.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/kfre_calculator.py):

- **Variables**: Age, biological sex, eGFR (mL/min/1.73 m2), and UACR (mg/g).
- **Linear Predictor**:
  $$\text{LP} = -0.2201 \cdot (\text{age}/10 - 7.0356) + 0.2467 \cdot (\text{male} - 0.5642) - 0.5567 \cdot (\text{eGFR}/5 - 7.222) + 0.4510 \cdot (\ln(\text{UACR}) - 5.137)$$
- **Predicted Failure Probability**:
  $$P(T \le t) = 1 - S_0(t)^{\exp(\text{LP})}$$
- **Regional Baselines**:
  - `north_america`: $S_0(2\text{y}) = 0.9832$, $S_0(5\text{y}) = 0.9365$
  - `non_north_america`: $S_0(2\text{y}) = 0.9770$, $S_0(5\text{y}) = 0.9240$
  - `original_tangri` (JAMA 2011): $S_0(2\text{y}) = 0.9750$, $S_0(5\text{y}) = 0.9240$
- **Eligibility Guardrails**: Applicable strictly to adult patients (age $\ge 18$) with established CKD G3–G5 ($\text{eGFR} < 60$ mL/min/1.73 m2).

---

## 7. Machine Learning Survival Models: Cox PH and Random Survival Forest

Engine 3 supports two survival model candidates:

1. **Cause-Specific Cox Proportional Hazards Model** ([`src/clinical/survival/cox_model.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/cox_model.py)):
   - Baseline interpretable model.
   - Exact Breslow tied-event partial likelihood with analytical gradients and Hessian.
   - Ridge $L_2$ regularization for numerical stability under collinearity.
   - Breslow step-function baseline cumulative hazard estimation ($H_0(t)$).
2. **Random Survival Forest** ([`src/clinical/survival/rsf_model.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/rsf_model.py)):
   - Nonlinear tree ensemble candidate.
   - Log-rank split test maximizing survival difference between daughter nodes.
   - Nelson–Aalen cumulative hazard estimation in terminal leaf nodes.
   - Out-of-bag (OOB) permutation variable importance (VIMP).

---

## 8. Competing-Risk Methodology & Personalized CIF

### 8.1 Estimand Separation
Engine 3 strictly distinguishes between:
1. **Cause-Specific Net Risk** ($1 - S_{\text{KM}}(t)$): Treats competing deaths as censored; measures net risk in a hypothetical world where death is eliminated.
2. **Actual Cumulative Incidence** ($\text{CIF}_1(t)$): Measures real-world probability of kidney failure before death.

Because competing events are absorbing states, $\text{CIF}_1(t) \le 1 - S_{\text{KM}}(t)$ with strict inequality whenever deaths occur.

### 8.2 Implementation Pathways
1. **Population Benchmark CIF**: Computed via `calculate_aalen_johansen_cif(dataset, horizons)` using non-parametric step functions.
2. **Personalized CIF Model (`CauseSpecificCumulativeIncidenceModel`)**:
   - Fits Model 1 (Kidney Failure hazard $\Lambda_{1i}$) and Model 2 (Competing Death hazard $\Lambda_{2i}$).
   - Integrates product-limit survival numerically:
     $$\widehat{\text{CIF}}_{1i}(t) = \sum_{k: \tau_k \le t} \hat{S}_{\text{overall}, i}(\tau_{k-1}) \cdot \left[1 - \exp(-\Delta \hat{\Lambda}_{1i}(\tau_k))\right] \cdot \exp(-0.5 \Delta \hat{\Lambda}_{2i}(\tau_k))$$
   - Enforces $\widehat{\text{CIF}}_{1i}(t) + \widehat{\text{CIF}}_{2i}(t) \le 1.0$ and $\text{net\_risk} \ge \text{CIF}_1(t)$.
3. **Fine-Gray Status**: External dependency (`lifelines.FineGrayFitter`) is uninstalled. Explicitly managed via `DeferredFineGrayEstimator`, raising informative errors rather than substituting unrelated models.

---

## 9. Evaluation & Competing-Risk Calibration

Implemented in [`src/clinical/survival/evaluation.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/survival/evaluation.py):

1. **Quantile Calibration**:
   - `calculate_competing_risk_calibration_by_quantiles`: Evaluates observed cumulative incidence using Aalen–Johansen in predicted risk bins.
   - Large-sample standard errors via Choudhury (2002) / Aalen (1978) formula, which collapses identically to Greenwood's formula when no competing deaths are present.
2. **Jackknife Pseudo-Observation Calibration Slope & Intercept**:
   - Replaces biased complete-case logistic regression.
   - Jackknife pseudo-values: $\theta_i(t) = N \hat{I}_1(t) - (N - 1) \hat{I}_1^{(-i)}(t)$.
   - Linear regression on probability scale: $\theta_i = \alpha + \beta \hat{p}_i$.
   - Sample mean identity: $\frac{1}{N}\sum \theta_i(t) \equiv \hat{I}_1(t)$ (verified to machine tolerance).
   - $\beta = 1.000$ indicates optimal calibration slope; $\alpha = 0.000$ indicates optimal calibration-in-the-large.

---

## 10. Clinical Explainability & Reliability Integration (CD-CIRPVM)

Integrated with candidate invention `ClinicalInputReliabilityMechanism`:

1. **Magnitude-Inferred Dimensional Reconciliation (MIDR)**: Automatically detects and reconciles clinical units (e.g. $\mu\text{mol/L}$ vs $\text{mg/dL}$ for creatinine, $\text{g/L}$ vs $\text{mg/dL}$ for hemoglobin).
2. **Clinical Reliability Index (CRI)**: Continuous data quality score ($0.0 - 1.0$) penalizing missingness and physiological boundary violations.
3. **Selective Abstention Gate**: When $\text{CRI} < 0.60$, automated progression predictions are withheld (`UNRELIABLE_INPUT_ABSTAIN`) with detailed audit logs.
4. **Risk Factor Attribution**: Identifies rapid progressors ($<-5$ mL/min/year decline), advanced baseline damage (G4/G5), severe albuminuria (A3), and uncontrolled hemodynamics.

---

## 11. Data Leakage Safeguards

1. **Strict Landmark Cut-off**: In both feature extraction and cohort generation, only visits with $\text{timestamp} \le \text{landmark\_time}$ are evaluated. Future visits are completely ignored.
2. **Forward Survival Horizons**: Survival follow-up duration is calculated strictly forward from landmark time ($T_{\text{forward}} = T_{\text{total}} - T_{\text{landmark}}$).
3. **Immutable Records**: Observation records and datasets are never mutated during extraction.
4. **Patient-Grouped Cross-Validation**: Patients with multiple landmark records are grouped by `patient_id` during train-test splitting to prevent intra-patient correlation leakage.

---

## 12. Complete Test Coverage & Verification Results

All Engine 3 subsystems and full repository regression tests execute cleanly:

```text
======================================================================
ENGINE 3 SUBSYSTEM TEST EXECUTION (10 SUITES)
======================================================================
tests/test_longitudinal_loader.py                    6 / 6 PASSED (0.12s)
tests/test_egfr_trajectory_lmm.py                    6 / 6 PASSED (0.14s)
tests/test_survival_contracts.py                   12 / 12 PASSED (0.08s)
tests/test_survival_models_and_evaluation.py       12 / 12 PASSED (0.95s)
tests/test_survival_statistical_verification.py    16 / 16 PASSED (1.20s)
tests/test_survival_competing_risk_calibration.py  12 / 12 PASSED (0.10s)
tests/test_kfre_calculator.py                      15 / 15 PASSED (0.01s)
tests/test_kidney_progression_engine.py            10 / 10 PASSED (0.03s)
tests/test_progression_features.py                 23 / 23 PASSED (0.06s)
tests/test_longitudinal_simulator.py               12 / 12 PASSED (0.58s)
----------------------------------------------------------------------
TOTAL ENGINE 3 TESTS:                             117 / 117 PASSED (3.29s)

======================================================================
FULL REPOSITORY REGRESSION SUITE (ENGINE 1, 2, 3, NHANES, APP)
======================================================================
Ran 289 tests in 15.992s - OK (0 failures, 0 errors, 0 regressions)
```

---

## 13. Data Provenance & CRIC Access Status

- **Synthetic Simulator Boundary**: Synthetic records produced by `LongitudinalDataSimulator` carry explicit provenance tags (`SYNTHETIC_TEST_FIXTURE_NEFROAI_X`, `is_synthetic=True`). Synthetic test fixtures are strictly restricted to software engineering verification and must **never** be used for clinical validation claims.
- **CRIC Access Status**:
  - The Chronic Renal Insufficiency Cohort (CRIC) is a restricted observational cohort governed by NIDDK Central Repository agreements.
  - The software infrastructure includes a cohort-ready adapter (`CRICLongitudinalAdapter`).
  - No real CRIC patient data are currently present in the repository.
  - Status: **BLOCKED — APPROVED LONGITUDINAL COHORT REQUIRED.**

---

## 14. Known Clinical Limitations

1. **Static KFRE Limitations**: KFRE estimates baseline risk from index measurements but does not incorporate longitudinal trajectory velocity, eGFR slope, or historical acute kidney injury (AKI) episodes.
2. **Population Trajectory Assumptions**: The linear mixed-effects model assumes a linear trajectory over time. In patients experiencing abrupt hemodynamic drops, nephrotoxic insults, or heart failure decompensation, nonlinear splines or joint models would be required.
3. **Competing Risk Calibration**: Competing-risk models require adequate event counts for both kidney failure and death. In younger populations with low mortality, competing risks have minimal impact, whereas in elderly cohorts with cardiovascular disease, competing death dominates.

---

## 15. Implemented vs. Deferred Functionality

| Subsystem Component | Implementation Status | Technical Details |
|---|:---:|---|
| Longitudinal observation schema & validation | **IMPLEMENTED** | `LongitudinalVisit`, `LongitudinalPatientHistory`, `LongitudinalCohort`. |
| Zero-leakage landmark cohort extraction | **IMPLEMENTED** | Strict filtering $\le \text{landmark}$ with forward survival targets. |
| Descriptive OLS eGFR slope | **IMPLEMENTED** | Validated in `ProgressionFeatures` (KDIGO $\ge 3$ visits, $\ge 365$ days). |
| Population Linear Mixed-Effects Model (LMM) | **IMPLEMENTED** | `LinearMixedEffectsTrajectoryModel` with Empirical Bayes BLUP slopes. |
| Tangri 4-variable KFRE calculator | **IMPLEMENTED** | 2-year and 5-year risks across 3 regional calibration profiles. |
| Cause-specific Cox Proportional Hazards | **IMPLEMENTED** | Exact Breslow tied partial likelihood, $L_2$ ridge regularization. |
| Cause-specific Random Survival Forest | **IMPLEMENTED** | Log-rank splitting, Nelson–Aalen terminal hazards, OOB VIMP. |
| Aalen–Johansen population CIF | **IMPLEMENTED** | Non-parametric cumulative incidence under competing risks. |
| Cause-specific personalized CIF model | **IMPLEMENTED** | `CauseSpecificCumulativeIncidenceModel` via numerical hazard integration. |
| Competing-risk quantile calibration | **IMPLEMENTED** | Aalen–Johansen observed CIF with Choudhury standard errors. |
| Pseudo-observation slope & intercept | **IMPLEMENTED** | Jackknife leave-one-out regression on probability scale. |
| Clinical Input Reliability Mechanism (CD-CIRPVM) | **IMPLEMENTED** | CRI scoring, physiological clamping, selective abstention. |
| Parametric Fine–Gray subdistribution model | **DEFERRED** | Blocked on missing external dependency `lifelines.FineGrayFitter`. |
| Real CRIC clinical validation & model weights | **DEFERRED** | Blocked pending authorized NIDDK DUA dataset acquisition. |
| Web UI / Streamlit integration | **DEFERRED** | Scheduled for Phase 8 of revised project roadmap. |

---

## 16. Instructions for Independently Invoking Engine 3

```python
from datetime import datetime, timezone
from src.engines.kidney_progression_engine import KidneyProgressionEngine
from src.clinical.progression_features import ClinicalObservation, LongitudinalPatientRecord
from src.clinical.kfre_calculator import KFREInput

# 1. Initialize engine
engine = KidneyProgressionEngine()

# 2. Assemble longitudinal patient record
t0 = datetime(2021, 1, 1, tzinfo=timezone.utc)
record = LongitudinalPatientRecord(
    patient_id="PAT_CLINICAL_001",
    age_baseline=65.0,
    sex="male",
    diabetes_history=True,
    hypertension_history=True,
    observations=[
        ClinicalObservation(timestamp=t0, egfr=50.0, uacr=120.0, systolic_bp=135.0),
        ClinicalObservation(timestamp=t0.replace(year=2021, month=7), egfr=45.0, uacr=150.0, systolic_bp=138.0),
        ClinicalObservation(timestamp=t0.replace(year=2022, month=1), egfr=40.0, uacr=180.0, systolic_bp=142.0),
    ],
    provenance="CLINICAL_EHR",
)

# 3. Explicit index KFRE inputs
kfre_input = KFREInput(
    age=66.0,
    sex="male",
    egfr=40.0,
    uacr=180.0,
    calibration_profile="north_america",
)

# 4. Execute progression assessment
result = engine.assess_progression(
    record=record,
    landmark_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
    kfre_input=kfre_input,
)

# 5. Inspect structured results
print(f"Patient ID: {result.patient_id}")
print(f"Historical OLS Slope: {result.historical_egfr_slope:.2f} mL/min/1.73m2/year")
print(f"LMM BLUP Slope: {result.lmm_trajectory.patient_slope:.2f} [95% CI: {result.lmm_trajectory.slope_ci_lower:.2f}, {result.lmm_trajectory.slope_ci_upper:.2f}]")
print(f"KFRE 2-Year Risk: {result.kfre_result.risk_2year * 100:.1f}%")
print(f"KFRE 5-Year Risk: {result.kfre_result.risk_5year * 100:.1f}%")
print(f"Clinical Reliability Index (CRI): {result.clinical_reliability['cri_score']:.2f}")
print(f"Trajectory Category: {result.progression_explanations['trajectory_category']}")
```

---

## 17. Dependencies for Subsequent Three-Engine Integration

For Phase 7 (Unified Multi-Engine Integration Architecture):
1. **Engine 1 (Screening CDSS)**: Produces screening classification and risk probability (Low, Moderate, High, Critical) using routine urinalysis and hematology.
2. **Engine 2 (Kidney Severity Engine)**: Evaluates KDIGO cross-sectional severity staging (G1–G5, A1–A3, composite risk).
3. **Engine 3 (Progression Risk Engine)**: Evaluates prospective progression velocity (eGFR slope, LMM BLUP, KFRE multi-year risk, competing-risk CIF).
4. **Integration Prerequisite**: Standardize patient identifier and landmark timestamp passing across all three engines, linking Engine 1 risk tiering to Engine 2 CGA severity staging and Engine 3 longitudinal progression forecasting.
