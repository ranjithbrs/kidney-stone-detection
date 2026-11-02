# CKD Project Roadmap using Antigravity
## Part 1 — Build the CKD Prediction System
### Live Demonstration Script & Examiner Viva Defense Guide

---

## 1. Quick Demonstration Setup

### 1.1 Starting the Streamlit Web Application
In your terminal, navigate to the project directory and launch the app:

```powershell
& ".venv\Scripts\streamlit.exe" run app_streamlit.py
```

The app will launch at **`http://localhost:8501`**.

---

## 2. Step-by-Step Viva Demonstration Walkthrough

### Step 1: System Overview & Architecture (1–2 minutes)
1. Open the browser to **`http://localhost:8501`**.
2. Select **`🏠 Overview & Architecture`** in the sidebar.
3. **Talking Points**:
   - Point out the 4 high-level metric cards:
     - **Clinical Sensitivity: 100.0%** ($0$ missed kidney disease patients).
     - **Clinical Specificity: 100.0%** ($0$ false alarms).
     - **ROC-AUC: 1.000** (Perfect diagnostic discrimination).
     - **Consensus Biomarkers: 10** (Down from 24, saving 60% in diagnostic lab costs).
   - Explain the architecture diagram:
     - Show how raw lab values flow through bounds clamping, leak-free imputation/scaling, consensus feature selection, Random Forest inference, and dual-layer XAI.

---

### Step 2: Clinical Diagnostic Presets & Real-Time Triage (3–4 minutes)
1. Navigate to **`🩺 Patient Clinical Diagnosis`** in the sidebar.

#### Demo Scenario A: Clinically Healthy Patient
1. Click the button: **`📋 Load Healthy Sample`**.
2. Point out the loaded biomarkers:
   - Hemoglobin: `15.2 g/dL` (Normal)
   - Specific Gravity: `1.025` (Concentrated, healthy tubular function)
   - Serum Creatinine: `0.8 mg/dL` (Safe GFR)
   - Urine Albumin: `0` (No proteinuria)
   - Hypertension / Diabetes: `No / No`
3. Click: **`🔍 Run Diagnostic Prediction`**.
4. **Outcome to Highlight**:
   - Green banner appears: **`✅ Healthy (No Chronic Kidney Disease)`**.
   - Calculated Disease Risk: **`0.0%`**.
   - Clinical Category: **`Low Risk (Normal)`**.
   - Progress bar remains near zero.
   - Point out the **Biomarker Impact Weights** horizontal bar chart showing normal protective leverage.

#### Demo Scenario B: High-Risk Renal Disease Patient
1. Click the button: **`⚠️ Load High-Risk Sample`**.
2. Point out the altered biomarkers:
   - Hemoglobin drops to: `8.4 g/dL` (Severe normocytic normochromic anemia)
   - Specific Gravity drops to: `1.010` (Isosthenuria, lost concentrating ability)
   - Serum Creatinine rises to: `4.2 mg/dL` (Severe nephron filtration failure)
   - Urine Albumin: `3` (Significant proteinuria)
   - Blood Urea: `78.0 mg/dL` (Accumulated uremic toxins)
   - Hypertension / Diabetes: `Yes / Yes` (Active microvascular injury)
3. Click: **`🔍 Run Diagnostic Prediction`**.
4. **Outcome to Highlight**:
   - Red alert banner appears: **`⚠️ Chronic Kidney Disease (At Risk)`**.
   - Calculated Disease Risk: **`100.0%`**.
   - Clinical Category: **`Critical Risk (Urgent Nephrology Consultation Required)`**.
   - Progress bar fills to 100%.
   - Explain the horizontal bar chart showing `hemo`, `pcv`, and `sc` driving the decision.

---

### Step 3: Dual-Layer Explainable AI (SHAP & LIME) (3 minutes)
1. Navigate to **`🔍 XAI Feature Insights`** in the sidebar.
2. Click **Tab 1: Global SHAP Interpretability**:
   - Explain the **SHAP Summary Beeswarm Plot**:
     - *Red dots* = High biomarker values; *Blue dots* = Low biomarker values.
     - Show how low hemoglobin (blue dots) spreads far to the right, proving that low hemoglobin is the single biggest driver of CKD risk.
     - Show how low specific gravity and high creatinine also push risk rightward.
   - Show the **Mean Absolute Shapley Feature Importance Bar Plot**, confirming that the top 5 biomarkers contribute over 80% of total decision weight.
3. Click **Tab 2: Local Case Study (Patient #0)**:
   - Show the **SHAP Waterfall Plot**:
     - Explains the journey from the baseline risk ($E[f(x)] = 0.625$) down to $f(x) = 0.00$ driven by protective negative Shapley values ($\Delta = -0.28$ for hemoglobin).
   - Show the **LIME Decision Rule Bar Chart**:
     - Highlights human-readable rules: `hemo > 15.00` and `sc <= 1.20`.
     - Highlight that **both SHAP and LIME independently agree on the same conclusion**.

---

### Step 4: Model Performance & Benchmark Curves (2 minutes)
1. Navigate to **`📊 Model Performance & Benchmarks`** in the sidebar.
2. Review the benchmark table comparing all 5 algorithms:
   - Random Forest: 100.0% Accuracy, 1.0000 ROC-AUC, 0.0095 Brier Score, 0.041 ms latency.
   - Gradient Boosting: 100.0% Accuracy, 1.0000 ROC-AUC, 0.052 ms latency.
   - SVM, Logistic Regression, KNN: 98.75% Accuracy.
3. Show the embedded plots:
   - **Multi-Model ROC Curves**: All models have curves hugging the top-left corner.
   - **Champion Random Forest Confusion Matrix**: Exactly 50 True Positives, 30 True Negatives, 0 False Positives, 0 False Negatives.

---

### Step 5: Clinical Report Generation & Export (1 minute)
1. Navigate to **`📄 Clinical Report Export`** in the sidebar.
2. Show the generated report preview formatted with:
   - Official system header & timestamp.
   - Full patient laboratory values table.
   - Calculated disease risk percentage and clinical triage tier.
   - Top XAI feature importance weights.
   - Medical disclaimer.
3. Click: **`💾 Download Signed Medical Report (.txt)`**.
4. Open the downloaded text file to demonstrate instant, point-of-care medical documentation.

---

## 3. Anticipated Examiner Questions & Expert Defense Guide

### Q1: "Why did you choose Random Forest over Deep Learning (like Neural Networks or CNNs)?"
> **Answer**:
> "For tabular clinical data with moderate sample size ($N=400$), tree-based ensembles consistently outperform deep neural networks (as proven by Grinsztajn et al., NeurIPS 2022). Deep neural networks tend to overfit small tabular datasets and lack inductive bias for axis-aligned decision boundaries. Furthermore, Random Forest achieved a perfect 1.000 ROC-AUC, zero false negatives, an ultra-low Brier calibration score of $0.0095$, and ultra-fast inference ($0.041\text{ ms}$), with full exact Shapley value computability via TreeExplainer."

### Q2: "How did you guarantee that there is no data leakage in your pipeline?"
> **Answer**:
> "We enforced strict data isolation:
> 1. The train/test split (80/20 stratified) was performed **before** any missing value imputation or scaling.
> 2. The `SimpleImputer` (median/mode) and `StandardScaler` were fit **exclusively** on the 320 training samples. The test cohort was transformed strictly using the training fold's parameters ($\mu$ and $\sigma$).
> 3. SMOTE was applied **only** to the training fold to balance classes (200 vs 200). The test fold remained completely untouched in its natural real-world distribution (50 CKD, 30 Healthy)."

### Q3: "Why did you use both SHAP and LIME? Isn't one enough?"
> **Answer**:
> "They serve complementary clinical purposes:
> - **SHAP** is rooted in cooperative game theory and guarantees *local accuracy*, *missingness*, and *consistency*. It provides mathematically exact global population insights (beeswarm) and exact additive patient waterfalls.
> - **LIME** trains a local interpretable linear surrogate with an exponential proximity kernel, providing easily readable boolean range rules (e.g. `hemo <= 12.0 AND sc > 1.4`).
> By employing both, we provide dual-layer validation: when both game theory (SHAP) and local linear surrogates (LIME) point to the exact same physiological biomarker drivers, clinical confidence is maximized."

### Q4: "How did you select the 10 features, and did reducing features harm performance?"
> **Answer**:
> "We used a hybrid consensus approach combining:
> 1. Filter: Mutual Information (non-linear).
> 2. Filter: ANOVA F-statistic (linear variance).
> 3. Embedded: Random Forest Gini impurity decrease.
> 4. Wrapper: Recursive Feature Elimination (RFE).
> By taking the Borda-count consensus of all four, we isolated the 10 most informative biomarkers (`hemo, sg, pcv, rc, al, htn, sc, bu, dm, bgr`). Far from harming performance, reducing features removed collinear noise (like the $r=0.84$ correlation between `hemo` and `pcv`), causing test accuracy to jump from 98.75% to 100.0% while slashing clinical lab load by 60%."

### Q5: "What makes your project ready for clinical use?"
> **Answer**:
> "Three factors:
> 1. **Calibrated Triage**: We don't just output a 0 or 1; we provide risk percentages mapped into 4 clinical action tiers (Low, Moderate, High, Critical).
> 2. **Fault-Tolerant Sanitation**: Our pipeline safely clamps numerical outliers, replaces NaNs, and handles partial inputs without crashing.
> 3. **Complete Automated Testing**: Our Phase 11 test suite passed 24 unit and stress tests with a 100% success rate and $3.1\text{ ms}$ cohort throughput."
