"""Unit test suite for the KidneyProgressionEngine orchestrator (Engine 3 Prototype).

Verifies:
- Independent operation and coordination between longitudinal features and KFRE
- Preservation of landmark timestamps and evaluation cut-offs
- Future observation exclusion and zero temporal leakage
- Correct handling of longitudinal abstention while preserving KFRE risk
- Correct handling of missing KFRE inputs without fabricating predictions
- Exact numerical agreement between engine KFRE and standalone calculator
- Provenance and synthetic flag preservation
"""

import unittest
from datetime import datetime, timedelta, timezone

from src.clinical.kfre_calculator import KFREInput, calculate_kfre
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
)
from src.data_sources.longitudinal_simulator import (
    SYNTHETIC_PROVENANCE_TAG,
    LongitudinalDataSimulator,
)
from src.engines.kidney_progression_engine import (
    ENGINE_3_DISCLAIMER,
    KidneyProgressionEngine,
    ProgressionEngineResult,
)


class TestKidneyProgressionEngine(unittest.TestCase):
    """Test suite for KidneyProgressionEngine orchestrator."""

    def setUp(self):
        self.engine = KidneyProgressionEngine()
        self.sim = LongitudinalDataSimulator(random_seed=42)

        self.t0 = datetime(2021, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        self.t1 = self.t0 + timedelta(days=180)
        self.t2 = self.t0 + timedelta(days=365)
        self.t3 = self.t0 + timedelta(days=540)
        self.t4 = self.t0 + timedelta(days=730)

        # 5-visit patient with progressive decline
        self.record_longitudinal = LongitudinalPatientRecord(
            patient_id="PT_ENG3_001",
            age_baseline=62.0,
            sex="male",
            diabetes_history=True,
            hypertension_history=True,
            observations=[
                ClinicalObservation(timestamp=self.t0, egfr=52.0, uacr=120.0),
                ClinicalObservation(timestamp=self.t1, egfr=48.0, uacr=150.0),
                ClinicalObservation(timestamp=self.t2, egfr=44.0, uacr=180.0),
                ClinicalObservation(timestamp=self.t3, egfr=40.0, uacr=210.0),
                ClinicalObservation(timestamp=self.t4, egfr=36.0, uacr=250.0),
            ],
            is_synthetic=True,
            provenance="SYNTHETIC_TEST_FIXTURE_NEFROAI_X",
        )

        # Explicit index KFRE inputs
        self.index_kfre = KFREInput(
            age=64.0,
            sex="male",
            egfr=36.0,
            uacr=250.0,
            calibration_profile="north_america",
        )

    # -----------------------------------------------------------------------
    # 1. Independent Calculator & Engine Agreement
    # -----------------------------------------------------------------------
    def test_engine_kfre_matches_standalone_calculator(self):
        """Test item 1 & 7: Engine produces exact same numerical KFRE results as standalone calculator."""
        standalone_res = calculate_kfre(self.index_kfre)
        engine_res = self.engine.assess_progression(kfre_input=self.index_kfre)

        self.assertIsNotNone(engine_res.kfre_result)
        kfre_e = engine_res.kfre_result

        self.assertEqual(kfre_e.risk_2year, standalone_res.risk_2year)
        self.assertEqual(kfre_e.risk_5year, standalone_res.risk_5year)
        self.assertEqual(kfre_e.linear_predictor, standalone_res.linear_predictor)
        self.assertEqual(kfre_e.calibration_profile, standalone_res.calibration_profile)

    # -----------------------------------------------------------------------
    # 2. Engine Calls Feature Extractor & Derives Slopes
    # -----------------------------------------------------------------------
    def test_engine_calls_step2_feature_extractor_correctly(self):
        """Test item 2: Engine successfully runs longitudinal feature extractor and derives historical slope."""
        res = self.engine.assess_progression(record=self.record_longitudinal, kfre_input=self.index_kfre)

        self.assertEqual(res.patient_id, "PT_ENG3_001")
        self.assertIsNotNone(res.longitudinal_result)
        self.assertTrue(res.longitudinal_result.is_eligible)

        # 5 observations spanning 730 days: historical slope must be computed
        self.assertIsNotNone(res.historical_egfr_slope)
        # eGFR drops from 52 to 36 over 2 years -> slope ~ -8.0 mL/min/yr
        self.assertAlmostEqual(res.historical_egfr_slope, -8.0, delta=0.5)
        self.assertEqual(res.slope_status, "CALCULATED_OLS_ANNUAL_SLOPE")

    # -----------------------------------------------------------------------
    # 3 & 4. Landmarking & Zero Temporal Leakage
    # -----------------------------------------------------------------------
    def test_engine_preserves_landmark_and_excludes_future_data(self):
        """Test items 3 & 4: Landmark timestamp is preserved and future observations are excluded."""
        # Evaluate at Day 365 (t2)
        res_t2 = self.engine.assess_progression(
            record=self.record_longitudinal,
            landmark_time=self.t2,
            kfre_input=self.index_kfre,
        )

        self.assertEqual(res_t2.landmark_time, self.t2)
        long_features = res_t2.longitudinal_result.features
        self.assertEqual(long_features.obs_count, 3)
        self.assertEqual(long_features.last_observation_time, self.t2)
        self.assertEqual(long_features.egfr_landmark, 44.0)

    # -----------------------------------------------------------------------
    # 5 & 6. Separation of Longitudinal Abstention from KFRE Evaluation
    # -----------------------------------------------------------------------
    def test_longitudinal_abstention_does_not_suppress_valid_kfre(self):
        """Test items 5 & 6: When longitudinal feature extractor abstains, valid KFRE is still computed and returned."""
        # Single-observation record (triggers K < 2 abstention)
        rec_single = self.sim.generate_edge_case("single_observation", patient_id="PT_ABSTAIN_KFRE_VALID")

        res = self.engine.assess_progression(
            record=rec_single,
            kfre_input=self.index_kfre,
        )

        # Longitudinal component abstains
        self.assertFalse(res.longitudinal_result.is_eligible)
        self.assertIsNotNone(res.longitudinal_abstention_explanation)
        self.assertIn("INSUFFICIENT_OBSERVATION_COUNT", res.longitudinal_abstention_explanation)
        self.assertIsNone(res.historical_egfr_slope)

        # KFRE component is completely valid and preserved!
        self.assertIsNotNone(res.kfre_result)
        self.assertTrue(res.kfre_result.is_valid)
        self.assertTrue(res.kfre_result.is_applicable)
        self.assertIsNotNone(res.kfre_result.risk_2year)
        self.assertIsNotNone(res.kfre_result.risk_5year)

    # -----------------------------------------------------------------------
    # 8. Missing KFRE Inputs Do Not Fabricate Predictions
    # -----------------------------------------------------------------------
    def test_missing_kfre_inputs_do_not_fabricate_predictions(self):
        """Test item 8: When no KFRE input is supplied, KFRE is None with an explicit explanation."""
        res = self.engine.assess_progression(record=self.record_longitudinal, kfre_input=None)

        self.assertIsNone(res.kfre_result)
        self.assertIsNotNone(res.kfre_applicability_explanation)
        self.assertIn("No explicit index KFRE measurements were provided", res.kfre_applicability_explanation)

        # Longitudinal features remain valid
        self.assertTrue(res.longitudinal_result.is_eligible)
        self.assertIsNotNone(res.historical_egfr_slope)

    # -----------------------------------------------------------------------
    # 9. Provenance and Governance Preservation
    # -----------------------------------------------------------------------
    def test_engine_preserves_provenance_and_governance(self):
        """Test item 9: Output preserves source provenance, synthetic flag, and governance disclaimer."""
        res = self.engine.assess_progression(record=self.record_longitudinal, kfre_input=self.index_kfre)

        self.assertTrue(res.is_synthetic)
        self.assertEqual(res.provenance, SYNTHETIC_PROVENANCE_TAG)
        self.assertEqual(res.engine_name, self.engine.name)
        self.assertEqual(res.engine_version, self.engine.version)
        self.assertIn("DISCLAIMER", res.clinical_governance["disclaimer"])

        # Serialization check
        d = res.to_dict()
        self.assertEqual(d["patient_id"], "PT_ENG3_001")
        self.assertIn("longitudinal", d)
        self.assertIn("kfre", d)
        self.assertIn("lmm_trajectory", d)
        self.assertIn("clinical_reliability", d)
        self.assertIn("progression_explanations", d)

    # -----------------------------------------------------------------------
    # 10. Population LMM Trajectory Integration
    # -----------------------------------------------------------------------
    def test_engine_incorporates_lmm_trajectory(self):
        """Test item 10: Engine evaluates Linear Mixed-Effects Model for eligible longitudinal records."""
        res = self.engine.assess_progression(record=self.record_longitudinal, kfre_input=self.index_kfre)

        self.assertIsNotNone(res.lmm_trajectory)
        lmm = res.lmm_trajectory
        self.assertTrue(lmm.is_eligible)
        self.assertEqual(lmm.obs_count, 5)
        self.assertEqual(lmm.status, "ESTIMATED_EMPIRICAL_BAYES_RANDOM_SLOPE")
        self.assertLess(lmm.patient_slope, 0.0)
        self.assertTrue(lmm.slope_ci_lower <= lmm.patient_slope <= lmm.slope_ci_upper)

    # -----------------------------------------------------------------------
    # 11. Clinical Input Reliability & Abstention Integration
    # -----------------------------------------------------------------------
    def test_engine_clinical_reliability_and_abstention(self):
        """Test item 11: CD-CIRPVM integration computes CRI and provides reliability audit."""
        res = self.engine.assess_progression(record=self.record_longitudinal, kfre_input=self.index_kfre)

        self.assertIn("cri_score", res.clinical_reliability)
        self.assertTrue(0.0 <= res.clinical_reliability["cri_score"] <= 1.0)
        self.assertEqual(res.clinical_reliability["status"], "VALID")
        self.assertIn("units_reconciled", res.clinical_reliability)

    # -----------------------------------------------------------------------
    # 12. Competing-Risk & Personalized CIF Integration
    # -----------------------------------------------------------------------
    def test_engine_competing_risk_and_personalized_cif(self):
        """Test item 12: Engine evaluates personalized CIF and population benchmark."""
        from datetime import date
        from src.clinical.survival.competing_risk import CauseSpecificCumulativeIncidenceModel
        from src.clinical.survival.survival_contracts import (
            SurvivalDataset,
            SurvivalEventType,
            SurvivalLandmarkRecord,
        )

        # Create a small benchmark dataset
        records = []
        base_d = date(2020, 1, 1)
        lm_d = date(2021, 1, 1)
        for i in range(20):
            ev = SurvivalEventType.KIDNEY_FAILURE if i < 6 else (SurvivalEventType.COMPETING_DEATH if i < 10 else SurvivalEventType.RIGHT_CENSORED)
            records.append(
                SurvivalLandmarkRecord(
                    patient_id=f"PAT_{i:02d}",
                    landmark_date=lm_d,
                    baseline_date=base_d,
                    follow_up_start_date=lm_d,
                    follow_up_end_date=date(2022, 6, 1),
                    event_type=ev,
                    event_kidney_failure=1 if ev == SurvivalEventType.KIDNEY_FAILURE else 0,
                    event_death=1 if ev == SurvivalEventType.COMPETING_DEATH else 0,
                    is_censored=1 if ev == SurvivalEventType.RIGHT_CENSORED else 0,
                    features={"age": 55.0 + i, "egfr": 30.0 + (i % 15), "uacr": 30.0 + ((i * 37) % 300)},
                )
            )
        cohort_ds = SurvivalDataset(records)

        # Fit CIF model
        cif_mod = CauseSpecificCumulativeIncidenceModel(feature_names=["age", "egfr", "uacr"])
        cif_mod.fit(cohort_ds)

        engine_with_cif = KidneyProgressionEngine(cif_model=cif_mod)
        res = engine_with_cif.assess_progression(
            record=self.record_longitudinal,
            kfre_input=self.index_kfre,
            cohort_dataset=cohort_ds,
        )

        cr = res.competing_risk_profile
        self.assertIsNotNone(cr["personalized_cif"])
        self.assertIn("cif_kidney_failure_2year", cr["personalized_cif"])
        self.assertIsNotNone(cr["population_benchmark_cif"])
        self.assertIn("cif_kf_2year", cr["population_benchmark_cif"])

    # -----------------------------------------------------------------------
    # 13. Clinical Explainability & Contributor Factors
    # -----------------------------------------------------------------------
    def test_engine_explainability_and_contributing_factors(self):
        """Test item 13: Engine identifies risk trajectory categories and contributing biomarkers."""
        res = self.engine.assess_progression(record=self.record_longitudinal, kfre_input=self.index_kfre)

        expl = res.progression_explanations
        self.assertEqual(expl["trajectory_category"], "RAPID_PROGRESSOR")
        self.assertTrue(len(expl["contributor_factors"]) >= 2)
        factor_names = [f["factor"] for f in expl["contributor_factors"]]
        self.assertIn("Baseline eGFR", factor_names)
        self.assertIn("Filtration Trajectory Slope", factor_names)


if __name__ == "__main__":
    unittest.main()
