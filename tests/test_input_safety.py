"""
Phase 4 — Step 2: Clinical Input Safety & Strict Schema Validation Test Suite
Automated regression tests covering all 15 scenarios specified in Section 8:

1. Complete valid CKD input (PREDICTION_AVAILABLE).
2. Missing non-critical features (INCOMPLETE_INPUT_ESTIMATE).
3. Missing serum creatinine (ABSTAIN_MISSING_CRITICAL_FEATURES).
4. Missing urine albumin (ABSTAIN_MISSING_CRITICAL_FEATURES).
5. Missing hemoglobin (ABSTAIN_MISSING_CRITICAL_FEATURES).
6. Multiple critical measurements missing (ABSTAIN_MISSING_CRITICAL_FEATURES).
7. Completely empty input (REJECTED_INVALID_SCHEMA / ABSTAIN).
8. Malformed numerical input handling (never coerced to healthy defaults).
9. Kidney-stone dataset rejection (dataset_B_kidney_stone.csv).
10. Simpson kidney-stone dataset rejection (dataset_C_simpson_kidney.csv).
11. Unknown schema rejection (unrelated tabular columns).
12. Mixed valid and incomplete batch records (row-level isolation).
13. Confirmation that missing critical values never silently produce a healthy prediction.
14. Compatibility with existing fitted model (models/clinical_pipeline.joblib).
15. Existing regression tests compatibility.
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd
import joblib

# Ensure src and root are in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline import KidneyDiagnosticPipeline, CRITICAL_FEATURES, TOP_10_CONSENSUS_FEATURES


class TestClinicalInputSafetyAndSchemaValidation(unittest.TestCase):
    """Rigorous verification suite for Phase 4 Step 2 clinical input safety guards."""

    @classmethod
    def setUpClass(cls):
        pipeline_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        cls.pipeline = KidneyDiagnosticPipeline.load(pipeline_path)

        # Standard canonical test fixtures
        cls.complete_healthy = {
            "hemo": 15.2, "sg": 1.025, "pcv": 45.0, "sc": 0.8, "rc": 5.2,
            "al": 0, "bu": 22.0, "bgr": 98.0, "htn": "no", "dm": "no"
        }
        cls.complete_ckd = {
            "hemo": 8.4, "sg": 1.010, "pcv": 26.0, "sc": 4.2, "rc": 3.1,
            "al": 3, "bu": 78.0, "bgr": 195.0, "htn": "yes", "dm": "yes"
        }

    # =========================================================================
    # SCENARIO 1: Complete valid CKD input (PREDICTION_AVAILABLE)
    # =========================================================================
    def test_scenario_01_complete_valid_input(self):
        """Scenario 1: Complete 10-feature panel yields PREDICTION_AVAILABLE with 100% completeness."""
        res = self.pipeline.predict_single(self.complete_healthy)
        self.assertTrue(res["input_valid"])
        self.assertEqual(res["prediction_status"], "PREDICTION_AVAILABLE")
        self.assertEqual(res["data_completeness_ratio"], 1.0)
        self.assertEqual(len(res["missing_features"]), 0)
        self.assertEqual(len(res["imputed_features"]), 0)
        self.assertIsNone(res["abstention_reason"])
        self.assertIn(res["diagnostic_class"], [0, 1])
        self.assertIsInstance(res["risk_probability"], float)
        self.assertTrue(0.0 <= res["risk_probability"] <= 1.0)
        self.assertEqual(res["diagnostic_class"], 0)

    # =========================================================================
    # SCENARIO 2: Missing non-critical features (INCOMPLETE_INPUT_ESTIMATE)
    # =========================================================================
    def test_scenario_02_missing_non_critical_features(self):
        """Scenario 2: Critical features present, missing non-critical features imputed with warning."""
        # Provide sc, al, hemo + pcv; omit bu, bgr, rc, sg, htn, dm
        partial_patient = {
            "sc": 1.1,
            "al": 0,
            "hemo": 13.8,
            "pcv": 41.0
        }
        res = self.pipeline.predict_single(partial_patient)
        self.assertTrue(res["input_valid"])
        self.assertEqual(res["prediction_status"], "INCOMPLETE_INPUT_ESTIMATE")
        self.assertLess(res["data_completeness_ratio"], 1.0)
        self.assertGreater(res["data_completeness_ratio"], 0.0)
        self.assertIn("bu", res["imputed_features"])
        self.assertIn("bgr", res["imputed_features"])
        self.assertIsNone(res["abstention_reason"])
        self.assertIn(res["diagnostic_class"], [0, 1])
        self.assertIsInstance(res["risk_probability"], float)

    # =========================================================================
    # SCENARIO 3: Missing serum creatinine (ABSTAIN_MISSING_CRITICAL_FEATURES)
    # =========================================================================
    def test_scenario_03_missing_serum_creatinine(self):
        """Scenario 3: Missing serum creatinine (sc) must withhold automated prediction."""
        no_sc = dict(self.complete_healthy)
        del no_sc["sc"]
        res = self.pipeline.predict_single(no_sc)
        self.assertEqual(res["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res["diagnostic_class"])
        self.assertIsNone(res["risk_probability"])
        self.assertIsNone(res["confidence_score"])
        self.assertIn("sc", res["missing_features"])
        self.assertIn("Serum Creatinine", res["abstention_reason"])

    # =========================================================================
    # SCENARIO 4: Missing urine albumin (ABSTAIN_MISSING_CRITICAL_FEATURES)
    # =========================================================================
    def test_scenario_04_missing_urine_albumin(self):
        """Scenario 4: Missing urine albumin (al) must withhold automated prediction."""
        no_al = dict(self.complete_healthy)
        del no_al["al"]
        res = self.pipeline.predict_single(no_al)
        self.assertEqual(res["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res["diagnostic_class"])
        self.assertIsNone(res["risk_probability"])
        self.assertIn("al", res["missing_features"])
        self.assertIn("Urine Albumin", res["abstention_reason"])

    # =========================================================================
    # SCENARIO 5: Missing hemoglobin (ABSTAIN_MISSING_CRITICAL_FEATURES)
    # =========================================================================
    def test_scenario_05_missing_hemoglobin(self):
        """Scenario 5: Missing hemoglobin (hemo) must withhold automated prediction."""
        no_hemo = dict(self.complete_healthy)
        del no_hemo["hemo"]
        res = self.pipeline.predict_single(no_hemo)
        self.assertEqual(res["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res["diagnostic_class"])
        self.assertIsNone(res["risk_probability"])
        self.assertIn("hemo", res["missing_features"])
        self.assertIn("Hemoglobin", res["abstention_reason"])

    # =========================================================================
    # SCENARIO 6: Multiple critical measurements missing (ABSTAIN)
    # =========================================================================
    def test_scenario_06_multiple_critical_missing(self):
        """Scenario 6: Omitting both sc and hemo reports all missing critical biomarkers."""
        multi_missing = dict(self.complete_healthy)
        del multi_missing["sc"]
        del multi_missing["hemo"]
        res = self.pipeline.predict_single(multi_missing)
        self.assertEqual(res["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res["diagnostic_class"])
        self.assertIsNone(res["risk_probability"])
        self.assertIn("sc", res["missing_features"])
        self.assertIn("hemo", res["missing_features"])

    # =========================================================================
    # SCENARIO 7: Completely empty input (REJECTED_INVALID_SCHEMA / ABSTAIN)
    # =========================================================================
    def test_scenario_07_completely_empty_input(self):
        """Scenario 7: Empty dictionary or non-dict input is safely rejected, never defaulting to Healthy."""
        for empty_val in [{}, None, "not_a_dict", []]:
            res = self.pipeline.predict_single(empty_val)
            self.assertEqual(res["prediction_status"], "REJECTED_INVALID_SCHEMA")
            self.assertFalse(res["input_valid"])
            self.assertIsNone(res["diagnostic_class"])
            self.assertIsNone(res["risk_probability"])
            self.assertIsNotNone(res["abstention_reason"])

    # =========================================================================
    # SCENARIO 8: Malformed numerical input handling (No silent healthy defaults)
    # =========================================================================
    def test_scenario_08_malformed_numerical_input_handling(self):
        """Scenario 8: Unparseable strings in critical features abstain, never defaulting to sc=1.0 or hemo=13.5."""
        malformed = {
            "hemo": "critically_anemic",
            "sc": "elevated_creatinine",
            "al": "grade_three",
            "sg": 1.020,
            "pcv": 40.0
        }
        res = self.pipeline.predict_single(malformed)
        self.assertEqual(res["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res["diagnostic_class"])
        self.assertIsNone(res["risk_probability"])
        # Verify unparseable fields were NOT coerced to healthy reference bounds
        sanitized = self.pipeline._validate_and_sanitize_record(malformed)
        self.assertTrue(np.isnan(sanitized["hemo"]))
        self.assertTrue(np.isnan(sanitized["sc"]))

    # =========================================================================
    # SCENARIO 9: Kidney-stone dataset rejection (dataset_B_kidney_stone.csv)
    # =========================================================================
    def test_scenario_09_kidney_stone_dataset_rejection(self):
        """Scenario 9: Kidney stone urinalysis dataset (Dataset B) is rejected immediately."""
        path_b = os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_B_kidney_stone.csv")
        self.assertTrue(os.path.exists(path_b))
        df_b = pd.read_csv(path_b)

        is_valid, reason = KidneyDiagnosticPipeline.validate_schema(df_b)
        self.assertFalse(is_valid)
        self.assertIn("Incompatible dataset schema detected", reason)

        with self.assertRaises(ValueError) as ctx:
            self.pipeline.predict_batch(df_b)
        self.assertIn("Schema Validation Error", str(ctx.exception))

    # =========================================================================
    # SCENARIO 10: Simpson kidney-stone dataset rejection (dataset_C_simpson)
    # =========================================================================
    def test_scenario_10_simpson_kidney_stone_rejection(self):
        """Scenario 10: Simpson stone removal surgical cohort (Dataset C) is rejected immediately."""
        path_c = os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_C_simpson_kidney.csv")
        self.assertTrue(os.path.exists(path_c))
        df_c = pd.read_csv(path_c)

        is_valid, reason = KidneyDiagnosticPipeline.validate_schema(df_c)
        self.assertFalse(is_valid)
        self.assertIn("Incompatible dataset schema detected", reason)

        with self.assertRaises(ValueError) as ctx:
            self.pipeline.predict_batch(df_c)
        self.assertIn("Schema Validation Error", str(ctx.exception))

    # =========================================================================
    # SCENARIO 11: Unknown schema rejection
    # =========================================================================
    def test_scenario_11_unknown_schema_rejection(self):
        """Scenario 11: Unrelated tabular columns (e.g. colA, colB) are rejected."""
        unrelated_df = pd.DataFrame({
            "patient_age_group": [1, 2, 3],
            "feature_x": [10.5, 20.3, 30.1],
            "measurement_y": [100, 200, 300]
        })
        is_valid, reason = KidneyDiagnosticPipeline.validate_schema(unrelated_df)
        self.assertFalse(is_valid)
        self.assertIn("None of the DataFrame columns match recognized CKD", reason)

        with self.assertRaises(ValueError):
            self.pipeline.predict_batch(unrelated_df)

    # =========================================================================
    # SCENARIO 12: Mixed valid and incomplete batch records
    # =========================================================================
    def test_scenario_12_mixed_valid_and_incomplete_batch_records(self):
        """Scenario 12: Batch prediction correctly isolates row statuses without cross-contamination."""
        row_complete = dict(self.complete_healthy)
        row_incomplete = {"sc": 1.1, "al": 0, "hemo": 14.0, "pcv": 42.0} # non-critical missing
        row_missing_crit = {"hemo": 14.0, "al": 0} # sc missing

        batch_df = pd.DataFrame([row_complete, row_incomplete, row_missing_crit])
        results = self.pipeline.predict_batch(batch_df)

        self.assertEqual(len(results), 3)

        # Row 1: Complete valid
        self.assertEqual(results.iloc[0]["prediction_status"], "PREDICTION_AVAILABLE")
        self.assertEqual(results.iloc[0]["diagnostic_class"], 0)
        self.assertIsNotNone(results.iloc[0]["risk_probability"])

        # Row 2: Incomplete non-critical estimate
        self.assertEqual(results.iloc[1]["prediction_status"], "INCOMPLETE_INPUT_ESTIMATE")
        self.assertIn(results.iloc[1]["diagnostic_class"], [0, 1])
        self.assertIsNotNone(results.iloc[1]["risk_probability"])
        self.assertGreater(len(results.iloc[1]["imputed_features"]), 0)

        # Row 3: Missing critical feature (sc) -> withholds prediction
        self.assertEqual(results.iloc[2]["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertTrue(pd.isna(results.iloc[2]["diagnostic_class"]))
        self.assertTrue(pd.isna(results.iloc[2]["risk_probability"]))
        self.assertIn("sc", results.iloc[2]["missing_features"])

    # =========================================================================
    # SCENARIO 13: Missing critical values never silently produce healthy prediction
    # =========================================================================
    def test_scenario_13_missing_critical_never_silently_healthy(self):
        """Scenario 13: Missing critical labs must NEVER produce diagnostic_class=0 or Healthy."""
        test_cases = [
            {}, # completely empty
            {"sc": None, "al": None, "hemo": None}, # all null
            {"sc": 0.8}, # missing al and hemo
            {"al": 0}, # missing sc and hemo
            {"hemo": 15.0}, # missing sc and al
            {"sc": "unparseable", "al": 0, "hemo": 15.0} # corrupted sc
        ]

        for case in test_cases:
            res = self.pipeline.predict_single(case)
            # Must NOT classify as Healthy (class 0) or produce a valid probability
            self.assertNotEqual(res.get("diagnostic_class"), 0, f"Failed for case: {case}")
            self.assertIsNone(res.get("risk_probability"), f"Risk probability must be None for: {case}")
            self.assertIn(
                res.get("prediction_status"),
                ["ABSTAIN_MISSING_CRITICAL_FEATURES", "REJECTED_INVALID_SCHEMA"],
                f"Status unexpected for case: {case}"
            )

    # =========================================================================
    # SCENARIO 14: Compatibility with existing fitted model
    # =========================================================================
    def test_scenario_14_compatibility_with_existing_fitted_model(self):
        """Scenario 14: Serialized pipeline loads cleanly and maintains all trained components."""
        p = self.pipeline
        self.assertEqual(len(p.selected_features), 10)
        self.assertEqual(set(p.selected_features), set(TOP_10_CONSENSUS_FEATURES))
        self.assertTrue(hasattr(p.model, "predict"))
        self.assertTrue(hasattr(p.model, "predict_proba"))
        self.assertTrue(hasattr(p.preprocessor, "transform_single_record"))
        self.assertTrue(hasattr(p.preprocessor, "transform_df"))

        # Verify inference on both healthy and diseased presets
        res_h = p.predict_single(self.complete_healthy)
        self.assertEqual(res_h["diagnostic_class"], 0)

        res_d = p.predict_single(self.complete_ckd)
        self.assertEqual(res_d["diagnostic_class"], 1)

    # =========================================================================
    # SCENARIO 15: Existing regression tests compatibility
    # =========================================================================
    def test_scenario_15_existing_regression_compatibility(self):
        """Scenario 15: Clinical report generation handles both valid and abstained inputs."""
        # Report for complete valid input
        report_valid = self.pipeline.generate_clinical_report(self.complete_healthy)
        self.assertIn("NEFROAI CLINICAL DIAGNOSTIC EVALUATION", report_valid)
        self.assertIn("PREDICTION_AVAILABLE", report_valid)
        self.assertIn("Calibrated Disease Probability", report_valid)

        # Report for abstained input
        report_abstained = self.pipeline.generate_clinical_report({"hemo": 14.0, "al": 0})
        self.assertIn("NEFROAI CLINICAL DIAGNOSTIC EVALUATION", report_abstained)
        self.assertIn("ABSTAIN_MISSING_CRITICAL_FEATURES", report_abstained)
        self.assertIn("Missing / Invalid Biomarkers", report_abstained)

    # =========================================================================
    # TARGETED SAFETY REVIEWS (Phase 4 Step 2 Corrections)
    # =========================================================================
    def test_unit_serum_creatinine_conversions(self):
        """Serum creatinine supports mg/dL and µmol/L; rejects incompatible units."""
        # Standard mg/dL
        rec_mg = dict(self.complete_healthy, sc="0.9 mg/dL")
        res_mg = self.pipeline.predict_single(rec_mg)
        self.assertEqual(res_mg["sanitized_inputs"]["sc"], 0.9)

        # Standard SI µmol/L (88.42 µmol/L == 1.0 mg/dL)
        rec_si = dict(self.complete_healthy, sc="88.42 umol/l")
        res_si = self.pipeline.predict_single(rec_si)
        self.assertAlmostEqual(res_si["sanitized_inputs"]["sc"], 1.0, places=2)

        # SI with micro sign µmol/L
        rec_si_u = dict(self.complete_healthy, sc="176.84 µmol/L")
        res_si_u = self.pipeline.predict_single(rec_si_u)
        self.assertAlmostEqual(res_si_u["sanitized_inputs"]["sc"], 2.0, places=2)

        # Incompatible unit (e.g. g/dL for creatinine) MUST be rejected, never silently stripped!
        rec_bad = dict(self.complete_healthy, sc="1.2 g/dL")
        res_bad = self.pipeline.predict_single(rec_bad)
        self.assertEqual(res_bad["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res_bad["diagnostic_class"])
        self.assertIn("sc", res_bad["feature_anomalies"])
        self.assertEqual(res_bad["feature_anomalies"]["sc"]["status"], "UNSUPPORTED_UNIT")

    def test_unit_hemoglobin_conversions(self):
        """Hemoglobin supports g/dL and g/L; rejects incompatible units."""
        # Standard g/dL
        rec_gdl = dict(self.complete_healthy, hemo="15.2 g/dL")
        res_gdl = self.pipeline.predict_single(rec_gdl)
        self.assertEqual(res_gdl["sanitized_inputs"]["hemo"], 15.2)

        # European SI g/L (150 g/L == 15.0 g/dL)
        rec_gl = dict(self.complete_healthy, hemo="150.0 g/L")
        res_gl = self.pipeline.predict_single(rec_gl)
        self.assertAlmostEqual(res_gl["sanitized_inputs"]["hemo"], 15.0, places=1)

        # Incompatible unit (e.g. mmol/L for hemoglobin) MUST be rejected!
        rec_bad = dict(self.complete_healthy, hemo="150 mmol/L")
        res_bad = self.pipeline.predict_single(rec_bad)
        self.assertEqual(res_bad["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res_bad["diagnostic_class"])
        self.assertEqual(res_bad["feature_anomalies"]["hemo"]["status"], "UNSUPPORTED_UNIT")

    def test_unit_blood_glucose_conversions(self):
        """Glucose supports mg/dL and mmol/L; rejects incompatible units."""
        # Standard mg/dL
        rec_mg = dict(self.complete_healthy, bgr="99.1 mg/dL")
        res_mg = self.pipeline.predict_single(rec_mg)
        self.assertEqual(res_mg["sanitized_inputs"]["bgr"], 99.1)

        # SI mmol/L (5.5 mmol/L * 18.0182 == 99.1 mg/dL)
        rec_mmol = dict(self.complete_healthy, bgr="5.5 mmol/L")
        res_mmol = self.pipeline.predict_single(rec_mmol)
        self.assertAlmostEqual(res_mmol["sanitized_inputs"]["bgr"], 99.1, delta=0.5)

        # Incompatible unit (e.g. umol/L for glucose) MUST be rejected, never silently imputed!
        rec_bad = dict(self.complete_healthy, bgr="5.5 umol/L")
        res_bad = self.pipeline.predict_single(rec_bad)
        self.assertEqual(res_bad["prediction_status"], "ABSTAIN_INVALID_INPUT_MEASUREMENT")
        self.assertIsNone(res_bad["risk_probability"])
        self.assertNotIn("bgr", res_bad["imputed_features"])
        self.assertEqual(res_bad["feature_anomalies"]["bgr"]["status"], "UNSUPPORTED_UNIT")

    def test_genuine_clinical_extremes_preserved_without_clamping(self):
        """Genuine clinical extreme values (e.g. sc=15.0, bgr=450) are preserved without clamping."""
        extreme_genuine = dict(self.complete_ckd, sc=15.0, bu=180.0, bgr=450.0)
        res = self.pipeline.predict_single(extreme_genuine)
        self.assertEqual(res["prediction_status"], "PREDICTION_AVAILABLE")
        self.assertEqual(res["sanitized_inputs"]["sc"], 15.0)
        self.assertEqual(res["sanitized_inputs"]["bu"], 180.0)
        self.assertEqual(res["sanitized_inputs"]["bgr"], 450.0)

    def test_unphysical_out_of_bounds_measurements_rejected(self):
        """Unphysical measurements (negative values, sg < 1.0, dipstick > 5) are rejected as invalid."""
        # Negative critical measurement
        res_neg = self.pipeline.predict_single(dict(self.complete_healthy, sc=-4.0))
        self.assertEqual(res_neg["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res_neg["diagnostic_class"])
        self.assertEqual(res_neg["feature_anomalies"]["sc"]["status"], "INVALID_REPRESENTATION")

        # Unphysical specific gravity (less than pure water, 1.000)
        res_sg_low = self.pipeline.predict_single(dict(self.complete_healthy, sg=0.950))
        self.assertEqual(res_sg_low["prediction_status"], "ABSTAIN_INVALID_INPUT_MEASUREMENT")
        self.assertNotIn("sg", res_sg_low["imputed_features"])
        self.assertEqual(res_sg_low["feature_anomalies"]["sg"]["status"], "INVALID_REPRESENTATION")

        # Impossible dipstick grade
        res_al = self.pipeline.predict_single(dict(self.complete_healthy, al=10))
        self.assertEqual(res_al["prediction_status"], "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIsNone(res_al["diagnostic_class"])

    def test_target_and_metadata_column_isolation(self):
        """
        Target columns ('classification', 'class', 'target') and metadata columns ('id', 'patient_id')
        must never influence predictions, reach the feature preprocessor, or leak into sanitized inputs.
        """
        base_record = dict(self.complete_healthy)

        # Baseline prediction on pure clinical features
        res_baseline = self.pipeline.predict_single(base_record, include_attributions=True)

        # Perturb with conflicting target and metadata columns
        variants = [
            dict(base_record, classification="ckd"),
            dict(base_record, classification="notckd"),
            dict(base_record, classification=1),
            dict(base_record, classification=0),
            dict(base_record, target=1),
            dict(base_record, target=0),
            dict(base_record, target="positive"),
            dict(base_record, id="PATIENT_9999", patient_id="PT_XYZ"),
            dict(base_record, classification="ckd", target=1, id="PATIENT_42")
        ]

        for var in variants:
            res_var = self.pipeline.predict_single(var, include_attributions=True)
            # 1. Predictions must be strictly identical
            self.assertEqual(res_var["diagnostic_class"], res_baseline["diagnostic_class"])
            self.assertEqual(res_var["risk_probability"], res_baseline["risk_probability"])
            self.assertEqual(res_var["confidence_score"], res_baseline["confidence_score"])
            self.assertEqual(res_var["risk_category"], res_baseline["risk_category"])
            # 2. Target/metadata keys must NOT be present in sanitized inputs
            for col in ["classification", "target", "id", "patient_id"]:
                self.assertNotIn(col, res_var["sanitized_inputs"])
            # 3. Attributions must match identically
            for f in self.pipeline.selected_features:
                self.assertEqual(
                    res_var["feature_attributions"][f]["importance_weight"],
                    res_baseline["feature_attributions"][f]["importance_weight"]
                )

        # Metadata-only records must be rejected by schema validator
        meta_only = {"id": 101, "classification": "ckd", "patient_id": "PT_01"}
        is_valid, reason = KidneyDiagnosticPipeline.validate_schema(meta_only)
        self.assertFalse(is_valid)
        self.assertIn("no clinical feature measurements", reason)

        # Batch prediction with and without target column
        df_clean = pd.DataFrame([self.complete_healthy, self.complete_ckd])
        df_with_target = pd.DataFrame([
            dict(self.complete_healthy, classification="ckd", target=1, id=101),
            dict(self.complete_ckd, classification="notckd", target=0, id=102)
        ])

        batch_res_clean = self.pipeline.predict_batch(df_clean)
        batch_res_target = self.pipeline.predict_batch(df_with_target)

        # Ensure target column presence inverted labels do NOT affect model outputs
        self.assertEqual(list(batch_res_clean["diagnostic_class"]), list(batch_res_target["diagnostic_class"]))
        self.assertEqual(list(batch_res_clean["risk_probability"]), list(batch_res_target["risk_probability"]))
        # Verify metadata column 'id' is cleanly retained in batch output
        self.assertIn("id", batch_res_target.columns)
        self.assertEqual(list(batch_res_target["id"]), [101, 102])

    def test_out_of_domain_measurements_abstain_with_neutral_messaging(self):
        """
        Measurements outside the model's empirical training envelope
        must trigger ABSTAIN_OUT_OF_DOMAIN_MEASUREMENT with neutral clinical messaging,
        preserving actual values without silent clamping or training median replacement.
        """
        ood_cases = [
            # 1. Low hemoglobin (hemo < 2.5 g/dL)
            ("hemo", 1.8, "hemo"),
            # 2. Elevated specific gravity (sg > 1.035)
            ("sg", 1.040, "sg"),
            # 3. High serum creatinine (sc > 30.0 mg/dL)
            ("sc", 35.0, "sc"),
            # 4. Elevated blood urea (bu > 400.0 mg/dL)
            ("bu", 550.0, "bu"),
            # 5. Elevated blood glucose (bgr > 600.0 mg/dL)
            ("bgr", 750.0, "bgr")
        ]

        expected_neutral_msg = (
            "This measurement is outside the model's validated operating range. "
            "Automated prediction has been withheld. Verify the laboratory measurement and obtain qualified clinical review."
        )

        for feat, extreme_val, expected_feat in ood_cases:
            patient = dict(self.complete_ckd, **{feat: extreme_val})
            res = self.pipeline.predict_single(patient)

            # 1. Must withhold prediction
            self.assertEqual(
                res["prediction_status"],
                "ABSTAIN_OUT_OF_DOMAIN_MEASUREMENT",
                f"Failed for {feat}={extreme_val}"
            )
            self.assertIsNone(res["risk_probability"])
            self.assertIsNone(res["diagnostic_class"])
            self.assertEqual(res["diagnosis"], "PREDICTION_WITHHELD (Out-of-Domain Measurement)")
            self.assertEqual(res["risk_category"], "Abstained (Out-of-Domain Measurement)")

            # 2. Genuine measurement must be PRESERVED in sanitized inputs (NEVER clamped!)
            self.assertIn(feat, res["sanitized_inputs"])
            self.assertEqual(res["sanitized_inputs"][feat], extreme_val)

            # 3. Value must NEVER be sent to median imputation!
            self.assertNotIn(feat, res["imputed_features"])
            self.assertEqual(len(res["imputed_features"]), 0)

            # 4. Out-of-domain feature list and neutral reason must be present
            self.assertIn(expected_feat, res["out_of_domain_features"])
            self.assertIn(expected_neutral_msg, res["abstention_reason"])

    def test_median_imputation_strictly_reserved_for_omitted_measurements(self):
        """
        Proves that median/mode imputation is reserved EXCLUSIVELY for omitted measurements
        and is NEVER applied to out-of-domain extreme or invalid inputs.
        """
        # Case A: Omitted non-critical feature (clinician didn't order blood urea)
        omitted_bu = dict(self.complete_healthy)
        del omitted_bu["bu"]
        res_omitted = self.pipeline.predict_single(omitted_bu)
        self.assertEqual(res_omitted["prediction_status"], "INCOMPLETE_INPUT_ESTIMATE")
        self.assertIn("bu", res_omitted["imputed_features"])
        self.assertIsNotNone(res_omitted["risk_probability"])

        # Case B: Out-of-domain extreme (clinician measured bu=550 mg/dL)
        ood_bu = dict(self.complete_healthy, bu=550.0)
        res_ood = self.pipeline.predict_single(ood_bu)
        self.assertEqual(res_ood["prediction_status"], "ABSTAIN_OUT_OF_DOMAIN_MEASUREMENT")
        self.assertNotIn("bu", res_ood["imputed_features"])
        self.assertEqual(res_ood["sanitized_inputs"]["bu"], 550.0)  # Preserved!
        self.assertIsNone(res_ood["risk_probability"])

        # Case C: Invalid negative measurement (clinician/instrument error bu=-50)
        invalid_bu = dict(self.complete_healthy, bu=-50.0)
        res_invalid = self.pipeline.predict_single(invalid_bu)
        self.assertEqual(res_invalid["prediction_status"], "ABSTAIN_INVALID_INPUT_MEASUREMENT")
        self.assertNotIn("bu", res_invalid["imputed_features"])
        self.assertIsNone(res_invalid["risk_probability"])

    def test_completeness_ratio_denominators(self):
        """Verifies exact denominators: 10 for model consensus, 24 for full panel."""
        # Complete healthy input provides all 10 model consensus features
        res = self.pipeline.predict_single(self.complete_healthy)
        self.assertEqual(res["data_completeness_ratio"], 1.0) # 10 / 10
        self.assertEqual(res["full_panel_completeness_ratio"], round(10 / 24, 4)) # 10 / 24

        # Sparse input with 4 features
        sparse = {"sc": 1.1, "al": 0, "hemo": 13.5, "pcv": 40.0}
        res_sp = self.pipeline.predict_single(sparse)
        self.assertEqual(res_sp["data_completeness_ratio"], 0.4) # 4 / 10
        self.assertEqual(res_sp["full_panel_completeness_ratio"], round(4 / 24, 4)) # 4 / 24


if __name__ == "__main__":
    unittest.main(verbosity=2)
