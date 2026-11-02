# Feature Selection & Model Performance Comparison Report

This report analyzes the individual and hybrid feature selection techniques applied to the clinical datasets as described in the **NefroAI** paper.

## 1. Dataset A (UCI Chronic Kidney Disease)

### Top 10 Consensus Biomarkers (Hybrid Feature Selection)
| Rank | Feature | Description | Consensus Rank Score | Mutual Info | RF Gini Importance |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **#1** | `hemo` | Hemoglobin (g/dL) | 2.5 | 0.5058 | 0.2355 |
| **#2** | `sg` | Specific Gravity | 3.5 | 0.3302 | 0.1087 |
| **#3** | `pcv` | Packed Cell Volume (%) | 3.5 | 0.476 | 0.1621 |
| **#4** | `rc` | Red Blood Cell Count | 4.75 | 0.4171 | 0.1057 |
| **#5** | `al` | Albumin | 5.75 | 0.2989 | 0.0404 |
| **#6** | `htn` | Hypertension | 7.0 | 0.2451 | 0.0589 |
| **#7** | `sc` | Serum Creatinine (mg/dL) | 7.25 | 0.4003 | 0.1321 |
| **#8** | `bu` | Blood Urea (mg/dL) | 8.25 | 0.1809 | 0.0213 |
| **#9** | `dm` | Diabetes Mellitus | 8.25 | 0.2114 | 0.0408 |
| **#10** | `bgr` | Blood Glucose Random (mg/dL) | 9.25 | 0.1835 | 0.0201 |

### Redundancy & Collinearity Findings (Dataset A)
- **`hemo` & `pcv`**: Pearson $r = 0.8407$. (*Physiological reason*: Hemoglobin and Packed Cell Volume both directly measure red blood cell volume/oxygen carrying capacity; one can serve as a surrogate for the other).

### Performance Comparison: Full 24 Features vs Selected Top 10 Subsets

| Model | Full 24 Features (Acc / F1 / AUC) | Hybrid Top 10 (Acc / F1 / AUC) | MI Filter Top 10 (Acc / F1 / AUC) | RFE Wrapper Top 10 (Acc / F1 / AUC) |
| :--- | :---: | :---: | :---: | :---: |
| **Random Forest** | 100.0% / 1.000 / 1.000 | **100.0% / 1.000 / 1.000** | 100.0% / 1.000 / 1.000 | 98.8% / 0.990 / 1.000 |
| **Logistic Regression** | 97.5% / 0.980 / 1.000 | **100.0% / 1.000 / 1.000** | 100.0% / 1.000 / 1.000 | 100.0% / 1.000 / 1.000 |
| **Decision Tree** | 97.5% / 0.980 / 0.973 | **98.8% / 0.990 / 0.990** | 97.5% / 0.980 / 0.980 | 97.5% / 0.980 / 0.973 |
| **Support Vector Machine** | 98.8% / 0.990 / 1.000 | **100.0% / 1.000 / 1.000** | 100.0% / 1.000 / 1.000 | 100.0% / 1.000 / 1.000 |
| **K Nearest Neighbors** | 96.2% / 0.969 / 1.000 | **98.8% / 0.990 / 1.000** | 97.5% / 0.980 / 1.000 | 98.8% / 0.990 / 1.000 |

---

## 2. Dataset B (Kidney Stone Urinalysis)

### Top Selected Urinalysis Indicators
| Rank | Feature | Description | Consensus Score | MI Score | RF Importance |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **#1** | `calc` | Calcium concentration (mmol/L) | 1.5 | 0.2217 | 0.3013 |
| **#2** | `gravity` | Urine Specific Gravity | 1.75 | 0.2124 | 0.2222 |
| **#3** | `osmo` | Osmolality (mOsm) | 3.5 | 0.0 | 0.1498 |
| **#4** | `urea` | Urea concentration (mmol/L) | 4.25 | 0.0182 | 0.1456 |

### Performance Comparison: Full 6 Features vs Hybrid Top 4 (Dataset B)

| Model | Full 6 Features (Acc / F1 / AUC) | Hybrid Top 4 Features (Acc / F1 / AUC) |
| :--- | :---: | :---: |
| **Random Forest** | 72.2% / 0.762 / 0.802 | **61.1% / 0.667 / 0.790** |
| **Logistic Regression** | 77.8% / 0.800 / 0.852 | **77.8% / 0.800 / 0.852** |
| **Decision Tree** | 61.1% / 0.667 / 0.611 | **61.1% / 0.667 / 0.611** |
| **Support Vector Machine** | 72.2% / 0.737 / 0.741 | **72.2% / 0.737 / 0.765** |
| **K Nearest Neighbors** | 66.7% / 0.700 / 0.673 | **50.0% / 0.571 / 0.660** |
