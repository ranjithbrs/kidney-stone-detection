"""Automated verification suite for Option A & Option B NEFROAI-X extensions."""

from __future__ import annotations

import hashlib
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.clinical.assessment_contracts import (
    Demographics,
    Engine1ScreeningInput,
    Engine2SeverityInput,
    Engine3ProgressionInput,
    PatientAssessmentRequest,
    ProvenanceSource,
)
from src.clinical.attestation import (
    arbitrate_clinical_action,
    verify_assessment_attestation,
)
from src.clinical.batch_screening import (
    get_sample_batch_csv,
    run_batch_clinical_screening,
)
from src.clinical.coherence_verifier import verify_cross_analyte_coherence
from src.clinical.conformal_calibrator import (
    evaluate_mondrian_prediction_set,
    get_calibrated_mondrian_result,
)
from src.clinical.drift_monitor import evaluate_batch_covariate_drift
from src.clinical.patient_store import ClinicalHistoryStore
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
    backtest_egfr_trajectory,
    evaluate_chronicity_and_aki_status,
)
from src.clinical.stacking_ensemble import get_stacking_ensemble
from src.clinical.xai_live import (
    compute_live_lime,
    compute_live_treeshap,
    compute_xai_concordance,
    generate_clinical_counterfactuals,
)
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.feature_selection import FeatureSelectionPipeline
from src.pipeline import KidneyDiagnosticPipeline
from src.ui.components.report_export import (
    generate_csv_export,
    generate_pdf_report,
    generate_text_report,
)


PROTECTED_SHA256 = {
    os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib"): "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826",
    os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_A_uci_ckd.csv"): "147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc",
    os.path.join(ROOT_DIR, "models", "preprocessor_Dataset_A.joblib"): "fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3",
    os.path.join(ROOT_DIR, "src", "clinical_input_reliability_mechanism.py"): "f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0",
}


class TestOptionAFeatureSelectionAndStacking(unittest.TestCase):
    """Option A: 5-method fold-safe feature selection & 4-family Stacking Ensemble."""

    def test_01_fold_safe_5method_feature_selection_stability(self):
        fsp = FeatureSelectionPipeline(random_state=42)
        stab = fsp.evaluate_cv_selection_stability(top_k=10, n_splits=5)
        self.assertTrue(stab["held_out_test_excluded"])
        self.assertEqual(stab["train_partition_size"], 320)
        self.assertEqual(stab["n_splits"], 5)
        self.assertEqual(len(stab["fold_selections"]), 5)
        self.assertGreaterEqual(stab["mean_pairwise_jaccard"], 0.60)
        # Core hematologic/renal biomarkers must persist cleanly across folds
        self.assertTrue({"hemo", "sc", "al"}.issubset(set(stab["consensus_by_frequency"])))

    def test_02_stacking_ensemble_metrics_calibration_and_cache(self):
        ens = get_stacking_ensemble()
        rep = ens.evaluation_report
        self.assertEqual(rep["train_samples"], 320)
        self.assertEqual(rep["test_samples"], 80)
        self.assertIn("Stacking Ensemble (Meta-LR)", rep["models"])
        stack = rep["models"]["Stacking Ensemble (Meta-LR)"]
        self.assertGreaterEqual(stack["macro_f1"], 0.95)
        self.assertGreaterEqual(stack["pr_auc"], 0.98)
        self.assertLessEqual(stack["brier_score"], 0.05)
        self.assertIn("roc_auc_ci95", stack["bootstrap_ci95"])
        self.assertIn("pr_auc_ci95", stack["bootstrap_ci95"])
        self.assertTrue(len(rep["subgroup_analysis"]) >= 4)

        sample = {
            "hemo": 9.5, "sg": 1.010, "pcv": 29.0, "rc": 3.4, "al": 3.0,
            "htn": "yes", "sc": 3.2, "bu": 85.0, "dm": "yes", "bgr": 210.0,
        }
        pred = ens.predict_with_disagreement(sample)
        self.assertGreater(pred["stacking_probability"], 0.85)
        self.assertIn("disagreement_spread", pred)
        self.assertIn("predictive_entropy_bits", pred)


class TestOptionBReliabilityCoherenceAndDrift(unittest.TestCase):
    """Option B: Mondrian Conformal, Cross-Analyte Coherence, and Batch Drift/OOD."""

    def test_01_mondrian_conformal_calibration_and_prediction_sets(self):
        m = get_calibrated_mondrian_result()
        self.assertTrue(m.held_out_test_excluded)
        self.assertGreater(m.q_healthy, 0.0)
        self.assertGreater(m.q_ckd, 0.0)
        self.assertGreaterEqual(m.empirical_coverage_healthy, 0.90)
        self.assertGreaterEqual(m.empirical_coverage_ckd, 0.90)

        high_risk_eval = evaluate_mondrian_prediction_set(0.96, m)
        self.assertEqual(high_risk_eval, [1])

        borderline_eval = evaluate_mondrian_prediction_set(0.50, m)
        self.assertIn(0, borderline_eval)
        self.assertIn(1, borderline_eval)

    def test_02_cross_analyte_coherence_verifier_catches_contradictions(self):
        coherent = verify_cross_analyte_coherence(
            {"hemo": 14.2, "pcv": 43.0, "rc": 4.9, "sc": 0.9, "bu": 15.0, "al": 0.0},
            uacr_mg_g=10.0,
        )
        self.assertTrue(coherent.is_coherent)
        self.assertEqual(coherent.coherence_score, 1.0)
        self.assertEqual(len(coherent.findings), 0)

        contradictory = verify_cross_analyte_coherence(
            {"hemo": 16.5, "pcv": 22.0, "rc": 1.8, "sc": 0.6, "bu": 95.0, "al": 0.0},
            uacr_mg_g=550.0,
        )
        self.assertFalse(contradictory.is_coherent)
        self.assertTrue(contradictory.specimen_verification_recommended)
        self.assertGreater(contradictory.total_cri_penalty, 0.0)
        check_ids = {f["check_id"] for f in contradictory.findings}
        self.assertIn("COH-01-HEMO-PCV-MISMATCH", check_ids)
        self.assertIn("COH-04-DIPSTICK-UACR-DISCORDANCE", check_ids)

    def test_03_batch_covariate_drift_and_mahalanobis_ood_integration(self):
        pipeline = KidneyDiagnosticPipeline.load(os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib"))
        sample_df = pd.read_csv(io.StringIO(get_sample_batch_csv()))
        summary = run_batch_clinical_screening(sample_df, pipeline=pipeline)
        self.assertTrue(summary.schema_valid)
        self.assertIsNotNone(summary.drift_report)
        self.assertIn("mahalanobis_distance", summary.results_df.columns)
        self.assertIn("mahalanobis_ood_flag", summary.results_df.columns)

        # Extreme out-of-distribution cohort must trigger Mahalanobis OOD flag & shift
        ood_df = pd.DataFrame([
            {
                "hemo": 19.5, "sg": 1.025, "pcv": 58.0, "rc": 7.5, "al": 0,
                "htn": "no", "sc": 24.0, "bu": 340.0, "dm": "no", "bgr": 490.0,
            }
            for _ in range(5)
        ])
        ood_drift = evaluate_batch_covariate_drift(ood_df)
        self.assertEqual(ood_drift.overall_drift_status, "SEVERE_COVARIATE_SHIFT")
        self.assertGreaterEqual(ood_drift.ood_row_count, 1)


class TestOptionBXAILimeConcordanceCounterfactualAndLongitudinal(unittest.TestCase):
    """Option B: Live LIME, Cross-XAI Concordance, Counterfactuals, AKI Guard, Backtest."""

    def test_01_live_lime_concordance_and_counterfactuals(self):
        pipeline = KidneyDiagnosticPipeline.load(os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib"))
        sample_ckd = {
            "hemo": 9.5, "sg": 1.010, "pcv": 29.0, "rc": 3.4, "al": 3.0,
            "htn": "yes", "sc": 3.2, "bu": 85.0, "dm": "yes", "bgr": 210.0,
        }
        shap_res = compute_live_treeshap(pipeline, sample_ckd)
        lime_res = compute_live_lime(pipeline, sample_ckd)
        self.assertIsNotNone(shap_res)
        self.assertIsNotNone(lime_res)
        self.assertTrue(len(lime_res.rules) > 0)

        conc = compute_xai_concordance(shap_res, lime_res, uacr_mg_g=450.0)
        self.assertIsNotNone(conc)
        self.assertIn(conc.concordance_status, {"HIGH_CONCORDANCE", "MODERATE_CONCORDANCE", "DIVERGENT_ATTRIBUTIONS"})

        cf = generate_clinical_counterfactuals(pipeline, sample_ckd, target_max_risk=0.25, max_changes=2)
        self.assertIsNotNone(cf)
        self.assertEqual(cf.locked_immutable_features, ["age", "sex", "htn", "dm"])
        self.assertLessEqual(cf.target_probability, cf.initial_probability)

    def test_02_aki_velocity_guard_and_walk_forward_backtest(self):
        obs = [
            ClinicalObservation(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.1, uacr=25.0),
            ClinicalObservation(timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc), serum_creatinine=1.25, uacr=45.0),
            ClinicalObservation(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.40, uacr=80.0),
            ClinicalObservation(timestamp=datetime(2026, 1, 5, tzinfo=timezone.utc), serum_creatinine=2.90, uacr=250.0),
        ]
        rec = LongitudinalPatientRecord(
            patient_id="TEST_AKI",
            age_baseline=60.0,
            sex="male",
            observations=obs,
            is_synthetic=True,
            provenance="SYNTHETIC_SIMULATOR",
        )
        aki = evaluate_chronicity_and_aki_status(rec)
        self.assertTrue(aki["acute_spike_detected"])
        self.assertTrue(aki["chronic_persistence_confirmed"])
        self.assertEqual(aki["status"], "ACUTE_ON_CHRONIC_DETERIORATION")

        bt = backtest_egfr_trajectory(rec)
        self.assertTrue(bt["eligible"])
        self.assertEqual(bt["evaluated_steps"], 2)
        self.assertGreaterEqual(bt["mae"], 0.0)
        self.assertGreaterEqual(bt["rmse"], 0.0)


class TestUnifiedArbitrationAttestationAndStore(unittest.TestCase):
    """End-to-end Unified engine arbitration (DISC-09/10), SHA-256 attestation, exports, store."""

    def test_01_unified_disc09_disc10_arbitration_attestation_and_exports(self):
        engine = UnifiedAssessmentEngine()
        obs = [
            ClinicalObservation(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.1, uacr=20.0, systolic_bp=125.0),
            ClinicalObservation(timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc), serum_creatinine=1.3, uacr=40.0, systolic_bp=130.0),
            ClinicalObservation(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.6, uacr=85.0, systolic_bp=138.0),
            ClinicalObservation(timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc), serum_creatinine=3.5, uacr=600.0, systolic_bp=155.0),
        ]
        rec = LongitudinalPatientRecord(
            patient_id="EXT_TEST_001",
            age_baseline=64.0,
            sex="male",
            observations=obs,
            is_synthetic=True,
            provenance="SYNTHETIC_SIMULATOR",
        )
        req = PatientAssessmentRequest(
            patient_id="EXT_TEST_001",
            demographics=Demographics(age=64.0, sex="M"),
            engine1_input=Engine1ScreeningInput(
                biomarkers={
                    "hemo": 16.0, "sg": 1.010, "pcv": 24.0, "rc": 2.0, "al": 0.0,
                    "htn": "yes", "sc": 3.5, "bu": 95.0, "dm": "yes", "bgr": 220.0,
                },
                provenance=ProvenanceSource.SYNTHETIC_SIMULATOR.value,
            ),
            engine2_input=Engine2SeverityInput(
                serum_creatinine=3.5, uacr=600.0, age=64.0, sex="M",
                provenance=ProvenanceSource.SYNTHETIC_SIMULATOR.value,
            ),
            engine3_input=Engine3ProgressionInput(
                longitudinal_record=rec,
                landmark_time=datetime(2026, 2, 1, tzinfo=timezone.utc),
                provenance=ProvenanceSource.SYNTHETIC_SIMULATOR.value,
            ),
            provenance=ProvenanceSource.SYNTHETIC_SIMULATOR.value,
        )
        resp = engine.assess_patient(req)
        disc_ids = {d.get("discrepancy_id") for d in resp.clinical_discrepancies}
        self.assertIn("DISC-09-CROSS-ANALYTE-COHERENCE-ALERT", disc_ids)
        self.assertTrue(any(did and did.startswith("DISC-10-") for did in disc_ids))
        self.assertEqual(resp.overall_completeness.get("arbitration_tier"), "SPECIMEN_VERIFICATION_REDRAW")

        # Tamper-evident attestation check
        payload = resp.to_dict()
        ok_orig, exp_sha, comp_sha = verify_assessment_attestation(payload)
        self.assertTrue(ok_orig)
        self.assertEqual(exp_sha, comp_sha)

        tampered = dict(payload)
        tampered["engine2_result"] = dict(payload["engine2_result"], egfr=95.0)
        ok_tamp, _, _ = verify_assessment_attestation(tampered)
        self.assertFalse(ok_tamp)

        # Text / CSV / PDF exports carry new sections cleanly
        txt = generate_text_report(resp)
        self.assertIn("SAFETY-MAX ARBITRATION & PROVENANCE ATTESTATION", txt)
        self.assertIn("SPECIMEN_VERIFICATION_REDRAW", txt)
        csv_s = generate_csv_export(resp)
        self.assertIn("attestation_sha256", csv_s)
        pdf_bytes = generate_pdf_report(resp)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_02_safety_max_arbitration_urgent_clinical_priority(self):
        arb = arbitrate_clinical_action(
            e1={"conformal_gate_decision": "ACCEPT", "risk_probability": 0.90},
            e2={"composite_risk_level": "Very High Risk", "egfr": 28.0},
            e3={"chronicity_aki_assessment": {"acute_spike_detected": True}},
            discrepancies=[{"discrepancy_id": "DISC-02-FALSE-ASSURANCE-RISK", "severity": "CRITICAL"}],
        )
        self.assertEqual(arb["tier"], "NEPHROLOGY_REFERRAL_PRIORITY")
        self.assertEqual(arb["urgency_rank"], 4)

    def test_03_clinical_history_store_auth_persistence_and_engine3_visits(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "vault.db")
            store = ClinicalHistoryStore(db_path=db_path)

            ok, _ = store.register_user(
                "dr_nephro", "Secure!Pass123", "Dr Nephro", "Nephrologist", email="nephro@hospital.org"
            )
            self.assertTrue(ok)
            self.assertIsNone(store.authenticate_user("dr_nephro", "WrongPass"))
            auth = store.authenticate_user("dr_nephro", "Secure!Pass123")
            self.assertEqual(auth["role"], "Nephrologist")
            auth_email = store.authenticate_user("nephro@hospital.org", "Secure!Pass123")
            self.assertEqual(auth_email["username"], "dr_nephro")
            self.assertEqual(store.count_assessments("dr_nephro"), 0)

            engine = UnifiedAssessmentEngine()
            req = PatientAssessmentRequest(
                patient_id="VAULT_PT_01",
                demographics=Demographics(age=58.0, sex="F"),
                engine1_input=Engine1ScreeningInput(
                    biomarkers={
                        "hemo": 10.2, "sg": 1.010, "pcv": 31.0, "rc": 3.5, "al": 2.0,
                        "htn": "yes", "sc": 2.1, "bu": 55.0, "dm": "no", "bgr": 115.0,
                    },
                    provenance=ProvenanceSource.SYNTHETIC_SIMULATOR.value,
                ),
                engine2_input=Engine2SeverityInput(
                    serum_creatinine=2.1, uacr=180.0, age=58.0, sex="F",
                    provenance=ProvenanceSource.SYNTHETIC_SIMULATOR.value,
                ),
            )
            resp = engine.assess_patient(req)
            row_id = store.save_assessment(
                resp, owner_username="dr_nephro", observation_date="2026-01-15", systolic_bp=142.0
            )
            self.assertGreater(row_id, 0)

            rows = store.list_assessments(patient_id="VAULT_PT_01", owner_username="dr_nephro")
            self.assertEqual(len(rows), 1)
            stored_payload = store.get_assessment_payload(resp.assessment_id)
            self.assertIsNotNone(stored_payload)
            v_ok, _, _ = verify_assessment_attestation(stored_payload)
            self.assertTrue(v_ok)

            visits = store.load_patient_visits_for_engine3("VAULT_PT_01", owner_username="dr_nephro")
            self.assertEqual(len(visits), 1)
            self.assertAlmostEqual(visits[0]["scr"], 2.1)
            self.assertAlmostEqual(visits[0]["sbp"], 142.0)


class TestProtectedAssetsAndFullAppTestNavigation(unittest.TestCase):
    """Protected SHA-256 baseline guard and headless Streamlit AppTest across all 8 views."""

    def test_01_protected_baseline_sha256_intact(self):
        for path, expected in PROTECTED_SHA256.items():
            with open(path, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(actual, expected, f"Protected baseline asset modified: {path}")

    def test_02_streamlit_all_8_views_render_without_exceptions(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(os.path.join(ROOT_DIR, "src", "streamlit_app.py"), default_timeout=45)
        at.run()
        self.assertFalse(at.exception, f"Home startup exception: {at.exception}")

        menu_labels = [
            "🩺 Patient Clinical Assessment",
            "📈 Longitudinal Kidney Assessment",
            "🔍 Explainability & Findings (XAI)",
            "📄 Clinical Assessment Report",
            "📖 About & Clinical Governance",
            "📊 Model Performance & Calibration",
            "🗂️ Patient History & Audit Vault",
        ]
        # Execute an assessment first so Explainability & Report views also test active patient flows
        at.sidebar.radio[0].set_value("🩺 Patient Clinical Assessment").run()
        self.assertFalse(at.exception, f"Assessment view exception: {at.exception}")
        exec_btn = [b for b in at.button if "Execute Clinical Assessment" in b.label]
        self.assertTrue(exec_btn)
        exec_btn[0].click().run()
        self.assertFalse(at.exception, f"Assessment execute exception: {at.exception}")

        for label in menu_labels[1:]:
            at.sidebar.radio[0].set_value(label).run()
            self.assertFalse(at.exception, f"Navigation exception on view '{label}': {at.exception}")

    def test_03_streamlit_signup_signin_signout_flow(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as td:
            temp_db = os.path.join(td, "ui_auth_test.db")
            with patch("src.clinical.patient_store.DEFAULT_DB_PATH", temp_db), patch(
                "src.ui.components.auth.ClinicalHistoryStore", lambda: ClinicalHistoryStore(db_path=temp_db)
            ), patch(
                "src.ui.views.history_view.ClinicalHistoryStore", lambda: ClinicalHistoryStore(db_path=temp_db)
            ):
                at = AppTest.from_file(os.path.join(ROOT_DIR, "src", "streamlit_app.py"), default_timeout=30)
                at.run()
                self.assertFalse(at.exception)
                # Sidebar Sign In & Sign Up buttons exist on startup
                sb_labels = [b.label for b in at.sidebar.button]
                self.assertTrue(any("Sign In" in lbl for lbl in sb_labels))
                self.assertTrue(any("Sign Up" in lbl for lbl in sb_labels))

                # Navigate to History & Audit Vault and register an account via form
                at.sidebar.radio[0].set_value("🗂️ Patient History & Audit Vault").run()
                self.assertFalse(at.exception)

                at.text_input(key="vault_reg_user").set_value("clin_demo")
                at.text_input(key="vault_reg_name").set_value("Dr Demo")
                at.text_input(key="vault_reg_email").set_value("demo@clinic.org")
                at.text_input(key="vault_reg_pw1").set_value("Pass!234")
                at.text_input(key="vault_reg_pw2").set_value("Pass!234")
                reg_submit = [b for b in at.button if "Create Account" in b.label][0]
                reg_submit.click().run()
                self.assertFalse(at.exception)
                self.assertEqual(at.session_state["auth_username"], "clin_demo")

                # Sign out cleanly via sidebar Sign Out button
                out_btn = [b for b in at.sidebar.button if "Sign Out" in b.label][0]
                out_btn.click().run()
                self.assertFalse(at.exception)
                self.assertNotIn("auth_username", at.session_state)

                # Sign back in via email + password
                at.text_input(key="vault_login_ident").set_value("demo@clinic.org")
                at.text_input(key="vault_login_pw").set_value("Pass!234")
                in_submit = [b for b in at.button if b.label == "🔑 Sign In"][0]
                in_submit.click().run()
                self.assertFalse(at.exception)
                self.assertEqual(at.session_state["auth_username"], "clin_demo")


if __name__ == "__main__":
    unittest.main()

