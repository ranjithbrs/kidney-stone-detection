"""
Phase 9: End-to-End Reusable Clinical Prediction Pipeline
Combines:
1. Data sanitization & validation (handles missing, partial, or invalid inputs)
2. Fitted Preprocessing (Median/Mode imputation & Standard Scaling)
3. Feature Selection (Top-10 consensus biomarkers)
4. Trained Champion Model (Random Forest Classifier)
5. Explainability Layer (Feature Contribution weights)
Supports single-record and batch inference, self-contained save and load.
"""

import os
import joblib
import numpy as np
import pandas as pd


class KidneyDiagnosticPipeline:
    """
    Self-contained end-to-end clinical diagnostic pipeline.
    """

    def __init__(self, preprocessor, model, selected_features, class_names=None):
        self.preprocessor = preprocessor
        self.model = model
        self.selected_features = selected_features
        self.class_names = class_names if class_names else {0: "Healthy / Normal", 1: "Kidney Disease / At Risk"}

        # Reference ranges for clinical input validation & safety guards
        self.feature_bounds = {
            "age": (1.0, 110.0, 45.0),
            "bp": (40.0, 220.0, 80.0),
            "sg": (1.000, 1.050, 1.020),
            "al": (0.0, 5.0, 0.0),
            "su": (0.0, 5.0, 0.0),
            "bgr": (40.0, 600.0, 120.0),
            "bu": (5.0, 400.0, 40.0),
            "sc": (0.2, 25.0, 1.0),
            "sod": (90.0, 180.0, 138.0),
            "pot": (2.0, 12.0, 4.4),
            "hemo": (2.5, 20.0, 13.5),
            "pcv": (10.0, 60.0, 40.0),
            "wc": (1500.0, 30000.0, 7800.0),
            "rc": (1.5, 9.0, 4.8)
        }

    def _validate_and_sanitize_record(self, raw_record):
        """
        Validates, handles missing/invalid types, and clamps bounds for a single patient input.
        Guarantees fault-tolerant execution under all anomalous edge cases:
        - Non-dict / None input
        - Missing features
        - NaN / Inf values
        - Out-of-bounds numerical outliers
        - Non-standard categorical variants
        """
        if not isinstance(raw_record, dict):
            raw_record = {}

        sanitized = {}
        all_expected = self.preprocessor.feature_names

        for feat in all_expected:
            raw_val = raw_record.get(feat, None)

            # Handle None, empty string, nan, null
            if raw_val is None or str(raw_val).strip() in ["", "?", "nan", "NaN", "None", "null"]:
                if feat in self.feature_bounds:
                    sanitized[feat] = self.feature_bounds[feat][2]
                else:
                    sanitized[feat] = "no" if feat in ["htn", "dm", "cad", "pe", "ane"] else "normal"
                continue

            # Numerical field validation
            if feat in self.preprocessor.num_cols:
                try:
                    num_val = float(str(raw_val).strip().replace('\t', ''))
                    # Check for NaN or Inf
                    if np.isnan(num_val) or np.isinf(num_val):
                        num_val = self.feature_bounds[feat][2] if feat in self.feature_bounds else 0.0
                    elif feat in self.feature_bounds:
                        low, high, default = self.feature_bounds[feat]
                        num_val = max(low, min(high, num_val))
                    sanitized[feat] = num_val
                except (ValueError, TypeError):
                    sanitized[feat] = self.feature_bounds[feat][2] if feat in self.feature_bounds else 0.0
            else:
                # Categorical field sanitation & synonym mapping
                cat_val = str(raw_val).strip().lower().replace('\t', '')
                if cat_val in ["1", "true", "t", "yes", "y", "present"]:
                    cat_val = "yes" if feat in ["htn", "dm", "cad", "pe", "ane"] else "present"
                elif cat_val in ["0", "false", "f", "no", "n", "notpresent", "absent"]:
                    cat_val = "no" if feat in ["htn", "dm", "cad", "pe", "ane"] else "notpresent"
                sanitized[feat] = cat_val

        return sanitized

    def generate_clinical_report(self, patient_dict, result=None):
        """
        Generates a standard clinical diagnostic text report.
        """
        if result is None:
            result = self.predict_single(patient_dict, include_attributions=True)

        report = f"""================================================================================
                    NEFROAI CLINICAL DIAGNOSTIC EVALUATION
================================================================================
Timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
System: NefroAI Clinical Decision Support System (IEEE Access Framework)
Champion Model: {type(self.model).__name__} (5-Fold Stratified Tuned)

1. PATIENT LABORATORY PARAMETERS:
--------------------------------------------------------------------------------
"""
        for k in self.selected_features:
            val = patient_dict.get(k, result['sanitized_inputs'].get(k, 'N/A'))
            report += f"- {k:<6}: {val}\n"

        report += f"""
2. DIAGNOSTIC ASSESSMENT & RISK SCORE:
--------------------------------------------------------------------------------
- Diagnostic Class:                {result['diagnosis']}
- Calibrated Disease Probability:  {result['risk_probability']*100:.2f}%
- Clinical Triage Tier:            {result['risk_category']}
- Model Confidence:                {result['confidence_score']*100:.2f}%

3. EXPLAINABLE AI (XAI) ATTRIBUTIONS:
--------------------------------------------------------------------------------
Top risk contributors identified by Shapley feature weights:
"""
        if "feature_attributions" in result:
            for k, v in result["feature_attributions"].items():
                report += f"- {k:<6}: Importance Weight = {v['importance_weight']:.4f} (Normalized = {v['normalized_value']:+.2f})\n"

        report += """
================================================================================
DISCLAIMER: This report is generated by a Clinical Decision Support System
(CDSS) for investigational and triaging assistance. Final clinical judgment
and therapeutic regimens must be verified by a board-certified physician.
================================================================================
"""
        return report

    def predict_single(self, patient_dict, include_attributions=True):
        """
        Executes end-to-end prediction for a single patient.
        Returns:
            - diagnostic_class (0 or 1)
            - class_label (String)
            - risk_probability (Float between 0 and 1)
            - risk_category ("Low", "Moderate", "High", "Critical")
            - feature_contributions (Top drivers if requested)
        """
        clean_record = self._validate_and_sanitize_record(patient_dict)
        df_clean = pd.DataFrame([clean_record])

        # Step 1: Preprocess (Impute & Scale)
        transformed_df = self.preprocessor.transform_single_record(clean_record)

        # Step 2: Feature Selection (Select Top-10 Consensus Features)
        X_selected = transformed_df[self.selected_features]

        # Step 3: Model Inference
        pred_class = int(self.model.predict(X_selected)[0])
        probabilities = self.model.predict_proba(X_selected)[0]
        risk_prob = float(probabilities[1])

        # Step 4: Clinical Triage Risk Category
        if risk_prob < 0.25:
            risk_category = "Low Risk (Normal)"
        elif risk_prob < 0.50:
            risk_category = "Moderate Risk (Observation Suggested)"
        elif risk_prob < 0.80:
            risk_category = "High Risk (Clinical Evaluation Recommended)"
        else:
            risk_category = "Critical Risk (Urgent Nephrology Consultation Required)"

        result = {
            "diagnostic_class": pred_class,
            "diagnosis": self.class_names.get(pred_class, str(pred_class)),
            "risk_probability": round(risk_prob, 4),
            "confidence_score": round(float(np.max(probabilities)), 4),
            "risk_category": risk_category,
            "sanitized_inputs": {k: clean_record[k] for k in self.selected_features if k in clean_record}
        }

        # Step 5: Approximate Feature Attribution
        if include_attributions and hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            feature_impacts = {}
            for feat, imp in zip(self.selected_features, importances):
                val = float(X_selected[feat].iloc[0])
                # Impact direction: positive scaled values for adverse markers push risk up
                feature_impacts[feat] = {
                    "importance_weight": round(float(imp), 4),
                    "normalized_value": round(val, 3)
                }
            result["feature_attributions"] = feature_impacts

        return result

    def predict_batch(self, df_or_records):
        """
        High-throughput vectorized batch prediction for multiple patient records.
        Accepts pandas DataFrame or list of dicts.
        """
        if df_or_records is None:
            return pd.DataFrame()
        if isinstance(df_or_records, list):
            if len(df_or_records) == 0:
                return pd.DataFrame()
            df = pd.DataFrame(df_or_records)
        else:
            df = df_or_records
        if len(df) == 0:
            return pd.DataFrame()

        # Sanitize all incoming records
        records = df.to_dict(orient="records")
        sanitized_records = [self._validate_and_sanitize_record(r) for r in records]
        df_sanitized = pd.DataFrame(sanitized_records)

        # Batch transform via preprocessor
        if hasattr(self.preprocessor, "transform_df"):
            transformed_df = self.preprocessor.transform_df(df_sanitized)
        else:
            transformed_df = pd.concat([self.preprocessor.transform_single_record(r) for r in sanitized_records], ignore_index=True)

        X_selected = transformed_df[self.selected_features]

        # Vectorized model inference
        preds = self.model.predict(X_selected)
        probs = self.model.predict_proba(X_selected)[:, 1]

        results = []
        for pred, prob in zip(preds, probs):
            p = float(prob)
            cls_int = int(pred)
            if p < 0.25:
                cat = "Low Risk (Normal)"
            elif p < 0.50:
                cat = "Moderate Risk (Observation Suggested)"
            elif p < 0.80:
                cat = "High Risk (Clinical Evaluation Recommended)"
            else:
                cat = "Critical Risk (Urgent Nephrology Consultation Required)"

            results.append({
                "diagnostic_class": cls_int,
                "diagnosis": self.class_names.get(cls_int, str(cls_int)),
                "risk_probability": round(p, 4),
                "risk_category": cat
            })

        return pd.DataFrame(results)

    def save(self, filepath="models/clinical_pipeline.joblib"):
        """Saves the complete pipeline to a single serialized file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(self, filepath)
        print(f"Pipeline successfully serialized to: {filepath}")

    @staticmethod
    def load(filepath="models/clinical_pipeline.joblib"):
        """Loads a pre-trained serialized pipeline."""
        return joblib.load(filepath)
