# Reproduction Instructions: NEFROAI-X Phase 2 Independent Validation Challenge

This document provides exact, deterministic commands to reproduce every finding, metric table, and visualization from the **Phase 2 Independent Validation Challenge**.

---

## 1. Prerequisites & Execution Environment

- **Operating System:** Windows, Linux, or macOS
- **Python Version:** Python 3.10.x
- **Project Virtual Environment:** `.venv`
- **Required Libraries:** `pandas`, `numpy`, `scipy`, `scikit-learn`, `imbalanced-learn`, `matplotlib`, `seaborn`, `joblib`

---

## 2. One-Line Execution Command

To run the complete audit from scratch and regenerate all 6 CSV files, 2 publication-grade figures, and logs:

```powershell
.venv\Scripts\python.exe audit/phase2/phase2_audit_script.py
```

Execution runtime is approximately **30 to 45 seconds**.

---

## 3. Verified Output Artifacts

Upon completion, confirm the generation of the following artifacts in `audit/phase2/`:

| Artifact | File Path | Description |
|---|---|---|
| **Audit Script** | `audit/phase2/phase2_audit_script.py` | Complete self-contained script executing Sections A through G. |
| **Nested CV & Feature Selection** | `audit/phase2/nested_cv_results.csv` | 5-fold Nested CV results, fold stability ($J=0.8576$), and 10-feature vs 24-feature comparison. |
| **Multi-Seed Robustness Table** | `audit/phase2/multi_seed_robustness.csv` | Full metric results across 10 random seeds with Clopper-Pearson 95% CIs and summary statistics. |
| **Calibration Curves Plot** | `audit/phase2/calibration_curves.png` | Reliability diagrams and ECE comparisons for 7 baseline classifiers. |
| **Multi-Seed Distribution Plot** | `audit/phase2/multi_seed_robustness.png` | 4-panel figure showing Accuracy, Sensitivity/Specificity, Brier score, and ROC-AUC across seeds. |
| **CD-CIRPVM Stress Test Data** | `audit/phase2/cirpvm_stress_test.csv` | 500 simulated stress-test records assessing acceptance, abstention, and unit reconciliation. |
| **External Validation Audit** | `audit/phase2/external_validation_audit.csv` | Audits of Kaggle mirror, contaminant stone datasets, and NHANES 2017-2018 ($N=5,154$). |
| **Regression & Progression Audit** | `audit/phase2/regression_progression_audit.csv` | eGFR trajectory slope estimation (MAE/RMSE) and Tangri KFRE risk calculations. |
| **Full Technical Report** | `audit/phase2/phase2_technical_report.md` | Comprehensive scientific report detailing all Phase 2 findings. |

---

## 4. Verification Checklist

1. **Verify Section A:** Check console output confirms $80/80$ correct ($100.0\%$) on held-out split `seed=42`.
2. **Verify Section B:** Inspect `nested_cv_results.csv` to verify fold-level feature stability ($0.8576$).
3. **Verify Section C:** Inspect `calibration_curves.png` to confirm Random Forest exhibits superior probability calibration over AdaBoost ($\text{ECE}=0.0398$ vs $0.2714$).
4. **Verify Section D:** Confirm multi-seed mean accuracy across 10 seeds is **$98.88\% \pm 1.09\%$** (range: $97.50\% - 100.00\%$).
5. **Verify Section E:** Confirm CD-CIRPVM achieves **$100.0\%$ correct rejection** of corrupted inputs and **$0.0\%$ error rate** among accepted predictions.
6. **Verify Section F:** Confirm NHANES evaluated $N=5,154$ adult examined participants with $8.60\%$ having $\text{eGFR} < 60\text{ mL/min/1.73m}^2$.
7. **Verify Section G:** Confirm Tangri KFRE calculations match published JAMA 2016 reference standards.
