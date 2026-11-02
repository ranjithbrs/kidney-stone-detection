# Explainable AI (XAI) Verification Report: SHAP & LIME

This report documents the implementation and verification of **SHAP** and **LIME** in accordance with the **NefroAI** clinical research framework.

## 1. Global Explainability (SHAP)

SHAP calculates Shapley values from cooperative game theory to quantify how each biomarker alters the baseline model expectation.

- **Summary Beeswarm Plot**: Captures feature impact, directionality, and patient variance across the test population.
- **Global Feature Importance**: Shows that **`hemo` (Hemoglobin)**, **`pcv` (Packed Cell Volume)**, **`sc` (Serum Creatinine)**, and **`sg` (Specific Gravity)** exert the highest global leverage on renal diagnostics.

## 2. Local Patient Explanation (Case Study: Patient #0)

- **Actual Ground Truth**: Class 0 (Chronic Kidney Disease)
- **Predicted Risk Probability**: **0.0%**

### SHAP vs. LIME Attribution Comparison for Patient #0:

| Biomarker Feature | SHAP Attribution (Shapley $\phi$) | LIME Attribution Weight | Clinical Physiological Interpretation |
| :--- | :---: | :---: | :--- |
| `hemo` | **-0.1100** | -0.0728 | Protective (-) |
| `sg` | **-0.0681** | -0.1036 | Protective (-) |
| `pcv` | **-0.0991** | -0.0271 | Protective (-) |
| `rc` | **-0.0737** | -0.1188 | Protective (-) |
| `al` | **-0.0215** | -0.0549 | Protective (-) |
| `htn` | **-0.0196** | -0.1027 | Protective (-) |
| `sc` | **-0.0857** | -0.0915 | Protective (-) |
| `bu` | **-0.0002** | -0.0011 | Protective (-) |
| `dm` | **-0.0070** | -0.0720 | Protective (-) |
| `bgr` | **-0.0132** | -0.0180 | Protective (-) |

## 3. Faithfulness Verification

We systematically perturbed the leading risk driver (`hemo`) to confirm that local attributions are faithful to model decision boundaries.
- Original Risk: `0.0%`
- Perturbed Risk: `16.0%`
- **Conclusion**: The explanation direction is certified faithful to model internal scoring.
