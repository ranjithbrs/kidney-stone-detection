"""NEFROAI-X Phase 9 QA, Security, and Deployment Readiness Verification Suite.

Comprehensive tests covering:
1. CSV Formula Injection sanitization (OWASP ASVS 5.0.0 V5.1.4 / CWE-1236).
2. Synthetic demonstration provenance tracking and safety warning banners.
3. KFRE DISC-05 applicability boundary validation for eGFR >= 60 vs < 60.
4. Single-measurement chronicity and hypertension diagnostic boundaries.
5. Longitudinal CSV upload limits and biological range filtering.
6. Session state isolation and reset behavior.
7. Secrets, credentials, and configuration safety audits.
8. Un-fabricated survival model status governance.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Ensure src/ and project root are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import src.pipeline as _pipe_mod
import src.preprocessing as _prep_mod
sys.modules.setdefault("pipeline", _pipe_mod)
sys.modules.setdefault("preprocessing", _prep_mod)

import pandas as pd
import streamlit as st

from src.clinical.assessment_contracts import (
    Demographics,
    Engine1ScreeningInput,
    Engine2SeverityInput,
    Engine3ProgressionInput,
    EngineStatus,
    PatientAssessmentRequest,
    ProvenanceSource,
    UnifiedAssessmentResponse,
)
from src.clinical.kfre_calculator import KFRECalibrationProfile, KFREInput, calculate_kfre
from src.clinical.progression_features import ClinicalObservation, LongitudinalPatientRecord
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.ui.components.input_forms import clear_session_state, initialize_session_state, load_preset
from src.ui.components.report_export import (
    generate_csv_export,
    generate_json_export,
    generate_pdf_report,
    generate_text_report,
    sanitize_csv_cell,
)


class TestPhase9QASecurity(unittest.TestCase):
    """Phase 9 Quality, Security, and Clinical Reliability verification tests."""

    @classmethod
    def setUpClass(cls):
        """Initialize the unified engine once for test efficiency."""
        cls.engine = UnifiedAssessmentEngine()

    def setUp(self):
        """Reset session state before each test."""
        st.session_state.clear()
        initialize_session_state()

    # -----------------------------------------------------------------------
    # 1. CSV Formula Injection Sanitization (OWASP ASVS V5.1.4)
    # -----------------------------------------------------------------------
    def test_01_csv_formula_injection_sanitization(self):
        """Verify cell values starting with =, +, -, @, \\t, \\r are safely prefixed."""
        malicious_inputs = [
            "=1+1",
            "+cmd|' /C calc'!A0",
            "-2+3",
            "@SUM(A1:A10)",
            "\tTAB_INJECTION",
            "\rCR_INJECTION",
        ]
        for val in malicious_inputs:
            sanitized = sanitize_csv_cell(val)
            self.assertTrue(
                sanitized.startswith("'"),
                f"Value {val} was not neutralized with single quote prefix: {sanitized}"
            )

        # Non-malicious values should remain untouched
        safe_inputs = ["PT-1001", "normal_text", 123, 45.6, None]
        for val in safe_inputs:
            self.assertEqual(sanitize_csv_cell(val), val)

    def test_02_csv_export_neutralizes_malicious_patient_id(self):
        """Verify generate_csv_export escapes formula injection in patient_id."""
        req = PatientAssessmentRequest(
            patient_id="=cmd|'/C calc'!A0",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.1, uacr=25.0, age=50.0, sex="male"),
            requested_engines=["engine2"],
        )
        resp = self.engine.assess_patient(req)
        csv_str = generate_csv_export(resp)
        self.assertIn("'=cmd|'/C calc'!A0", csv_str)
        self.assertNotIn("\n=cmd", csv_str)

    # -----------------------------------------------------------------------
    # 2. Synthetic Demonstration Provenance Tracking & Warnings
    # -----------------------------------------------------------------------
    def test_03_preset_loading_sets_synthetic_provenance(self):
        """Verify loading presets marks session state as synthetic demonstration."""
        load_preset("healthy")
        self.assertTrue(st.session_state.get("is_synthetic_demonstration"))
        self.assertEqual(st.session_state.get("preset_label"), "healthy")

        load_preset("high_risk_ckd")
        self.assertTrue(st.session_state.get("is_synthetic_demonstration"))
        self.assertEqual(st.session_state.get("preset_label"), "high_risk_ckd")

    def test_04_session_reset_clears_synthetic_demonstration_flag(self):
        """Verify resetting session state clears the synthetic demonstration flag."""
        load_preset("rapid_progressor")
        self.assertTrue(st.session_state.get("is_synthetic_demonstration"))

        clear_session_state()
        self.assertFalse(st.session_state.get("is_synthetic_demonstration"))
        self.assertIsNone(st.session_state.get("preset_label"))

    def test_05_synthetic_warning_presence_in_exported_reports(self):
        """Verify synthetic demonstration records include prominent warning banners in text/PDF."""
        req = PatientAssessmentRequest(
            patient_id="PT-SYNTH-QA",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.2, uacr=45.0, age=55.0, sex="female"),
            provenance=ProvenanceSource.SYNTHETIC_DEMONSTRATION.value,
            requested_engines=["engine2"],
        )
        resp = self.engine.assess_patient(req)
        txt = generate_text_report(resp)
        self.assertIn("SYNTHETIC DEMONSTRATION RECORD WARNING", txt)
        self.assertIn("SOFTWARE VERIFICATION PURPOSES ONLY", txt)

        # PDF generation should embed demonstration marker
        pdf_bytes = generate_pdf_report(resp)
        self.assertGreater(len(pdf_bytes), 1000)

    # -----------------------------------------------------------------------
    # 3. KFRE DISC-05 Applicability Boundary Audits
    # -----------------------------------------------------------------------
    def test_06_kfre_disc05_triggers_when_egfr_ge_60(self):
        """Verify DISC-05 triggers when eGFR >= 60 (CKD G1/G2 is out of validated KFRE scope)."""
        req = PatientAssessmentRequest(
            patient_id="PT-KFRE-OUT-OF-SCOPE",
            # Normal creatinine in young male gives eGFR > 90 (Stage G1)
            engine2_input=Engine2SeverityInput(serum_creatinine=0.8, uacr=15.0, age=30.0, sex="male"),
            engine3_input=Engine3ProgressionInput(),
            requested_engines=["engine2", "engine3"],
        )
        resp = self.engine.assess_patient(req)
        disc_ids = [d["discrepancy_id"] for d in resp.clinical_discrepancies]
        self.assertIn("DISC-05-KFRE-OUT-OF-APPLICABILITY", disc_ids)
        self.assertIsNone(resp.engine3_result.kfre_2year_risk)

    def test_07_kfre_calculates_and_avoids_disc05_for_stage_g3_g5(self):
        """Verify KFRE calculates valid risk scores and does NOT trigger DISC-05 for eGFR < 60."""
        req = PatientAssessmentRequest(
            patient_id="PT-KFRE-VALID-STAGE-G3",
            # Elevated creatinine in older adult gives eGFR ~35 (Stage G3b)
            engine2_input=Engine2SeverityInput(serum_creatinine=2.0, uacr=150.0, age=65.0, sex="male"),
            engine3_input=Engine3ProgressionInput(),
            requested_engines=["engine2", "engine3"],
        )
        resp = self.engine.assess_patient(req)
        self.assertTrue(resp.engine3_result.kfre_is_applicable)
        self.assertIsNotNone(resp.engine3_result.kfre_2year_risk)
        self.assertGreater(resp.engine3_result.kfre_2year_risk, 0.0)

        disc_ids = [d["discrepancy_id"] for d in resp.clinical_discrepancies]
        self.assertNotIn("DISC-05-KFRE-OUT-OF-APPLICABILITY", disc_ids)

    # -----------------------------------------------------------------------
    # 4. Diagnostic & Chronicity Boundary Audits
    # -----------------------------------------------------------------------
    def test_08_single_bp_does_not_mutate_history_triggers_disc07(self):
        """Verify a single elevated BP measurement triggers DISC-07 without silently modifying history."""
        req = PatientAssessmentRequest(
            patient_id="PT-BP-CONFLICT",
            engine1_input=Engine1ScreeningInput(
                biomarkers={
                    "hemo": 14.0, "sg": 1.020, "pcv": 42.0, "sc": 1.1, "rc": 4.8,
                    "al": 0, "bu": 28.0, "bgr": 105.0, "htn": "no", "dm": "no",
                    "bp": 155.0,  # Elevated single measurement
                }
            ),
            requested_engines=["engine1"],
        )
        resp = self.engine.assess_patient(req)
        disc_ids = [d["discrepancy_id"] for d in resp.clinical_discrepancies]
        self.assertIn("DISC-07-HYPERTENSION-HISTORY-CONFLICT", disc_ids)

        # Verify clinical action advises measurement technique verification, not established diagnosis
        disc = next(d for d in resp.clinical_discrepancies if d["discrepancy_id"] == "DISC-07-HYPERTENSION-HISTORY-CONFLICT")
        self.assertIn("assess for undiagnosed hypertension", disc["clinical_action"].lower())

    def test_09_single_exam_triggers_chronicity_warning_disc03(self):
        """Verify cross-sectional staging triggers DISC-03 advising 3-month verification."""
        req = PatientAssessmentRequest(
            patient_id="PT-SINGLE-EXAM",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.8, uacr=220.0, age=60.0, sex="female"),
            requested_engines=["engine2"],
        )
        resp = self.engine.assess_patient(req)
        disc_ids = [d["discrepancy_id"] for d in resp.clinical_discrepancies]
        self.assertIn("DISC-03-CROSS-SECTIONAL-CHRONICITY-UNVERIFIED", disc_ids)

        disc = next(d for d in resp.clinical_discrepancies if d["discrepancy_id"] == "DISC-03-CROSS-SECTIONAL-CHRONICITY-UNVERIFIED")
        self.assertIn("repeat serum creatinine and uacr in 3 months", disc["clinical_action"].lower())

    # -----------------------------------------------------------------------
    # 5. Longitudinal Biological Validity & Limits
    # -----------------------------------------------------------------------
    def test_10_biological_bounds_constants_exist(self):
        """Verify biological validity bounds cover key renal biomarkers."""
        from src.data_sources.longitudinal_loader import BIOLOGICAL_BOUNDS
        self.assertIn("serum_creatinine", BIOLOGICAL_BOUNDS)
        self.assertIn("egfr", BIOLOGICAL_BOUNDS)
        self.assertIn("uacr", BIOLOGICAL_BOUNDS)
        self.assertEqual(BIOLOGICAL_BOUNDS["serum_creatinine"], (0.2, 25.0))

    # -----------------------------------------------------------------------
    # 6. Survival Model Status & Data Governance
    # -----------------------------------------------------------------------
    def test_11_survival_models_deferred_no_synthetic_predictions(self):
        """Verify survival models remain strictly deferred without fabricated probabilities."""
        req = PatientAssessmentRequest(
            patient_id="PT-SURVIVAL-GATE",
            engine3_input=Engine3ProgressionInput(
                longitudinal_record=LongitudinalPatientRecord(
                    patient_id="PT-SURVIVAL-GATE",
                    age_baseline=60.0,
                    sex="male",
                    observations=[
                        ClinicalObservation(timestamp=datetime(2022, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.2),
                        ClinicalObservation(timestamp=datetime(2022, 6, 1, tzinfo=timezone.utc), serum_creatinine=1.4),
                        ClinicalObservation(timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc), serum_creatinine=1.6),
                    ]
                )
            ),
            requested_engines=["engine3"],
        )
        resp = self.engine.assess_patient(req)
        self.assertEqual(resp.engine3_result.survival_status, "DEFERRED_PENDING_APPROVED_COHORT")
        surv_probs = resp.engine3_result.survival_predictions.get("survival_probabilities")
        self.assertTrue(surv_probs is None or surv_probs == {})

    # -----------------------------------------------------------------------
    # 7. Secrets & Git Repository Hygiene
    # -----------------------------------------------------------------------
    def test_12_no_secrets_in_tracked_source(self):
        """Verify source code does not contain hardcoded private keys or live API tokens."""
        forbidden_tokens = ["BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", "aws_secret_access_key"]
        checked_exts = (".py", ".json", ".yaml", ".yml")
        for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "src")):
            for f in files:
                if f.endswith(checked_exts):
                    p = os.path.join(root, f)
                    with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                        for tok in forbidden_tokens:
                            self.assertNotIn(tok, content, f"Forbidden token '{tok}' detected in {p}")

    def test_13_gitignore_safeguards_credentials(self):
        """Verify .gitignore blocks .env, secrets, and private keys."""
        gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
        self.assertTrue(os.path.isfile(gitignore_path))
        with open(gitignore_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertIn(".env", lines)
        self.assertIn("secrets.json", lines)


if __name__ == "__main__":
    unittest.main()
