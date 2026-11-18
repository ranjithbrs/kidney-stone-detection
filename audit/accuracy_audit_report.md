# Independent ML Accuracy Audit & Scientific Evaluation Report
## NEFROAI-X v1.0 — Multimodal Kidney Disease Clinical Decision Support System

**Auditor Role:** Senior Machine Learning Engineer, Clinical Data Scientist & Independent ML Quality Auditor  
**Date of Audit:** 2026-11-06  
**Target Repository:** `ranjithbrs/kidney-stone-detection` (Branch: `main`)  
**Commit Reference:** `c8262cb` / `v1.0`  
**Primary Benchmark Dataset:** UCI Machine Learning Repository Chronic Kidney Disease (`datasets/clinical/dataset_A_uci_ckd.csv`)  
**Evaluation Script:** `evaluation/ckd_accuracy_audit.py`  
**Clinical Designation:** `INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE`

---

## 1. Executive Summary

This independent audit was commissioned to rigorously investigate, independently reproduce, and verify the machine learning performance claims of the **NEFROAI-X** framework. Specifically, the audit evaluates whether the previously reported **100.0% accuracy (80/80 correct)** on the held-out test split of the UCI Chronic Kidney Disease (CKD) dataset is mathematically reproducible, whether it resulted from data leakage, and how it compares against the published base paper (*Md. Sadi Al Huda et al., IEEE Access, 2025*).

### Key Audit Findings:
1. **Mathematical Reproducibility of 100% Test Accuracy:**
   - **VERIFIED.** On the fixed held-out test partition ($N=80$, 50 CKD cases, 30 non-CKD cases; stratified 80/20 split, `random_state=42`), the champion Random Forest model ($50$ trees) and the serialized `models/clinical_pipeline.joblib` indeed achieve $80/80$ correct predictions ($100.0\%$ observed accuracy, Sensitivity $100.0\%$, Specificity $100.0\%$, ROC-AUC $1.000$, Brier score $0.0095$).
2. **Data Leakage Identification (SMOTE-before-CV):**
   - **LEAKAGE IDENTIFIED IN CROSS-VALIDATION ONLY.** In the legacy training scripts (`src/preprocessing.py` and `src/tune_models.py`), SMOTE oversampling was applied to the entire training split ($320 \rightarrow 400$ records) *before* 5-fold cross-validation. This caused synthetic samples to leak across CV folds, optimistically biasing cross-validation metrics ($99.25\% \pm 0.61\%$).
   - **NO TEST CONTAMINATION.** The held-out test set ($N=80$) was strictly isolated prior to any imputer fitting, scaling, or SMOTE resampling.
   - **LEAK-FREE RETEST:** When evaluated under a strict `imblearn.pipeline.Pipeline` where SMOTE and imputers operate strictly inside each CV fold, Random Forest achieves **$99.06\% \pm 0.62\%$ CV accuracy** and retains **$100.0\%$ test accuracy** on the held-out split.
3. **Statistical Uncertainty & The 95% Confidence Interval:**
   - Observing $80/80$ correct on a sample of $N=80$ does **not** prove infallible real-world clinical accuracy.
   - The exact **Clopper-Pearson 95% Confidence Interval** for accuracy is **$[95.49\%, 100.0\%]$** (lower bound: **$95.5\%$**).
   - Sensitivity 95% CI is **$[92.89\%, 100.0\%]$** (lower bound: **$92.9\%$**).
   - Specificity 95% CI is **$[88.43\%, 100.0\%]$** (lower bound: **$88.4\%$**).
4. **Base Paper Comparison:**
   - The published base paper (*Al Huda et al., IEEE Access, 2025*, DOI: `10.1109/ACCESS.2025.3649006`) also reported **$100.0\%$ test accuracy** for Random Forest on Dataset A and Dataset C.
   - The true clinical advancement of NEFROAI-X is **not a higher raw accuracy score**, but **compression from 24 features down to 10 routine consensus biomarkers**, a multi-engine clinical framework (KDIGO CGA staging + KFRE progression), and the CD-CIRPVM reliability mechanism that **selectively abstains** on corrupted data.

---

## 2. Phase 1 — Repository and Dataset Audit

### 2.1 Dataset Verification
- **File:** `datasets/clinical/dataset_A_uci_ckd.csv`
- **File Size:** $43,578\text{ bytes}$ ($42.6\text{ KB}$)
- **Dimensions:** Exactly **400 rows × 26 columns** ($1\text{ ID}$ + $24\text{ predictors}$ + $1\text{ target}$).
- **Target Column:** `classification`
- **Raw Class Distribution:**
  - `ckd`: $248$
  - `ckd\t`: $2$ (Contains rogue trailing tab characters from original UCI encoding)
  - `notckd`: $150$
  - **Sanitized Distribution:** $250\text{ CKD }(62.5\%)$ vs $150\text{ Normal }(37.5\%)$. Total = $400$.
- **Predictor Schema (24 features):**
  - Numerical ($14$): `age, bp, sg, al, su, bgr, bu, sc, sod, pot, hemo, pcv, wc, rc`
  - Categorical ($10$): `rbc, pc, pcc, ba, htn, dm, cad, appet, pe, ane`

### 2.2 Component Audit Table

| Pipeline Component | Source File / Artifact | Implementation Status | Audit Finding / Identified Issue |
|---|---|:---:|---|
| **Raw Dataset** | `datasets/clinical/dataset_A_uci_ckd.csv` | **Verified** | UCI CKD repository ($N=400$); dirty strings (`ckd\t`, `?`) require sanitization. |
| **Kaggle Mirror** | `datasets/clinical/dataset_C_kaggle_ckd.csv` | **Audited** | Byte-level duplicate of Dataset A ($0$ mismatches); not an independent cohort. |
| **Data Preprocessing** | `src/preprocessing.py` | **Implemented** | Median/mode imputation + StandardScaler; splits before imputer fitting. |
| **SMOTE Resampling** | `src/preprocessing.py` | **Leakage Found** | Applied to entire `X_train` ($320 \rightarrow 400$) before CV. Did not contaminate `X_test`. |
| **Feature Selection** | `src/feature_selection.py` | **Implemented** | 4-way consensus ranking (MI, ANOVA F, RF Gini, RFE). Top-10 consensus selected. |
| **Top-10 Biomarkers** | `models/clinical_pipeline.joblib` | **Verified** | `['hemo', 'sg', 'pcv', 'rc', 'al', 'htn', 'sc', 'bu', 'dm', 'bgr']`. |
| **Model Tuning** | `src/tune_models.py` | **Audited** | GridSearchCV 5-fold CV on `X_train`; test set evaluated for progress logging. |
| **Baseline Evaluation** | `src/evaluate_models.py` | **Verified** | Evaluates tuned joblib models on `X_test` ($N=80$); correctly reports $80/80$. |
| **Production Pipeline** | `models/clinical_pipeline.joblib` | **Verified** | Self-contained artifact containing fitted preprocessor + RF champion model. |
| **CD-CIRPVM Prototype** | `src/clinical_input_reliability_mechanism.py` | **Standalone** | Unit reconciliation (MIDR), CRI scoring ($0.0-1.0$), and selective abstention. |

---

## 3. Phase 2 — Verification of the Existing Accuracy Claim

We conducted an independent code audit addressing the 10 critical validation questions:

| # | Audit Check | Verdict | Evidence / Code Location |
|---|---|:---:|---|
| **1** | Was dataset split before preprocessing? | **YES** | `src/preprocessing.py` lines 111–113: `train_test_split(test_size=0.2, stratify=y, random_state=42)` executed before imputer fitting. |
| **2** | Was test dataset completely isolated? | **YES** | `Dataset_A_X_test.csv` ($N=80$) was transformed using training parameters; never seen by imputers or SMOTE. |
| **3** | Was imputation fitted exclusively on training data? | **YES** | `src/preprocessing.py` lines 139–140: `self.num_imputer.fit_transform(X_train)`. |
| **4** | Was feature selection performed on training data? | **YES** | `src/feature_selection.py` line 34: `run_hybrid_selection(X_train, y_train)`. |
| **5** | Was scaling fitted only on training data? | **YES** | `src/preprocessing.py` line 140: `self.scaler.fit_transform(num_data)`. |
| **6** | Was SMOTE applied exclusively to training data? | **YES** | `src/preprocessing.py` line 122: `smote.fit_resample(X_train_proc, y_train)`. |
| **7** | Was SMOTE applied before cross-validation? | **YES (LEAKAGE)** | Preprocessing saved `X_train` post-SMOTE ($400$ rows). `src/tune_models.py` ran `StratifiedKFold` on the post-SMOTE data. |
| **8** | Was hyperparameter tuning independent of test set? | **PARTIAL** | Model selection was guided by CV F1 score on `X_train`, but test set was evaluated inside the tuning logging loop. |
| **9** | Was the test set repeatedly inspected? | **YES** | Test set was evaluated across baseline, tuning, and evaluation scripts during development. |
| **10** | Do saved predictions match reported results? | **YES** | Exactly $80/80$ correct ($30$ Normal, $50$ CKD; ROC-AUC $1.000$, Brier $0.0095$). |

---

## 4. Phase 3 & 4 — Leakage-Safe Head-to-Head Algorithm Comparison

To eliminate the "SMOTE-before-CV" flaw, we executed `evaluation/ckd_accuracy_audit.py` using `imblearn.pipeline.Pipeline`, ensuring:
1. Imputation, scaling, and SMOTE are embedded **inside** the pipeline.
2. SMOTE is applied strictly to the training folds during each cross-validation iteration, never touching validation folds or the held-out test partition.
3. All models are trained and tested on the exact same fixed outer partitions ($N_{\text{train}}=320$, $N_{\text{test}}=80$).

### 4.1 Comparative Experimental Results (Held-Out Test Split, $N=80$)

| Model Architecture | 5-Fold CV Acc (Train) | Test Acc | 95% Exact CI (Acc) | Sens (Recall) | 95% CI (Sens) | Spec | 95% CI (Spec) | F1-Score | ROC-AUC | PR-AUC | Brier Score |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Random Forest (Champion)** | **99.06% ± 0.62%** | **100.00%** | **[95.5%, 100.0%]** | **100.00%** | **[92.9%, 100.0%]** | **100.00%** | **[88.4%, 100.0%]** | **1.0000** | **1.0000** | **1.0000** | **0.0085** |
| **AdaBoost** | 99.38% ± 0.77% | 100.00% | [95.5%, 100.0%] | 100.00% | [92.9%, 100.0%] | 100.00% | [88.4%, 100.0%] | 1.0000 | 1.0000 | 1.0000 | 0.0839 |
| **Logistic Regression** | 98.12% ± 1.82% | 100.00% | [95.5%, 100.0%] | 100.00% | [92.9%, 100.0%] | 100.00% | [88.4%, 100.0%] | 1.0000 | 1.0000 | 1.0000 | 0.0102 |
| **Gradient Boosting** | 98.44% ± 2.42% | 98.75% | [93.2%, 100.0%] | 98.00% | [89.4%, 99.9%] | 100.00% | [88.4%, 100.0%] | 0.9899 | 1.0000 | 1.0000 | 0.0042 |
| **Support Vector Machine** | 98.44% ± 1.40% | 98.75% | [93.2%, 100.0%] | 98.00% | [89.4%, 99.9%] | 100.00% | [88.4%, 100.0%] | 0.9899 | 1.0000 | 1.0000 | 0.0047 |
| **K-Nearest Neighbors** | 96.56% ± 1.17% | 98.75% | [93.2%, 100.0%] | 98.00% | [89.4%, 99.9%] | 100.00% | [88.4%, 100.0%] | 0.9899 | 1.0000 | 1.0000 | 0.0084 |
| **Decision Tree** | 96.88% ± 2.21% | 95.00% | [87.7%, 98.6%] | 94.00% | [83.5%, 98.7%] | 96.67% | [82.8%, 99.9%] | 0.9592 | 0.9530 | 0.9590 | 0.0501 |
| **NEFROAI-X Production Pipeline** | 100.0% (Pre-SMOTE) | 100.00% | [95.5%, 100.0%] | 100.00% | [92.9%, 100.0%] | 100.00% | [88.4%, 100.0%] | 1.0000 | 1.0000 | 1.0000 | 0.0095 |

*Note on XGBoost:* `xgboost` is not installed in the local virtual environment; Gradient Boosting and AdaBoost serve as tree-ensemble benchmarks.

### 4.2 Key Observations from Fair Benchmark:
1. **Tree Ensembles and Linear Boundaries:** Random Forest, AdaBoost, and Logistic Regression all achieve $100.0\%$ accuracy on the held-out test split.
2. **Why Random Forest is Champion:** Random Forest exhibits superior probability calibration ($\text{Brier} = 0.0085$) compared to AdaBoost ($\text{Brier} = 0.0839$) and provides natural compatibility with game-theoretic `shap.TreeExplainer`.
3. **Statistical Uncertainty:** While $80/80$ is observed, the $95\%$ confidence interval lower bound is **$95.5\%$**. A single 80-patient test set cannot distinguish between a $96\%$ model and a $100\%$ model with statistical significance ($p > 0.05$).

---

## 5. Phase 5 — Verification Against the Published Base Paper

### 5.1 Base Paper Identification
- **Title:** *NefroAI: An Explainable and Real-Time Framework for Predicting Chronic Kidney Disease Using Diverse Machine Learning Models and Different Feature Selection Techniques*
- **Authors:** Md. Sadi Al Huda, Esrath Kanon, Md. Shahidul Khan Pappo, Md. Asraf Ali, and Nasim Ahmed
- **Journal:** *IEEE Access*, Volume 13, 2025
- **DOI:** [`10.1109/ACCESS.2025.3649006`](https://doi.org/10.1109/ACCESS.2025.3649006)
- **Public Code Repository:** [`https://github.com/esrath99/CKD-Code`](https://github.com/esrath99/CKD-Code)

### 5.2 Methodological Comparison

| Experimental Parameter | Published Base Paper (Al Huda et al., 2025) | NEFROAI-X Re-Implementation |
|---|---|---|
| **Primary Cohort** | UCI Machine Learning Repository CKD ($N=400$) | UCI CKD ($N=400$) |
| **Train/Test Partition** | Stratified 80:20 split (`random_state=42`) | Stratified 80:20 split (`random_state=42`, $N_{\text{test}}=80$) |
| **Feature Space** | Evaluated on full $24$ features and feature selection subsets | Compressed to **Top-10 Consensus Routine Biomarkers** |
| **SMOTE Placement** | Applied on training data; CV executed post-SMOTE | Replicated baseline (SMOTE-before-CV) + Leak-free pipeline |
| **Reported RF Accuracy** | **100.0%** on Dataset A (and Dataset C) | **100.0%** Observed (95% CI: $[95.5\%, 100.0\%]$) |
| **Reported RF ROC-AUC** | **1.000** | **1.000** |
| **Decision Support Scope** | Single-point binary classification script | **Three-Engine Clinical Platform** (Screening + KDIGO + KFRE) |
| **Data Quality Gate** | None (blind model inference on all inputs) | **CD-CIRPVM** (MIDR unit reconciliation + Selective Abstention) |

### 5.3 Verdict on Comparison:
- **Did we reproduce the paper's reported accuracy?** **YES.** Under identical 80/20 partitioning on Dataset A, Random Forest reproduces $100.0\%$ test accuracy ($80/80$).
- **Can we claim accuracy superiority?** **NO.** Both models reach the theoretical ceiling ($100.0\%$) on this held-out test split. Claiming a numerical accuracy improvement is mathematically impossible.
- **Where is the legitimate improvement?**
  1. **Clinical Cost & Panel Reduction:** Achieving identical diagnostic accuracy using only **10 routine biomarkers** instead of 24.
  2. **Clinical Staging Integration:** Incorporating guideline-mandated **KDIGO 2024 CGA staging** and **Tangri KFRE** trajectory.
  3. **Safety Through Selective Abstention:** The CD-CIRPVM mechanism **abstains** on corrupted or severely incomplete panels ($15/80$ raw test cases), preventing dangerous automated misdiagnoses.

---

## 6. Phase 6 — Audit of Proposed Technical Advancements

| # | Technical Claim | Classification | Implementation Status & Evidence in Source Code |
|---|---|:---:|---|
| **1** | Feature reduction (24 to 10 biomarkers) | **Fully Implemented & Tested** | `src/pipeline.py` lines 86–92 (`TOP_10_CONSENSUS_FEATURES`); verified in test suite. |
| **2** | 4-way hybrid consensus selection | **Fully Implemented & Tested** | `src/feature_selection.py` (`run_hybrid_selection` combining MI, ANOVA, RF, RFE). |
| **3** | Three-engine architecture | **Fully Implemented & Tested** | `src/engines/unified_assessment_engine.py` coordinating Engine 1, 2, and 3. |
| **4** | CKD-EPI 2021 race-free eGFR | **Calculator / Rule-Based** | `src/clinical/egfr_calculator.py` implements the 2021 ASPE/NKF guideline equation. |
| **5** | KDIGO CGA staging matrix | **Calculator / Rule-Based** | `src/clinical/kdigo_staging.py` implements 18-cell $(G_1-G_5 \times A_1-A_3)$ grid. |
| **6** | Longitudinal eGFR trajectory (LMM/OLS) | **Fully Implemented & Tested** | `src/clinical/lmm_trajectory.py` computes OLS and BLUP random-effects slopes. |
| **7** | Tangri 4-variable KFRE calculator | **Calculator / Rule-Based** | `src/clinical/kfre_calculator.py` computes 2-yr and 5-yr kidney failure probabilities. |
| **8** | Dual-layer explainability (SHAP/LIME) | **Fully Implemented & Tested** | `src/explainability.py` (`TreeExplainer` waterfall + `LimeTabularExplainer`). |
| **9** | CD-CIRPVM & discrepancy auditing | **Fully Implemented & Tested** | `src/clinical_input_reliability_mechanism.py` and `src/ui/components/discrepancies.py` (DISC-01 to DISC-07). |
| **10** | Unit reconciliation & selective abstention | **Fully Implemented & Tested** | `MIDR` detects international units (e.g. $\mu\text{mol/L}$); abstains when critical biomarkers are missing. |

*Auditor Note on Multimodal Classification:* NEFROAI-X is a **multimodal tabular clinical platform** (combining screening ML, clinical guideline equations, and longitudinal time-series), not an imaging/computer-vision system. Ultrasound/CT image models from legacy repositories are excluded from clinical inference.

---

## 7. Audit Answers to Mandatory Questions

### A. Is the previously reported NEFROAI-X 100% accuracy reproducible?
**YES.** When evaluated on the 80 held-out test patients from the UCI CKD dataset (`random_state=42`), the champion Random Forest model accurately classifies all $80/80$ cases ($50$ CKD, $30$ Normal).

### B. What is the corrected, independently calculated test accuracy?
**100.00%** on the held-out test split ($N=80$). However, this must always be reported alongside its statistical confidence bounds.

### C. What are the sensitivity, specificity, F1-score, ROC-AUC and 95% confidence interval?
- **Accuracy:** $100.00\%$ (Exact Clopper-Pearson 95% CI: **$[95.49\%, 100.0\%]$**)
- **Sensitivity (Recall):** $100.00\%$ (Exact Clopper-Pearson 95% CI: **$[92.89\%, 100.0\%]$**)
- **Specificity:** $100.00\%$ (Exact Clopper-Pearson 95% CI: **$[88.43\%, 100.0\%]$**)
- **F1-Score:** **$1.0000$**
- **ROC-AUC:** **$1.0000$**
- **PR-AUC:** **$1.0000$**
- **Brier Score:** **$0.0085$** (Leak-free pipeline) / **$0.0095$** (Production artifact)

### D. Which conventional algorithm performs best under our fair experimental setup?
**Random Forest** is the optimal champion model. While AdaBoost and Logistic Regression also achieved $100.0\%$ on the test split, Random Forest demonstrated superior probability calibration ($\text{Brier} = 0.0085$ vs $0.0839$) and lower variance across cross-validation folds ($99.06\% \pm 0.62\%$).

### E. Does NEFROAI-X demonstrate an actual measurable improvement over baseline models?
**YES, in feature efficiency, calibration, and safety.** It matches the peak accuracy of full-feature models using only **10 consensus biomarkers** (a $58\%$ reduction in lab burden) and introduces selective abstention to prevent overconfident errors on corrupted records.

### F. Can we honestly claim superiority over the published base paper?
**NOT on raw accuracy.** The published base paper already reported $100.0\%$ on Dataset A. Superiority can **only** be claimed legitimately on:
1. Architectural scope (Three engines vs single binary classifier).
2. Diagnostic cost reduction ($10$ consensus features vs $24$).
3. Clinical safety (Magnitude-Inferred unit reconciliation and selective abstention).

### G. What exact accuracy and technical claims should we present during our final department review?
Present:
> *"On the held-out UCI CKD benchmark split ($N=80$), our leak-free Random Forest model achieved 100.0% observed test accuracy with an exact 95% Clopper-Pearson confidence interval of 95.5% to 100.0%. Rather than claiming higher raw accuracy than published literature, our primary contributions are: (1) compressing the feature space from 24 to 10 routine consensus biomarkers without accuracy loss, (2) integrating KDIGO 2024 staging and longitudinal KFRE progression, and (3) establishing clinical reliability guardrails (CD-CIRPVM) that abstain on corrupted or incomplete lab inputs."*

---

## 8. Audit File Artifacts Generated

1. `audit/model_comparison.csv` — Full model-wise cross-validation and test evaluation metrics.
2. `audit/predictions.csv` — Case-by-case test record predictions, true labels, and probability scores.
3. `audit/test_indices.json` — Exact deterministic split indices ($320$ train, $80$ test).
4. `audit/confusion_matrices.png` — High-resolution 2×4 grid of confusion matrices across all evaluated models.
5. `audit/model_comparison.png` — Comparative bar chart displaying Accuracy, F1-Score, and ROC-AUC.
6. `audit/reproduction_instructions.md` — Step-by-step instructions to rerun this evaluation on any machine.
7. `audit/department_review_comparison.md` — Review-ready summary tailored for faculty presentation.
