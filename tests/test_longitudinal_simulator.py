"""Unit test suite for NEFROAI-X synthetic longitudinal patient simulator.

Verifies:
- Deterministic reproducibility with a fixed random seed
- Explicit synthetic provenance and disclaimer tags
- Generation of clinically plausible irregular visit intervals
- Generation of stable, declining, and variable trajectory presets
- Generation of edge cases for abstention testing (single visit, short follow-up,
  non-monotonic timestamps, duplicate timestamps, missing laboratory data)
- Full compatibility with the time-aware feature extraction engine
"""

import unittest
from datetime import datetime, timezone

from src.clinical.progression_features import extract_progression_features
from src.data_sources.longitudinal_simulator import (
    SYNTHETIC_PROVENANCE_TAG,
    LongitudinalDataSimulator,
)


class TestLongitudinalSimulator(unittest.TestCase):
    """Test suite for synthetic patient record simulator."""

    def setUp(self):
        self.sim = LongitudinalDataSimulator(random_seed=42)

    # -----------------------------------------------------------------------
    # 17: Simulator Reproducibility with Fixed Seed
    # -----------------------------------------------------------------------
    def test_simulator_reproducibility_with_fixed_seed(self):
        """Test item 17: Exact reproducibility when instantiated with identical random seed."""
        sim1 = LongitudinalDataSimulator(random_seed=12345)
        sim2 = LongitudinalDataSimulator(random_seed=12345)

        rec1 = sim1.generate_patient_record("PT_REP", trajectory_type="declining", num_visits=5)
        rec2 = sim2.generate_patient_record("PT_REP", trajectory_type="declining", num_visits=5)

        self.assertEqual(rec1.age_baseline, rec2.age_baseline)
        self.assertEqual(rec1.sex, rec2.sex)
        self.assertEqual(len(rec1.observations), len(rec2.observations))

        for obs1, obs2 in zip(rec1.observations, rec2.observations):
            self.assertEqual(obs1.timestamp, obs2.timestamp)
            self.assertEqual(obs1.egfr, obs2.egfr)
            self.assertEqual(obs1.serum_creatinine, obs2.serum_creatinine)
            self.assertEqual(obs1.uacr, obs2.uacr)
            self.assertEqual(obs1.systolic_bp, obs2.systolic_bp)

    # -----------------------------------------------------------------------
    # 18: Synthetic Provenance Identification
    # -----------------------------------------------------------------------
    def test_synthetic_provenance_identification(self):
        """Test item 18: Explicit synthetic provenance tags and non-clinical status."""
        rec = self.sim.generate_patient_record("PT_PROV_01", trajectory_type="stable")
        self.assertTrue(rec.is_synthetic)
        self.assertEqual(rec.provenance, SYNTHETIC_PROVENANCE_TAG)

        # Confirm when features are extracted, synthetic status is preserved
        res = extract_progression_features(rec)
        self.assertTrue(res.is_eligible)
        self.assertTrue(res.features.is_synthetic)
        self.assertEqual(res.features.provenance, SYNTHETIC_PROVENANCE_TAG)

    # -----------------------------------------------------------------------
    # 19: Irregular Visit Interval Generation
    # -----------------------------------------------------------------------
    def test_irregular_visit_interval_generation(self):
        """Test item 19: Generated visit intervals have realistic irregular spacing."""
        rec = self.sim.generate_patient_record(
            "PT_IRREG", trajectory_type="stable", num_visits=6, total_followup_years=3.0
        )
        timestamps = [obs.timestamp for obs in rec.observations]
        intervals = [
            (timestamps[i + 1] - timestamps[i]).total_seconds() / 86400.0
            for i in range(len(timestamps) - 1)
        ]

        # Ensure all intervals are positive and strictly monotonic
        for interval in intervals:
            self.assertTrue(interval >= 14.0)

        # Confirm intervals are not all identical (variance > 0 proves irregular jitter)
        self.assertTrue(len(set([round(inv, 1) for inv in intervals])) > 1)

    # -----------------------------------------------------------------------
    # Trajectory Types: Stable, Declining, Variable
    # -----------------------------------------------------------------------
    def test_stable_trajectory_preset(self):
        """Test stable trajectory produces mild negative slope and low CV."""
        rec = self.sim.generate_patient_record(
            "PT_STABLE", trajectory_type="stable", num_visits=6, total_followup_years=3.0
        )
        res = extract_progression_features(rec)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertIsNotNone(f.egfr_historical_slope)
        # Stable slope should be modest (~ -0.2 to -2.0)
        self.assertTrue(-2.5 <= f.egfr_historical_slope <= 0.5)

    def test_declining_trajectory_preset(self):
        """Test rapid progressor trajectory produces steep negative slope."""
        rec = self.sim.generate_patient_record(
            "PT_DECLINE", trajectory_type="declining", num_visits=6, total_followup_years=3.0
        )
        res = extract_progression_features(rec)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertIsNotNone(f.egfr_historical_slope)
        # Declining slope should be accelerated (<= -3.0 mL/min/yr)
        self.assertTrue(f.egfr_historical_slope <= -3.0)

    def test_variable_trajectory_preset(self):
        """Test variable trajectory exhibits high eGFR coefficient of variation."""
        rec = self.sim.generate_patient_record(
            "PT_VAR", trajectory_type="variable", num_visits=6, total_followup_years=3.0
        )
        res = extract_progression_features(rec)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertIsNotNone(f.egfr_variability_cv)
        # High variability CV
        self.assertTrue(f.egfr_variability_cv > 0.05)

    # -----------------------------------------------------------------------
    # Edge Cases & Abstention Scenarios
    # -----------------------------------------------------------------------
    def test_edge_case_single_observation(self):
        """Test simulator single_observation edge case triggers abstention."""
        rec = self.sim.generate_edge_case("single_observation")
        res = extract_progression_features(rec)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.abstention.reason_code, "INSUFFICIENT_OBSERVATION_COUNT")

    def test_edge_case_short_followup(self):
        """Test simulator short_followup edge case triggers abstention."""
        rec = self.sim.generate_edge_case("short_followup")
        res = extract_progression_features(rec)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.abstention.reason_code, "INSUFFICIENT_FOLLOWUP_DURATION")

    def test_edge_case_non_monotonic_timestamps(self):
        """Test simulator non_monotonic edge case triggers abstention."""
        rec = self.sim.generate_edge_case("non_monotonic")
        res = extract_progression_features(rec)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.abstention.reason_code, "NON_MONOTONIC_TIMESTAMPS")

    def test_edge_case_duplicate_timestamps(self):
        """Test simulator duplicate_timestamps edge case triggers abstention."""
        rec = self.sim.generate_edge_case("duplicate_timestamps")
        res = extract_progression_features(rec)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.abstention.reason_code, "NON_MONOTONIC_TIMESTAMPS")

    def test_edge_case_zero_uacr_baseline(self):
        """Test simulator zero_uacr_baseline does not cause division by zero."""
        rec = self.sim.generate_edge_case("zero_uacr_baseline")
        res = extract_progression_features(rec)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertIsNone(f.uacr_progression_ratio)

    def test_edge_case_insufficient_for_slope(self):
        """Test simulator insufficient_for_slope allows basic features but leaves slope as None."""
        rec = self.sim.generate_edge_case("insufficient_for_slope")
        res = extract_progression_features(rec)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertEqual(f.obs_count, 2)
        self.assertIsNone(f.egfr_historical_slope)
        self.assertIn("INSUFFICIENT_OBSERVATION_COUNT_FOR_SLOPE", f.egfr_slope_status)

    # -----------------------------------------------------------------------
    # Cohort Generation
    # -----------------------------------------------------------------------
    def test_cohort_generation(self):
        """Test generation of a multi-patient synthetic cohort."""
        cohort = self.sim.generate_cohort(num_patients=10, random_seed=999)
        self.assertEqual(len(cohort), 10)
        for pt in cohort:
            self.assertTrue(pt.is_synthetic)
            self.assertEqual(pt.provenance, SYNTHETIC_PROVENANCE_TAG)
            self.assertTrue(len(pt.observations) >= 3)


if __name__ == "__main__":
    unittest.main()
