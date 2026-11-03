# NEFROAI-X: Existing Repository & Clinical Dataset Inventory

**Framework:** NEFROAI-X — Advanced Explainable Hybrid AI Framework  
**Phase:** Phase 5 — Dataset Collection & Clinical Data Harmonization  
**Audit Date:** 2026-11-03  
**Status:** Certified Ground Truth Audit  

---

## 1. Executive Summary

An exhaustive clinical data audit was conducted across all datasets residing in `datasets/clinical/`. The audit verified record counts, schemas, target distributions, missingness patterns, cryptographic SHA-256 hashes, and cross-dataset independence.

### Summary Overview Table

| Dataset Identifier | File Path | File Size | SHA-256 Checksum | Dimensions (Rows × Cols) | Missing Cells (%) | Target Column & Classes | Clinical Suitability for NEFROAI-X |
|---|---|---|---|:---:|:---:|---|---|
| **Dataset A (UCI CKD)** | `datasets/clinical/dataset_A_uci_ckd.csv` | 43,578 bytes | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | $400 \times 26$ | 1,012 / 10,400 (9.73%) | `classification`: `ckd` (248), `notckd` (150), `ckd\t` (2) | **Primary Training Ground Truth** (Engine 1) |
| **Dataset C (Kaggle Mirror)** | `datasets/clinical/dataset_C_kaggle_ckd.csv` | 48,551 bytes | `835c57ec100db2d3751165fae615fec425caf444cca23bab6a853d4c08bf5556` | $400 \times 26$ | 1,009 / 10,400 (9.70%) | `classification`: `ckd` (248), `notckd` (150), `ckd\t` (2) | **Duplicate Mirror Only** (Not independent validation) |
| **Dataset B (Kidney Stone)** | `datasets/clinical/dataset_B_kidney_stone.csv` | 3,725 bytes | `30083bb37abfe2a48980e363bd12546a20215558f9968b2fae6368bb2fb5b579` | $90 \times 8$ | 0 / 720 (0.00%) | `target`: 0 (45), 1 (45) | **Incompatible** (Calcium oxalate nephrolithiasis) |
| **Dataset C (Simpson Stone)** | `datasets/clinical/dataset_C_simpson_kidney.csv` | 7,029 bytes | `858d079f350e3cf0515787de81eac139a9eab499f6fda2818c767dd1614d3d70` | $700 \times 3$ | 0 / 2,100 (0.00%) | `success`: 0 / 1 (Surgical outcome) | **Incompatible** (Surgical nephrolithotomy outcomes) |

---

## 2. Detailed Dataset Profiles

### 2.1 Dataset A — UCI Chronic Kidney Disease (Primary Ground Truth)
- **Source**: UCI Machine Learning Repository ([https://archive.ics.uci.edu/dataset/336/chronic+kidney+disease](https://archive.ics.uci.edu/dataset/336/chronic+kidney+disease)), collected by Apollo Hospitals, Manipal Hospitals, and Apollo Gleneagles Hospital in India (Dr. P. Soundarapandian et al.).
- **Cohort Size**: 400 patient records.
- **Features**: 24 clinical biomarkers + `id` + `classification`:
  - Hematological & Urinalysis: `age, bp, sg, al, su, rbc, pc, pcc, ba, bgr, bu, sc, sod, pot, hemo, pcv, wc, rc`.
  - Clinical History: `htn, dm, cad, appet, pe, ane`.
- **Target Distribution**:
  - `ckd`: 248 records (62.0%)
  - `notckd`: 150 records (37.5%)
  - `ckd\t` (whitespace artifact): 2 records (0.5%)
  - Cleaned binary balance: 250 CKD positive (62.5%), 150 Healthy control (37.5%).
- **Missingness**: 1,012 missing values out of 10,400 data cells (9.73%). No patient record is 100% complete across all 24 features.
- **NEFROAI-X Role**: Serves as the authoritative supervised classification baseline for Engine 1 (CKD Screening).

### 2.2 Dataset C — Kaggle CKD Dataset (Mirror Audit)
- **Source**: Kaggle mirror of the UCI CKD repository.
- **Findings**:
  - Contains exactly 400 records and the identical 26 column headers.
  - Target breakdown is identically distributed (`ckd`: 248, `notckd`: 150, `ckd\t`: 2).
  - Minor byte-level divergence is caused solely by numerical formatting in three string columns: `pcv` (packed cell volume), `wc` (white blood cell count), and `rc` (red blood cell count), which are formatted as integers or raw strings in Dataset C (e.g., `'44'`) versus floats in Dataset A (e.g., `44.0`).
- **Audit Conclusion**: Dataset C contains zero new patient records and represents a non-independent mirror of Dataset A. It must never be represented as an external independent validation cohort in research reports.

### 2.3 Legacy Contaminant Datasets (Kidney Stone / Nephrolithiasis)
- **`dataset_B_kidney_stone.csv`**:
  - 90 urine samples measuring physical-chemical crystal parameters (`gravity, ph, osmo, cond, urea, calc`) for calcium oxalate nephrolithiasis crystal formation.
  - Lacks essential renal biomarkers: serum creatinine, hemoglobin, albumin, BUN, and glomerular filtration surrogates.
  - Excluded permanently from CKD training.
- **`dataset_C_simpson_kidney.csv`**:
  - 700 surgical intervention records evaluating open surgery vs. percutaneous nephrolithotomy outcomes for kidney stones (Simpson's Paradox benchmark).
  - Lacks all laboratory and hematological variables.
  - Excluded permanently from CKD training.

---

## 3. Production Model Artifact Integrity

- **Artifact**: `models/clinical_pipeline.joblib`
- **File Size**: 141,177 bytes
- **SHA-256 Checksum**: `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826`
- **Status**: Strictly preserved and verified unmodified throughout all Phase 5 operations.
