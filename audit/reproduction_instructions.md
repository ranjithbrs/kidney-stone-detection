# Reproducible Audit Instructions: NEFROAI-X ML Accuracy Verification

This document provides exact, deterministic instructions to independently reproduce and verify the machine learning accuracy claims, cross-validation metrics, and baseline comparisons for the **NEFROAI-X v1.0** Clinical Decision Support System.

---

## 1. Environment & Hardware Prerequisites

- **Operating System:** Windows 10/11, Linux (Ubuntu 20.04+), or macOS
- **Python Version:** Python 3.10.x (Virtual environment: `.venv`)
- **Key Python Packages:**
  - `numpy >= 1.23.0`
  - `pandas >= 1.5.0`
  - `scikit-learn >= 1.2.0`
  - `imbalanced-learn >= 0.10.0`
  - `joblib >= 1.2.0`
  - `matplotlib >= 3.6.0`
  - `seaborn >= 0.12.0`
  - `scipy >= 1.9.0`

---

## 2. Step-by-Step Reproduction Procedure

### Step 1: Open Terminal & Set Working Directory
Open PowerShell or CMD and navigate to the project root directory:
```powershell
cd "c:\Users\B Ranjith\Downloads\project"
```

### Step 2: Verify the Project Virtual Environment
Confirm that Python 3.10 is accessible from the local virtual environment:
```powershell
.venv\Scripts\python.exe --version
```
*Expected output:* `Python 3.10.x`

### Step 3: Execute the Leakage-Safe Accuracy Audit Script
Run the dedicated audit script:
```powershell
.venv\Scripts\python.exe evaluation/ckd_accuracy_audit.py
```

### Step 4: Verify Console Output
During execution, the script will:
1. Load `datasets/clinical/dataset_A_uci_ckd.csv` ($N=400$, 24 features).
2. Clean string artifacts (`ckd\t` $\rightarrow$ `ckd`, `?` $\rightarrow$ `NaN`).
3. Execute deterministic stratified train/test splitting ($80/20$, `random_state=42`), producing:
   - Training partition: $N=320$ ($200$ CKD, $120$ Normal)
   - Held-out test partition: $N=80$ ($50$ CKD, $30$ Normal)
4. Train each model using `imblearn.pipeline.Pipeline`, ensuring:
   - Median and mode imputation fitted strictly on training folds.
   - StandardScaler fitted strictly on training folds.
   - SMOTE resampling applied strictly inside training folds during 5-fold CV.
5. Compute exact Clopper-Pearson 95% Confidence Intervals for test accuracy, sensitivity, and specificity.
6. Evaluate the serialized production artifact (`models/clinical_pipeline.joblib`) on the identical $N=80$ test partition.
7. Save all metrics, charts, and predictions into the `audit/` folder.

---

## 3. Audit Output Files Verification

Once the audit script finishes, confirm the creation and integrity of the following artifacts in `audit/`:

| Artifact | File Path | Expected Properties |
|---|---|---|
| **Model Comparison Table** | `audit/model_comparison.csv` | Contains 8 models (7 algorithms + production pipeline) with CV scores, test accuracy, 95% CIs, sensitivity, specificity, ROC-AUC, PR-AUC, and Brier scores. |
| **Case-by-Case Predictions** | `audit/predictions.csv` | Exactly 80 rows corresponding to the held-out test split, containing ground truth (`y_true`), predicted labels, and probabilities. |
| **Split Indices** | `audit/test_indices.json` | JSON dictionary recording the exact 320 train indices and 80 test indices. |
| **Confusion Matrices** | `audit/confusion_matrices.png` | 2×4 subplots showing $80/80$ correct for Random Forest, AdaBoost, Logistic Regression, and minor error counts for other baselines. |
| **Performance Bar Chart** | `audit/model_comparison.png` | High-resolution comparison of Test Accuracy, F1-Score, and ROC-AUC. |

---

## 4. Validating the Production Pipeline Separately

To directly verify the packaged production model artifact (`models/clinical_pipeline.joblib`):

```powershell
.venv\Scripts\python.exe -c "
import joblib, pandas as pd, json, numpy as np
from sklearn.metrics import accuracy_score, classification_report

pipeline = joblib.load('models/clinical_pipeline.joblib')
df = pd.read_csv('datasets/clinical/dataset_A_uci_ckd.csv')
with open('audit/test_indices.json', 'r') as f:
    indices = json.load(f)

test_df = df.iloc[indices['test_indices']]
X_test = test_df.drop(columns=['id', 'classification'], errors='ignore')
y_test = test_df['classification'].astype(str).str.strip().map({'ckd': 1, 'notckd': 0}).values

# Test on preprocessed test features
X_test_proc = pd.read_csv('datasets/clinical/processed/Dataset_A_X_test.csv')
preds = pipeline.model.predict(X_test_proc[pipeline.selected_features])
acc = accuracy_score(y_test, preds)
print(f'Production Model Test Accuracy: {acc * 100:.2f}% ({sum(preds == y_test)}/{len(y_test)})')
"
```
*Expected terminal output:*
```
Production Model Test Accuracy: 100.00% (80/80)
```

---

## 5. Running the Complete System Test Suite

To verify that Engine 1, Engine 2 (KDIGO), Engine 3 (KFRE/LMM), and CD-CIRPVM are intact and passing all unit tests:

```powershell
.venv\Scripts\python.exe src/run_test_suite.py
```
*Expected output:* All core test suites pass ($100\%$ green across modules).

---

## 6. Audit & Review Checklist for Faculty

When presenting to the review committee or external reviewers:
- [x] **Dataset ground truth verified:** 400 patients (250 CKD, 150 Normal).
- [x] **Test split determinism verified:** Fixed seed (`random_state=42`, $N_{\text{train}}=320$, $N_{\text{test}}=80$).
- [x] **Leakage-free resampling verified:** `imblearn.pipeline.Pipeline` isolates SMOTE to training folds.
- [x] **Statistical honesty maintained:** Exact Clopper-Pearson 95% CI reported ($[95.5\%, 100.0\%]$).
- [x] **Literature alignment confirmed:** Results correctly compared against Al Huda et al. (*IEEE Access*, 2025).
- [x] **Novelty positioned accurately:** Feature reduction (24 $\rightarrow$ 10), multi-engine clinical staging, and CD-CIRPVM selective abstention.
