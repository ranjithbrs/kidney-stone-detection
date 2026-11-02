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
        """
        sanitized = {}
        # Expected all features needed by preprocessor
        all_expected = self.preprocessor.feature_names

        for feat in all_expected:
            raw_val = raw_record.get(feat, None)

            # Handle None, empty string, nan
            if raw_val is None or str(raw_val).strip() in ["", "?", "nan", "None", "null"]:
                # Default to median/safe value if missing
                if feat in self.feature_bounds:
                    sanitized[feat] = self.feature_bounds[feat][2]
                else:
                    sanitized[feat] = "no" if feat in ["htn", "dm", "cad", "pe", "ane"] else "normal"
                continue

            # Numerical field validation
            if feat in self.preprocessor.num_cols:
                try:
                    num_val = float(str(raw_val).strip().replace('\t', ''))
                    # Bounds checking
                    if feat in self.feature_bounds:
                        low, high, default = self.feature_bounds[feat]
                        if num_val < low or num_val > high:
                            # Clamp to bounds to prevent out-of-distribution crashes
                            num_val = max(low, min(high, num_val))
                    sanitized[feat] = num_val
                except (ValueError, TypeError):
                    sanitized[feat] = self.feature_bounds[feat][2] if feat in self.feature_bounds else 0.0
            else:
                # Categorical field sanitation
                cat_val = str(raw_val).strip().lower().replace('\t', '')
                sanitized[feat] = cat_val

        return sanitized

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

    def predict_batch(self, df):
        """Batch prediction for multiple patient records."""
        results = [self.predict_single(row.to_dict(), include_attributions=False) for _, row in df.iterrows()]
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
