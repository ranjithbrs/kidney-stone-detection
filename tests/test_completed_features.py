"""Verification suite for completed NEFROAI-X CKD CDSS features:
1. Dynamic Conformal Calibration (train-only OOF and inductive split, zero test leakage)
2. Live cooperative game-theoretic TreeSHAP waterfall explanations & additivity
3. CD-CIRPVM Conformal Reliability & MIDR integration in Engine 1 + DISC-08
4. Batch CKD Screening CSV ingestion, strict schema rejection, and CWE-1236 export
5. Headless Streamlit AppTest navigation & execution smoke tests
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import unittest
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.clinical.assessment_contracts import (
    Demographics,
    Engine1ScreeningInput,
    PatientAssessmentRequest,
    ProvenanceSource,
)
from src.clinical.batch_screening import (
    get_sample_batch_csv,
    run_batch_clinical_screening,
)
from src.clinical.conformal_calibrator import (
    build_calibrated_reliability_mechanism,
    calibrate_conformal_quantile,
)
from src.clinical.xai_live import compute_live_treeshap
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.pipeline import KidneyDiagnosticPipeline
from src.ui.components.report_export import (
    generate_csv_export,
    generate_pdf_report,
    generate_text_report,
)
from src.ui.components.result_cards import render_engine1_card
from src.ui.components.visualizations import render_live_treeshap_waterfall


class TestDynamicConformalCalibration(unittest.TestCase):
    """1. Verify dynamic conformal calibration on training split only."""

    def test_01_oof_conformal_calibration_bounds_and_coverage(self):
        cal = calibrate_conformal_quantile(alpha=0.05, method="oof")
        self.assertFalse(cal.fallback_used)
        self.assertTrue(cal.held_out_test_excluded)
        self.assertEqual(cal.train_partition_size, 320)
        self.assertEqual(cal.calibration_samples, 320)
        self.assertGreater(cal.conformal_quantile, 0.0)
        self.assertLess(cal.conformal_quantile, 0.50)
        self.assertGreaterEqual(cal.empirical_coverage_on_calibration, 0.95)

    def test_02_inductive_split_conformal_calibration(self):
        cal = calibrate_conformal_quantile(alpha=0.05, method="split", cal_fraction=0.25)
        self.assertFalse(cal.fallback_used)
        self.assertTrue(cal.held_out_test_excluded)
        self.assertEqual(cal.train_partition_size, 320)
        self.assertEqual(cal.calibration_samples, 80)
        self.assertGreater(cal.conformal_quantile, 0.0)
        self.assertLess(cal.conformal_quantile, 0.50)
        self.assertGreaterEqual(cal.empirical_coverage_on_calibration, 0.95)

    def test_03_invalid_alpha_or_method_rejected(self):
        with self.assertRaises(ValueError):
            calibrate_conformal_quantile(alpha=0.0)
        with self.assertRaises(ValueError):
            calibrate_conformal_quantile(alpha=1.0)
        with self.assertRaises(ValueError):
            calibrate_conformal_quantile(method="invalid")

    def test_04_protected_assets_hashes_unchanged(self):
        expected = {
            "models/clinical_pipeline.joblib": "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826",
            "datasets/clinical/dataset_A_uci_ckd.csv": "147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc",
            "models/preprocessor_Dataset_A.joblib": "fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3",
            "src/clinical_input_reliability_mechanism.py": "f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0",
        }
        for rel, exp_sha in expected.items():
            raw = Path(ROOT_DIR, rel).read_bytes()
            got = hashlib.sha256(raw).hexdigest()
            self.assertEqual(got, exp_sha, f"Protected asset hash mismatch for {rel}")


class TestLiveTreeSHAP(unittest.TestCase):
    """2. Verify live cooperative TreeSHAP calculation and waterfall plotting."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = KidneyDiagnosticPipeline.load(os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib"))

    def test_01_treeshap_exact_additivity_healthy_and_ckd(self):
        healthy = {
            "hemo": 15.2, "sg": 1.025, "pcv": 45.0, "rc": 5.2, "al": 0,
            "htn": "no", "sc": 0.85, "bu": 22.0, "dm": "no", "bgr": 95.0,
        }
        ckd = {
            "hemo": 8.4, "sg": 1.010, "pcv": 26.0, "rc": 3.1, "al": 3,
            "htn": "yes", "sc": 4.2, "bu": 78.0, "dm": "yes", "bgr": 195.0,
        }

        for rec in (healthy, ckd):
            res = compute_live_treeshap(self.pipeline, rec)
            self.assertIsNotNone(res)
            self.assertEqual(len(res.shap_values), 10)
            self.assertLess(res.additivity_error, 1e-6)
            self.assertAlmostEqual(
                res.base_value + sum(res.shap_values.values()),
                res.predicted_probability,
                places=5,
            )

    def test_02_render_live_treeshap_waterfall_figure(self):
        ckd = {
            "hemo": 9.8, "sg": 1.012, "pcv": 30.0, "rc": 3.3, "al": 3,
            "htn": "yes", "sc": 2.4, "bu": 72.0, "dm": "yes", "bgr": 185.0,
        }
        shap_res = compute_live_treeshap(self.pipeline, ckd)
        fig = render_live_treeshap_waterfall(shap_res, patient_id="PT-SHAP-TEST")
        self.assertIsInstance(fig, plt.Figure)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        self.assertGreater(len(buf.getvalue()), 5000)

        fallback_fig = render_live_treeshap_waterfall(None)
        self.assertIsInstance(fallback_fig, plt.Figure)
        plt.close(fallback_fig)

    def test_03_non_tree_mock_pipeline_returns_none(self):
        class DummyPipe:
            pass

        self.assertIsNone(compute_live_treeshap(DummyPipe(), {"sc": 1.0}))


class TestCDCIRPVMIntegration(unittest.TestCase):
    """3. Verify CD-CIRPVM conformal gating and DISC-08 inside UnifiedAssessmentEngine."""

    @classmethod
    def setUpClass(cls):
        cls.engine = UnifiedAssessmentEngine()

    def test_01_engine_uses_dynamic_conformal_quantile(self):
        self.assertIsNotNone(self.engine.conformal_calibration)
        self.assertFalse(self.engine.conformal_calibration.fallback_used)
        self.assertNotEqual(self.engine.reliability_mechanism.conformal_quantile, 0.261)

    def test_02_complete_healthy_and_ckd_proceed_with_cri_1(self):
        healthy_req = PatientAssessmentRequest(
            patient_id="PT-CIRPVM-HEALTHY",
            demographics=Demographics(age=42.0, sex="male"),
            engine1_input=Engine1ScreeningInput(biomarkers={
                "hemo": 15.2, "sg": 1.025, "pcv": 45.0, "rc": 5.2, "al": 0,
                "htn": "no", "sc": 0.85, "bu": 22.0, "dm": "no", "bgr": 95.0,
            }),
            requested_engines=["engine1"],
        )
        res = self.engine.assess_patient(healthy_req)
        e1 = res.engine1_result
        self.assertEqual(e1.clinical_reliability_index, 1.0)
        self.assertEqual(e1.conformal_set, [0])
        self.assertEqual(e1.conformal_gate_decision, "PROCEED")
        self.assertIsNotNone(e1.live_shap_attributions)
        self.assertLess(e1.live_shap_attributions["additivity_error"], 1e-6)
        render_engine1_card(e1)

    def test_03_epistemic_ambiguity_or_low_cri_triggers_disc08_abstain(self):
        # Sparse record (only 3 critical features -> 7 consensus features missing -> CRI < 0.60)
        sparse_req = PatientAssessmentRequest(
            patient_id="PT-CIRPVM-SPARSE",
            engine1_input=Engine1ScreeningInput(biomarkers={
                "sc": 1.2, "al": 1, "hemo": 12.5,
            }),
            requested_engines=["engine1"],
        )
        res = self.engine.assess_patient(sparse_req)
        e1 = res.engine1_result
        self.assertLess(e1.clinical_reliability_index, 0.60)
        self.assertEqual(e1.conformal_gate_decision, "ABSTAIN")
        self.assertEqual(e1.conformal_gate_status, "REJECTED_UNRELIABLE_DATA")
        disc_ids = [d["discrepancy_id"] for d in res.clinical_discrepancies]
        self.assertIn("DISC-08-CONFORMAL-RELIABILITY-GATE", disc_ids)

        # Verify reports surface CD-CIRPVM fields cleanly
        txt = generate_text_report(res)
        self.assertIn("Clinical Reliability:", txt)
        csv_str = generate_csv_export(res)
        self.assertIn("e1_cri", csv_str)
        pdf_bytes = generate_pdf_report(res)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_04_borderline_uncertainty_conformal_set_two_classes(self):
        # Engine 1 borderline prediction (P_CKD ~ 0.58) with CRI=1.0 must abstain on epistemic ambiguity {0, 1}
        borderline_req = PatientAssessmentRequest(
            patient_id="PT-CIRPVM-BORDER",
            engine1_input=Engine1ScreeningInput(biomarkers={
                "hemo": 13.0, "sg": 1.020, "pcv": 40.0, "rc": 4.5, "al": 0,
                "htn": "no", "sc": 1.2, "bu": 35.0, "dm": "no", "bgr": 110.0,
            }),
            requested_engines=["engine1"],
        )
        res = self.engine.assess_patient(borderline_req)
        e1 = res.engine1_result
        self.assertEqual(e1.clinical_reliability_index, 1.0)
        self.assertIsNotNone(e1.risk_probability)
        self.assertGreater(e1.risk_probability, 0.20)
        self.assertLess(e1.risk_probability, 0.80)
        self.assertEqual(e1.conformal_set, [0, 1])
        self.assertEqual(e1.conformal_gate_decision, "ABSTAIN")
        self.assertEqual(e1.conformal_gate_status, "REJECTED_EPISTEMIC_UNCERTAINTY")
        disc_ids = [d["discrepancy_id"] for d in res.clinical_discrepancies]
        self.assertIn("DISC-08-CONFORMAL-RELIABILITY-GATE", disc_ids)


class TestBatchScreeningCSV(unittest.TestCase):
    """4. Verify Batch CKD CSV upload service, strict schema rejection, and CWE-1236 safety."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = KidneyDiagnosticPipeline.load(os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib"))
        cls.mech, _ = build_calibrated_reliability_mechanism()

    def test_01_valid_sample_batch_cohort(self):
        df = pd.read_csv(io.StringIO(get_sample_batch_csv()))
        summary = run_batch_clinical_screening(df, self.pipeline, self.mech)
        self.assertTrue(summary.schema_valid)
        self.assertEqual(summary.total_rows, 4)
        self.assertEqual(summary.abstained_rows, 1)
        self.assertEqual(summary.predictions_available + summary.incomplete_estimates, 3)
        self.assertIn("clinical_reliability_index", summary.results_df.columns)
        self.assertIn("conformal_set", summary.results_df.columns)
        self.assertIn("conformal_gate_decision", summary.results_df.columns)
        # Explicit SI unit row should maintain full CRI=1.0
        unit_row = summary.results_df.iloc[2]
        self.assertEqual(unit_row["clinical_reliability_index"], 1.0)
        self.assertIn("sc", unit_row["unit_conversions_detected"])

    def test_02_reject_incompatible_kidney_stone_datasets(self):
        stone_df = pd.read_csv(os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_B_kidney_stone.csv"))
        res_stone = run_batch_clinical_screening(stone_df, self.pipeline, self.mech)
        self.assertFalse(res_stone.schema_valid)
        self.assertIn("Incompatible", res_stone.schema_message)

        simpson_df = pd.read_csv(os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_C_simpson_kidney.csv"))
        res_simpson = run_batch_clinical_screening(simpson_df, self.pipeline, self.mech)
        self.assertFalse(res_simpson.schema_valid)

    def test_03_reject_empty_or_oversized_batch_and_sanitize_formula_injection(self):
        empty_res = run_batch_clinical_screening(pd.DataFrame(), self.pipeline, self.mech)
        self.assertFalse(empty_res.schema_valid)

        sample_df = pd.read_csv(io.StringIO(get_sample_batch_csv())).iloc[[0]].copy()
        sample_df["patient_id"] = "=cmd|'/C calc'!A0"
        summary = run_batch_clinical_screening(sample_df, self.pipeline, self.mech)
        self.assertTrue(summary.schema_valid)
        csv_out = summary.to_sanitized_csv()
        self.assertIn("'=cmd|'/C calc'!A0", csv_out)
        self.assertNotIn("\n=cmd", csv_out)

        oversized = pd.concat([sample_df] * 501, ignore_index=True)
        over_res = run_batch_clinical_screening(oversized, self.pipeline, self.mech, max_rows=500)
        self.assertFalse(over_res.schema_valid)
        self.assertIn("500", over_res.schema_message)


class TestStreamlitHeadlessAppTest(unittest.TestCase):
    """5. Verify end-to-end Streamlit UI rendering via AppTest without runtime errors."""

    def test_01_app_boots_and_navigates_cleanly(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(os.path.join(ROOT_DIR, "src", "streamlit_app.py"), default_timeout=20)
        at.run()
        self.assertFalse(at.exception, f"Streamlit startup exception: {at.exception}")

        # Navigate to Patient Clinical Assessment and trigger Healthy preset + execution
        at.sidebar.radio[0].set_value("🩺 Patient Clinical Assessment").run()
        self.assertFalse(at.exception, f"Assessment view exception: {at.exception}")

        # Execute assessment button
        exec_btn = [b for b in at.button if "Execute Clinical Assessment" in b.label]
        self.assertTrue(exec_btn, "Execute Clinical Assessment button not found")
        exec_btn[0].click().run()
        self.assertFalse(at.exception, f"Execution exception: {at.exception}")

        # Navigate to Explainability view to verify live TreeSHAP waterfall renders cleanly
        at.sidebar.radio[0].set_value("🔍 Explainability & Findings (XAI)").run()
        self.assertFalse(at.exception, f"Explainability view exception: {at.exception}")


if __name__ == "__main__":
    unittest.main()
