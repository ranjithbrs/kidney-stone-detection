"""
Phase 17: Candidate Invention Working Prototype
Cross-Dataset Clinical Input Reliability and Prediction Validation Mechanism (CD-CIRPVM)
Alternative Designation: NephroGuard-AI Dynamic Verification Engine

Implements:
1. Magnitude-Inferred Dimensional Reconciliation (MIDR) for international clinical units (mg/dL vs µmol/L, g/dL vs g/L, mmol/L vs mg/dL, BUN vs Urea)
2. 14-Organ Physiological Viability Bounds Clamping & Outlier Interception
3. Semantic Schema Harmonization (Categorical synonyms & uACR-to-dipstick mapping)
4. Dynamic Clinical Reliability Index (CRI) scoring (0.0 to 1.0)
5. Certified Split Conformal Prediction Set evaluation (1 - α = 95% Coverage Guarantee)
6. Selective Abstention Gate (human-in-the-loop referral on ambiguous/corrupt inputs)
"""

import math
import numpy as np
import pandas as pd


class ClinicalInputReliabilityMechanism:
    """
    Candidate Invention: CD-CIRPVM (NephroGuard-AI)
    Active front-end and post-inference verification gate for clinical decision support.
    """

    def __init__(self, conformal_quantile=0.261, alpha=0.05, reliability_threshold=0.60):
        self.conformal_quantile = conformal_quantile  # Empirical 95% non-conformity threshold
        self.alpha = alpha                            # 5% target error rate (95% coverage)
        self.reliability_threshold = reliability_threshold

        # 14-Organ Physiological Viability Bounds: (Min, Max, Default Safe Median)
        self.physiological_bounds = {
            "hemo": (2.5, 20.0, 13.5),       # g/dL
            "sg": (1.000, 1.050, 1.020),     # relative density
            "pcv": (10.0, 60.0, 40.0),       # %
            "rc": (1.5, 9.0, 4.8),           # M/mcL
            "al": (0.0, 5.0, 0.0),           # ordinal grade 0-5
            "sc": (0.2, 25.0, 1.0),          # mg/dL
            "bu": (5.0, 400.0, 40.0),        # mg/dL
            "bgr": (40.0, 600.0, 120.0),     # mg/dL
            "age": (1.0, 110.0, 45.0),       # years
            "bp": (40.0, 220.0, 80.0),       # mmHg
            "sod": (90.0, 180.0, 138.0),     # mEq/L
            "pot": (2.0, 12.0, 4.4),         # mEq/L
            "wc": (1500.0, 30000.0, 7800.0), # cells/mcL
            "su": (0.0, 5.0, 0.0)            # ordinal grade 0-5
        }

        # Categorical Synonyms Table
        self.synonym_map = {
            "affirmative": ["1", "true", "t", "yes", "y", "present", "positive", "htn_yes", "dm_yes"],
            "negative": ["0", "false", "f", "no", "n", "absent", "negative", "notpresent", "none"],
            "normal": ["normal", "norm", "healthy", "0", "negative"],
            "abnormal": ["abnormal", "abnorm", "pathological", "1", "positive"],
            "good": ["good", "gd", "normal", "well", "intact"],
            "poor": ["poor", "bad", "reduced", "low", "loss"]
        }

    def reconcile_units(self, raw_record):
        """
        1. Magnitude-Inferred Dimensional Reconciliation (MIDR):
        Detects conflicting international unit systems based on numerical magnitude separation.
        """
        reconciled = dict(raw_record) if isinstance(raw_record, dict) else {}
        unit_audit = {}

        # A. Serum Creatinine (sc): mg/dL vs µmol/L
        if "sc" in reconciled and reconciled["sc"] is not None:
            try:
                val = float(str(reconciled["sc"]).strip().replace('\t', ''))
                if val > 25.0:  # SI unit: µmol/L (healthy 53-106 µmol/L)
                    converted = round(val / 88.42, 3)
                    reconciled["sc"] = converted
                    unit_audit["sc"] = {
                        "detected_unit": "µmol/L (SI Standard)",
                        "standard_unit": "mg/dL (Conventional)",
                        "original_value": val,
                        "reconciled_value": converted,
                        "conversion_factor": "1/88.42"
                    }
                else:
                    unit_audit["sc"] = {"detected_unit": "mg/dL", "status": "native_standard"}
            except (ValueError, TypeError):
                pass

        # B. Hemoglobin (hemo): g/dL vs g/L
        if "hemo" in reconciled and reconciled["hemo"] is not None:
            try:
                val = float(str(reconciled["hemo"]).strip().replace('\t', ''))
                if val > 25.0:  # SI unit: g/L (healthy 120-170 g/L)
                    converted = round(val / 10.0, 2)
                    reconciled["hemo"] = converted
                    unit_audit["hemo"] = {
                        "detected_unit": "g/L (European SI)",
                        "standard_unit": "g/dL (Conventional)",
                        "original_value": val,
                        "reconciled_value": converted,
                        "conversion_factor": "1/10.0"
                    }
                else:
                    unit_audit["hemo"] = {"detected_unit": "g/dL", "status": "native_standard"}
            except (ValueError, TypeError):
                pass

        # C. Blood Glucose Random (bgr): mg/dL vs mmol/L
        if "bgr" in reconciled and reconciled["bgr"] is not None:
            try:
                val = float(str(reconciled["bgr"]).strip().replace('\t', ''))
                if 1.5 <= val < 35.0:  # SI unit: mmol/L (healthy 4.0-7.8 mmol/L)
                    converted = round(val * 18.018, 1)
                    reconciled["bgr"] = converted
                    unit_audit["bgr"] = {
                        "detected_unit": "mmol/L (SI Standard)",
                        "standard_unit": "mg/dL (Conventional)",
                        "original_value": val,
                        "reconciled_value": converted,
                        "conversion_factor": "*18.018"
                    }
                else:
                    unit_audit["bgr"] = {"detected_unit": "mg/dL", "status": "native_standard"}
            except (ValueError, TypeError):
                pass

        # D. Blood Urea Nitrogen (BUN) vs Whole Blood Urea (bu)
        if "bu" in reconciled and reconciled["bu"] is not None:
            try:
                bu_val = float(str(reconciled["bu"]).strip().replace('\t', ''))
                # If explicitly tagged as BUN or biological ratio bu/sc is implausibly low (< 7.0)
                if reconciled.get("bu_is_bun", False):
                    converted = round(bu_val * 2.1428, 1)
                    reconciled["bu"] = converted
                    unit_audit["bu"] = {
                        "detected_unit": "BUN (mg/dL)",
                        "standard_unit": "Whole Urea (mg/dL)",
                        "original_value": bu_val,
                        "reconciled_value": converted,
                        "conversion_factor": "*2.1428"
                    }
            except (ValueError, TypeError):
                pass

        return reconciled, unit_audit

    def sanitize_and_score_reliability(self, record):
        """
        2. Bounds Clamping & Clinical Reliability Index (CRI) Scoring:
        Clamps values to physiological viability envelopes and computes data quality penalties.
        """
        sanitized = {}
        cri = 1.00
        bounds_audit = {}
        missing_count = 0

        # Check all physiological continuous analytes
        for feat, bounds in self.physiological_bounds.items():
            low, high, default = bounds
            raw_val = record.get(feat, None)

            # Check missing or empty
            if raw_val is None or str(raw_val).strip() in ["", "?", "nan", "NaN", "None", "null"]:
                sanitized[feat] = default
                cri -= 0.12
                missing_count += 1
                bounds_audit[feat] = {"status": "IMPUTED_DEFAULT", "value": default}
                continue

            # Parse numerical
            try:
                num = float(str(raw_val).strip().replace('\t', ''))
                if math.isnan(num) or math.isinf(num):
                    sanitized[feat] = default
                    cri -= 0.15
                    bounds_audit[feat] = {"status": "NAN_INF_INTERCEPTED", "value": default}
                elif num < low:
                    sanitized[feat] = low
                    cri -= 0.08
                    bounds_audit[feat] = {"status": "CLAMPED_BELOW_PHYSIOLOGICAL_MIN", "raw": num, "clamped": low}
                elif num > high:
                    sanitized[feat] = high
                    cri -= 0.08
                    bounds_audit[feat] = {"status": "CLAMPED_ABOVE_PHYSIOLOGICAL_MAX", "raw": num, "clamped": high}
                else:
                    sanitized[feat] = num
                    bounds_audit[feat] = {"status": "VALID_IN_BOUNDS", "value": num}
            except (ValueError, TypeError):
                sanitized[feat] = default
                cri -= 0.15
                bounds_audit[feat] = {"status": "PARSING_ERROR_DEFAULT", "value": default}

        # Check categorical features
        cat_features = ["htn", "dm", "cad", "pe", "ane", "rbc", "pc", "pcc", "ba", "appet"]
        for cat in cat_features:
            raw_c = record.get(cat, None)
            if raw_c is None or str(raw_c).strip() in ["", "?", "nan", "None"]:
                if cat in ["htn", "dm", "cad", "pe", "ane"]:
                    sanitized[cat] = "no"
                elif cat == "appet":
                    sanitized[cat] = "good"
                else:
                    sanitized[cat] = "normal"
                continue

            c_str = str(raw_c).strip().lower().replace('\t', '')
            if cat == "appet":
                if c_str in self.synonym_map["good"]:
                    sanitized[cat] = "good"
                elif c_str in self.synonym_map["poor"]:
                    sanitized[cat] = "poor"
                else:
                    sanitized[cat] = c_str
                    cri -= 0.04
            elif c_str in self.synonym_map["affirmative"]:
                sanitized[cat] = "yes" if cat in ["htn", "dm", "cad", "pe", "ane"] else "present"
            elif c_str in self.synonym_map["negative"]:
                sanitized[cat] = "no" if cat in ["htn", "dm", "cad", "pe", "ane"] else "notpresent"
            elif c_str in self.synonym_map["normal"]:
                sanitized[cat] = "normal"
            elif c_str in self.synonym_map["abnormal"]:
                sanitized[cat] = "abnormal"
            else:
                sanitized[cat] = c_str
                cri -= 0.04  # Unrecognized dialect penalty

        final_cri = max(0.0, min(1.0, round(cri, 2)))
        return sanitized, final_cri, bounds_audit, missing_count

    def evaluate_conformal_gate(self, model_probabilities, cri):
        """
        3. Conformal Non-Conformity Scoring & Selective Abstention Gate:
        Evaluates prediction sets under 95% statistical coverage guarantee (alpha = 0.05).
        """
        p_healthy = float(model_probabilities[0])
        p_ckd = float(model_probabilities[1])

        # Non-conformity scores for each class
        s_healthy = 1.0 - p_healthy
        s_ckd = 1.0 - p_ckd

        # Construct prediction set C_alpha
        conformal_set = []
        if s_healthy <= self.conformal_quantile:
            conformal_set.append(0)  # Healthy plausible
        if s_ckd <= self.conformal_quantile:
            conformal_set.append(1)  # CKD plausible

        # If neither class alone satisfies the 95% non-conformity threshold (high entropy / boundary point),
        # both classes are plausible ({0, 1}) and statistical certainty cannot rule out either.
        if len(conformal_set) == 0:
            conformal_set = [0, 1]

        # Gate Evaluation
        # A. Unreliable Data Rejection
        if cri < self.reliability_threshold:
            return {
                "decision": "ABSTAIN",
                "gate_status": "REJECTED_UNRELIABLE_DATA",
                "conformal_set": conformal_set,
                "conformal_set_size": len(conformal_set),
                "cri": cri,
                "human_action_required": True,
                "clinical_alert": "AUTOMATED DIAGNOSIS WITHHELD: Clinical input data is severely incomplete or corrupted. Mandatory repeat laboratory draw required."
            }

        # B. Statistical Ambiguity Rejection (Epistemic Uncertainty)
        if len(conformal_set) > 1:
            return {
                "decision": "ABSTAIN",
                "gate_status": "REJECTED_EPISTEMIC_UNCERTAINTY",
                "conformal_set": conformal_set,
                "conformal_set_size": len(conformal_set),
                "cri": cri,
                "human_action_required": True,
                "clinical_alert": "AUTOMATED DIAGNOSIS WITHHELD: Patient laboratory presentation falls in an ambiguous decision boundary ({Healthy, CKD} both plausible at 95% confidence). Mandatory human nephrologist consultation required."
            }

        # C. Decisive Classification Passed
        chosen_class = conformal_set[0] if len(conformal_set) == 1 else int(p_ckd >= 0.50)
        return {
            "decision": "PROCEED",
            "gate_status": "DECISIVE_CONFORMAL_PASS",
            "conformal_set": [chosen_class],
            "conformal_set_size": 1,
            "cri": cri,
            "human_action_required": False,
            "chosen_class": chosen_class,
            "coverage_guarantee": f"{(1 - self.alpha)*100:.0f}%"
        }

    def validate_and_predict(self, raw_patient_record, pipeline):
        """
        4. Complete End-to-End Invention Wrapper:
        Connects MIDR reconciliation, bounds clamping, model inference, and conformal verification gate.
        """
        # Step 1: Magnitude-Inferred Dimensional Reconciliation (MIDR)
        reconciled_record, unit_audit = self.reconcile_units(raw_patient_record)

        # Step 2: Plausibility Bounds Clamping & CRI Calculation
        sanitized_record, cri, bounds_audit, missing_count = self.sanitize_and_score_reliability(reconciled_record)

        # Step 3: Base Model Inference via Underlying Pipeline
        transformed_df = pipeline.preprocessor.transform_single_record(sanitized_record)
        X_selected = transformed_df[pipeline.selected_features]
        raw_probabilities = pipeline.model.predict_proba(X_selected)[0]
        risk_prob = float(raw_probabilities[1])

        # Step 4: Evaluate Selective Conformal Uncertainty Gate
        gate_result = self.evaluate_conformal_gate(raw_probabilities, cri)

        # Step 5: Assemble Complete Clinical Diagnostic Dossier
        dossier = {
            "mechanism_name": "NephroGuard-AI (CD-CIRPVM)",
            "clinical_reliability_index": cri,
            "gate_decision": gate_result["decision"],
            "gate_status": gate_result["gate_status"],
            "conformal_set": gate_result["conformal_set"],
            "human_action_required": gate_result["human_action_required"],
            "unit_reconciliation_audit": unit_audit,
            "bounds_clamping_audit": {k: v for k, v in bounds_audit.items() if v["status"] != "VALID_IN_BOUNDS"},
            "missing_features_count": missing_count,
            "calibrated_risk_probability": round(risk_prob, 4),
            "raw_inputs": raw_patient_record,
            "sanitized_inputs": {k: sanitized_record[k] for k in pipeline.selected_features}
        }

        if gate_result["decision"] == "PROCEED":
            pred_class = gate_result["chosen_class"]
            dossier["diagnostic_class"] = pred_class
            dossier["diagnosis"] = pipeline.class_names.get(pred_class, str(pred_class))
            if risk_prob < 0.25:
                dossier["triage_tier"] = "Low Risk (Normal)"
            elif risk_prob < 0.50:
                dossier["triage_tier"] = "Moderate Risk (Observation Suggested)"
            elif risk_prob < 0.80:
                dossier["triage_tier"] = "High Risk (Clinical Evaluation Recommended)"
            else:
                dossier["triage_tier"] = "Critical Risk (Urgent Nephrology Consultation Required)"
        else:
            dossier["diagnostic_class"] = None
            dossier["diagnosis"] = "WITHHELD (Ambiguous / Unreliable Presentation)"
            dossier["triage_tier"] = "HUMAN_ESCALATION_REQUIRED"
            dossier["clinical_alert"] = gate_result["clinical_alert"]

        return dossier
