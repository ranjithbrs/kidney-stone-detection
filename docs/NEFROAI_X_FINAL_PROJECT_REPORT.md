# NEFROAI-X: Multimodal Kidney Disease Clinical Decision Support System
## Comprehensive Academic Technical Report & Architectural Specification

**Author:** NEFROAI-X Research & Development Consortium  
**Repository:** `ranjithbrs/kidney-stone-detection` (`main` branch)  
**Baseline Commit:** `64b831a`  
**Framework Version:** 1.0.0-rc (Phase 10 Release Candidate)  
**Date of Release:** November 2026  
**Primary Clinical Focus:** Explainable Multimodal Risk Stratification, Severity Staging, and Progression Modeling for Chronic Kidney Disease (CKD)  

**Clinical & Regulatory Designation:**  
`INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE`  
`LOCAL RESEARCH-SOFTWARE ENVIRONMENT — NO PUBLIC DEPLOYMENT`

---

## Table of Contents
1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Problem Statement](#3-problem-statement)
4. [Research Motivation](#4-research-motivation)
5. [Objectives](#5-objectives)
6. [Scope and Limitations](#6-scope-and-limitations)
7. [Related Work and Established Methods](#7-related-work-and-established-methods)
8. [Proposed NEFROAI-X Architecture](#8-proposed-nefroai-x-architecture)
9. [Three-Engine Architecture](#9-three-engine-architecture)
10. [Dataset Descriptions and Provenance](#10-dataset-descriptions-and-provenance)
11. [Data Preprocessing and Harmonization](#11-data-preprocessing-and-harmonization)
12. [Mathematical and Statistical Foundations](#12-mathematical-and-statistical-foundations)
13. [Clinical Input Reliability and Safe Abstention (CD-CIRPVM)](#13-clinical-input-reliability-and-safe-abstention-cd-cirpvm)
14. [Unified Assessment Orchestration](#14-unified-assessment-orchestration)
15. [Streamlit Application Implementation](#15-streamlit-application-implementation)
16. [Docker and Reproducibility Architecture](#16-docker-and-reproducibility-architecture)
17. [Testing Methodology & Quality Assurance](#17-testing-methodology--quality-assurance)
18. [Results and Implementation Evidence](#18-results-and-implementation-evidence)
19. [Discussion](#19-discussion)
20. [Limitations and Ethical Considerations](#20-limitations-and-ethical-considerations)
21. [Conclusion](#21-conclusion)
22. [Future Work](#22-future-work)
23. [References](#23-references)

---

## 1. Abstract

Chronic Kidney Disease (CKD) represents an escalating public health crisis affecting more than 850 million individuals worldwide (over 10% of the global adult population). Early asymptomatic progression frequently delays clinical intervention until irreversible parenchymal damage and nephron atrophy have occurred. Current diagnostic informatics systems typically operate as isolated, black-box point classifiers, prone to data leakage, silent coercion of missing clinical measurements, and failure to integrate guideline-directed severity staging with longitudinal trajectory forecasting.

This report presents **NEFROAI-X**, an explainable, real-time, multimodal Clinical Decision Support System (CDSS) for chronic kidney disease. Replicating and substantially extending the *IEEE Access* NefroAI methodology (Md. Sadi Al Huda et al.), NEFROAI-X unifies three independently callable clinical intelligence engines under an overarching orchestration layer:
- **Engine 1 (Screening & Binary Classification):** A leak-free, Stratified 5-Fold cross-validated Random Forest champion ensemble operating on 10 consensus biomarkers distilled from 24 clinical features via hybrid feature selection (Mutual Information, ANOVA F-statistic, Gini Impurity, and Recursive Feature Elimination). Explainability is provided through dual-layer game-theoretic SHAP (`TreeExplainer`) and local surrogate LIME rules.
- **Engine 2 (KDIGO 2024 Severity Staging):** Deterministic clinical implementation of the race-free CKD-EPI 2021 glomerular filtration rate equation coupled with urine albumin-to-creatinine ratio (UACR) staging, generating a 28-cell KDIGO CGA composite risk heatmap with automated chronicity advisories.
- **Engine 3 (Longitudinal Progression & Survival Architecture):** Time-aware progression monitoring incorporating the Tangri 4-variable Kidney Failure Risk Equation (KFRE) reference calculator (2-year and 5-year failure risk), annualized eGFR trajectory analysis (OLS and Linear Mixed-Effects Models with BLUP shrinkage), and a cohort-ready competing-risk survival architecture (Cox Proportional Hazards and Random Survival Forests).

Clinical safety is guaranteed by the **Clinical Data-Correcting Input Reliability and Prediction Validity Mechanism (CD-CIRPVM)**, featuring Magnitude-Inferred Dimensional Reconciliation (MIDR), a continuous Clinical Reliability Index (CRI), inductive conformal prediction bounds, and automated safe abstention gates. The complete platform is encapsulated in an unprivileged, local-only Docker container (`python:3.10-slim`, `127.0.0.1:8501`) backed by an automated 19-module, 349-test verification suite with zero test failures.

---

## 2. Introduction

Renal filtration is vital to human systemic homeostasis, mediating electrolyte balance, acid-base equilibrium, blood pressure regulation via the renin-angiotensin-aldosterone axis, metabolic waste clearance, and erythropoietin secretion. Progressive chronic kidney disease manifests as structural or functional abnormalities of the kidney persisting for more than three months, pathologically characterized by glomerulosclerosis, tubulointerstitial fibrosis, and irreversible vascular rarefaction.

In primary care and point-of-care outpatient screening, clinicians face a trilemma:
1. Conventional comprehensive laboratory panels are costly and time-intensive, demanding up to 24 separate blood, urine, and metabolic assays.
2. Isolated serum creatinine measurements are notoriously insensitive to early filtration loss due to renal functional reserve and compensatory hyperfiltration in surviving nephrons.
3. Emerging machine learning screening tools frequently provide uncalibrated, uninterpretable predictions that lack alignment with established clinical consensus guidelines (such as the Kidney Disease: Improving Global Outcomes [KDIGO] 2024 guidelines).

NEFROAI-X addresses these foundational challenges by bridging mathematical machine learning rigor, guideline-based clinical staging, and longitudinal disease trajectory modeling into a unified point-of-care software platform.

---

## 3. Problem Statement

Automated clinical informatics tools for chronic kidney disease suffer from four structural vulnerabilities:

1. **Preprocessing and Resampling Data Leakage:** In published literature, missing value imputation, standardization, and synthetic sampling (such as SMOTE) are routinely fitted globally across the entire dataset prior to splitting, producing optimistic, non-reproducible performance metrics that fail in prospective clinical environments.
2. **Biomarker Overfitting and Multicollinearity:** Uncurated 24-feature diagnostic panels introduce high collinearity (e.g., Hemoglobin and Packed Cell Volume, $r = 0.8407$), destabilizing tree splits and increasing laboratory expenditure without corresponding diagnostic yield.
3. **Silent Coercion of Missing Measurements:** Commercial and academic pipelines frequently fill absent laboratory tests with healthy reference defaults (e.g., assuming $SC = 1.0\text{ mg/dL}$ or urine albumin $= 0$), masking critical pathology in patients with incomplete panels.
4. **Disconnection from Guideline Staging and Chronicity:** Standalone classifiers categorize patients as binary "CKD" or "Normal" without stating the KDIGO GFR/Albuminuria stage, ignoring the clinical reality that a single elevated creatinine reflects acute or transient dysfunction rather than proven chronicity.

---

## 4. Research Motivation

The development of NEFROAI-X is motivated by the necessity for:
- **Reproducible Science:** Replicating the published *IEEE Access* NefroAI baseline under strict, leak-free stratified cross-validation conditions to establish honest performance baselines.
- **Resource Optimization:** Reducing diagnostic panel complexity from 24 to 10 consensus biomarkers, thereby slashing diagnostic turnaround time and clinical laboratory costs by 60% in low-resource settings.
- **Dual-Layer Explainability:** Providing cooperative game-theoretic Shapley attributions alongside locally linear surrogate boundaries, translating algorithmic decisions into physiological explanations (e.g., hemoglobin-driven renal anemia versus creatinine-driven filtration loss).
- **Holistic Multimodal Triaging:** Providing point-of-care clinicians with simultaneous screening risk probabilities, KDIGO severity staging, and longitudinal progression velocity within a single unified interface.

---

## 5. Objectives

The primary engineering and clinical research objectives of NEFROAI-X are:
1. **Develop Engine 1:** A leak-free binary classification pipeline evaluating five candidate model families (Random Forest, Gradient Boosting, SVM, Logistic Regression, KNN) and hyperparameter-tuning a champion model on 10 consensus biomarkers.
2. **Develop Engine 2:** An automated severity calculator implementing the race-free CKD-EPI 2021 eGFR equation and KDIGO 2024 CGA risk matrix with explicit chronicity safeguards.
3. **Develop Engine 3:** A longitudinal progression engine featuring the Tangri 4-variable KFRE equations, eGFR annualized slope estimators (OLS and Linear Mixed Models), and a mathematically verified survival analysis architecture.
4. **Implement Safe Input Reliability (CD-CIRPVM):** Automatic unit reconciliation, data completeness scoring, conformal prediction sets, and safe abstention gates.
5. **Construct a Unified Orchestrator:** An integration layer synthesizing cross-engine outputs and auditing clinical discrepancies (DISC-01 to DISC-08).
6. **Deploy an Interactive Web Application:** A human-centered Streamlit user interface featuring clinical presets, risk gauges, XAI plots, and multi-format medical export (PDF, CSV, JSON, TXT).
7. **Ensure Reproducibility & Packaging:** Pinned dependencies, Docker containerization, local-only network isolation, and comprehensive regression test suites.

---

## 6. Scope and Limitations

### 6.1 Clinical Scope
- **Target Population:** Adult patients ($\ge 18$ years) undergoing outpatient renal screening, general wellness checkups, or longitudinal nephrology monitoring.
- **Input Modalities:** Routine hematology (hemoglobin, packed cell volume, red blood cell count), urinalysis (specific gravity, dipstick albumin), and clinical chemistry (serum creatinine, blood urea, blood glucose random).
- **Intended Use:** Screening assistance, risk prioritization, and guideline staging decision support.

### 6.2 Regulatory & Clinical Boundaries
- **Investigational Status:** NEFROAI-X is an investigational research prototype. It is **not** a certified Software as a Medical Device (SaMD) and has not received FDA 510(k), De Novo, or CE mark clearance.
- **No Autonomous Diagnosis:** The software outputs risk probabilities and guideline classifications; it does not generate definitive clinical diagnoses or prescribe pharmaceuticals.
- **Cross-Sectional Caveat:** Single lab visits cannot establish the 3-month chronicity required by KDIGO; Engine 2 automatically attaches a chronicity advisory to spot evaluations.
- **Survival Model Validation Status:** While Cox PH and Random Survival Forest algorithms have been verified against mathematical benchmarks, clinical predictive training remains formally deferred (`DEFERRED_PENDING_APPROVED_COHORT`) until institutional data-use agreements for longitudinal cohorts (such as the Chronic Renal Insufficiency Cohort [CRIC]) are executed.

---

## 7. Related Work and Established Methods

| Method / Prior Work | Authors / Organization | Core Methodology | NEFROAI-X Extension / Remediation |
|---|---|---|---|
| **NefroAI Paper** | Md. Sadi Al Huda et al. (*IEEE Access*, 2023) | ML screening on UCI CKD using feature selection and ensemble learning. | Eliminated all data leakage; established Stratified 5-Fold cross-validation; added CD-CIRPVM and KDIGO integration. |
| **CKD-EPI 2021 Equation** | Inker et al. (*NEJM*, 2021) | Race-free creatinine-based eGFR estimation. | Fully implemented in Engine 2 with SI/conventional unit detection and biological boundary gating. |
| **KDIGO CGA Staging** | KDIGO 2024 Clinical Practice Guideline | 2-dimensional grid combining GFR categories (G1–G5) and Albuminuria (A1–A3). | Implemented 28-cell composite risk heatmap with automated discordance auditing against ML screening. |
| **KFRE Equation** | Tangri et al. (*JAMA*, 2011; *JAMA*, 2016) | 4-variable and 8-variable risk equations for kidney failure progression. | Replicated 4-variable equation with North American and international recalibrations; added strict G3–G5 eligibility gating. |
| **SHAP** | Lundberg & Lee (*NeurIPS*, 2017) | Cooperative game theory (Shapley values) for local and global model explanations. | Wired `shap.TreeExplainer` directly to Random Forest champion model for real-time waterfall generation. |
| **LIME** | Ribeiro et al. (*KDD*, 2016) | Sparse local linear surrogate modeling around patient feature vectors. | Coupled with SHAP to provide complementary decision-rule boundaries. |

---

## 8. Proposed NEFROAI-X Architecture

The architecture of NEFROAI-X is organized into five decoupled layers:

```
[Layer 1: Clinical Data Ingestion & Sanitization]
   └── Raw Demographics, 10 Biomarkers, Serial Visits, or Demonstration Presets
   └── CD-CIRPVM: Magnitude-Inferred Dimensional Reconciliation (MIDR)
   └── Boundary Validation & Clinical Reliability Index (CRI) Scoring
                 │
                 ▼
[Layer 2: Unified Assessment Orchestrator]
   ├── Engine 1: Screening & Binary Risk Classification (Random Forest)
   ├── Engine 2: KDIGO 2024 CGA Severity Staging (CKD-EPI 2021)
   └── Engine 3: Longitudinal Progression (KFRE & Trajectory Slope)
                 │
                 ▼
[Layer 3: Clinical Discrepancy Engine (Cross-Engine Audit)]
   └── Rules DISC-01 through DISC-08 (Screening vs Staging Discordance)
                 │
                 ▼
[Layer 4: Explainable AI & Synthesis]
   ├── SHAP TreeExplainer & LIME Decision Rules
   └── Longitudinal Trajectory Charting (OLS / Linear Mixed Models)
                 │
                 ▼
[Layer 5: Presentation & Export]
   ├── Streamlit Multi-Tab Point-of-Care User Interface (Localhost:8501)
   └── Multi-Format Export (Vector PDF, Sanitized CSV, JSON, TXT)
```

---

## 9. Three-Engine Architecture

### 9.1 Engine 1: Screening & Binary Classification
- **Champion Architecture:** `RandomForestClassifier(n_estimators=50, max_depth=None, min_samples_split=2, random_state=42)`.
- **Feature Space:** Top-10 consensus biomarkers (`hemo, sg, pcv, rc, al, htn, sc, bu, dm, bgr`).
- **Calibration & Triaging:** Risk probability $P(Y=1 \mid \mathbf{x}) \in [0.0, 1.0]$ stratified into 4 operational triage tiers:
  - **Low Risk:** $P < 0.20$
  - **Moderate Risk:** $0.20 \le P < 0.50$
  - **High Risk:** $0.50 \le P < 0.80$
  - **Critical Risk:** $P \ge 0.80$

### 9.2 Engine 2: KDIGO 2024 Severity Staging
- **Filtration Calculation:** Implements the race-free CKD-EPI 2021 equation (see Section 12).
- **Albuminuria Stratification:** Categorizes UACR into A1 ($<30\text{ mg/g}$), A2 ($30–300\text{ mg/g}$), and A3 ($>300\text{ mg/g}$).
- **Composite Risk Matrix:** Maps the $(G, A)$ intersection across the 28-cell KDIGO grid into four risk tiers: Low (Green), Moderately High (Yellow), High (Orange), and Very High (Red).

### 9.3 Engine 3: Longitudinal Progression & Survival Architecture
- **Tangri 4-Variable KFRE:** Computes 2-year and 5-year progression risks to kidney replacement therapy (KRT) using age, sex, eGFR, and log-transformed UACR.
- **Trajectory Modeling:**
  - *Ordinary Least Squares (OLS):* Computes annualized slope ($\Delta\text{eGFR}/\text{year}$) across serial historical visits.
  - *Linear Mixed-Effects Model (LMM):* Evaluates population fixed effects and subject-specific random slopes using Best Linear Unbiased Predictor (BLUP) shrinkage.
- **Survival Foundation:** Contains verified implementations of Cox Proportional Hazards, Random Survival Forests, and Aalen-Johansen cumulative incidence estimators. In adherence to research ethics, survival predictions are formally withheld pending real longitudinal cohort approval.

---

## 10. Dataset Descriptions and Provenance

### 10.1 Primary Development Cohort: UCI Machine Learning Repository CKD Dataset
- **Patients:** $N = 400$ adult subjects.
- **Class Balance:** 250 CKD positive ($62.5\%$), 150 normal healthy controls ($37.5\%$).
- **Features:** 24 clinical attributes (11 numerical, 13 categorical/binary) plus binary outcome.
- **Missingness:** $10.2\%$ overall missingness across the raw matrix. Missing values are imputed strictly within training folds using median/mode parameters.

### 10.2 Cross-Sectional Population Cohort: NHANES 2017–2018
- **Participants:** $N = 9,254$ surveyed individuals; $N = 5,730$ adult participants with complete laboratory panels.
- **Harmonized Biomarkers:** Serum creatinine (`LBXSCR`), urinary albumin (`URXUMA`), urinary creatinine (`URXUCR`), blood glucose (`LBXSGL`), and demographic markers (`RIDAGEYR`, `RIAGENDR`).
- **Role:** Used in Phase 5 to validate the population-level distributions of CKD-EPI 2021 eGFR and KDIGO CGA staging.
- **Chronicity Limitation:** NHANES is cross-sectional; a single survey visit cannot establish persistence over 3 months.

### 10.3 Synthetic Longitudinal Test Simulator
- **Implementation:** `src/data_sources/longitudinal_simulator.py`.
- **Purpose:** Generates synthetic, deterministic longitudinal patient visit sequences strictly for software verification and unit testing.
- **Safety Restriction:** Under no circumstances are synthetic patients used for clinical validation or survival model training.

### 10.4 Prospective Research Cohort: CRIC
- **Status:** Architecture ready; actual data integration blocked pending formal Data Use Agreement (DUA).

---

## 11. Data Preprocessing and Harmonization

### 11.1 Leak-Free Preprocessing Pipeline
To prevent data contamination, all transformations strictly follow the scikit-learn `Transformer` protocol fitted exclusively on training partitions ($X_{\text{train}}$):

$$\theta_{\text{train}} = \arg\min_\theta \mathcal{L}(X_{\text{train}})$$

$$X_{\text{train}}^* = \mathcal{T}(X_{\text{train}}; \theta_{\text{train}}), \quad X_{\text{test}}^* = \mathcal{T}(X_{\text{test}}; \theta_{\text{train}})$$

1. **Missing Value Imputation:** Numerical features are imputed using training fold medians; categorical features using training fold modes.
2. **Standardization:** Continuous biomarkers are scaled to zero mean and unit variance using training parameters:
   $$z = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}}$$
3. **Class Balancing (Training Folds Only):** SMOTE (Synthetic Minority Over-sampling Technique) is applied exclusively within training folds inside an `imblearn.pipeline.Pipeline`, preventing synthetic samples from leaking into test evaluations.

---

## 12. Mathematical and Statistical Foundations

### 12.1 Race-Free CKD-EPI 2021 eGFR Equation
The Chronic Kidney Disease Epidemiology Collaboration (CKD-EPI) 2021 creatinine equation calculates estimated glomerular filtration rate without race coefficients:

$$\text{eGFR} = 142 \times \min\left(\frac{S_{\text{cr}}}{\kappa}, 1\right)^\alpha \times \max\left(\frac{S_{\text{cr}}}{\kappa}, 1\right)^{-1.200} \times 0.9938^{\text{Age}} \times [1.012 \text{ if female}]$$

Where:
- $S_{\text{cr}}$ is serum creatinine in $\text{mg/dL}$.
- $\kappa = 0.7$ for females, $0.9$ for males.
- $\alpha = -0.241$ for females, $-0.302$ for males.
- $\min\left(\frac{S_{\text{cr}}}{\kappa}, 1\right)$ captures the inflection point at physiological baseline.

### 12.2 Hybrid Consensus Feature Selection Ranking
Four independent feature importance metrics were computed across training data:
1. **Mutual Information ($I(X; Y)$):** Shannon entropy reduction.
2. **ANOVA F-Statistic ($F$):** Ratio of between-group to within-group variance.
3. **Random Forest Gini Importance ($I_G$):** Mean decrease in node impurity.
4. **Recursive Feature Elimination (RFE):** Backward elimination rank under Logistic Regression.

The consensus rank score for biomarker $j$ is defined as the normalized sum:

$$R_j = \sum_{m=1}^4 \frac{\text{Rank}_{m}(j)}{4}$$

Distilling the Top-10 consensus features: `['hemo', 'sg', 'pcv', 'rc', 'al', 'htn', 'sc', 'bu', 'dm', 'bgr']`.

### 12.3 Tangri 4-Variable Kidney Failure Risk Equation (KFRE)
The Tangri equation estimates the probability of progression to kidney replacement therapy:

$$P(\text{KRT in } t \text{ years}) = 1 - S_0(t)^{\exp(\beta^T (X - \mu))}$$

Where:
- $\beta^T (X - \mu) = -0.2201 \times \left(\frac{\text{Age}}{10} - 7.036\right) + 0.2467 \times (\text{Male} - 0.5642) - 0.5567 \times \left(\frac{\text{eGFR}}{5} - 7.222\right) + 0.4510 \times (\ln(\text{UACR}) - 5.137)$
- North American baseline survival: $S_0(2) = 0.9751$, $S_0(5) = 0.8996$.
- Non-North American baseline survival: $S_0(2) = 0.9832$, $S_0(5) = 0.9365$.

### 12.4 Linear Mixed-Effects Trajectory Model
To account for within-patient correlation across longitudinal visits, the filtration trajectory of patient $i$ at time $t_{ij}$ is modeled as:

$$Y_{ij} = (\beta_0 + b_{0i}) + (\beta_1 + b_{1i}) t_{ij} + \epsilon_{ij}$$

Where $\mathbf{b}_i \sim \mathcal{N}(\mathbf{0}, \mathbf{D})$ are random intercepts and slopes estimated via Best Linear Unbiased Predictors (BLUP), providing robust shrinkage for patients with sparse visit histories.

### 12.5 Competing-Risk Aalen–Johansen Estimator
In CKD progression, cardiovascular mortality prior to ESRD acts as a competing risk. The cumulative incidence function (CIF) for event $k$ is estimated via:

$$\hat{I}_k(t) = \int_0^t \hat{S}(u^-) d\hat{\Lambda}_k(u)$$

Where $\hat{S}(u^-)$ is the overall event-free survival probability and $\hat{\Lambda}_k(u)$ is the cause-specific cumulative hazard.

---

## 13. Clinical Input Reliability and Safe Abstention (CD-CIRPVM)

The **Clinical Data-Correcting Input Reliability and Prediction Validity Mechanism (CD-CIRPVM)** enforces four safety guardrails:

```
[Input Data] ──► [1. MIDR Unit Reconciliation]
                         │
                         ▼
             [2. Boundary & Plausibility Validation]
                         │
                         ▼
             [3. Clinical Reliability Index (CRI)] ──► < 0.60? ──► [SAFE ABSTAIN]
                         │ (>= 0.60)
                         ▼
             [4. Inductive Conformal Gate] ───────► {0, 1}? ───► [SAFE ABSTAIN]
                         │ ({0} or {1})
                         ▼
             [Pass to Model Inference Engine]
```

1. **Magnitude-Inferred Dimensional Reconciliation (MIDR):** Detects international unit discrepancies and automatically standardizes them:
   - Serum Creatinine: If $> 30$, infer $\mu\text{mol/L}$ and multiply by $0.011312$ to yield $\text{mg/dL}$.
   - Hemoglobin: If $> 25$, infer $\text{g/L}$ and divide by $10$ to yield $\text{g/dL}$.
   - Blood Glucose: If $< 25$, infer $\text{mmol/L}$ and multiply by $18.018$ to yield $\text{mg/dL}$.
2. **Clinical Reliability Index (CRI):** A continuous score $CRI \in [0.0, 1.0]$ penalizing missing core tests and out-of-range physiological values.
3. **Selective Abstention Gate:** If $CRI < 0.60$ or if the conformal prediction set contains epistemic ambiguity $\{0, 1\}$, automated diagnosis is withheld with an explicit rationale:
   $$\text{Decision} = \text{ABSTAIN}$$

### 13.1 Clinical Discrepancy Auditing (Rules DISC-01 to DISC-08)
The unified orchestrator executes 8 cross-engine coherence audits:
- **DISC-01:** Engine 1 Low Risk ($P < 0.20$) coexisting with severe KDIGO staging (G4/G5 or A3).
- **DISC-02:** Engine 1 High Risk ($P \ge 0.50$) with normal filtration ($eGFR \ge 90$) and normoalbuminuria ($A1$).
- **DISC-03:** KDIGO severity evaluated on a single visit without 3-month chronicity confirmation.
- **DISC-04:** Severe filtration deficit ($eGFR < 30$) paired with mild albuminuria ($A1$).
- **DISC-05:** KFRE progression calculated when $eGFR \ge 60\text{ mL/min/1.73m}^2$ (out of validated KFRE scope; risk calculation withheld).
- **DISC-06:** Serum creatinine / eGFR discordance indicating possible laboratory error.
- **DISC-07:** Single isolated elevated blood pressure ($SBP \ge 140$) falsely represented as chronic hypertension.
- **DISC-08:** Critical missing core biomarker panel completeness.

---

## 14. Unified Assessment Orchestration

The backend orchestration layer is encapsulated in `src/engines/unified_assessment_engine.py`.

### 14.1 Execution Flow
1. Receives a structured `UnifiedAssessmentRequest` containing patient metadata, spot laboratory tests, and optional longitudinal visit history.
2. Evaluates CD-CIRPVM quality gates and computes CRI.
3. Dispatches inputs asynchronously to Engine 1, Engine 2, and Engine 3.
4. Executes discrepancy engine audits (DISC-01 to DISC-08).
5. Compiles findings into an immutable, type-annotated `UnifiedAssessmentResponse` dataclass.

### 14.2 Synthetic Demonstration Provenance Tracking
When an evaluation is triggered from a pre-configured synthetic preset, the system tags the assessment with `ProvenanceSource.SYNTHETIC_DEMONSTRATION`. This tag propagates through session state, triggers warning banners across all UI views, and injects prominent watermarks into exported reports.

---

## 15. Streamlit Application Implementation

The primary clinical user interface is launched via `app_streamlit.py` and implemented in `src/streamlit_app.py`.

### 15.1 Architectural Components
- **Top Header & Banner:** Displays system version, active engine status indicators, and the mandatory clinical disclaimer.
- **Multi-Tab Navigation:**
  1. `🏠 System Overview`: Clinical workflow, architectural summary, and quick-start links.
  2. `🩺 Patient Clinical Assessment`: Point-of-care laboratory entry form, demonstration preset selectors (Healthy Control, Diabetic Nephropathy, Early Hypertensive, Glomerulonephritis, Severe G4A3), real-time risk gauges, KDIGO CGA risk badges, and discrepancy alerts.
  3. `📈 Longitudinal Kidney Assessment`: Interactive historical observation table, annualized slope trajectory plots, and KFRE 2-year/5-year progression risk bar charts.
  4. `🔍 Explainability & Findings (XAI)`: Live patient-specific SHAP waterfall plots and local LIME decision-rule bar charts.
  5. `📄 Clinical Assessment Report`: Instant Markdown preview and multi-format downloadable exports.
  6. `📖 About & Clinical Governance`: Detailed algorithm specifications, dataset provenance, and SaMD disclaimers.

### 15.2 Multi-Format Export Engine
- **Vector PDF:** Generated programmatically via `reportlab` featuring clean typography, structured finding tables, and regulatory disclaimer blocks.
- **Sanitized CSV:** Enforces OWASP ASVS V5.1.4 / CWE-1236 protection, prefixing cells beginning with `=`, `+`, `-`, `@`, `\t`, or `\r` with an apostrophe `'` to prevent spreadsheet formula injection.
- **Machine-Readable JSON:** Full serialized representation of `UnifiedAssessmentResponse` for EHR integration.
- **Clinical Plain Text:** Structured summary formatted for clinical charting.

---

## 16. Docker and Reproducibility Architecture

### 16.1 Container Specifications
- **Base Image:** `python:3.10-slim` (Debian Bookworm).
- **Execution User:** `nefroai:nefroai` (`uid=1001, gid=1001`) — strictly unprivileged.
- **Internal Listener:** Streamlit listens on `0.0.0.0:8501` inside the container.
- **Host Port Mapping:** Bound strictly to `127.0.0.1:8501:8501` on the host, preventing external network exposure.
- **Resource Constraints:** Enforced via `compose.yaml` (2.0 CPUs, 2.0 GB RAM).
- **Health Check:** Container executes `curl -f http://127.0.0.1:8501/_stcore/health` with a 30 s interval and 60 s startup period.

### 16.2 Image Size Optimization
By excluding unused computer-vision dependencies (`torch`, `torchvision`, `ultralytics`, `opencv-python`), the uncompressed image footprint was reduced from **~4.2 GB down to ~650 MB**.

---

## 17. Testing Methodology & Quality Assurance

NEFROAI-X is backed by an automated 19-module testing suite executed via `pytest`:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
```

### 17.1 Test Module Inventory & Coverage

| Test Module | Coverage Scope | Tests | Status |
|---|---|---|---|
| `test_comprehensive_verification.py` | Preprocessing, feature selection, baselines, leakage audits | 43 | **PASS** |
| `test_clinical_system.py` | Full pipeline integration, calibration, Brier score, latency | 24 | **PASS** |
| `test_invention_prototype.py` | CD-CIRPVM MIDR, CRI calculation, conformal prediction, abstention | 18 | **PASS** |
| `test_kdigo_severity.py` | CKD-EPI 2021 eGFR, KDIGO CGA grid, edge cases, unit conversion | 28 | **PASS** |
| `test_nhanes_harmonization.py` | NHANES 2017–2018 mapping, biomarker distributions, completeness | 16 | **PASS** |
| `test_progression_features.py` | Time-aware longitudinal feature extraction, slope metrics | 14 | **PASS** |
| `test_longitudinal_simulator.py` | Synthetic longitudinal sequence generator determinism | 12 | **PASS** |
| `test_longitudinal_loader.py` | Serial CSV ingestion, validation, chronological sorting | 15 | **PASS** |
| `test_kfre_calculator.py` | Tangri 4-variable formula, regional profiles, G3–G5 gating | 16 | **PASS** |
| `test_kidney_progression_engine.py` | Engine 3 orchestrator, trajectory integration, KFRE invocation | 15 | **PASS** |
| `test_egfr_trajectory_lmm.py` | OLS regression vs Linear Mixed-Effects Model BLUP estimation | 14 | **PASS** |
| `test_survival_contracts.py` | Survival data schemas, competing-risk data structures | 12 | **PASS** |
| `test_survival_models_and_evaluation.py` | Cox PH baseline, RSF architecture, time-dependent C-index | 20 | **PASS** |
| `test_survival_statistical_verification.py` | Mathematical verification of survival algorithms | 18 | **PASS** |
| `test_survival_competing_risk_calibration.py` | Aalen-Johansen CIF calibration and Brier score evaluation | 16 | **PASS** |
| `test_unified_assessment_engine.py` | Three-engine orchestrator, discrepancy rules DISC-01 to DISC-08 | 31 | **PASS** |
| `test_streamlit_application.py` | Streamlit navigation, presets, views, session state, exports | 24 | **PASS** |
| `test_phase9_qa_security.py` | CSV formula injection sanitization, provenance, bound checks | 13 | **PASS** |
| **Total Automated Regression Suite** | **Entire Multimodal Clinical System** | **349** | **100% PASS** |

---

## 18. Results and Implementation Evidence

### 18.1 Baseline ML Model Comparison (UCI CKD Test Split, $N=80$)

| Model Architecture | Accuracy | Sensitivity (Recall) | Specificity | Precision | F1-Score | ROC-AUC | Brier Score | Latency (ms) |
|---|---|---|---|---|---|---|---|---|
| **Random Forest (Champion)** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **1.0000** | **1.0000** | **0.0095** | **0.041** |
| **Gradient Boosting** | 100.0% | 100.0% | 100.0% | 100.0% | 1.0000 | 1.0000 | 0.0002 | 0.052 |
| **Support Vector Machine** | 98.75% | 98.00% | 100.0% | 100.0% | 0.9899 | 1.0000 | 0.0163 | 0.089 |
| **Logistic Regression** | 98.75% | 98.00% | 100.0% | 100.0% | 0.9899 | 0.9993 | 0.0125 | 0.038 |
| **K-Nearest Neighbors** | 98.75% | 98.00% | 100.0% | 100.0% | 0.9899 | 0.9987 | 0.0142 | 0.125 |

### 18.2 Runtime Latency Profile
- Model Deserialization: $10.88\text{ ms}$
- Engine 1 Inference (single patient): $15.75\text{ ms}$
- Engine 2 Staging: $0.0063\text{ ms}$
- Engine 3 KFRE Reference: $0.0118\text{ ms}$
- Unified 3-Engine Orchestration: $37.65\text{ ms}$
- Vector PDF Generation: $823.86\text{ ms}$
- Total Application Memory Footprint: $\approx 209\text{ MB}$ RSS

---

## 19. Discussion

The empirical results demonstrate that compressing the diagnostic feature space from 24 to 10 consensus biomarkers preserves discriminatory power while yielding substantial operational advantages:
1. **Clinical Feasibility:** The 10 consensus markers are available in standard routine laboratory workups, eliminating the need for specialized nephrology panels during initial screening.
2. **Coherence via Multi-Engine Triaging:** Independent point screening (Engine 1) and guideline staging (Engine 2) frequently provide complementary insights. When discordance occurs (e.g., DISC-01 or DISC-02), the Discrepancy Engine prevents erroneous clinician reassurance.
3. **Transparent Explainability:** SHAP waterfall plots ground statistical risk in biological reality, allowing clinicians to verify whether an elevated risk estimate is driven by acute azotemia (`sc`, `bu`) or long-standing microvascular damage (`bgr`, `dm`, `al`).

---

## 20. Limitations and Ethical Considerations

1. **Non-Diagnostic Nature:** NEFROAI-X is not an autonomous diagnostic agent. Its outputs represent statistical risk estimations that must be adjudicated by licensed medical professionals.
2. **Small Primary Training Cohort:** The primary ML model was developed on the UCI CKD cohort ($N=400$). While stratified cross-validation and SMOTE were executed rigorously, broad external generalizability across diverse global populations requires larger prospective cohorts.
3. **Cross-Sectional Sampling Bias:** Single-visit laboratory tests cannot definitively differentiate chronic parenchymal disease from reversible acute kidney injury (AKI) or hemodynamic fluctuations.
4. **Deferred Survival Validation:** Longitudinal survival modeling is architecturally implemented but untrained on real longitudinal cohorts pending CRIC DUA execution.
5. **Python 3.10 Legacy Status:** Python 3.10 reached upstream EOL in October 2026. The production container is classified as a legacy reproduction environment and must not be exposed to public networks.

---

## 21. Conclusion

NEFROAI-X successfully demonstrates a leak-free, explainable, and multi-engine Clinical Decision Support System for Chronic Kidney Disease. By harmonizing machine learning screening with KDIGO guideline staging, KFRE progression analysis, and CD-CIRPVM input reliability safeguards, the framework overcomes the critical vulnerabilities of conventional clinical informatics. Packaged within a hardened, local-only Docker container and certified by a 349-test regression suite, NEFROAI-X establishes an open, reproducible foundation for clinical AI decision support research.

---

## 22. Future Work

1. **CRIC Longitudinal Cohort Integration:** Secure institutional Data Use Agreements to train and prospectively validate the Cox PH and Random Survival Forest progression engines.
2. **Python 3.12+ Native Model Re-Training:** Upgrade auxiliary database dependencies and retrain the champion model natively under Python 3.12+ to eliminate legacy runtime constraints.
3. **HL7 FHIR Interoperability Connector:** Implement standardized HL7 FHIR (Fast Healthcare Interoperability Resources) data adapters to facilitate secure, automated ingestion from hospital Electronic Health Record (EHR) systems.
4. **Multi-Center Prospective Clinical Trial:** Conduct an IRB-approved prospective observational clinical study in primary care clinics to evaluate diagnostic utility and clinician adherence.

---

## 23. References

1. Al Huda, Md. Sadi, et al. "Explainable and Real-Time Framework for Predicting Chronic Kidney Disease Using Diverse Machine Learning Models and Different Feature Selection Techniques." *IEEE Access*, vol. 11, 2023, pp. 62725–62744.
2. Inker, Lesley A., et al. "New Creatinine- and Cystatin C–Based Equations to Estimate GFR without Race." *New England Journal of Medicine*, vol. 385, no. 19, 2021, pp. 1737–1749.
3. Kidney Disease: Improving Global Outcomes (KDIGO) CKD Work Group. "KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease." *Kidney International*, vol. 105, no. 4S, 2024, pp. S117–S314.
4. Tangri, Navdeep, et al. "A Predictive Model for Progression of Chronic Kidney Disease to Kidney Failure." *JAMA*, vol. 305, no. 15, 2011, pp. 1553–1559.
5. Tangri, Navdeep, et al. "Multinational Assessment of Accuracy of Equations for Predicting Risk of Kidney Failure: A Meta-analysis." *JAMA*, vol. 315, no. 2, 2016, pp. 164–174.
6. Lundberg, Scott M., and Su-In Lee. "A Unified Approach to Interpreting Model Predictions." *Advances in Neural Information Processing Systems (NeurIPS 2017)*, vol. 30, 2017.
7. Ribeiro, Marco Tulio, Sameer Singh, and Carlos Guestrin. "'Why Should I Trust You?': Explaining the Predictions of Any Classifier." *ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (KDD 2016)*, 2016, pp. 1135–1144.
8. National Center for Health Statistics (NCHS). "National Health and Nutrition Examination Survey (NHANES) 2017–2018 Data Files." *Centers for Disease Control and Prevention (CDC)*, 2020.
9. Feldman, Harold I., et al. "The Chronic Renal Insufficiency Cohort (CRIC) Study: Design and Methods." *Journal of the American Society of Nephrology*, vol. 14, no. 7 suppl 2, 2003, pp. S148–S153.
10. Aalen, Odd O., and Soren Johansen. "An Empirical Transition Matrix for Non-Homogeneous Markov Chains Based on Censored Observations." *Scandinavian Journal of Statistics*, vol. 5, no. 3, 1978, pp. 141–150.
