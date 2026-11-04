"""NEFROAI-X Phase 7 End-to-End Integration Test Suite.

Verifies the Unified Clinical Assessment Engine (Orchestrator) and its
shared data contracts across all required integration scenarios:
1. All three engines available
2. Engine 1 only
3. Engine 2 only
4. Engine 3 only
5. Partial input availability (e.g. Engine 1 + 2, Engine 2 + 3)
6. Independent engine failure handling
7. Engine-specific abstention
8. Missing critical measurements
9. Invalid / non-standard units handling
10. No silent imputation of clinical measurements
11. Conflicting engine outputs (False Assurance Risk)
12. Cross-sectional versus longitudinal separation
13. KFRE applicability warnings
14. Untrained survival model blocking
15. Patient identifier and provenance preservation
16. No temporal leakage into Engine 3
17. Same-day measurement consistency
18. Reproducibility of unified response
19. Engine independence (no forced positivity)
20. Complete assessment serialization and JSON export readiness
21. Flat dictionary input auto-normalization
22. Explicit requested_engines filtering
23. Clinical history conflict detection
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from src.clinical.assessment_contracts import (
    ClinicalDiscrepancy,
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
    UnifiedFinding,
)
from src.clinical.kfre_calculator import KFRECalibrationProfile, KFREInput
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
)
from src.engines.kidney_progression_engine import KidneyProgressionEngine
from src.engines.kidney_severity_engine import KidneySeverityEngine
from src.engines.unified_assessment_engine import UnifiedAssessmentEngine


class TestUnifiedAssessmentEngine(unittest.TestCase):
    """Integration test suite for the three-engine unified assessment orchestrator."""

    @classmethod
    def setUpClass(cls):
        """Initialize the unified orchestrator with production assets."""
        cls.engine = UnifiedAssessmentEngine()

        # Reusable standard patient test fixtures
        cls.base_time = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)

        cls.healthy_biomarkers = {
            "age": 42.0, "bp": 78.0, "sg": 1.025, "al": 0.0, "su": 0.0,
            "bgr": 95.0, "bu": 24.0, "sc": 0.85, "hemo": 15.2, "pcv": 44.0,
            "rc": 5.2, "htn": "no", "dm": "no"
        }

        cls.ckd_biomarkers = {
            "age": 62.0, "bp": 88.0, "sg": 1.012, "al": 2.0, "su": 0.0,
            "bgr": 145.0, "bu": 62.0, "sc": 2.1, "hemo": 10.4, "pcv": 32.0,
            "rc": 3.6, "htn": "yes", "dm": "yes"
        }

        cls.standard_visits = [
            ClinicalObservation(timestamp=cls.base_time - timedelta(days=360), serum_creatinine=1.5, uacr=120.0),
            ClinicalObservation(timestamp=cls.base_time - timedelta(days=180), serum_creatinine=1.8, uacr=150.0),
            ClinicalObservation(timestamp=cls.base_time, serum_creatinine=2.1, uacr=190.0),
        ]
        cls.standard_record = LongitudinalPatientRecord(
            patient_id="PT-UNIFIED-01",
            age_baseline=61.0,
            sex="M",
            observations=cls.standard_visits,
            provenance=ProvenanceSource.CLINICAL_EHR.value,
        )

    # -----------------------------------------------------------------------
    # Scenario 1: All Three Engines Available
    # -----------------------------------------------------------------------
    def test_01_all_three_engines_available(self):
        req = PatientAssessmentRequest(
            patient_id="PT-ALL-ENGINES",
            demographics=Demographics(age=62.0, sex="male"),
            engine1_input=Engine1ScreeningInput(biomarkers=self.ckd_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=2.1, uacr=190.0, age=62.0, sex="M"),
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
            provenance=ProvenanceSource.CLINICAL_EHR.value,
        )
        res = self.engine.assess_patient(req)

        self.assertIsInstance(res, UnifiedAssessmentResponse)
        self.assertEqual(res.patient_id, "PT-ALL-ENGINES")
        self.assertEqual(set(res.engines_executed), {"engine1", "engine2", "engine3"})
        self.assertEqual(len(res.engines_skipped), 0)
        self.assertEqual(res.overall_completeness["status"], "COMPLETE")
        self.assertEqual(res.overall_completeness["completeness_ratio"], 1.0)

        # Engine 1 checks
        self.assertIsNotNone(res.engine1_result)
        self.assertIn("Chronic Kidney Disease", res.engine1_result.diagnosis)
        self.assertGreater(res.engine1_result.risk_probability, 0.70)

        # Engine 2 checks
        self.assertIsNotNone(res.engine2_result)
        self.assertEqual(res.engine2_result.gfr_category, "G3b")
        self.assertEqual(res.engine2_result.albuminuria_category, "A2")
        self.assertIn("Very High Risk", res.engine2_result.composite_risk_level)

        # Engine 3 checks
        self.assertIsNotNone(res.engine3_result)
        self.assertIsNotNone(res.engine3_result.lmm_annual_slope)
        self.assertIsNotNone(res.engine3_result.kfre_2year_risk)
        self.assertIn("DEFERRED", res.engine3_result.survival_status)

    # -----------------------------------------------------------------------
    # Scenario 2: Engine 1 Only
    # -----------------------------------------------------------------------
    def test_02_engine1_only(self):
        req = PatientAssessmentRequest(
            patient_id="PT-E1-ONLY",
            engine1_input=Engine1ScreeningInput(biomarkers=self.healthy_biomarkers),
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.engines_executed, ["engine1"])
        self.assertIn("engine2", res.engines_skipped)
        self.assertIn("engine3", res.engines_skipped)
        self.assertIsNotNone(res.engine1_result)
        self.assertIsNone(res.engine2_result)
        self.assertIsNone(res.engine3_result)
        self.assertIn("Healthy", res.engine1_result.diagnosis)
        self.assertEqual(res.overall_completeness["status"], "PARTIAL")

    # -----------------------------------------------------------------------
    # Scenario 3: Engine 2 Only
    # -----------------------------------------------------------------------
    def test_03_engine2_only(self):
        req = PatientAssessmentRequest(
            patient_id="PT-E2-ONLY",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.1, uacr=25.0, age=50.0, sex="female"),
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.engines_executed, ["engine2"])
        self.assertIn("engine1", res.engines_skipped)
        self.assertIn("engine3", res.engines_skipped)
        self.assertIsNone(res.engine1_result)
        self.assertIsNotNone(res.engine2_result)
        self.assertIsNone(res.engine3_result)
        self.assertEqual(res.engine2_result.gfr_category, "G2")
        self.assertEqual(res.engine2_result.albuminuria_category, "A1")

    # -----------------------------------------------------------------------
    # Scenario 4: Engine 3 Only
    # -----------------------------------------------------------------------
    def test_04_engine3_only(self):
        req = PatientAssessmentRequest(
            patient_id="PT-E3-ONLY",
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.engines_executed, ["engine3"])
        self.assertIn("engine1", res.engines_skipped)
        self.assertIn("engine2", res.engines_skipped)
        self.assertIsNone(res.engine1_result)
        self.assertIsNone(res.engine2_result)
        self.assertIsNotNone(res.engine3_result)
        self.assertIsNotNone(res.engine3_result.lmm_annual_slope)

    # -----------------------------------------------------------------------
    # Scenario 5: Partial Input Availability (Engine 1 + 2, Engine 2 + 3)
    # -----------------------------------------------------------------------
    def test_05_partial_input_combinations(self):
        # A. Engine 1 + 2
        req_12 = PatientAssessmentRequest(
            patient_id="PT-E1-E2",
            engine1_input=Engine1ScreeningInput(biomarkers=self.ckd_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=2.1, uacr=190.0, age=62.0, sex="male"),
        )
        res_12 = self.engine.assess_patient(req_12)
        self.assertEqual(set(res_12.engines_executed), {"engine1", "engine2"})
        self.assertIn("engine3", res_12.engines_skipped)

        # B. Engine 2 + 3
        req_23 = PatientAssessmentRequest(
            patient_id="PT-E2-E3",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.5, uacr=80.0, age=55.0, sex="female"),
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
        )
        res_23 = self.engine.assess_patient(req_23)
        self.assertEqual(set(res_23.engines_executed), {"engine2", "engine3"})
        self.assertIn("engine1", res_23.engines_skipped)

    # -----------------------------------------------------------------------
    # Scenario 6: Independent Engine Failure Handling
    # -----------------------------------------------------------------------
    def test_06_independent_engine_failure_handling(self):
        # Create an engine with a mock failing pipeline
        class FailingPipeline:
            def predict_single(self, *args, **kwargs):
                raise RuntimeError("Catastrophic simulated matrix inversion crash")

        failing_engine = UnifiedAssessmentEngine(pipeline=FailingPipeline())

        req = PatientAssessmentRequest(
            patient_id="PT-FAIL-E1",
            engine1_input=Engine1ScreeningInput(biomarkers=self.ckd_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=1.8, uacr=150.0, age=60.0, sex="M"),
        )
        res = failing_engine.assess_patient(req)

        self.assertIn("engine1", res.engines_executed)
        self.assertIn("engine2", res.engines_executed)
        self.assertEqual(res.engine1_result.status, EngineStatus.EXECUTION_ERROR.value)
        self.assertIn("Catastrophic", res.engine1_result.abstention_reason)

        # Engine 2 must succeed normally despite Engine 1 crash!
        self.assertIsNotNone(res.engine2_result)
        self.assertEqual(res.engine2_result.status, EngineStatus.AVAILABLE.value)
        self.assertEqual(res.engine2_result.gfr_category, "G3b")

    # -----------------------------------------------------------------------
    # Scenario 7: Engine-Specific Abstention
    # -----------------------------------------------------------------------
    def test_07_engine_specific_abstention(self):
        # Engine 1 abstains when critical biomarker (hemo) is omitted,
        # but Engine 2 has valid scr/uacr/age/sex and proceeds.
        incomplete_e1 = dict(self.ckd_biomarkers)
        incomplete_e1.pop("hemo")  # Critical biomarker missing

        req = PatientAssessmentRequest(
            patient_id="PT-ABSTAIN-E1",
            engine1_input=Engine1ScreeningInput(biomarkers=incomplete_e1),
            engine2_input=Engine2SeverityInput(serum_creatinine=2.0, uacr=120.0, age=60.0, sex="M"),
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.engine1_result.status, "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIn("hemo", res.engine1_result.missing_features)
        self.assertIsNone(res.engine1_result.diagnostic_class)

        # Engine 2 executes completely
        self.assertEqual(res.engine2_result.status, EngineStatus.AVAILABLE.value)
        self.assertEqual(res.engine2_result.gfr_category, "G3b")

    # -----------------------------------------------------------------------
    # Scenario 8: Missing Critical Measurements Gate
    # -----------------------------------------------------------------------
    def test_08_missing_critical_measurements_gate(self):
        # When all critical features (sc, al, hemo) are absent from Engine 1
        empty_req = PatientAssessmentRequest(
            patient_id="PT-CRIT-EMPTY",
            engine1_input=Engine1ScreeningInput(biomarkers={"age": 55, "bp": 80}),
        )
        res = self.engine.assess_patient(empty_req)
        self.assertEqual(res.engine1_result.status, "ABSTAIN_MISSING_CRITICAL_FEATURES")
        self.assertIn("sc", res.engine1_result.missing_features)
        self.assertIn("al", res.engine1_result.missing_features)
        self.assertIn("hemo", res.engine1_result.missing_features)

    # -----------------------------------------------------------------------
    # Scenario 9: Non-Standard Unit Handling
    # -----------------------------------------------------------------------
    def test_09_non_standard_units_handling(self):
        # SI units: 176.84 µmol/L scr (~2.0 mg/dL), 20 mg/mmol uACR (~176.8 mg/g)
        req = PatientAssessmentRequest(
            patient_id="PT-UNITS-SI",
            engine2_input=Engine2SeverityInput(
                serum_creatinine=176.84,
                serum_creatinine_unit="µmol/L",
                uacr=20.0,
                uacr_unit="mg/mmol",
                age=60.0,
                sex="M",
            ),
        )
        res = self.engine.assess_patient(req)

        self.assertIsNotNone(res.engine2_result)
        # Verify conversion occurred
        self.assertAlmostEqual(res.engine2_result.egfr, 37.0, delta=3.0)
        self.assertAlmostEqual(res.engine2_result.uacr, 176.8, delta=1.0)
        self.assertTrue(any("µmol/L to" in w for w in res.safety_warnings))

    # -----------------------------------------------------------------------
    # Scenario 10: No Silent Imputation
    # -----------------------------------------------------------------------
    def test_10_no_silent_imputation_preserves_missing_status(self):
        # Only sc, al, hemo provided to Engine 1; others omitted
        sparse_biomarkers = {"sc": 1.2, "al": 1.0, "hemo": 12.5}
        req = PatientAssessmentRequest(
            patient_id="PT-SPARSE",
            engine1_input=Engine1ScreeningInput(biomarkers=sparse_biomarkers),
        )
        res = self.engine.assess_patient(req)

        # Missing features must be explicitly recorded, not concealed
        self.assertIn("bgr", res.engine1_result.missing_features)
        self.assertIn("bu", res.engine1_result.missing_features)
        self.assertIn("pcv", res.engine1_result.missing_features)
        self.assertLess(res.engine1_result.data_completeness_ratio, 1.0)

    # -----------------------------------------------------------------------
    # Scenario 11: Conflicting Engine Outputs (False Assurance Risk)
    # -----------------------------------------------------------------------
    def test_11_conflicting_engine_outputs_false_assurance_risk(self):
        # Patient looks healthy on Engine 1 screening panel (e.g. normal blood counts),
        # but Engine 2 reveals severe isolated albuminuria (uACR 450 mg/g, A3) and eGFR 52 mL/min (G3a).
        misleading_healthy_biomarkers = {
            "age": 45.0, "bp": 75.0, "sg": 1.020, "al": 0.0, "su": 0.0,
            "bgr": 90.0, "bu": 20.0, "sc": 0.9, "hemo": 14.5, "pcv": 43.0,
            "rc": 5.0, "htn": "no", "dm": "no"
        }
        req = PatientAssessmentRequest(
            patient_id="PT-DISCORDANT",
            engine1_input=Engine1ScreeningInput(biomarkers=misleading_healthy_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=1.4, uacr=450.0, age=45.0, sex="female"),
        )
        res = self.engine.assess_patient(req)

        # Engine 1 says Healthy (Class 0)
        self.assertEqual(res.engine1_result.diagnostic_class, 0)
        # Engine 2 says G3a / A3
        self.assertEqual(res.engine2_result.gfr_category, "G3a")
        self.assertEqual(res.engine2_result.albuminuria_category, "A3")

        # Discrepancy detector MUST catch False Assurance Risk!
        critical_discs = [
            d for d in res.clinical_discrepancies
            if d["discrepancy_id"] == "DISC-02-FALSE-ASSURANCE-RISK"
        ]
        self.assertEqual(len(critical_discs), 1)
        self.assertEqual(critical_discs[0]["severity"], FindingSeverity.CRITICAL.value)
        self.assertIn("DO NOT rely on the negative binary screening prediction", critical_discs[0]["clinical_action"])

    # -----------------------------------------------------------------------
    # Scenario 12: Cross-Sectional vs Longitudinal Separation
    # -----------------------------------------------------------------------
    def test_12_cross_sectional_vs_longitudinal_separation(self):
        req = PatientAssessmentRequest(
            patient_id="PT-CROSS-SECTIONAL",
            engine2_input=Engine2SeverityInput(serum_creatinine=1.8, uacr=150.0, age=65.0, sex="M"),
            engine3_input=Engine3ProgressionInput(longitudinal_record=None),
        )
        res = self.engine.assess_patient(req)

        # Engine 2 must assert chronicity is unconfirmed
        self.assertFalse(res.engine2_result.chronicity_confirmed)
        self.assertIn("single-timepoint", res.engine2_result.disclaimer.lower())

        # Discrepancy logged regarding chronicity persistence
        chron_disc = [
            d for d in res.clinical_discrepancies
            if d["discrepancy_id"] == "DISC-03-CROSS-SECTIONAL-CHRONICITY-UNVERIFIED"
        ]
        self.assertEqual(len(chron_disc), 1)

    # -----------------------------------------------------------------------
    # Scenario 13: KFRE Applicability Range Warning
    # -----------------------------------------------------------------------
    def test_13_kfre_applicability_range_warning(self):
        # KFRE evaluated on normal eGFR (75 mL/min > 60) -> Out of target scope!
        # When out of scope, risk probability is withheld to prevent misleading prognostication.
        k_in = KFREInput(age=55.0, sex="female", egfr=75.0, uacr=15.0)
        req = PatientAssessmentRequest(
            patient_id="PT-KFRE-OUT-OF-BOUNDS",
            engine3_input=Engine3ProgressionInput(kfre_input=k_in),
        )
        res = self.engine.assess_patient(req)

        self.assertIsNone(res.engine3_result.kfre_2year_risk)
        self.assertFalse(res.engine3_result.kfre_is_applicable)
        self.assertTrue(any("KFRE Applicability" in w for w in res.safety_warnings))

    # -----------------------------------------------------------------------
    # Scenario 14: Untrained Survival Model Blocking
    # -----------------------------------------------------------------------
    def test_14_untrained_survival_model_blocking(self):
        req = PatientAssessmentRequest(
            patient_id="PT-SURV-BLOCK",
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
        )
        res = self.engine.assess_patient(req)

        # Survival model inference must be deferred / unfitted
        self.assertIn("DEFERRED", res.engine3_result.survival_status)
        self.assertEqual(
            res.engine3_result.survival_predictions.get("models_evaluated", {}).get("cox_ph", {}).get("status"),
            "UNFITTED_PENDING_APPROVED_LONGITUDINAL_COHORT",
        )

    # -----------------------------------------------------------------------
    # Scenario 15: Patient Identifier and Provenance Preservation
    # -----------------------------------------------------------------------
    def test_15_provenance_and_id_preservation(self):
        req = PatientAssessmentRequest(
            patient_id="PT-CLINICAL-HIST-992",
            engine1_input=Engine1ScreeningInput(biomarkers=self.healthy_biomarkers, provenance=ProvenanceSource.UCI_CKD_SCREENING.value),
            engine2_input=Engine2SeverityInput(serum_creatinine=0.9, uacr=10.0, age=40.0, sex="F", provenance=ProvenanceSource.NHANES_CROSS_SECTIONAL.value),
            provenance=ProvenanceSource.CLINICAL_EHR.value,
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.patient_id, "PT-CLINICAL-HIST-992")
        self.assertEqual(res.provenance["source"], ProvenanceSource.CLINICAL_EHR.value)
        self.assertEqual(res.engine1_result.provenance, ProvenanceSource.UCI_CKD_SCREENING.value)
        self.assertEqual(res.engine2_result.provenance, ProvenanceSource.NHANES_CROSS_SECTIONAL.value)

    # -----------------------------------------------------------------------
    # Scenario 16: No Temporal Leakage into Engine 3
    # -----------------------------------------------------------------------
    def test_16_no_temporal_leakage_landmark_filtering(self):
        landmark = self.base_time - timedelta(days=100)
        # Visit 3 is at base_time (> landmark) and should be excluded by Engine 3
        req = PatientAssessmentRequest(
            patient_id="PT-LANDMARK",
            engine3_input=Engine3ProgressionInput(
                longitudinal_record=self.standard_record,
                landmark_time=landmark,
            ),
        )
        res = self.engine.assess_patient(req)

        # When evaluated with landmark filtering, only visits 1 & 2 are used
        self.assertIsNotNone(res.engine3_result)
        # Should execute without throwing temporal error
        self.assertEqual(res.engine3_result.status, EngineStatus.AVAILABLE.value)

    # -----------------------------------------------------------------------
    # Scenario 17: Same-Day Measurement Consistency
    # -----------------------------------------------------------------------
    def test_17_same_day_measurement_consistency(self):
        # A. Same day (difference 0)
        req_same = PatientAssessmentRequest(
            patient_id="PT-SAME-DAY",
            engine2_input=Engine2SeverityInput(
                serum_creatinine=1.4,
                uacr=50.0,
                age=50.0,
                sex="male",
                observation_date_scr=datetime(2023, 5, 1, 9, 0),
                observation_date_uacr=datetime(2023, 5, 1, 11, 0),
            ),
        )
        res_same = self.engine.assess_patient(req_same)
        self.assertTrue(res_same.engine2_result.same_day_measurement)

        # B. Different dates (>30 days apart)
        req_diff = PatientAssessmentRequest(
            patient_id="PT-DIFF-DAY",
            engine2_input=Engine2SeverityInput(
                serum_creatinine=1.4,
                uacr=50.0,
                age=50.0,
                sex="male",
                observation_date_scr=datetime(2023, 1, 1),
                observation_date_uacr=datetime(2023, 4, 1),
            ),
        )
        res_diff = self.engine.assess_patient(req_diff)
        self.assertFalse(res_diff.engine2_result.same_day_measurement)
        self.assertTrue(any("Temporal Discrepancy" in w for w in res_diff.safety_warnings))

    # -----------------------------------------------------------------------
    # Scenario 18: Reproducibility of Unified Response
    # -----------------------------------------------------------------------
    def test_18_reproducibility_of_response(self):
        req = PatientAssessmentRequest(
            patient_id="PT-REPRO",
            demographics=Demographics(age=60.0, sex="male"),
            engine1_input=Engine1ScreeningInput(biomarkers=self.ckd_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=1.8, uacr=120.0, age=60.0, sex="male"),
        )
        res1 = self.engine.assess_patient(req)
        res2 = self.engine.assess_patient(req)

        self.assertEqual(res1.engine1_result.risk_probability, res2.engine1_result.risk_probability)
        self.assertEqual(res1.engine2_result.egfr, res2.engine2_result.egfr)
        self.assertEqual(res1.engine2_result.cga_string, res2.engine2_result.cga_string)
        self.assertEqual(len(res1.clinical_discrepancies), len(res2.clinical_discrepancies))

    # -----------------------------------------------------------------------
    # Scenario 19: Engine Independence (No Forced Positivity)
    # -----------------------------------------------------------------------
    def test_19_engine_independence_no_forced_positivity(self):
        # Engine 1 screening is negative (Healthy), but Engine 2 and 3 operate completely independently
        req = PatientAssessmentRequest(
            patient_id="PT-INDEPENDENT",
            engine1_input=Engine1ScreeningInput(biomarkers=self.healthy_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=0.8, uacr=8.0, age=42.0, sex="male"),
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.engine1_result.diagnostic_class, 0)
        self.assertEqual(res.engine2_result.status, EngineStatus.AVAILABLE.value)
        self.assertEqual(res.engine3_result.status, EngineStatus.AVAILABLE.value)

    # -----------------------------------------------------------------------
    # Scenario 20: Complete Assessment Serialization
    # -----------------------------------------------------------------------
    def test_20_complete_assessment_serialization_and_json(self):
        req = PatientAssessmentRequest(
            patient_id="PT-SERIALIZE",
            demographics=Demographics(age=65.0, sex="female"),
            engine1_input=Engine1ScreeningInput(biomarkers=self.ckd_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=2.2, uacr=210.0, age=65.0, sex="female"),
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
        )
        res = self.engine.assess_patient(req)

        # Test to_dict()
        res_dict = res.to_dict()
        self.assertIsInstance(res_dict, dict)
        self.assertIn("assessment_id", res_dict)
        self.assertIn("engine1_result", res_dict)
        self.assertIn("engine2_result", res_dict)
        self.assertIn("engine3_result", res_dict)
        self.assertIn("summary_findings", res_dict)
        self.assertIn("clinical_discrepancies", res_dict)
        self.assertIn("safety_warnings", res_dict)

        # Test to_json()
        json_str = res.to_json(indent=2)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["patient_id"], "PT-SERIALIZE")
        self.assertEqual(len(parsed["engines_executed"]), 3)

    # -----------------------------------------------------------------------
    # Scenario 21: Flat Dictionary Input Normalization
    # -----------------------------------------------------------------------
    def test_21_flat_dictionary_input_normalization(self):
        flat_dict = {
            "patient_id": "PT-FLAT-01",
            "age": 58.0,
            "sex": "female",
            "sc": 1.4,
            "uacr": 65.0,
            "hemo": 12.0,
            "al": 1.0,
            "sg": 1.018,
            "bgr": 115.0,
            "bu": 38.0,
            "pcv": 36.0,
            "rc": 4.1,
            "htn": "yes",
            "dm": "no",
        }
        res = self.engine.assess_patient(flat_dict)

        self.assertIsInstance(res, UnifiedAssessmentResponse)
        self.assertEqual(res.patient_id, "PT-FLAT-01")
        # Should auto-execute Engine 1 and Engine 2 from flat keys
        self.assertIn("engine1", res.engines_executed)
        self.assertIn("engine2", res.engines_executed)
        self.assertEqual(res.engine2_result.gfr_category, "G3b")

    # -----------------------------------------------------------------------
    # Scenario 22: Explicit requested_engines Filtering
    # -----------------------------------------------------------------------
    def test_22_explicit_requested_engines_filtering(self):
        # Pass all inputs, but explicitly request only Engine 2
        req = PatientAssessmentRequest(
            patient_id="PT-FILTER-E2",
            engine1_input=Engine1ScreeningInput(biomarkers=self.ckd_biomarkers),
            engine2_input=Engine2SeverityInput(serum_creatinine=1.7, uacr=90.0, age=55.0, sex="M"),
            engine3_input=Engine3ProgressionInput(longitudinal_record=self.standard_record),
            requested_engines=["engine2"],
        )
        res = self.engine.assess_patient(req)

        self.assertEqual(res.engines_executed, ["engine2"])
        self.assertIn("engine1", res.engines_skipped)
        self.assertIn("engine3", res.engines_skipped)
        self.assertIsNone(res.engine1_result)
        self.assertIsNotNone(res.engine2_result)
        self.assertIsNone(res.engine3_result)

    # -----------------------------------------------------------------------
    # Scenario 23: Clinical History Conflict Detection
    # -----------------------------------------------------------------------
    def test_23_clinical_history_conflict_detection(self):
        # Patient history says htn="no", but measured systolic blood pressure is 155 mmHg
        conflict_biomarkers = dict(self.healthy_biomarkers)
        conflict_biomarkers["htn"] = "no"
        conflict_biomarkers["bp"] = 155.0  # Elevated SBP >= 140

        req = PatientAssessmentRequest(
            patient_id="PT-HTN-CONFLICT",
            engine1_input=Engine1ScreeningInput(biomarkers=conflict_biomarkers),
        )
        res = self.engine.assess_patient(req)

        htn_disc = [
            d for d in res.clinical_discrepancies
            if d["discrepancy_id"] == "DISC-07-HYPERTENSION-HISTORY-CONFLICT"
        ]
        self.assertEqual(len(htn_disc), 1)
        self.assertIn("155.0 mmHg", htn_disc[0]["description"])


if __name__ == "__main__":
    unittest.main()
