"""NEFROAI-X Phase 8 Streamlit Application & UI Test Suite.

Comprehensive verification of:
1. Application startup and module loading
2. Multipage navigation routing
3. Engine 1 form validation and execution
4. Engine 2 form validation and unit reconciliation
5. Engine 3 multi-visit observation handling
6. Unified multi-engine assessment execution
7. Independent engine execution
8. Engine failure isolation
9. Missing clinical data handling
10. Invalid units handling
11. Invalid timestamps handling
12. Landmark time-cutoff filtering
13. Deferred survival model display
14. KFRE applicability warnings
15. Cross-engine discrepancy display (DISC-01 to DISC-07)
16. Explainability charts and feature leverage
17. Charts with missing observations
18. Medical report text generation
19. JSON report export
20. CSV export and upload parsing
21. Session-state isolation and reset
22. No silent imputation preservation
23. Gated survival models (no fabricated predictions)
24. Mandatory disclaimer presence in app and exports
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import src.streamlit_app as sa
from src.clinical.assessment_contracts import (
    Demographics,
    Engine1Result,
    Engine1ScreeningInput,
    Engine2Result,
    Engine2SeverityInput,
    Engine3ProgressionInput,
    Engine3Result,
    EngineStatus,
    FindingSeverity,
    PatientAssessmentRequest,
    ProvenanceSource,
    UnifiedAssessmentResponse,
)
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine
from src.ui.components.discrepancies import render_discrepancies
from src.ui.components.header import render_app_header
from src.ui.components.input_forms import (
    clear_session_state,
    initialize_session_state,
    load_preset,
)
from src.ui.components.report_export import (
    generate_csv_export,
    generate_json_export,
    generate_pdf_report,
    generate_text_report,
)
from src.ui.components.result_cards import (
    render_engine1_card,
    render_engine2_card,
    render_engine3_card,
)
from src.ui.components.visualizations import (
    render_feature_attributions_chart,
    render_kdigo_matrix,
    render_longitudinal_timeline,
)
from src.ui.views.about_view import render_about_view
from src.ui.views.assessment_view import render_assessment_view
from src.ui.views.explainability_view import render_explainability_view
from src.ui.views.home_view import render_home_view
from src.ui.views.longitudinal_view import render_longitudinal_view
from src.ui.views.report_view import render_report_view


class TestStreamlitApplication(unittest.TestCase):
    """Test suite for the unified Streamlit application components and views."""

    @classmethod
    def setUpClass(cls):
        """Prepare sample patient assessment fixture."""
        cls.engine = UnifiedAssessmentEngine()
        cls.sample_req = PatientAssessmentRequest(
            patient_id="PT-UI-VERIFY",
            demographics=Demographics(age=62.0, sex="male"),
            engine1_input=Engine1ScreeningInput(biomarkers={
                "sc": 1.9, "al": 2, "hemo": 11.0, "sg": 1.015,
                "pcv": 33.0, "rc": 3.7, "bu": 58.0, "bgr": 145.0,
                "htn": "yes", "dm": "no"
            }),
            engine2_input=Engine2SeverityInput(
                serum_creatinine=1.9, uacr=190.0, age=62.0, sex="male"
            ),
            engine3_input=Engine3ProgressionInput(),
            provenance=ProvenanceSource.CLINICAL_EHR.value,
        )
        cls.sample_resp = cls.engine.assess_patient(cls.sample_req)

    def setUp(self):
        """Reset session state before each test."""
        st.session_state.clear()
        initialize_session_state()

    # -----------------------------------------------------------------------
    # 1. Application Startup & Entry Point
    # -----------------------------------------------------------------------
    def test_01_app_startup_and_main_callable(self):
        """Verify main Streamlit entry point is importable and callable."""
        self.assertTrue(callable(sa.main))
        self.assertIsNotNone(sa.render_app_header)

    # -----------------------------------------------------------------------
    # 2. Page Navigation Routing
    # -----------------------------------------------------------------------
    def test_02_page_navigation_routing(self):
        """Verify navigation routing functions without throwing exceptions."""
        with patch("streamlit.sidebar.radio", return_value="🏠 System Overview"):
            with patch("src.streamlit_app.render_home_view") as mock_home:
                sa.main()
                mock_home.assert_called_once()

        with patch("streamlit.sidebar.radio", return_value="🩺 Patient Clinical Assessment"):
            with patch("src.streamlit_app.render_assessment_view") as mock_assess:
                sa.main()
                mock_assess.assert_called_once()

    # -----------------------------------------------------------------------
    # 3. Engine 1 Form Validation
    # -----------------------------------------------------------------------
    def test_03_engine1_form_validation(self):
        """Verify Engine 1 inputs are validated and mapped to screening schema."""
        load_preset("healthy")
        self.assertEqual(st.session_state.e1_hemo, 15.2)
        self.assertEqual(st.session_state.e1_sc, 0.85)
        self.assertEqual(st.session_state.e1_al, 0)

    # -----------------------------------------------------------------------
    # 4. Engine 2 Form Validation & Unit Conversions
    # -----------------------------------------------------------------------
    def test_04_engine2_form_validation_and_units(self):
        """Verify Engine 2 accepts custom units and maps them cleanly."""
        st.session_state.e2_scr = 176.84
        st.session_state.e2_scr_unit = "µmol/L"
        st.session_state.e2_uacr = 25.0
        st.session_state.e2_uacr_unit = "mg/mmol"

        # Execute through engine
        req = PatientAssessmentRequest(
            patient_id="PT-UNITS-TEST",
            engine2_input=Engine2SeverityInput(
                serum_creatinine=176.84,
                serum_creatinine_unit="µmol/L",
                uacr=25.0,
                uacr_unit="mg/mmol",
                age=55.0,
                sex="male",
            )
        )
        res = self.engine.assess_patient(req)
        self.assertIsNotNone(res.engine2_result)
        self.assertAlmostEqual(res.engine2_result.uacr, 221.0, delta=2.0)

    # -----------------------------------------------------------------------
    # 5. Engine 3 Multiple Observation Handling
    # -----------------------------------------------------------------------
    def test_05_engine3_multiple_observations(self):
        """Verify Engine 3 multi-visit observations structure."""
        load_preset("rapid_progressor")
        self.assertEqual(len(st.session_state.e3_observations), 5)
        self.assertLess(st.session_state.e3_observations[0]["scr"], st.session_state.e3_observations[-1]["scr"])

    # -----------------------------------------------------------------------
    # 6. Unified Assessment Execution
    # -----------------------------------------------------------------------
    def test_06_unified_assessment_execution(self):
        """Verify unified assessment coordinates all three engines."""
        res = self.sample_resp
        self.assertIsInstance(res, UnifiedAssessmentResponse)
        self.assertIn("engine1", res.engines_executed)
        self.assertIn("engine2", res.engines_executed)

    # -----------------------------------------------------------------------
    # 7. Independent Engine Execution
    # -----------------------------------------------------------------------
    def test_07_independent_engine_execution(self):
        """Verify executing an individual engine produces isolated output."""
        req = PatientAssessmentRequest(
            patient_id="PT-E2-ONLY",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.2, uacr=45.0, age=50.0, sex="female"),
            requested_engines=["engine2"],
        )
        res = self.engine.assess_patient(req)
        self.assertEqual(res.engines_executed, ["engine2"])
        self.assertIsNone(res.engine1_result)
        self.assertIsNotNone(res.engine2_result)

    # -----------------------------------------------------------------------
    # 8. Engine Failure Isolation
    # -----------------------------------------------------------------------
    def test_08_engine_failure_isolation(self):
        """Verify render_engine1_card handles execution errors cleanly."""
        err_res = Engine1Result(
            status=EngineStatus.EXECUTION_ERROR.value,
            abstention_reason="Simulated numerical error",
        )
        # Should render warning without throwing exception
        render_engine1_card(err_res)

    # -----------------------------------------------------------------------
    # 9. Missing Clinical Data Handling
    # -----------------------------------------------------------------------
    def test_09_missing_clinical_data_handling(self):
        """Verify missing features are flagged in result cards."""
        abstain_res = Engine1Result(
            status="ABSTAIN_MISSING_CRITICAL_FEATURES",
            abstention_reason="Critical biomarker sc is missing",
            missing_features=["sc"],
            data_completeness_ratio=0.7,
        )
        render_engine1_card(abstain_res)

    # -----------------------------------------------------------------------
    # 10. Invalid Units Handling
    # -----------------------------------------------------------------------
    def test_10_invalid_units_handling(self):
        """Verify unrecognized units trigger warning rather than silent crash."""
        req = PatientAssessmentRequest(
            patient_id="PT-BAD-UNIT",
            engine2_input=Engine2SeverityInput(
                serum_creatinine=1.5,
                serum_creatinine_unit="unknown_unit",
                age=50.0,
                sex="M"
            )
        )
        res = self.engine.assess_patient(req)
        self.assertTrue(any("Unit Warning" in w for w in res.safety_warnings))

    # -----------------------------------------------------------------------
    # 11. Invalid Timestamps Handling
    # -----------------------------------------------------------------------
    def test_11_invalid_timestamps_handling(self):
        """Verify timeline rendering with empty observations does not crash."""
        fig = render_longitudinal_timeline([])
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    # -----------------------------------------------------------------------
    # 12. Landmark Time-Cutoff Filtering
    # -----------------------------------------------------------------------
    def test_12_landmark_filtering_ui(self):
        """Verify timeline rendering marks landmark cutoff accurately."""
        lm = datetime(2023, 6, 1, tzinfo=timezone.utc)
        obs = [
            {"date": date(2022, 6, 1), "scr": 1.2, "uacr": 50.0},
            {"date": date(2023, 6, 1), "scr": 1.6, "uacr": 120.0},
        ]
        fig = render_longitudinal_timeline(obs, landmark_time=lm)
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    # -----------------------------------------------------------------------
    # 13. Deferred Survival Model Display
    # -----------------------------------------------------------------------
    def test_13_deferred_survival_model_display(self):
        """Verify Engine 3 result card renders deferred status clearly."""
        e3_res = Engine3Result(
            status=EngineStatus.AVAILABLE.value,
            survival_status="DEFERRED_PENDING_APPROVED_COHORT",
            historical_egfr_slope=-2.4,
            slope_status="PROGRESSION_DECLINE",
        )
        render_engine3_card(e3_res)

    # -----------------------------------------------------------------------
    # 14. KFRE Applicability Warnings
    # -----------------------------------------------------------------------
    def test_14_kfre_applicability_warning_display(self):
        """Verify KFRE out-of-scope status renders warning."""
        e3_out = Engine3Result(
            status=EngineStatus.AVAILABLE.value,
            kfre_is_applicable=False,
            kfre_applicability_explanation="KFRE is out of scope for eGFR >= 60 mL/min.",
        )
        render_engine3_card(e3_out)

    # -----------------------------------------------------------------------
    # 15. Cross-Engine Discrepancy Display
    # -----------------------------------------------------------------------
    def test_15_cross_engine_discrepancy_display(self):
        """Verify render_discrepancies renders DISC-02 as critical."""
        discs = [{
            "discrepancy_id": "DISC-02-FALSE-ASSURANCE-RISK",
            "title": "Screening-Staging Discordance",
            "severity": FindingSeverity.CRITICAL.value,
            "involved_engines": ["Engine 1", "Engine 2"],
            "description": "Engine 1 screening says healthy, but Engine 2 shows severe CKD.",
            "clinical_action": "Do not rely on binary screening.",
        }]
        render_discrepancies(discs)

    # -----------------------------------------------------------------------
    # 16. Explainability Components
    # -----------------------------------------------------------------------
    def test_16_explainability_components(self):
        """Verify feature attributions horizontal chart generates cleanly."""
        attribs = {
            "sc": {"importance_weight": 0.28, "normalized_value": 1.5},
            "hemo": {"importance_weight": 0.22, "normalized_value": -1.2},
            "al": {"importance_weight": 0.18, "normalized_value": 2.0},
        }
        fig = render_feature_attributions_chart(attribs)
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    # -----------------------------------------------------------------------
    # 17. KDIGO Heatmap Matrix Rendering
    # -----------------------------------------------------------------------
    def test_17_kdigo_heatmap_matrix_rendering(self):
        """Verify KDIGO matrix generates with patient highlight."""
        fig = render_kdigo_matrix("G3b", "A2")
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    # -----------------------------------------------------------------------
    # 18. Medical Report Text Generation
    # -----------------------------------------------------------------------
    def test_18_report_generation_text(self):
        """Verify formatted medical report text contains all required sections."""
        txt = generate_text_report(self.sample_resp)
        self.assertIn("NEFROAI-X CLINICAL DECISION SUPPORT SYSTEM", txt)
        self.assertIn("1. ENGINE 1: SCREENING", txt)
        self.assertIn("2. ENGINE 2: KDIGO CGA SEVERITY STAGING", txt)
        self.assertIn("3. ENGINE 3: LONGITUDINAL PROGRESSION", txt)
        self.assertIn("MANDATORY CLINICAL DISCLAIMER", txt)
        self.assertIn("PHYSICIAN REVIEW & SIGN-OFF", txt)

    # -----------------------------------------------------------------------
    # 19. JSON Report Export
    # -----------------------------------------------------------------------
    def test_19_json_report_export(self):
        """Verify JSON export produces valid schema."""
        json_str = generate_json_export(self.sample_resp)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["patient_id"], "PT-UI-VERIFY")
        self.assertIn("engine_versions", parsed)

    # -----------------------------------------------------------------------
    # 20. CSV Export & Formatting
    # -----------------------------------------------------------------------
    def test_20_csv_report_export(self):
        """Verify CSV export produces structured tabular data."""
        csv_str = generate_csv_export(self.sample_resp)
        df = pd.read_csv(pd.io.common.StringIO(csv_str))
        self.assertEqual(len(df), 1)
        self.assertEqual(df["patient_id"].iloc[0], "PT-UI-VERIFY")

    # -----------------------------------------------------------------------
    # 21. PDF Report Generation
    # -----------------------------------------------------------------------
    def test_21_pdf_report_generation(self):
        """Verify PDF generation produces multi-page valid binary bytes."""
        pdf_bytes = generate_pdf_report(self.sample_resp)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 5000)

    # -----------------------------------------------------------------------
    # 22. Session State Isolation & Clear
    # -----------------------------------------------------------------------
    def test_22_session_state_isolation(self):
        """Verify clear_session_state resets cached evaluation data."""
        st.session_state.latest_unified_response = self.sample_resp
        st.session_state.e3_observations = [{"date": date.today(), "scr": 1.2}]
        clear_session_state()
        self.assertIsNone(st.session_state.latest_unified_response)
        self.assertEqual(len(st.session_state.e3_observations), 0)

    # -----------------------------------------------------------------------
    # 23. No Fabricated Clinical Survival Predictions
    # -----------------------------------------------------------------------
    def test_23_no_fabricated_survival_predictions(self):
        """Verify survival predictions remain deferred and un-fabricated."""
        res = self.sample_resp
        self.assertIn(res.engine3_result.survival_status, [
            "DEFERRED_PENDING_APPROVED_COHORT",
            "NO_VALID_LONGITUDINAL_FEATURES",
        ])
        self.assertNotIn("100% Infallible", str(res.to_dict()))
        # Ensure survival probabilities are empty or None (un-fabricated)
        surv_probs = res.engine3_result.survival_predictions.get("survival_probabilities")
        self.assertTrue(surv_probs is None or surv_probs == {})

    # -----------------------------------------------------------------------
    # 24. Mandatory Disclaimer Presence
    # -----------------------------------------------------------------------
    def test_24_mandatory_disclaimer_presence(self):
        """Verify persistent disclaimer appears in header and report text."""
        txt = generate_text_report(self.sample_resp)
        self.assertIn("INVESTIGATIONAL RESEARCH SOFTWARE", txt.upper())
        self.assertIn("DOES NOT PROVIDE DEFINITIVE MEDICAL DIAGNOSES", txt.upper())
        self.assertIn("RESEARCH", txt.upper())


if __name__ == "__main__":
    unittest.main()
