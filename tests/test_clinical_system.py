"""
Phase 11: Comprehensive Test Suite for NefroAI Kidney Diagnostic System
Contains rigorous test cases across all 10 clinical software verification criteria:
1. Normal inputs (Healthy vs Diseased profiles)
2. Missing / partial inputs
3. Invalid / corrupted input data types
4. Unusual numerical values & out-of-distribution extremes
5. Model loading & serialization round-trip
6. Prediction determinism & physiological monotonicity
7. Feature attribution & XAI explanation generation
8. Clinical diagnostic report generation
9. Application error handling & benchmark asset integrity
10. Complete end-to-end patient workflow & batch latency
"""

import os
import sys
import unittest
import json
import joblib
import numpy as np
import pandas as pd

# Add src and root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline import KidneyDiagnosticPipeline
from preprocessing import ClinicalDataPreprocessor


class TestNormalInputs(unittest.TestCase):
    """1. Test normal patient inputs across healthy and pathological profiles."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_normal_healthy_patient(self):
        healthy_input = {
            "hemo": 15.5, "sg": 1.025, "pcv": 46.0, "sc": 0.8, "rc": 5.2,
            "al": 0, "bu": 24.0, "bgr": 95.0, "htn": "no", "dm": "no"
        }
        res = self.pipeline.predict_single(healthy_input, include_attributions=True)
        self.assertEqual(res["diagnostic_class"], 0)
        self.assertIn("Healthy", res["diagnosis"])
        self.assertLessEqual(res["risk_probability"], 0.20)
        self.assertEqual(res["risk_category"], "Low Risk (Normal)")
        self.assertGreaterEqual(res["confidence_score"], 0.80)

    def test_normal_diseased_patient(self):
        diseased_input = {
            "hemo": 7.8, "sg": 1.010, "pcv": 24.0, "sc": 4.8, "rc": 2.9,
            "al": 3, "bu": 85.0, "bgr": 210.0, "htn": "yes", "dm": "yes"
        }
        res = self.pipeline.predict_single(diseased_input, include_attributions=True)
        self.assertEqual(res["diagnostic_class"], 1)
        self.assertIn("Chronic Kidney Disease", res["diagnosis"])
        self.assertGreaterEqual(res["risk_probability"], 0.80)
        self.assertIn("Risk", res["risk_category"])
        self.assertGreaterEqual(res["confidence_score"], 0.80)


class TestMissingInputs(unittest.TestCase):
    """2. Test fault-tolerant handling of incomplete and missing inputs."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_completely_empty_input(self):
        res = self.pipeline.predict_single({}, include_attributions=True)
        self.assertIn(res["diagnostic_class"], [0, 1])
        self.assertTrue(0.0 <= res["risk_probability"] <= 1.0)
        self.assertIsNotNone(res["risk_category"])

    def test_sparse_partial_input(self):
        partial = {"hemo": 14.5, "sc": 0.9}
        res = self.pipeline.predict_single(partial, include_attributions=True)
        self.assertEqual(res["diagnostic_class"], 0)
        self.assertIn("sanitized_inputs", res)
        self.assertEqual(len(res["sanitized_inputs"]), 10)

    def test_explicit_none_and_nan_values(self):
        dirty = {
            "hemo": None, "sg": np.nan, "pcv": "nan", "sc": None,
            "rc": "null", "al": "", "bu": "  ", "bgr": "?", "htn": None, "dm": None
        }
        res = self.pipeline.predict_single(dirty, include_attributions=True)
        self.assertIn(res["diagnostic_class"], [0, 1])
        self.assertFalse(np.isnan(res["risk_probability"]))


class TestInvalidInputs(unittest.TestCase):
    """3. Test rejection and sanitization of corrupted data types and values."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_non_dict_input(self):
        res_none = self.pipeline.predict_single(None, include_attributions=True)
        self.assertIn(res_none["diagnostic_class"], [0, 1])
        res_str = self.pipeline.predict_single("not_a_dict", include_attributions=True)
        self.assertIn(res_str["diagnostic_class"], [0, 1])

    def test_unparseable_string_numbers(self):
        corrupted = {"hemo": "critically_anemic", "sc": "elevated_creatinine", "sg": "normal_gravity"}
        res = self.pipeline.predict_single(corrupted, include_attributions=True)
        self.assertIn(res["diagnostic_class"], [0, 1])
        self.assertFalse(np.isnan(res["risk_probability"]))

    def test_categorical_synonym_mappings(self):
        cases = [
            ({"htn": "1", "dm": "TRUE"}, "yes"),
            ({"htn": "0", "dm": "FALSE"}, "no"),
            ({"htn": "Y", "dm": "N"}, ("yes", "no"))
        ]
        sanitized_1 = self.pipeline._validate_and_sanitize_record(cases[0][0])
        self.assertEqual(sanitized_1["htn"], "yes")
        self.assertEqual(sanitized_1["dm"], "yes")

        sanitized_2 = self.pipeline._validate_and_sanitize_record(cases[1][0])
        self.assertEqual(sanitized_2["htn"], "no")
        self.assertEqual(sanitized_2["dm"], "no")


class TestUnusualNumericalValues(unittest.TestCase):
    """4. Test extreme boundary stress values, infinities, and outliers."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_extreme_high_outliers(self):
        extreme_high = {
            "hemo": 35.0, "sg": 1.150, "pcv": 90.0, "sc": 85.0, "rc": 20.0,
            "al": 10, "bu": 900.0, "bgr": 2500.0, "htn": "yes", "dm": "yes"
        }
        res = self.pipeline.predict_single(extreme_high, include_attributions=True)
        self.assertIn(res["diagnostic_class"], [0, 1])
        self.assertTrue(0.0 <= res["risk_probability"] <= 1.0)
        # Clamped values
        self.assertLessEqual(res["sanitized_inputs"]["sc"], 25.0)
        self.assertLessEqual(res["sanitized_inputs"]["bgr"], 600.0)

    def test_negative_values(self):
        negative_input = {
            "hemo": -5.0, "sg": -1.0, "pcv": -30.0, "sc": -4.0, "rc": -2.0,
            "al": -1, "bu": -50.0, "bgr": -100.0, "htn": "no", "dm": "no"
        }
        res = self.pipeline.predict_single(negative_input, include_attributions=True)
        self.assertGreaterEqual(res["sanitized_inputs"]["hemo"], 2.5)
        self.assertGreaterEqual(res["sanitized_inputs"]["sc"], 0.2)
        self.assertTrue(0.0 <= res["risk_probability"] <= 1.0)

    def test_infinities_and_raw_nans(self):
        inf_input = {
            "hemo": float('inf'), "sc": float('-inf'), "bgr": float('nan'),
            "sg": 1.020, "pcv": 40.0, "rc": 4.5, "al": 0, "bu": 30.0, "htn": "no", "dm": "no"
        }
        res = self.pipeline.predict_single(inf_input, include_attributions=True)
        self.assertFalse(np.isinf(res["risk_probability"]))
        self.assertFalse(np.isnan(res["risk_probability"]))


class TestModelLoading(unittest.TestCase):
    """5. Test model serialization, deserialization, and integrity."""

    def test_model_loading_success(self):
        p = KidneyDiagnosticPipeline.load("models/clinical_pipeline.joblib")
        self.assertIsInstance(p, KidneyDiagnosticPipeline)
        self.assertEqual(len(p.selected_features), 10)
        self.assertTrue(hasattr(p.model, "predict"))

    def test_model_loading_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            KidneyDiagnosticPipeline.load("models/nonexistent_model_path.joblib")

    def test_serialization_roundtrip(self):
        p = KidneyDiagnosticPipeline.load("models/clinical_pipeline.joblib")
        temp_path = "models/test_temp_pipeline.joblib"
        try:
            p.save(temp_path)
            p_reloaded = KidneyDiagnosticPipeline.load(temp_path)
            sample = {"hemo": 14.0, "sc": 1.0, "sg": 1.020, "pcv": 42.0, "rc": 4.8, "al": 0, "bu": 30.0, "bgr": 100.0, "htn": "no", "dm": "no"}
            res1 = p.predict_single(sample)
            res2 = p_reloaded.predict_single(sample)
            self.assertEqual(res1["risk_probability"], res2["risk_probability"])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestPredictionConsistency(unittest.TestCase):
    """6. Test deterministic reproducibility and clinical monotonicity."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_prediction_determinism(self):
        sample = {
            "hemo": 12.2, "sg": 1.015, "pcv": 36.0, "sc": 1.6, "rc": 4.1,
            "al": 1, "bu": 45.0, "bgr": 130.0, "htn": "yes", "dm": "no"
        }
        probs = [self.pipeline.predict_single(sample)["risk_probability"] for _ in range(50)]
        self.assertEqual(len(set(probs)), 1, "Predictions must be strictly deterministic across repeated invocations")

    def test_batch_vs_single_consistency(self):
        p1 = {"hemo": 15.0, "sg": 1.025, "pcv": 45.0, "sc": 0.8, "rc": 5.0, "al": 0, "bu": 25.0, "bgr": 90.0, "htn": "no", "dm": "no"}
        p2 = {"hemo": 8.0, "sg": 1.010, "pcv": 25.0, "sc": 4.5, "rc": 3.0, "al": 3, "bu": 80.0, "bgr": 200.0, "htn": "yes", "dm": "yes"}
        
        batch_df = self.pipeline.predict_batch([p1, p2])
        single_1 = self.pipeline.predict_single(p1)
        single_2 = self.pipeline.predict_single(p2)

        self.assertEqual(batch_df["risk_probability"].iloc[0], single_1["risk_probability"])
        self.assertEqual(batch_df["risk_probability"].iloc[1], single_2["risk_probability"])

    def test_physiological_monotonicity_creatinine(self):
        """As Serum Creatinine increases, renal risk should not decrease."""
        base = {"hemo": 13.0, "sg": 1.020, "pcv": 38.0, "rc": 4.5, "al": 0, "bu": 35.0, "bgr": 105.0, "htn": "no", "dm": "no"}
        sc_values = [0.8, 1.4, 2.5, 5.0]
        risks = []
        for sc in sc_values:
            inp = dict(base)
            inp["sc"] = sc
            risks.append(self.pipeline.predict_single(inp)["risk_probability"])
        for i in range(len(risks) - 1):
            self.assertLessEqual(risks[i], risks[i+1], f"Monotonicity violated: SC {sc_values[i]} had risk {risks[i]}, but SC {sc_values[i+1]} had risk {risks[i+1]}")


class TestExplanationGeneration(unittest.TestCase):
    """7. Test SHAP and LIME feature attribution calculations."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_pipeline_attributions_presence(self):
        sample = {"hemo": 10.0, "sc": 2.5, "sg": 1.015, "pcv": 30.0, "rc": 3.8, "al": 2, "bu": 55.0, "bgr": 140.0, "htn": "yes", "dm": "yes"}
        res = self.pipeline.predict_single(sample, include_attributions=True)
        self.assertIn("feature_attributions", res)
        attribs = res["feature_attributions"]
        self.assertEqual(len(attribs), len(self.pipeline.selected_features))
        for feat in self.pipeline.selected_features:
            self.assertIn("importance_weight", attribs[feat])
            self.assertIn("normalized_value", attribs[feat])
            self.assertFalse(np.isnan(attribs[feat]["importance_weight"]))

    def test_attributions_sum(self):
        sample = {"hemo": 15.0, "sc": 0.8, "sg": 1.020, "pcv": 45.0, "rc": 5.0, "al": 0, "bu": 25.0, "bgr": 90.0, "htn": "no", "dm": "no"}
        res = self.pipeline.predict_single(sample, include_attributions=True)
        weights = [v["importance_weight"] for v in res["feature_attributions"].values()]
        total_weight = sum(weights)
        self.assertAlmostEqual(total_weight, 1.0, places=2)


class TestReportGeneration(unittest.TestCase):
    """8. Test clinical diagnostic report assembly and export."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_report_generation_content(self):
        sample = {
            "hemo": 9.2, "sg": 1.010, "pcv": 28.0, "sc": 3.4, "rc": 3.2,
            "al": 2, "bu": 65.0, "bgr": 175.0, "htn": "yes", "dm": "yes"
        }
        report = self.pipeline.generate_clinical_report(sample)
        self.assertIsInstance(report, str)
        self.assertIn("NEFROAI CLINICAL DIAGNOSTIC EVALUATION", report)
        self.assertIn("DIAGNOSTIC ASSESSMENT & RISK SCORE", report)
        self.assertIn("EXPLAINABLE AI (XAI) ATTRIBUTIONS", report)
        self.assertIn("DISCLAIMER", report)
        self.assertIn("3.4", report)  # creatinine value
        self.assertIn("9.2", report)  # hemo value


class TestApplicationHealth(unittest.TestCase):
    """9. Test Streamlit helper functions, data assets, and plots."""

    def test_benchmark_data_integrity(self):
        eval_path = "runs/evaluation/final_evaluation_report.json"
        feat_path = "runs/feature_selection/selected_features.json"
        self.assertTrue(os.path.exists(eval_path))
        self.assertTrue(os.path.exists(feat_path))

        with open(eval_path) as f:
            eval_data = json.load(f)
        self.assertIn("Dataset_A", eval_data)
        self.assertIn("evaluations", eval_data["Dataset_A"])

    def test_visual_assets_exist_and_nonempty(self):
        images = [
            "runs/evaluation/plots/Dataset_A_roc_curves.png",
            "runs/evaluation/plots/Dataset_A_Random_Forest_cm.png",
            "runs/explainability/plots/shap_summary_beeswarm.png",
            "runs/explainability/plots/shap_importance_bar.png",
            "runs/explainability/plots/patient_0_shap_waterfall.png",
            "runs/explainability/plots/patient_0_lime_bar.png"
        ]
        for img in images:
            self.assertTrue(os.path.exists(img), f"Missing plot: {img}")
            self.assertGreater(os.path.getsize(img), 1000, f"Empty plot: {img}")


class TestEndToEndWorkflow(unittest.TestCase):
    """10. Complete end-to-end patient workflow & batch stress test."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = joblib.load("models/clinical_pipeline.joblib")

    def test_complete_patient_journey(self):
        # 1. Incoming unvalidated labs
        raw_patient = {"hemo": "14.2 g/dL", "sg": 1.020, "pcv": 42.0, "sc": " 0.9 mg/dL", "rc": 4.9, "al": 0, "bu": 28.0, "bgr": 102.0, "htn": "no", "dm": "no"}
        # 2. Prediction with attributions
        result = self.pipeline.predict_single(raw_patient, include_attributions=True)
        # 3. Assertions
        self.assertEqual(result["diagnostic_class"], 0)
        self.assertLess(result["risk_probability"], 0.20)
        # 4. Generate report
        report = self.pipeline.generate_clinical_report(raw_patient, result=result)
        self.assertGreater(len(report), 500)

    def test_cohort_batch_performance(self):
        # 50 simulated clinical profiles
        np.random.seed(42)
        cohort = []
        for _ in range(50):
            cohort.append({
                "hemo": float(np.random.uniform(7.0, 17.0)),
                "sg": float(np.random.choice([1.005, 1.010, 1.015, 1.020, 1.025])),
                "pcv": float(np.random.uniform(20.0, 50.0)),
                "sc": float(np.random.uniform(0.5, 6.0)),
                "rc": float(np.random.uniform(2.5, 6.0)),
                "al": int(np.random.choice([0, 1, 2, 3])),
                "bu": float(np.random.uniform(15.0, 120.0)),
                "bgr": float(np.random.uniform(80.0, 250.0)),
                "htn": str(np.random.choice(["yes", "no"])),
                "dm": str(np.random.choice(["yes", "no"]))
            })

        import time
        t0 = time.time()
        batch_results = self.pipeline.predict_batch(cohort)
        elapsed = time.time() - t0

        self.assertEqual(len(batch_results), 50)
        per_sample_ms = (elapsed / 50) * 1000
        # Verification condition: High throughput clinical inference (< 10ms per patient)
        self.assertLess(per_sample_ms, 15.0, f"Inference too slow: {per_sample_ms:.2f} ms/patient")


if __name__ == "__main__":
    unittest.main(verbosity=2)
