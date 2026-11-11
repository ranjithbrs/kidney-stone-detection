# Project Guidelines: Chronic Kidney Disease (CKD) Clinical Decision Support System

## 1. Project Identity & Clinical Scope
- **Project Title**: *"Explainable and Real-Time Framework for Predicting Chronic Kidney Disease Using Diverse Machine Learning Models and Different Feature Selection Techniques"*
- **Framework**: NefroAI Clinical Decision Support System (CDSS) replicating and enhancing the methodology published in *IEEE Access* (Md. Sadi Al Huda et al.).
- **Primary Clinical Focus**: Non-invasive early risk stratification and mathematically explainable prediction of Chronic Kidney Disease (CKD) using routine hematological and urinalysis biomarkers.
- **Regulatory & Diagnostic Disclaimer**: This software is an investigational Clinical Decision Support System (CDSS) designed for screening assistance and risk triaging. It does **not** provide definitive medical diagnosis or replace board-certified nephrologist clinical judgment.

---

## 2. Environment & Runtime Configuration
- **Python Version**: Python 3.10.x.
- **Virtual Environment**: Always use the project-local virtual environment located at `.venv/`:
  - Windows PowerShell / CMD: `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe`
- **Dependency Management**:
  - Never install packages globally.
  - When new packages are added, update `requirements.txt` via `.venv\Scripts\python.exe -m pip freeze > requirements.txt`.
- **Environment Configuration**:
  - Environment variables are loaded securely from `.env` via `python-dotenv` (`override=False`).
  - Template credentials remain strictly in `.env.example`. Never commit actual `.env` files or credentials to Git.

---

## 3. System Architecture & Entry Points

### 3.1 Primary Web Application (Streamlit)
- **Root Launcher**: [app_streamlit.py](file:///c:/Users/B%20Ranjith/Downloads/project/app_streamlit.py)
- **Implementation**: [src/streamlit_app.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/streamlit_app.py)
- **Launch Command**:
  ```powershell
  .venv\Scripts\streamlit.exe run app_streamlit.py
  ```
- **Capabilities**:
  - Real-time patient laboratory data input with clinical presets (Healthy vs High-Risk).
  - Risk probability estimation and clinical triage tiering (Low, Moderate, High, Critical).
  - Visualization of model evaluation curves (Multi-model ROC and Confusion Matrices).
  - Population-level and local case-study Explainable AI (SHAP Beeswarm, Waterfall, LIME).
  - Automated timestamped medical evaluation report preview and `.txt` export.

### 3.2 Legacy Web Portal (Flask)
- **Entry Point**: [App.py](file:///c:/Users/B%20Ranjith/Downloads/project/App.py)
- **Role**: Legacy multi-user portal providing user registration, authentication, and secure SMTP alerting.
- **Database**: Local MySQL (`localhost:3306`, engine `mysql.connector`, primary table `regtb`).
- **Status**: Auxiliary authentication portal; not the primary clinical ML inference engine.

### 3.3 Clinical Machine Learning Pipeline
- **Pipeline Architecture**: `KidneyDiagnosticPipeline` in [src/pipeline.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/pipeline.py).
- **Serialized Production Artifact**: [models/clinical_pipeline.joblib](file:///c:/Users/B%20Ranjith/Downloads/project/models/clinical_pipeline.joblib) ($141\text{ KB}$), self-contained bundle containing:
  1. Fitted `ClinicalDataPreprocessor` (median/mode imputation, `StandardScaler`).
  2. Tuned Champion Model: `RandomForestClassifier(n_estimators=50, random_state=42)`.
  3. Consensus Feature Slicing: Top-10 consensus biomarkers.
  4. Class Mapping: `{0: "Healthy (No Chronic Kidney Disease)", 1: "Chronic Kidney Disease (At Risk)"}`.
- **Pipeline Runner & Certification**: [src/run_pipeline.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/run_pipeline.py).

### 3.4 Data Preprocessing & Leak-Free Engineering
- **Implementation**: `ClinicalDataPreprocessor` in [src/preprocessing.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/preprocessing.py).
- **Leak-Free Guarantee**: Stratified train/test splitting ($80/20$) is executed **before** any imputer or scaler is fitted. Imputers, scalers, and SMOTE class rebalancing are fitted strictly on training data (`X_train`). Test partitions (`X_test`) are transformed using training parameters.
- **Fold-Level Resampling & Pipelines**: SMOTE must be applied independently inside each cross-validation training fold. Prefer `imblearn.pipeline.Pipeline` to combine preprocessing, resampling, and model fitting.
- **Preprocessor Artifacts**: `models/preprocessor_Dataset_A.joblib`.

### 3.5 Consensus Feature Selection
- **Implementation**: [src/feature_selection.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/feature_selection.py).
- **Methodology**: Hybrid consensus ranking combining four distinct techniques:
  1. Filter Method 1: Mutual Information (`mutual_info_classif`).
  2. Filter Method 2: ANOVA F-statistic (`f_classif`).
  3. Embedded Method: Random Forest Gini Feature Importance.
  4. Wrapper Method: Recursive Feature Elimination (RFE) with Logistic Regression.
- **Active 10 Consensus Biomarkers**:
  `['hemo', 'sg', 'pcv', 'rc', 'al', 'htn', 'sc', 'bu', 'dm', 'bgr']`
  - `hemo`: Hemoglobin ($\text{g/dL}$) — primary marker of renal anemia.
  - `sg`: Specific Gravity — urine concentration capability.
  - `pcv`: Packed Cell Volume / Hematocrit ($\%$) — depleted in progressive CKD.
  - `rc`: Red Blood Cell Count ($\text{M/mcL}$) — depleted erythropoiesis.
  - `al`: Urine Albumin (Dipstick Grade 0–5) — glomerular barrier permeability breakdown.
  - `htn`: Hypertension (`yes`/`no`) — leading cause and consequence of nephrosclerosis.
  - `sc`: Serum Creatinine ($\text{mg/dL}$) — primary surrogate for eGFR estimation.
  - `bu`: Blood Urea ($\text{mg/dL}$) — nitrogenous waste uremic retention.
  - `dm`: Diabetes Mellitus (`yes`/`no`) — diabetic nephropathy etiology.
  - `bgr`: Blood Glucose Random ($\text{mg/dL}$) — microvascular renal damage driver.
- **Full Schema**: The underlying 24-analyte schema includes `age, bp, su, sod, pot, wc, rbc, pc, pcc, ba, cad, appet, pe, ane`.

### 3.6 Model Training, Tuning, and Evaluation Suite
- **Baseline Training**: [src/train_baselines.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/train_baselines.py).
- **Hyperparameter Tuning**: [src/tune_models.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/tune_models.py) using `StratifiedKFold(n_splits=5)` and `GridSearchCV` on training data only. The final held-out test set must never influence hyperparameter tuning or champion-model selection.
- **Model Evaluation & MCDA**: [src/evaluate_models.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/evaluate_models.py).
- **Evaluated Architectures** in `models/tuned/`:
  - `Dataset_A_Random_Forest_best.joblib` (Champion)
  - `Dataset_A_Gradient_Boosting_best.joblib`
  - `Dataset_A_Support_Vector_Machine_best.joblib`
  - `Dataset_A_Logistic_Regression_best.joblib`
  - `Dataset_A_K_Nearest_Neighbors_best.joblib`

### 3.7 Explainable AI (XAI) Suite
- **Implementation**: `ClinicalXAIExplainer` in [src/explainability.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/explainability.py).
- **Core Interpreters**:
  - Game-theoretic **SHAP** (`shap.TreeExplainer`) for global summary beeswarms, global importance bars, and patient-specific waterfall attributions.
  - Surrogate **LIME** (`LimeTabularExplainer`) for local linear decision rule breakdowns.
- **Artifacts**: Stored in `runs/explainability/plots/`.

### 3.8 Candidate Invention Prototype (CD-CIRPVM)
- **Implementation**: `ClinicalInputReliabilityMechanism` in [src/clinical_input_reliability_mechanism.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical_input_reliability_mechanism.py).
- **Core Mechanisms**:
  1. **Magnitude-Inferred Dimensional Reconciliation (MIDR)**: Automatically detects and reconciles international units (e.g. $\mu\text{mol/L}$ vs $\text{mg/dL}$ for creatinine, $\text{g/L}$ vs $\text{g/dL}$ for hemoglobin, $\text{mmol/L}$ vs $\text{mg/dL}$ for glucose).
  2. **Clinical Reliability Index (CRI)**: Computes a continuous data quality score ($0.0 - 1.0$) based on missingness, corrupted values, and physiological boundary violations.
  3. **Inductive Split Conformal Prediction**: Computes prediction sets $C_\alpha$ with finite-sample statistical coverage guarantee ($1 - \alpha = 95\%$).
  4. **Selective Abstention Gate**: Automatically withholds automated diagnosis (`ABSTAIN`) when $\text{CRI} < 0.60$ or when the conformal prediction set contains epistemic uncertainty $\{0, 1\}$.
- **Status**: Standalone validated prototype; wired in experimental verification scripts ([src/validate_invention_experiments.py](file:///c:/Users/B%20Ranjith/Downloads/project/src/validate_invention_experiments.py)).

---

## 4. Dataset Ground Truth & Cohort Status
- **Primary Legitimate Dataset**: `datasets/clinical/dataset_A_uci_ckd.csv` ($400$ patients, $26$ columns).
  - Class distribution: $250$ CKD ($62.5\%$), $150$ Normal ($37.5\%$).
  - Source: UCI Machine Learning Repository Chronic Kidney Disease dataset.
- **Kaggle Mirror Dataset**: `datasets/clinical/dataset_C_kaggle_ckd.csv` ($400$ patients, $26$ columns).
  - **Audit Status**: Verified byte-level duplicate of Dataset A ($0$ mismatches). It is **not** an independent validation cohort. Do not claim cross-dataset generalization against Dataset C.
- **Legacy Contaminant Datasets (Scheduled for Archival/Removal)**:
  - `datasets/clinical/dataset_B_kidney_stone.csv`: Urinalysis for calcium oxalate nephrolithiasis crystal risk. Not suitable for CKD models.
  - `datasets/clinical/dataset_C_simpson_kidney.csv`: Surgical outcomes benchmark for stone removal. Not suitable for CKD models.
  - `datasets/test/images/` and `datasets/data.yaml`: Computer-vision kidney stone ultrasound/CT scan images.

---

## 5. Status: Implemented vs. Planned Features

| Component / Feature | Current Implementation Status | Notes / Remediation Target |
|---|:---:|---|
| Single-patient Streamlit evaluation | **IMPLEMENTED** | Functional in `app_streamlit.py` with presets and risk triage. |
| Production serialized pipeline | **IMPLEMENTED** | `models/clinical_pipeline.joblib` (Random Forest + Preprocessor). |
| Top-10 consensus feature selection | **IMPLEMENTED** | MI, ANOVA F, RF, RFE hybrid selection verified. |
| Stratified 5-Fold tuned ML models | **IMPLEMENTED** | RF, GB, SVM, LR, KNN tuned on training partitions. |
| Static XAI evaluation plots | **IMPLEMENTED** | SHAP beeswarm, waterfall, and LIME plots in `runs/explainability/`. |
| Medical report text export | **IMPLEMENTED** | Functional in Streamlit UI (exports single-patient evaluation). |
| CD-CIRPVM invention prototype | **IMPLEMENTED (STANDALONE)** | Implemented in `src/clinical_input_reliability_mechanism.py`. |
| Batch CSV upload in Streamlit UI | **IMPLEMENTED** | Tabbed batch screening CSV uploader in `assessment_view.py` + `batch_screening.py` with CWE-1236 export. |
| Strict schema validation guard | **IMPLEMENTED** | Enforced in `pipeline.validate_schema()` & batch CSV uploader (rejects non-renal CSVs). |
| Dynamic live TreeSHAP waterfall | **IMPLEMENTED** | Cached `shap.TreeExplainer` waterfall & additivity check in `xai_live.py` & `explainability_view.py`. |
| CD-CIRPVM UI integration | **IMPLEMENTED** | CRI gauge, conformal prediction set, MIDR audit, and `DISC-08` wired in Engine 1 & UI. |
| Dynamic conformal calibration | **IMPLEMENTED** | `conformal_calibrator.py` computes training-only OOF/split quantiles & Mondrian class-conditional quantiles. |
| 4-Family Stacking Ensemble & Calibration UI | **IMPLEMENTED** | `stacking_ensemble.py` (RF, XGBoost, SVM-RBF, MLP + LR meta-learner) & `performance_view.py` (PR-AUC, Brier, calibration, CIs, subgroups). |
| 5-Method Fold-Safe Feature Selection | **IMPLEMENTED** | MI, ANOVA F, RF, RFE, and inner-fold `TreeExplainer` SHAP stability with Jaccard scoring in `feature_selection.py`. |
| Cross-Analyte Coherence Verifier (`COH-01`–`04`) | **IMPLEMENTED** | `coherence_verifier.py` checks Hemo–PCV, MCV proxy, BU/SC, and Dipstick–uACR invariants; raises `DISC-09`. |
| Live LIME, XAI Concordance & Counterfactuals | **IMPLEMENTED** | `xai_live.py` & `explainability_view.py` provide live LIME rules, SHAP/LIME/KDIGO concordance, and constrained counterfactual recourse. |
| Batch Covariate-Shift & Mahalanobis OOD Monitor | **IMPLEMENTED** | `drift_monitor.py` computes training-anchored PSI, two-sample KS, and Mahalanobis OOD alerts for CSV cohorts. |
| AKI Velocity Guard & Trajectory Backtest | **IMPLEMENTED** | `progression_features.py` separates acute creatinine spikes from `>=90d` persistence and computes walk-forward MAE/RMSE/R². |
| Safety-Max Arbitration (`DISC-01`–`10`) & SHA-256 Attestation | **IMPLEMENTED** | `attestation.py` & `unified_assessment_engine.py` compute non-compensatory action tiers and tamper-evident SHA-256 manifests. |
| Authenticated Patient History & Audit Vault | **IMPLEMENTED** | `patient_store.py` (SQLite + PBKDF2) & `history_view.py` support saving/loading Engine 3 trajectories and report verification. |

---

## 6. Mandatory Clinical AI & Engineering Rules

1. **Never Silently Replace Missing Clinical Measurements with Healthy Defaults**:
   - Missing lab tests must never be coerced to normal physiological values (`sc=1.0`, `al=0`, `hemo=13.5`) without an explicit missingness indicator and clinician warning.
   - Predictions made on incomplete panels must be clearly flagged with a data completeness penalty.
2. **Never Accept Incompatible Datasets for CKD Prediction**:
   - The inference pipeline must enforce strict schema validation. If an uploaded record or CSV lacks core renal biomarkers (`hemo, sc, sg, pcv, bu, al`), it must be rejected immediately with a descriptive error.
3. **Preserve Strict Train/Test Separation**:
   - Any train/test splitting must be stratified and executed **before** any transformation.
   - Never fit imputers, scalers, encoders, or SMOTE on the test partition.
   - The final held-out test set must never influence hyperparameter tuning or champion-model selection.
4. **Prevent Preprocessing and SMOTE Leakage**:
   - Preprocessing parameters (medians, means, scales) and SMOTE synthetic samples must be derived exclusively from training folds.
   - SMOTE must be applied independently inside each cross-validation training fold.
   - Prefer `imblearn.pipeline.Pipeline` to combine preprocessing, resampling, and model fitting.
5. **Do Not Describe Heuristic Feature Importance as SHAP**:
   - Clearly distinguish model Gini/MDI feature importance heuristics from game-theoretic Shapley values (`shap.TreeExplainer`). Never label heuristic weights as "Shapley weights" in clinical reports.
6. **Do Not Claim Absolute Clinical Diagnostic Capability**:
   - Frame model outputs as risk stratification and decision support. Avoid unsupported claims such as "zero false negatives guarantee" or "100% infallible clinical accuracy".
   - State performance with statistical confidence intervals (e.g. Clopper-Pearson 95% CI: $[95.5\%, 100.0\%]$ on $N=80$).
7. **Do Not Claim Patent Novelty Without Legal Grounding**:
   - Describe candidate invention components (MIDR, CRI, conformal gates) objectively as algorithmic reliability mechanisms. Avoid asserting legal patentability or unverified prior art exclusivity.

---

## 7. Git, Testing & Repository Standards
- **Git Hygiene**:
  - Do NOT commit `.venv/`, temporary caches (`__pycache__`), raw datasets in cache, or large model weight archives (`.pt`).
  - Keep the working tree clean and write descriptive, imperative commit messages (`feat: ...`, `fix: ...`, `test: ...`, `docs: ...`).
- **Testing & Quality Assurance**:
  - Automated test runner: `.venv\Scripts\python.exe src/run_test_suite.py`
  - Formal clinical test suite: `.venv\Scripts\python.exe -m pytest tests/ -v`
  - Invention verification: `.venv\Scripts\python.exe src/test_invention_prototype.py`
  - Option A/B verification: `.venv\Scripts\python.exe -m pytest tests/test_option_ab_extensions.py -v`
  - All tests must pass before proposing commits.
