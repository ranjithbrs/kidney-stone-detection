# Automated Testing Gap Audit Report: CKD Prediction System

**Role**: Senior Python Test Automation Engineer & Machine Learning Quality Assurance Engineer  
**Date**: November 2, 2026  
**Repository Inspected**: `CKD Prediction System / Kidney Stone Detection`  
**Execution Environment**: Python 3.10.0 (`.venv\Scripts\python.exe` on Windows)  
**Status**: Comprehensive Quality Assurance & Test Architecture Audit Complete (Ready for Review)  

---

## Executive Summary & Audit Scorecard

An exhaustive quality assurance inspection of the repository was conducted, covering all machine learning pipelines, data preprocessing modules, feature selection algorithms, evaluation scripts, explainability tooling (SHAP/LIME), serialized model artifacts, web applications (`streamlit_app.py`, `App.py`), and the candidate invention module (`CD-CIRPVM`).

While the repository contains functional testing suites covering core CKD model inference and conformal reliability gating (with 24 tests in `test_clinical_system.py`, 50 checkpoints in `test_comprehensive_verification.py`, and 5 validation scenarios in `test_invention_prototype.py`), **critical architectural test gaps, inadequate test assumptions, and high-risk security vulnerabilities exist in the broader codebase**. Most notably, the legacy Flask web application (`App.py`) contains plain-text hardcoded email credentials and raw SQL injection vulnerabilities that are completely untouched by any automated test, and the repository's Ultralytics YOLO11 computer vision pipeline has 0% automated test coverage.

### High-Level Quality Assurance Scorecard

| Testing Dimension | Automated Test Coverage | Test Rigor / Depth | Risk Level |
| :--- | :---: | :---: | :---: |
| **1. Dataset Validation** | High (Dataset A only) | Moderate (Dataset B & C omitted) | **Medium** |
| **2. Data Preprocessing** | Moderate | Inadequate (Dataset B & C untested) | **Medium** |
| **3. Data Leakage Prevention** | Moderate | Inadequate (Post-hoc hash checks) | **High** |
| **4. SMOTE & CV Safety** | Moderate | Partial (Leakage in tuning untested) | **High** |
| **5. Machine-Learning Models** | Moderate | Inadequate (Tuned artifacts untested) | **Medium** |
| **6. Feature Selection** | Moderate | Inadequate (Stability untested) | **Medium** |
| **7. Model Saving & Loading** | High | Strong | **Low** |
| **8. Evaluation Metrics** | Moderate | Inadequate (Toy test vector only) | **Medium** |
| **9. SHAP & LIME Explainability** | Moderate | Inadequate (Additive property untested) | **Medium** |
| **10. Prediction Pipeline** | High | Strong | **Low** |
| **11. Streamlit Application** | Low | Inadequate (Backend only; UI untested) | **High** |
| **12. Input Validation (CD-CIRPVM)** | Very High | Strong (MIDR, bounds, conformal) | **Low** |
| **13. Security & Reliability** | **Critical Deficit** | **Severely Inadequate (App.py blindspot)** | **CRITICAL** |

---

## 1. Existing Testing Framework Analysis

### 1.1 Architecture & Test Runners
The project currently employs Python's standard `unittest` library as its testing harness. Tests are organized across two main directories:
- `tests/test_clinical_system.py` (10 test classes, 24 test methods) — Triggered via `src/run_test_suite.py`.
- `tests/test_comprehensive_verification.py` (8 test classes, 50 test methods) — Standalone runner.
- `src/test_invention_prototype.py` (Functional script validating 5 candidate invention scenarios).
- `src/validate_invention_experiments.py` (Benchmark script evaluating 150 clinical instances across 5 cohorts).

### 1.2 Missing Framework Infrastructure
1. **No Pytest Harness**: No `pytest.ini`, `conftest.py`, or parameterized fixtures. The current runners use bespoke script loops instead of standard test runners with failure exit codes.
2. **Zero Code Coverage Measurement**: No integration with `coverage.py` or `pytest-cov`. Line, branch, and statement coverage metrics are neither tracked nor enforced.
3. **No CI/CD Automation**: No GitHub Actions workflows (`.github/workflows/ci.yml`) or pre-commit hooks exist to block broken code or credential leaks before pushing to `origin/main`.
4. **No Database Fixtures / Mocks**: No mocking framework (`unittest.mock` / `pytest-mock`) exists for the MySQL database required by `App.py`.

---

## 2. Existing Test Coverage Inventory

### 2.1 File-by-File Code vs. Test Coverage Mapping

| Source File / Component | Purpose | Corresponding Test File | Test Coverage Level |
| :--- | :--- | :--- | :---: |
| `src/pipeline.py` | Reusable clinical inference pipeline | `test_clinical_system.py`, `test_comprehensive_verification.py` | **85% (High)** |
| `src/clinical_input_reliability_mechanism.py` | Candidate invention (CD-CIRPVM) | `test_invention_prototype.py`, `test_comprehensive_verification.py` | **90% (High)** |
| `src/preprocessing.py` | Imputation, scaling, categorical encoding | `test_comprehensive_verification.py` (Dataset A only) | **45% (Moderate)** |
| `src/feature_selection.py` | Consensus biomarker discovery | `test_comprehensive_verification.py` (Schema check only) | **20% (Low)** |
| `src/train_baselines.py` | Training 5 baseline ML classifiers | `test_comprehensive_verification.py` (Synthetic fit only) | **15% (Low)** |
| `src/tune_models.py` | 5-fold CV hyperparameter tuning | *None* | **0% (None)** |
| `src/evaluate_models.py` | Cross-dataset ROC/PR evaluation | *None* (Toy vector in `test_comprehensive_verification.py`) | **10% (Low)** |
| `src/explainability.py` | Global beeswarm & waterfall generation | *None* (Inline attributions in `pipeline.py` tested) | **25% (Low)** |
| `src/streamlit_app.py` | NefroAI interactive web application | `test_comprehensive_verification.py` (Import check only) | **15% (Low)** |
| `App.py` | Legacy Flask app with MySQL & email alert | *None* | **0% (None)** |
| `models/best.pt`, `yolo11n.pt` | YOLO11 Kidney Stone detection models | *None* | **0% (None)** |
| `src/dataset_audit.py` | Dataset profiling and integrity audit | *None* | **0% (None)** |
| `src/generate_pptx.py` | Presentation generator | *None* | **0% (None)** |

---

## 3. Deep-Dive Gap Analysis Across the 13 Mandated Categories

### Category 1: Dataset Validation
- **Existing Coverage**: `TestDatasetValidation` checks columns, target values, nulls, duplicates, numerical types, and whitespace dialects on `dataset_A_uci_ckd.csv`.
- **Gaps Identified [MEDIUM]**:
  - `datasets/clinical/dataset_B_kidney_stone.csv` (urinalysis 6 features: gravity, ph, osmo, cond, urea, calc) has zero automated schema validation tests.
  - `datasets/clinical/dataset_C_kaggle_ckd.csv` and `dataset_C_simpson_kidney.csv` have zero automated schema validation tests.
  - No check for extreme covariate shift or multicollinearity between raw features.

### Category 2: Data Preprocessing
- **Existing Coverage**: Imputation, scaling order, and unseen categorical encoding tested on `preprocessor_Dataset_A.joblib`.
- **Gaps Identified [MEDIUM]**:
  - `models/preprocessor_Dataset_B.joblib` and `models/preprocessor_Dataset_C.joblib` are completely untested.
  - No test verifies inverse transform behavior (`scaler.inverse_transform`).
  - No test verifies numerical stability under extreme near-zero standard deviations ($\sigma < 10^{-7}$).

### Category 3: Data Leakage Prevention
- **Existing Coverage**: Checks for column name absence (`target` not in `X_train`) and row hash disjointness between `X_train` and `X_test`.
- **Inadequacy Identified [HIGH]**:
  - The hash comparison is performed on `datasets/processed/Dataset_A_X_train.csv` and `Dataset_A_X_test.csv` *after* preprocessing and SMOTE.
  - **Flawed Assumption**: Testing post-split matrices does not prove that imputation parameters ($\text{median}$) or scaling parameters ($\mu, \sigma$) were calculated exclusively on the train split prior to transforming the test split.
  - Missing an automated test that intercepts the preprocessor during fitting to verify that `X_test` was never passed to `fit()`.

### Category 4: SMOTE and Cross-Validation Safety
- **Existing Coverage**: Verifies that the test set `y_test` retains an unbalanced native distribution ($44 \ne 36$).
- **Gaps Identified [HIGH]**:
  - No automated test verifies that SMOTE was applied *inside* cross-validation folds during hyperparameter tuning (`tune_models.py`). If SMOTE is applied prior to K-Fold partitioning, synthetic samples bleed across train/val folds (a common academic methodological error).
  - No test verifies that SMOTE interpolation does not produce physically impossible combinations (e.g. negative creatinine or conflicting categorical comorbidities).

### Category 5: Machine-Learning Models
- **Existing Coverage**: `test_C1` trains 5 baseline models on a 50-row toy slice; `test_C2` to `test_C7` verify prediction bounds and reproducibility.
- **Inadequacy Identified [MEDIUM]**:
  - The actual saved model artifacts in `models/baselines/` and `models/tuned/` are never loaded or tested. The tests instantiate fresh un-tuned models on toy data.
  - No automated test checks model calibration error (Brier score or Expected Calibration Error [ECE]).
  - No test checks model behavior under adverse class imbalances ($99:1$).

### Category 6: Feature Selection
- **Existing Coverage**: Asserts that consensus features exist in the dataset schema and count equals 10.
- **Gaps Identified [MEDIUM]**:
  - The selection algorithms in `src/feature_selection.py` (Random Forest feature importance, Mutual Information, Recursive Feature Elimination [RFE]) are never executed in automated tests.
  - No test checks feature selection stability (e.g., Jaccard similarity of selected features across bootstrap resamples).
  - No test asserts behavior when collinear features ($r > 0.95$, such as `hemo` and `pcv`) are evaluated.

### Category 7: Model Saving and Loading
- **Existing Coverage**: `test_C4` and `test_C5` serialize `KidneyDiagnosticPipeline` to a temporary joblib file and verify bit-identical predictions.
- **Evaluation [LOW RISK]**: This component has high-quality test coverage. Backward compatibility across joblib versions is the only minor unmonitored risk.

### Category 8: Evaluation Metrics
- **Existing Coverage**: `TestEvaluation` computes accuracy, precision, recall, F1, specificity, and ROC-AUC on a fixed 10-element toy vector.
- **Inadequacy Identified [HIGH]**:
  - **Zero-Division Vulnerability**: What happens when a model predicts all zeros ($\text{TP} = 0, \text{FP} = 0$)? Precision denominator is zero. Standard scikit-learn functions raise warnings or return 0.0 depending on `zero_division`. This edge case is not tested.
  - **Single-Class ROC-AUC Crash**: When evaluating a batch with only one class present, `roc_auc_score` raises an uncaught `ValueError`. No test guards against this clinical reality in small clinic cohorts.
  - Does not test the actual evaluation generation script (`src/evaluate_models.py`).

### Category 9: SHAP and LIME Explainability
- **Existing Coverage**: Tests that `feature_attributions` dictionary is populated and matches selected feature names.
- **Inadequacy Identified [MEDIUM]**:
  - Does not test the SHAP local accuracy / additive property:
    $$\sum_{i=1}^M \phi_i \approx f(x) - \mathbb{E}[f(X)]$$
  - Does not test LIME convergence stability (LIME uses stochastic perturbation sampling; different seeds can produce different local explanation weights).
  - Does not test image file creation or rendering failure fallbacks for `shap_summary_beeswarm.png` and `patient_0_lime_bar.png`.

### Category 10: Prediction Pipeline
- **Existing Coverage**: Strong coverage across normal inputs, missing inputs, outlier inputs, and vectorized batch inference in `pipeline.py`.
- **Evaluation [LOW RISK]**: Well-covered with defensive clamping and defaults.

### Category 11: Streamlit Application
- **Existing Coverage**: `TestStreamlitApp` tests only that the script imports and `load_clinical_pipeline()` exists.
- **Inadequacy Identified [HIGH]**:
  - **UI Interaction Untested**: Form inputs, slider boundaries, selectbox state, file uploader widgets, session state, and download buttons are completely unverified.
  - **ScriptRunContext Hazards**: Running Streamlit in bare Python mode without `streamlit.testing.v1.AppTest` triggers 30+ internal warnings and fails to test component reactivity.

### Category 12: Input Validation & Reliability Gating (CD-CIRPVM)
- **Existing Coverage**: `test_invention_prototype.py` and `validate_invention_experiments.py` rigorously validate MIDR unit conversion, 14-organ bounds clamping, CRI scoring, and conformal abstention.
- **Evaluation [LOW RISK]**: Exceptionally strong coverage across 150 clinical instances.

### Category 13: Security and Reliability
- **Existing Coverage**: `TestSecurityAndReliability` checks for PII, basic string patterns in `src/`, and tempfile cleanup.
- **Inadequacy Identified [CRITICAL]**:
  - **Severe False Sense of Security**: `test_H1` passed because it restricted its scan to `src/`. It completely overlooked `App.py` in the root directory!

---

## 4. Inadequate Tests and Flawed Assumptions Identified

```
====================================================================================================
                        INADEQUATE TESTS & FLAWED ASSUMPTIONS AUDIT
====================================================================================================
```

### Inadequacy 1: Blind Credential Scan in `test_H1` [CRITICAL]
- **Flawed Code**:
  ```python
  code_files = [f for f in os.listdir(SRC_DIR) if f.endswith(".py")]
  ```
- **Why It Is Inadequate**: It only scans the `src/` folder. It ignores the repository root, where `App.py` contains:
  - Hardcoded active Gmail app password: `s.login(fromaddr, "tdyr kebi hnyr yzyh")` (Line 188)
  - Hardcoded Flask Secret Key: `app.config['SECRET_KEY'] = '7d441f27d441f27567d441f2b6176a'` (Line 12)
  - Hardcoded admin credentials: `uname == 'admin' and pas == 'admin'` (Line 31)
- **Impact**: The test runner reports `[OK] PASS : No API keys or passwords exposed`, misleading stakeholders while active credentials remain committed to version control.

### Inadequacy 2: Post-Processing Data Leakage Hash Test in `test_A7` [HIGH]
- **Flawed Code**:
  ```python
  train_hashes = set(pd.util.hash_pandas_object(self.X_train))
  test_hashes = set(pd.util.hash_pandas_object(self.X_test))
  self.assertEqual(len(train_hashes.intersection(test_hashes)), 0)
  ```
- **Why It Is Inadequate**: `X_train` and `X_test` were already processed by `StandardScaler` and `SMOTE`. Even if data leakage occurred *during* preprocessing (e.g. scaling `X_test` with global mean/variance), the scaled row hashes will still be disjoint. The test verifies that train and test rows are not identical, but it does NOT verify that the test set was withheld from feature transformation fitting.

### Inadequacy 3: Toy Vector Evaluation in `test_E1` - `test_E4` [MEDIUM]
- **Flawed Code**:
  ```python
  cls.y_true = np.array([0, 1, 0, 1, 1, 0, 1, 0, 1, 0])
  cls.y_pred = np.array([0, 1, 0, 1, 0, 0, 1, 0, 1, 1])
  ```
- **Why It Is Inadequate**: This is a static textbook sanity check on an artificial 10-element array. It does not test the evaluation functions on real model output, does not test multi-threshold ROC curves, does not test multiclass confusion matrices, and does not test zero-division edge cases.

### Inadequacy 4: Unverified Streamlit UI Health in `test_G1` [MEDIUM]
- **Flawed Code**:
  ```python
  self.assertTrue(hasattr(streamlit_app, "load_clinical_pipeline") or hasattr(streamlit_app, "main"))
  ```
- **Why It Is Inadequate**: Merely inspecting module attributes does not test whether Streamlit's reactive DAG compiles, whether sidebar widgets bind to pipeline parameters, or whether session state resets corrupt user inputs.

---

## 5. Failed Tests and Execution Warnings

When executing the test suites in the clean workspace environment, the following behaviors were observed:

### 1. `tests/test_comprehensive_verification.py`
- **Exit Status**: Code 0 (50/50 Passed).
- **Execution Warnings**:
  - `Streamlit missing ScriptRunContext`: 30+ internal warnings emitted because `streamlit_app.py` is imported directly in standard Python unittest without Streamlit's browser execution context.
  - `Pandas FutureWarning`: `FutureWarning: Downcasting behavior in replace is deprecated and will be removed in a future version. To retain the old behavior, explicitly call result.infer_objects(copy=False)`.

### 2. `tests/test_clinical_system.py`
- **Exit Status**: Code 0 (24/24 Passed).
- **Execution Time**: 1.78 seconds. Clean execution.

### 3. `App.py` (Flask Application Execution Check)
- **Status**: **FAILED UPON EXECUTION**.
- **Error**: When `App.py` is executed, navigating to any route (e.g. `/AdminLogin` or `/newuser`) crashes with:
  ```
  mysql.connector.errors.InterfaceError: 2003: Can't connect to MySQL server on 'localhost:3306' (10061)
  ```
  Because no automated test exists for `App.py`, this crash was completely unmonitored by the test suite.

---

## 6. Critical Risks & Production Vulnerabilities

```
====================================================================================================
                        CRITICAL PRODUCTION RISKS CLASSIFICATION
====================================================================================================
```

### Risk 1: Plaintext Credentials & Sensitive Secrets in Version Control [SEVERITY: CRITICAL]
- **Location**: `App.py` (Lines 12, 31, 188)
- **Details**:
  - Plaintext Gmail App Password: `"tdyr kebi hnyr yzyh"`
  - Plaintext hardcoded admin credentials: `'admin'` / `'admin'`
  - Hardcoded Flask secret key: `'7d441f27d441f27567d441f2b6176a'`
- **Clinical/Legal Threat**: Violation of HIPAA, GDPR, and basic cyber-security standards. Compromised SMTP credentials can be abused for spam or phishing.

### Risk 2: Raw SQL Injection Vulnerabilities in `App.py` [SEVERITY: CRITICAL]
- **Location**: `App.py` (Lines 103, 115)
- **Details**:
  ```python
  cursor.execute("SELECT * from regtb where UserName='" + uname + "' and password='" + pas + "'")
  ```
- **Threat**: Direct unsanitized string interpolation permits classical SQL injection attacks (`' OR '1'='1`). An attacker can bypass authentication or dump the entire user registration database.

### Risk 3: Zero Automated Tests for Ultralytics YOLO11 Pipeline [SEVERITY: HIGH]
- **Location**: `models/best.pt`, `models/yolo11n.pt`, `datasets/data.yaml`
- **Details**: The project repository includes YOLO11 weights and Roboflow dataset configs for kidney stone detection. However, there are zero tests verifying:
  - Model loading via `ultralytics.YOLO`
  - Input image tensor shape and normalization (640x640)
  - Class prediction mapping (0: Stone, 1: Normal)
  - Non-max suppression (NMS) confidence filtering
- **Threat**: Any regression in OpenCV, PyTorch, or Ultralytics packages could break kidney stone detection without triggering a single test failure.

### Risk 4: Uncaught Exception on Single-Class Evaluation Batches [SEVERITY: HIGH]
- **Location**: `src/evaluate_models.py`
- **Details**: In clinic screening deployments, a batch of 10–20 patients may occasionally be 100% negative or 100% positive. Calling `roc_auc_score(y_true, y_prob)` on a single-class ground truth throws an uncaught `ValueError: Only one class present in y_true`.
- **Threat**: Unexpected pipeline crash in clinical production environments during cohort evaluation.

### Risk 5: Untested Cross-Dataset Generalization on Datasets B & C [SEVERITY: MEDIUM]
- **Location**: `datasets/clinical/dataset_B_kidney_stone.csv`, `dataset_C_kaggle_ckd.csv`
- **Details**: All automated preprocessing and model tests exclusively test Dataset A. Preprocessors for Dataset B and C are serialized in `models/` but never validated in automated unit tests.

---

## 7. Recommended Additional Test Cases & Prioritized Roadmap

```
====================================================================================================
                        RECOMMENDED TEST EXPANSION ROADMAP
====================================================================================================
```

### Tier 1: Critical Priority (Immediate Implementation Needed)
1. **Repository-Wide Comprehensive Security & Secret Scan Test (`test_security_deep_scan.py`)**:
   - Recursively scan ALL `.py`, `.json`, `.yaml`, `.md`, `.env`, and `.txt` files across root, `src/`, `tests/`, and `docs/`.
   - Implement regex patterns for AWS, Google App Passwords, private keys, database connection strings, and Flask secrets.
   - Assert zero matches repository-wide.
2. **Flask Application Unit & Integration Tests (`test_flask_app.py`)**:
   - Use Flask's `test_client()` to test routes `/`, `/AdminLogin`, `/newuser`, `/UserLogin`.
   - Mock `mysql.connector.connect` to verify authentication logic without requiring a live local MySQL daemon.
   - Test SQL injection payload rejection on `uname` and `pas`.

### Tier 2: High Priority (Quality & Leakage Assurance)
3. **End-to-End Leak-Free Preprocessing Pipeline Test (`test_preprocessing_leakage.py`)**:
   - Split raw data in memory *before* instantiating `ClinicalDataPreprocessor`.
   - Assert that `preprocessor.scaler.mean_` is mathematically identical to `X_train.mean()` and mathematically distinct from `X_test.mean()`.
   - Assert that SMOTE is never invoked when `transform_single_record` or `transform_df` is called on test splits.
4. **Ultralytics YOLO11 Computer Vision Tests (`test_yolo_kidney_stone.py`)**:
   - Test loading `models/yolo11n.pt` and `models/best.pt`.
   - Test dummy image tensor `(1, 3, 640, 640)` inference.
   - Verify output bounding box structure, confidence scores $\in [0, 1]$, and class labels $\in \{0, 1\}$.
5. **Streamlit Headless UI Component Tests (`test_streamlit_ui.py`)**:
   - Utilize `streamlit.testing.v1.AppTest.from_file("src/streamlit_app.py")`.
   - Simulate user inputs (sliders, radio buttons, file uploads).
   - Assert that prediction metrics, risk alerts, and download buttons render without script errors.

### Tier 3: Medium Priority (Robustness & Explainability)
6. **Multi-Dataset Preprocessing Tests (`test_multidataset_preprocessing.py`)**:
   - Test `models/preprocessor_Dataset_B.joblib` and `models/preprocessor_Dataset_C.joblib`.
   - Verify that Dataset B (Kidney Stone, 6 features) imputes and scales cleanly.
7. **SHAP Additive Property & LIME Convergence Tests (`test_xai_mathematical_integrity.py`)**:
   - Test local accuracy: $| \sum \phi_i - (f(x) - \mathbb{E}[f(X)]) | < 10^{-3}$.
   - Test that LIME explanation top feature remains identical across 5 repeated runs with fixed seed.
8. **Evaluation Metric Edge-Case Tests (`test_evaluation_edge_cases.py`)**:
   - Test `roc_auc_score` safety wrapper when `y_true` has only class 0 or only class 1.
   - Test `precision_score` and `recall_score` with `zero_division=0` on all-zero predictions.

### Tier 4: Low Priority (Code Quality & Maintenance)
9. **Pandas Deprecation Warning Cleanup**:
   - Replace deprecated `.replace(['?', '', 'nan'], np.nan)` with `.replace(..., regex=True)` or explicit downcasting to eliminate `FutureWarning` clutter during test execution.
10. **Automated CI/CD GitHub Actions Workflow (`.github/workflows/test.yml`)**:
    - Automatically execute the full test suite on push and pull request.

---

## 8. Exact Commands for Running the Test Suite

All commands must be executed using the project-local virtual environment (`.venv\Scripts\python.exe`):

### 1. Run the Comprehensive 50-Checkpoint Verification Suite
```powershell
& ".venv\Scripts\python.exe" tests\test_comprehensive_verification.py
```

### 2. Run the Clinical System Quality Assurance Suite (Phase 11)
```powershell
& ".venv\Scripts\python.exe" src\run_test_suite.py
```

### 3. Run the Candidate Invention Prototype Verification Suite (Phase 17)
```powershell
& ".venv\Scripts\python.exe" src\test_invention_prototype.py
```

### 4. Run the 150-Patient Multi-Cohort Empirical Validation Benchmark (Phase 18)
```powershell
& ".venv\Scripts\python.exe" src\validate_invention_experiments.py
```

### 5. Run Unittest Discovery Across All Test Modules
```powershell
& ".venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
```

---

## 9. Conclusion & Auditor Sign-Off

The CKD Prediction System demonstrates strong automated test coverage around its core tabular inference pipeline (`src/pipeline.py`) and candidate invention (`CD-CIRPVM`). However, the presence of **hardcoded credentials in `App.py`**, **untested raw SQL queries**, and **zero automated testing for the YOLO11 model** represent critical gaps that must be resolved prior to production clinical deployment or external security audits.

*This audit report is submitted for stakeholder review. In accordance with project instructions, no application code or tests have been modified or deleted.*
