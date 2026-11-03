# Antigravity Instructions: Chronic Kidney Disease (CKD) CDSS

Refer to [AGENTS.md](AGENTS.md) for full project standards, clinical feature specifications, and runtime configuration.

## Key Operating Rules for AI Agents:
1. **Runtime & Virtual Environment**: Always execute Python commands using the project-local virtual environment:
   ```powershell
   .venv\Scripts\python.exe
   ```
2. **Primary Application Entry Point**:
   - The primary clinical application is built on Streamlit:
     ```powershell
     .venv\Scripts\streamlit.exe run app_streamlit.py
     ```
   - Primary model artifact: `models/clinical_pipeline.joblib` (Random Forest champion model with Top-10 consensus biomarkers).
3. **Data Integrity & Leakage Prevention**:
   - Primary ground-truth dataset is `datasets/clinical/dataset_A_uci_ckd.csv` (UCI CKD, 400 patients, 24 features). Note that `dataset_C_kaggle_ckd.csv` is an exact duplicate mirror.
   - All preprocessing (imputation, scaling, SMOTE) must be fitted strictly on training data (`X_train`), never on test partitions.
4. **Clinical Safety Safeguards**:
   - **Never** silently replace missing patient clinical measurements with healthy normal values. Missing data must be explicitly flagged and penalized.
   - Enforce strict schema validation: immediately reject incompatible datasets (e.g. kidney stone urinalysis, surgical datasets, or computer-vision images) from the CKD pipeline.
5. **Explainability & Attribution Integrity**:
   - Do not describe Random Forest Gini/MDI feature importance heuristics as "Shapley weights" in code, UI, or clinical reports. True SHAP requires `shap.TreeExplainer`.
6. **Clinical & Legal Boundaries**:
   - Frame the framework as a Clinical Decision Support System (CDSS) for risk triaging and screening, not a definitive diagnostic engine.
   - Describe candidate invention components (MIDR, CRI, conformal gates) objectively as algorithmic verification mechanisms without unsupported legal novelty claims.
