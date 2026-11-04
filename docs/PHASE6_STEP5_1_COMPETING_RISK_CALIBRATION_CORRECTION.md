# NEFROAI-X — Phase 6 Step 5.1: Competing-Risk Calibration Consistency Correction

## 1. Executive Summary & Clinical Context

In Chronic Kidney Disease (CKD) progression modeling (Engine 3), estimating the long-term risk of kidney failure requiring kidney replacement therapy (KRT: dialysis or transplantation) must account for the clinical reality of **death prior to kidney failure as a competing event**. In elderly, cardiovascular, or diabetic CKD populations, patients may die before ever progressing to end-stage kidney failure.

During Phase 6 Step 5, statistical verification of the survival evaluation suite revealed a methodological tension:
- The baseline calibration function (`calculate_calibration_by_quantiles`) estimated observed risk within risk quantiles using the complement of the Kaplan–Meier estimator ($1 - S_{\text{KM}}(t)$).
- A naive logistic regression on complete cases was used to compute calibration slope and intercept.

When applied to models predicting real-world cumulative incidence (such as the Kidney Failure Risk Equation, Fine-Gray subdistribution hazard models, or competing-risk cumulative incidence models), the Kaplan–Meier failure estimator violates survival analysis principles by treating competing deaths as non-informative right-censoring. This mathematically assumes that individuals who died of cardiovascular disease or other causes remained at risk for kidney failure indefinitely, creating an upward bias ($1 - S_{\text{KM}}(t) \ge \text{CIF}_1(t)$). Consequently, evaluating a well-calibrated cumulative incidence model against Kaplan–Meier generates a spurious underprediction diagnosis.

Step 5.1 resolves this discrepancy by implementing mathematically sound competing-risk calibration components:
1. **Aalen–Johansen Cumulative Incidence Quantile Calibration**: Replaces Kaplan–Meier failure with the non-parametric Aalen–Johansen estimator of cumulative incidence within risk quantiles, with analytical large-sample standard errors.
2. **Pseudo-Observation Regression for Calibration Slope and Intercept**: Replaces complete-case logistic regression with jackknife leave-one-out pseudo-observation regression, which properly accounts for both competing deaths and right-censoring without selection bias.
3. **Explicit Estimand Separation**: Maintains both `cause_specific_survival` and `competing_risk_cif` pathways with distinct, descriptive API interfaces and contracts.

---

## 2. Statistical Estimand Distinction

A fundamental requirement of clinical decision support systems is to explicitly state the estimand being evaluated:

| Estimand Attribute | Cause-Specific Net Risk | Actual Cumulative Incidence (Clinical Progression Target) |
|---|---|---|
| **Mathematical Definition** | $P(T_1 \le t \mid \text{competing events eliminated}) = 1 - \exp(-\Lambda_1(t))$ | $P(T \le t, \epsilon = 1) = \int_0^t S(u^-) d\Lambda_1(u)$ |
| **Competing Event Treatment** | Competing deaths treated as right-censored | Competing deaths treated as distinct competing absorbing states |
| **Non-Parametric Estimator** | Kaplan–Meier complement ($1 - S_{\text{KM}}(t)$) | Aalen–Johansen estimator ($\hat{I}_1(t)$) |
| **Clinical Question Answered** | "What would be the biological kidney failure risk if all other causes of death were completely eliminated?" | "What is the real-world probability that this patient will reach kidney replacement therapy before dying?" |
| **Applicable Models** | Cause-specific Cox PH, Cause-specific RSF | KFRE (Tangri et al.), Fine-Gray subdistribution hazards, multi-state models |
| **Calibration Target** | Net hazard discrimination | Real-world clinical decision support & patient counseling |

### Mathematical Inequality
Let $S(t) = P(T > t)$ denote overall survival from any cause (kidney failure or death), and let $S_1(t) = \exp(-\Lambda_1(t))$ denote cause-specific survival where death is treated as censored. Since $d_{\cdot k} = d_{1k} + d_{2k} \ge d_{1k}$:
$$S(u^-) \le S_1(u^-) \quad \forall u \ge 0$$
Integrating against the cause-specific hazard increments $d\Lambda_1(u)$:
$$\text{CIF}_1(t) = \int_0^t S(u^-) d\Lambda_1(u) \le \int_0^t S_1(u^-) d\Lambda_1(u) = 1 - S_1(t)$$
Whenever any competing deaths occur on or before horizon $t$ ($d_{2k} > 0$), the inequality is **strict**:
$$\text{CIF}_1(t) < 1 - S_1(t)$$
Calibrating a cumulative incidence predictor against $1 - S_1(t)$ imposes an artificial positive calibration penalty.

---

## 3. Mathematical Implementations

### 3.1 Non-Parametric Aalen–Johansen CIF in Quantile Groups
Within each predicted risk quantile group $g$, the observed cumulative incidence at horizon $t$ is estimated using the Aalen–Johansen estimator:
$$\hat{I}_{1, g}(t) = \sum_{k: \tau_k \le t} S_g(\tau_{k-1}) \frac{d_{1k, g}}{n_{k, g}}$$
where:
- $\tau_k$ are the ordered distinct event times of any event (type 1 or type 2).
- $n_{k, g}$ is the number of subjects at risk in group $g$ just prior to $\tau_k$.
- $d_{1k, g}$ is the number of kidney failure events at $\tau_k$.
- $d_{2k, g}$ is the number of competing deaths at $\tau_k$.
- $S_g(\tau_k) = S_g(\tau_{k-1})\left(1 - \frac{d_{1k, g} + d_{2k, g}}{n_{k, g}}\right)$ is the overall event-free survival.

#### Large-Sample Variance & Confidence Intervals
The variance of $\hat{I}_{1, g}(t)$ is computed analytically using the Choudhury (2002) / Aalen (1978) formulation:
$$\widehat{\text{Var}}(\hat{I}_{1, g}(t)) = \sum_{k: \tau_k \le t} \left\{ \left[\hat{I}_{1, g}(t) - \hat{I}_{1, g}(\tau_k)\right]^2 \frac{d_{\cdot k, g}}{n_{k, g}(n_{k, g} - d_{\cdot k, g})} + S_g(\tau_{k-1})^2 \frac{d_{1k, g}(n_{k, g} - d_{1k, g})}{n_{k, g}^3} - 2\left[\hat{I}_{1, g}(t) - \hat{I}_{1, g}(\tau_k)\right] S_g(\tau_{k-1}) \frac{d_{1k, g}}{n_{k, g}^2} \right\}$$

**Greenwood Collapse Property:**
When no competing deaths occur in group $g$ ($d_{2k, g} = 0 \implies d_{\cdot k, g} = d_{1k, g}$), $\hat{I}_{1, g}(t) = 1 - S_g(t)$, and this formula collapses identically to Greenwood's formula:
$$\widehat{\text{Var}}(1 - S_g(t)) = S_g(t)^2 \sum_{k: \tau_k \le t} \frac{d_{1k, g}}{n_{k, g}(n_{k, g} - d_{1k, g})}$$
The $95\%$ confidence interval is computed as:
$$[\max(0.0, \hat{I}_1 - 1.96 \cdot \text{SE}), \min(1.0, \hat{I}_1 + 1.96 \cdot \text{SE})]$$

---

### 3.2 Pseudo-Observation Regression for Calibration Slope & Intercept

#### Why Complete-Case Logistic Calibration Fails
Standard logistic calibration models:
$$\text{logit}(P(Y = 1)) = \alpha + \beta \cdot \text{logit}(\hat{p})$$
On right-censored data with competing risks, a subject's status at horizon $t$ is:
- $T_i \le t, \epsilon_i = 1$: Primary failure (case).
- $T_i > t$: Event-free (control).
- $T_i \le t, \epsilon_i = 2$: Competing death.
- $T_i \le t, \epsilon_i = 0$: Censored before horizon.

Dropping censored subjects and competing deaths (complete-case analysis) violates independence assumptions because subjects remaining event-free past $t$ have lower intrinsic baseline hazards than subjects who dropped out or died early. Treating competing deaths as controls ($Y = 0$) artificially depresses the observed risk curve.

#### The Jackknife Pseudo-Observation Solution
In modern survival analysis (Andersen, Klein, Rosthøj 2003; Andersen & Pohar Perme 2010; Gerds, Scheike, Andersen 2014), the jackknife leave-one-out pseudo-value for patient $i$ at horizon $t$ is defined as:
$$\theta_i(t) = N \cdot \hat{I}_1(t) - (N - 1) \cdot \hat{I}_1^{(-i)}(t)$$
where $\hat{I}_1(t)$ is the Aalen–Johansen estimator on the entire sample of size $N$, and $\hat{I}_1^{(-i)}(t)$ is the estimator recomputed on the sample of size $N - 1$ with subject $i$ removed.

**Key Mathematical Properties:**
1. **Unbiased Conditional Expectation:**
   $$\mathbb{E}[\theta_i(t) \mid X_i] \approx P(T_i \le t, \epsilon_i = 1 \mid X_i) = \text{CIF}_1(t \mid X_i)$$
2. **Exact Sample Mean Identity:**
   $$\frac{1}{N} \sum_{i=1}^N \theta_i(t) = \hat{I}_1(t) \quad \text{(identically down to machine precision)}$$
3. **Censoring and Competing Risk Integration:** Right-censoring and competing deaths are non-parametrically integrated out by the Aalen–Johansen step functions, producing continuous pseudo-observations for every subject without dropping any observation.

#### Linear Calibration Model
Regressing $\theta_i(t)$ on predicted cumulative incidence $\hat{p}_i$:
$$\theta_i(t) = \alpha + \beta \cdot \hat{p}_i + \varepsilon_i$$
Using ordinary least squares:
$$\beta = \frac{\sum_{i=1}^N (\hat{p}_i - \bar{p})(\theta_i - \bar{\theta})}{\sum_{i=1}^N (\hat{p}_i - \bar{p})^2}, \quad \alpha = \bar{\theta} - \beta \bar{p}$$
Because $\bar{\theta} = \hat{I}_1(t)$:
- **Calibration Slope ($\beta$):** Reflects prediction spread. Perfect calibration corresponds to $\beta = 1.0$. Values $\beta < 1.0$ indicate over-dispersion (predictions too extreme, requiring shrinkage). Values $\beta > 1.0$ indicate under-dispersion.
- **Calibration Intercept ($\alpha$):** Reflects calibration-in-the-large. When $\beta = 1.0$ and mean predictions match overall cumulative incidence ($\bar{p} = \hat{I}_1(t)$), $\alpha = 0.0$.
- **Linear Scale Stability:** Pseudo-observations on the linear probability scale avoid numerical instability and clipping issues associated with logit links, guaranteeing exact closed-form convergence.

---

## 4. Architectural Updates & API Design

### 4.1 Refactored Functions in `src/clinical/survival/evaluation.py`

1. **`calculate_competing_risk_calibration_by_quantiles`**
   ```python
   def calculate_competing_risk_calibration_by_quantiles(
       durations: Union[np.ndarray, List[float]],
       event_types: Union[np.ndarray, List[int]],
       predicted_cifs: Union[np.ndarray, List[float]],
       horizon_time: float,
       n_groups: int = 5,
   ) -> Tuple[List[CalibrationGroup], float]:
   ```
   - Computes quantile bins based on predicted cumulative incidence.
   - Evaluates observed CIF via Aalen–Johansen in each bin.
   - Reports large-sample standard error, $95\%$ CI, expected-to-observed ratio, and mean calibration error.
   - Handles empty bins, zero events, and all-censored bins gracefully.

2. **`calculate_cause_specific_calibration_by_quantiles`**
   ```python
   def calculate_cause_specific_calibration_by_quantiles(
       durations: Union[np.ndarray, List[float]],
       events: Union[np.ndarray, List[int]],
       predicted_risks: Union[np.ndarray, List[float]],
       horizon_time: float,
       n_groups: int = 5,
   ) -> Tuple[List[CalibrationGroup], float]:
   ```
   - Renamed from `calculate_calibration_by_quantiles` with clear cause-specific net risk docstrings.
   - Backward-compatible alias `calculate_calibration_by_quantiles` retained.

3. **`calculate_competing_risk_calibration_slope_and_intercept`**
   ```python
   def calculate_competing_risk_calibration_slope_and_intercept(
       durations: Union[np.ndarray, List[float]],
       event_types: Union[np.ndarray, List[int]],
       predicted_cifs: Union[np.ndarray, List[float]],
       horizon_time: float,
   ) -> Tuple[Optional[float], Optional[float]]:
   ```
   - Implements leave-one-out jackknife pseudo-observation regression with horizon memoization.
   - Validates sample size ($N \ge 10$) and prediction variance.

4. **`calculate_cause_specific_calibration_slope_and_intercept`**
   ```python
   def calculate_cause_specific_calibration_slope_and_intercept(
       durations: np.ndarray,
       events: np.ndarray,
       predicted_risks: np.ndarray,
       horizon_time: float,
   ) -> Tuple[Optional[float], Optional[float]]:
   ```
   - Exposes logistic calibration on complete cases for cause-specific survival.
   - Alias `_compute_calibration_slope_and_intercept` retained for existing internal callers.

5. **`evaluate_survival_model`**
   - Added parameter: `estimand_type: str = "cause_specific_survival"`.
   - Supports `estimand_type="competing_risk_cif"`, routing calibration to Aalen–Johansen and pseudo-observations.

6. **`compare_models_with_kfre_on_cohort`**
   - Added parameter: `estimand_type: str = "cause_specific_survival"`.
   - When set to `"competing_risk_cif"`, extracts raw multi-category `event_type` (0 = Censored, 1 = KF, 2 = Death) and evaluates both KFRE and survival models against competing-risk calibration benchmarks.

---

## 5. Verification & Test Suite Summary

A dedicated test suite was implemented in `tests/test_survival_competing_risk_calibration.py` covering all 9 required verification scenarios:

| Test Case | Methodological Condition Tested | Expected Mathematical Result | Observed Result | Status |
|---|---|---|---|:---:|
| `test_01` | KF with no competing deaths | AJ CIF equals Kaplan–Meier failure ($1 - S_{\text{KM}}$) and SE equals Greenwood SE | Difference $< 10^{-8}$ | **PASSED** |
| `test_02` | KF with competing deaths | AJ CIF is strictly lower than KM failure ($1 - S_{\text{KM}} > \text{CIF}_{\text{AJ}}$) | $\text{Bias} > 0.05$ ($5.0$ percentage points) | **PASSED** |
| `test_03` | Quantile calibration discrepancy | KM failure falsely indicates underprediction; AJ confirms accurate calibration | $\text{Error}_{\text{KM}} > \text{Error}_{\text{AJ}}$ | **PASSED** |
| `test_04` | Quantile grouping & monotonicity | Predictions ordered into 5 quantiles with bounded rates & valid CIs | $0 \le \text{obs} \le 1$, $\text{CI}_{\text{low}} \le \text{CI}_{\text{high}}$ | **PASSED** |
| `test_05` | Sparse event counts | Quantile bin with 0 kidney failure events produces rate 0.0 without crashing | $\text{Obs} = 0.0$, $\text{CI} = [0.0, 0.0]$ | **PASSED** |
| `test_06` | Early right-censoring | Censoring before horizon properly weighted in risk sets without complete-case bias | Correct non-parametric risk set deduction | **PASSED** |
| `test_07` | All-censored groups | All subjects in group censored before horizon | $\text{Obs} = 0.0$, no unhandled exceptions | **PASSED** |
| `test_08` | Jackknife pseudo-observation identity | Sample mean of leave-one-out pseudo-values matches overall Aalen–Johansen CIF | $|\bar{\theta} - \hat{I}_1(t)| < 10^{-12}$ | **PASSED** |
| `test_09` | Pseudo-observation regression | Slope $\beta \approx 1.0$, intercept $\alpha \approx 0.0$ for calibrated predictions; $\beta \approx 0.80$ for $1.25\times$ over-dispersed | $\beta = 1.000$, $\alpha = 0.000$; $\beta_{\text{od}} = 0.80$ | **PASSED** |
| `test_10` | Input validation & small samples | Length mismatch, empty arrays, non-positive horizon, $N < 10$ | `ValueError` raised or `None` returned | **PASSED** |
| `test_11` | `evaluate_survival_model` dispatch | Correct handling and labeling of both `cause_specific_survival` and `competing_risk_cif` | Result `estimand_type` properly recorded | **PASSED** |

### Suite-Wide Test Results
- **Competing-Risk Calibration Suite**: 11 / 11 tests passed in $0.10\text{ s}$.
- **Engine 3 Longitudinal & Survival Suite**: 100 / 100 tests passed in $5.11\text{ s}$.
- **Full Repository Test Suite**: 272 / 272 tests passed in $23.97\text{ s}$ with zero regressions.

---

## 6. Protected Dataset & Model Integrity

The SHA-256 digests of all protected repository assets were verified and remain identical to baseline:

| Protected File | Expected SHA-256 Digest | Verified SHA-256 Digest | Status |
|---|---|---|:---:|
| `models/clinical_pipeline.joblib` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | **VERIFIED** |
| `datasets/clinical/dataset_A_uci_ckd.csv` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | **VERIFIED** |
| `models/preprocessor_Dataset_A.joblib` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | **VERIFIED** |
| `src/clinical_input_reliability_mechanism.py` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | **VERIFIED** |

---

## 7. Clinical & Regulatory Guardrails

1. **Investigational CDSS Status**: This software component is an investigational Clinical Decision Support System (CDSS) for mathematical calibration of kidney progression risk predictions. It is **not** a cleared Medical Device (SaMD) and must not be used for autonomous diagnostic or clinical intervention decisions.
2. **Synthetic Data Boundary**: Testing was performed using strictly controlled mathematical fixtures and deterministic synthetic trajectories. Synthetic performance metrics must **not** be presented as real-world clinical validation.
3. **Model Retraining Proscription**: No machine learning models were retrained during Step 5.1, preserving reproducibility and preventing data leakage.
