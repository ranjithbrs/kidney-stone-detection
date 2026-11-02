# Dataset Audit Report & Final Dataset Plan
**Project:** Kidney Disease & Nephrolithiasis AI Diagnosis (NefroAI Implementation)  
**Date:** November 2026  
**Audited Datasets:** Dataset A (UCI CKD), Dataset B (Kidney Stone Urinalysis), Dataset C (Kaggle CKD)

---

## 1. Executive Summary

This audit evaluates the three clinical tabular datasets acquired for implementing the NefroAI framework. The datasets provide complementary views of renal pathology:
- **Systemic Chronic Kidney Disease (CKD)** via routine blood and urine biomarkers (Datasets A and C).
- **Kidney Stone (Nephrolithiasis) Crystallization Risk** via physicochemical urinalysis (Dataset B).

---

## 2. Dataset Metrics Breakdown

| Metric | Dataset A (UCI CKD) | Dataset B (Kidney Stone) | Dataset C (Kaggle CKD) |
| :--- | :--- | :--- | :--- |
| **Source** | Apollo Hospitals / UCI ML | Kaggle / Urinalysis Study | Kaggle Clinical Cohort |
| **Sample Size (Rows)** | 400 | 90 | 400 |
| **Total Features** | 24 clinical + 1 target | 6 physicochemical + 1 target | 24 clinical + 1 target |
| **Target Column** | `classification` | `target` | `classification` |
| **Target Classes** | `ckd` (250), `notckd` (150) | `1` (45), `0` (45) | `ckd` (250), `notckd` (150) |
| **Class Balance** | 62.5% vs 37.5% | **50.0% vs 50.0% (Perfect)** | 62.5% vs 37.5% |
| **Duplicate Rows** | 0 (0%) | 0 (0%) | 0 (0%) |
| **Total Missing Values** | 1,012 | 0 (None) | 1,009 |
| **Missing % in Dataset** | ~10.5% of total cells | 0.0% | ~10.5% of total cells |
| **Features with Missing** | 24 out of 24 features | 0 | 24 out of 24 features |

---

## 3. Deep Dive into Data Integrity & Quality

### 3.1 Missing Values Analysis (Datasets A & C)
* **High Missingness (>25%)**:
  * Red Blood Cells (`rbc`): 152 missing (38.0%)
  * Red Blood Cell Count (`rc`): 131 missing (32.8%)
  * White Blood Cell Count (`wc`): 106 missing (26.5%)
* **Moderate Missingness (10% - 25%)**:
  * Potassium (`pot`): 88 missing (22.0%)
  * Sodium (`sod`): 87 missing (21.8%)
  * Packed Cell Volume (`pcv`): 71 missing (17.8%)
  * Pus Cell (`pc`): 65 missing (16.3%)
  * Hemoglobin (`hemo`): 52 missing (13.0%)
  * Sugar (`su`): 49 missing (12.3%)
  * Specific Gravity (`sg`): 47 missing (11.8%)
  * Albumin (`al`): 46 missing (11.5%)
  * Blood Glucose Random (`bgr`): 44 missing (11.0%)
* **Low Missingness (<10%)**:
  * Blood Urea (`bu`): 19 missing (4.8%)
  * Serum Creatinine (`sc`): 17 missing (4.3%)
  * Blood Pressure (`bp`): 12 missing (3.0%)
  * Age (`age`): 9 missing (2.3%)
  * Pus Cell Clumps (`pcc`), Bacteria (`ba`), Hypertension (`htn`), Diabetes (`dm`), CAD, Appetite, Pedal Edema, Anemia: <2% missing.

### 3.2 Data Formatting & Type Coercion Findings
* In Dataset C, columns `pcv`, `wc`, and `rc` contain embedded tab characters (`\t`) and special question mark characters (`?` or `\t?`), causing Pandas to parse them as text (`object`) instead of floating-point numbers.
* The target column in Datasets A and C contains trailing whitespace/tabs (e.g. `'ckd\t'`), requiring string sanitization before model encoding.

---

## 4. Cross-Dataset Feature Comparison

| Physiological Category | Dataset A / C (CKD) Features | Dataset B (Kidney Stone) Features | Physiological Relevance |
| :--- | :--- | :--- | :--- |
| **Urinary Concentration** | `sg` (Specific Gravity: 1.005–1.025) | `gravity` (Specific Gravity: 1.005–1.040) | Urine concentration directly influences stone precipitation and tubular reabsorption efficiency. |
| **Nitrogenous Waste** | `bu` (Blood Urea: 1.5–391 mg/dL) | `urea` (Urine Urea: 10–640 mmol/L) | Uremic toxicity reflects glomerular filtration reduction; urinary urea affects uric acid crystallization. |
| **Acid-Base Balance** | - | `ph` (Urine pH: 4.76–7.94) | Acidic pH (<5.5) promotes uric acid and cystine stones; alkaline pH (>7.0) promotes calcium phosphate/struvite. |
| **Solute & Osmolarity** | `sod` (Sodium), `pot` (Potassium) | `osmo` (Osmolality), `cond` (Conductivity) | Total ionic solute concentration driving supersaturation of stone-forming salts. |
| **Mineral Excretion** | - | `calc` (Urine Calcium: 0.17–14.3 mmol/L) | Hypercalciuria is the leading etiology for calcium oxalate stone formation. |
| **Glomerular / Cellular** | `sc`, `al`, `rbc`, `pc`, `hemo`, `pcv` | - | Proteinuria, hematuria, and impaired creatinine clearance indicate nephron structural damage. |

---

## 5. Ethical & Responsible AI Usage

1. **Patient De-Identification**: The datasets are thoroughly anonymized. No names, medical record numbers (MRNs), phone numbers, or geolocations are present.
2. **Clinical Decision Support (CDSS)**: The models are intended to serve as risk screening and triaging tools for clinicians, never as autonomous diagnostic replacements.
3. **Transparent Explanations**: SHAP and LIME explanations must always accompany model outputs to prevent blind trust in AI probability scores.
4. **Demographic Sensitivity**: The data reflects specific regional demographic distributions (e.g., Apollo Hospitals cohort). Disclaimers must be included regarding validation across diverse populations.

---

## 6. Final Dataset Plan

```
[Raw CSVs] 
    │
    ▼
[Data Sanitizer (src/data_cleaner.py)]
    ├── Strip whitespace & whitespace-tab artifacts ('\t')
    ├── Cast numerical columns (pcv, wc, rc) to float64
    ├── Impute numerical columns via Median
    ├── Impute categorical columns via Mode
    ├── Label encode categorical features & targets
    └── Standardize feature names
    │
    ▼
[Cleaned Artifacts] ──► datasets/clinical/clean_dataset_A.csv
                    ──► datasets/clinical/clean_dataset_B.csv
                    ──► datasets/clinical/clean_dataset_C.csv
    │
    ▼
[Preprocessed Splits]
    ├── 80/20 Stratified Train/Test Split
    ├── Min-Max / Standard Scaler fit on Train only
    └── SMOTE applied strictly to Training set to balance class distribution
```
