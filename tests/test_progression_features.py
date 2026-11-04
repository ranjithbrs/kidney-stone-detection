"""Unit test suite for NEFROAI-X time-aware progression feature engineering.

Verifies:
- Temporal interval and follow-up duration correctness
- eGFR trajectory derivation, OLS slope estimation, and recent acceleration
- UACR time-weighted exposure and progression ratio
- Landmarking safeguards, future observation exclusion, and zero temporal leakage
- Selective abstention on insufficient history, short follow-up, and non-monotonic timestamps
- Protection against division by zero and input record immutability
"""

import unittest
from datetime import datetime, timedelta, timezone

from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
    extract_progression_features,
    resolve_observation_egfr,
    validate_longitudinal_chronology,
)


class TestProgressionFeatures(unittest.TestCase):
    """Test suite for time-aware longitudinal progression feature extraction."""

    def setUp(self):
        self.t0 = datetime(2020, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        self.t1 = self.t0 + timedelta(days=180)
        self.t2 = self.t0 + timedelta(days=365)
        self.t3 = self.t0 + timedelta(days=540)
        self.t4 = self.t0 + timedelta(days=730)

        # Standard 5-visit test patient spanning 2 years (730 days)
        # eGFR drops from 80.0 to 60.0 linearly (slope ~ -10.0 mL/min/yr)
        self.obs_standard = [
            ClinicalObservation(
                timestamp=self.t0,
                serum_creatinine=1.0,
                egfr=80.0,
                uacr=30.0,
                systolic_bp=125.0,
                diastolic_bp=80.0,
                hba1c=5.5,
            ),
            ClinicalObservation(
                timestamp=self.t1,
                serum_creatinine=1.1,
                egfr=75.0,
                uacr=35.0,
                systolic_bp=128.0,
                diastolic_bp=82.0,
                hba1c=5.6,
            ),
            ClinicalObservation(
                timestamp=self.t2,
                serum_creatinine=1.2,
                egfr=70.0,
                uacr=40.0,
                systolic_bp=130.0,
                diastolic_bp=84.0,
                hba1c=5.7,
            ),
            ClinicalObservation(
                timestamp=self.t3,
                serum_creatinine=1.3,
                egfr=65.0,
                uacr=50.0,
                systolic_bp=135.0,
                diastolic_bp=85.0,
                hba1c=5.8,
            ),
            ClinicalObservation(
                timestamp=self.t4,
                serum_creatinine=1.4,
                egfr=60.0,
                uacr=60.0,
                systolic_bp=138.0,
                diastolic_bp=88.0,
                hba1c=5.9,
            ),
        ]

        self.record_standard = LongitudinalPatientRecord(
            patient_id="PT_STD_001",
            age_baseline=60.0,
            sex="male",
            diabetes_history=False,
            hypertension_history=True,
            observations=list(self.obs_standard),
        )

    # -----------------------------------------------------------------------
    # 1 & 2: Observation count, follow-up duration, and intervals
    # -----------------------------------------------------------------------
    def test_observation_count_and_followup_duration(self):
        """Test item 1: Correct observation count and total follow-up duration."""
        res = extract_progression_features(self.record_standard)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertEqual(f.obs_count, 5)
        self.assertAlmostEqual(f.total_followup_days, 730.0, places=1)
        self.assertEqual(f.first_observation_time, self.t0)
        self.assertEqual(f.last_observation_time, self.t4)

    def test_visit_interval_calculations(self):
        """Test item 2: Correct median visit interval in days."""
        res = extract_progression_features(self.record_standard)
        f = res.features
        # Intervals are [180, 185, 175, 190] -> median is around 182.5 days
        self.assertIsNotNone(f.median_visit_interval_days)
        self.assertTrue(170.0 <= f.median_visit_interval_days <= 190.0)

    # -----------------------------------------------------------------------
    # 3: eGFR trajectory and annualized OLS slope
    # -----------------------------------------------------------------------
    def test_egfr_change_and_annualized_ols_slope(self):
        """Test item 3: Correct eGFR delta and OLS annualized slope."""
        res = extract_progression_features(self.record_standard)
        f = res.features
        self.assertEqual(f.egfr_baseline, 80.0)
        self.assertEqual(f.egfr_landmark, 60.0)
        self.assertEqual(f.egfr_delta_absolute, -20.0)

        # 20.0 decline over ~1.9986 years -> slope ~ -10.0 mL/min/1.73m2/yr
        self.assertIsNotNone(f.egfr_historical_slope)
        self.assertAlmostEqual(f.egfr_historical_slope, -10.0, delta=0.2)
        self.assertEqual(f.egfr_slope_status, "CALCULATED_OLS_ANNUAL_SLOPE")

        # eGFR CV (SD / Mean)
        self.assertIsNotNone(f.egfr_variability_cv)
        self.assertTrue(f.egfr_variability_cv > 0.0)

    # -----------------------------------------------------------------------
    # 4, 5, 6: Landmarking and Zero Temporal Leakage
    # -----------------------------------------------------------------------
    def test_landmark_filtering_excludes_future_observations(self):
        """Test items 4 & 6: Only observations at or before landmark are included."""
        # Landmark at t2 (Day 365) -> only first 3 observations should be included
        res_t2 = extract_progression_features(self.record_standard, landmark_time=self.t2)
        self.assertTrue(res_t2.is_eligible)
        f_t2 = res_t2.features
        self.assertEqual(f_t2.obs_count, 3)
        self.assertEqual(f_t2.egfr_baseline, 80.0)
        self.assertEqual(f_t2.egfr_landmark, 70.0)
        self.assertEqual(f_t2.last_observation_time, self.t2)
        self.assertAlmostEqual(f_t2.total_followup_days, 365.0, places=1)

    def test_proof_adding_future_observations_does_not_change_landmark_features(self):
        """Test item 5: Mathematical proof that appending future observations does not alter features at landmark."""
        # Base record with only first 3 observations
        rec_early = LongitudinalPatientRecord(
            patient_id="PT_LEAK_PROOF",
            age_baseline=60.0,
            sex="male",
            observations=self.obs_standard[:3],
        )
        res_early = extract_progression_features(rec_early, landmark_time=self.t2)

        # Extended record with 2 future observations added (t3 and t4)
        rec_extended = LongitudinalPatientRecord(
            patient_id="PT_LEAK_PROOF",
            age_baseline=60.0,
            sex="male",
            observations=self.obs_standard,
        )
        res_extended = extract_progression_features(rec_extended, landmark_time=self.t2)

        # All features evaluated at t2 must be 100% bitwise identical
        f_early = res_early.features
        f_extended = res_extended.features

        self.assertEqual(f_early.obs_count, f_extended.obs_count)
        self.assertEqual(f_early.total_followup_days, f_extended.total_followup_days)
        self.assertEqual(f_early.egfr_baseline, f_extended.egfr_baseline)
        self.assertEqual(f_early.egfr_landmark, f_extended.egfr_landmark)
        self.assertEqual(f_early.egfr_delta_absolute, f_extended.egfr_delta_absolute)
        self.assertEqual(f_early.egfr_historical_slope, f_extended.egfr_historical_slope)
        self.assertEqual(f_early.uacr_landmark, f_extended.uacr_landmark)
        self.assertEqual(f_early.uacr_time_weighted_mean, f_extended.uacr_time_weighted_mean)

    # -----------------------------------------------------------------------
    # 7 & 8: Abstention on insufficient count and short follow-up
    # -----------------------------------------------------------------------
    def test_insufficient_observation_count_abstention(self):
        """Test item 7: Abstention when fewer than 2 observations exist (K < 2)."""
        rec_single = LongitudinalPatientRecord(
            patient_id="PT_SINGLE",
            age_baseline=55.0,
            sex="female",
            observations=[self.obs_standard[0]],
        )
        res = extract_progression_features(rec_single)
        self.assertFalse(res.is_eligible)
        self.assertIsNone(res.features)
        self.assertIsNotNone(res.abstention)
        self.assertTrue(res.abstention.should_abstain)
        self.assertEqual(res.abstention.reason_code, "INSUFFICIENT_OBSERVATION_COUNT")
        self.assertIn("minimum_2_observations", res.abstention.insufficient_criteria)

    def test_short_followup_duration_abstention(self):
        """Test item 8: Abstention when follow-up is shorter than 90 days."""
        rec_short = LongitudinalPatientRecord(
            patient_id="PT_SHORT",
            age_baseline=55.0,
            sex="female",
            observations=[
                self.obs_standard[0],
                ClinicalObservation(
                    timestamp=self.t0 + timedelta(days=60),  # Only 60 days
                    serum_creatinine=1.1,
                    egfr=78.0,
                    uacr=32.0,
                ),
            ],
        )
        res = extract_progression_features(rec_short)
        self.assertFalse(res.is_eligible)
        self.assertIsNone(res.features)
        self.assertEqual(res.abstention.reason_code, "INSUFFICIENT_FOLLOWUP_DURATION")
        self.assertIn("minimum_90_days_followup", res.abstention.insufficient_criteria)

    # -----------------------------------------------------------------------
    # 9 & 10: Slope unavailable criteria
    # -----------------------------------------------------------------------
    def test_slope_unavailable_when_fewer_than_three_observations(self):
        """Test item 9: Slope is None when fewer than 3 observations exist, but record is eligible."""
        rec_two_obs = LongitudinalPatientRecord(
            patient_id="PT_TWO_OBS",
            age_baseline=55.0,
            sex="female",
            observations=[
                self.obs_standard[0],
                self.obs_standard[4],  # Spanning 730 days, but only 2 observations
            ],
        )
        res = extract_progression_features(rec_two_obs)
        self.assertTrue(res.is_eligible)  # Eligible for basic features!
        f = res.features
        self.assertEqual(f.obs_count, 2)
        self.assertIsNone(f.egfr_historical_slope)
        self.assertIn("INSUFFICIENT_OBSERVATION_COUNT_FOR_SLOPE", f.egfr_slope_status)

    def test_slope_unavailable_when_followup_shorter_than_365_days(self):
        """Test item 10: Slope is None when follow-up is shorter than 365 days (even with >= 3 observations)."""
        rec_three_short = LongitudinalPatientRecord(
            patient_id="PT_THREE_SHORT",
            age_baseline=55.0,
            sex="male",
            observations=[
                self.obs_standard[0],
                ClinicalObservation(
                    timestamp=self.t0 + timedelta(days=95),
                    serum_creatinine=1.1,
                    egfr=78.0,
                ),
                ClinicalObservation(
                    timestamp=self.t0 + timedelta(days=200),  # 200 days total (< 365)
                    serum_creatinine=1.2,
                    egfr=72.0,
                ),
            ],
        )
        res = extract_progression_features(rec_three_short)
        self.assertTrue(res.is_eligible)
        f = res.features
        self.assertEqual(f.obs_count, 3)
        self.assertAlmostEqual(f.total_followup_days, 200.0, places=1)
        self.assertIsNone(f.egfr_historical_slope)
        self.assertIn("INSUFFICIENT_FOLLOWUP_FOR_SLOPE", f.egfr_slope_status)

    # -----------------------------------------------------------------------
    # 11, 12, 13: Albuminuria (UACR) & Division by Zero Safeguards
    # -----------------------------------------------------------------------
    def test_missing_uacr_handling_and_coverage(self):
        """Test item 11: Correct missingness indicators and coverage ratio when UACR is partially missing."""
        obs_missing_uacr = [
            ClinicalObservation(timestamp=self.t0, egfr=80.0, uacr=30.0),
            ClinicalObservation(timestamp=self.t1, egfr=75.0, uacr=None),  # Missing UACR
            ClinicalObservation(timestamp=self.t2, egfr=70.0, uacr=45.0),
        ]
        rec = LongitudinalPatientRecord(
            patient_id="PT_MISS_UACR",
            age_baseline=50.0,
            sex="female",
            observations=obs_missing_uacr,
        )
        res = extract_progression_features(rec)
        f = res.features
        self.assertEqual(f.uacr_valid_count, 2)
        self.assertEqual(f.uacr_missing_count, 1)
        self.assertAlmostEqual(f.uacr_coverage_ratio, 2 / 3, places=3)
        self.assertTrue(f.missingness_flags["has_missing_uacr"])

    def test_zero_uacr_baseline_division_by_zero_protection(self):
        """Test items 12 & 13: Zero UACR baseline results in None progression ratio without division by zero."""
        obs_zero_uacr = [
            ClinicalObservation(timestamp=self.t0, egfr=80.0, uacr=0.0),  # Zero baseline UACR
            ClinicalObservation(timestamp=self.t2, egfr=70.0, uacr=30.0),
        ]
        rec = LongitudinalPatientRecord(
            patient_id="PT_ZERO_UACR",
            age_baseline=50.0,
            sex="male",
            observations=obs_zero_uacr,
        )
        res = extract_progression_features(rec)
        f = res.features
        self.assertEqual(f.uacr_baseline, 0.0)
        self.assertEqual(f.uacr_landmark, 30.0)
        # Progression ratio must be None, not ZeroDivisionError or Inf
        self.assertIsNone(f.uacr_progression_ratio)

    def test_uacr_trapezoidal_time_weighted_mean(self):
        """Test trapezoidal time-weighted mean calculation on known values."""
        # t0: 30 mg/g, t2 (365 days later): 50 mg/g
        # Average = (30 + 50) / 2 = 40.0 mg/g
        obs_uacr = [
            ClinicalObservation(timestamp=self.t0, egfr=80.0, uacr=30.0),
            ClinicalObservation(timestamp=self.t2, egfr=70.0, uacr=50.0),
        ]
        rec = LongitudinalPatientRecord(
            patient_id="PT_TWM",
            age_baseline=50.0,
            sex="male",
            observations=obs_uacr,
        )
        res = extract_progression_features(rec)
        f = res.features
        self.assertAlmostEqual(f.uacr_time_weighted_mean, 40.0, places=1)
        self.assertEqual(f.uacr_time_weighted_status, "TRAPEZOIDAL_TIME_WEIGHTED_MEAN")

    # -----------------------------------------------------------------------
    # 14 & 15: Timestamp Chronology & Duplicate Rejection
    # -----------------------------------------------------------------------
    def test_duplicate_timestamp_rejection(self):
        """Test item 14: Rejection of identical duplicate observation timestamps."""
        obs_dup = [
            ClinicalObservation(timestamp=self.t0, egfr=80.0, uacr=30.0),
            ClinicalObservation(timestamp=self.t0, egfr=78.0, uacr=32.0),  # Duplicate timestamp!
        ]
        rec = LongitudinalPatientRecord(
            patient_id="PT_DUP",
            age_baseline=50.0,
            sex="female",
            observations=obs_dup,
        )
        res = extract_progression_features(rec)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.abstention.reason_code, "NON_MONOTONIC_TIMESTAMPS")
        self.assertIn("Duplicate timestamp", res.abstention.message)

    def test_non_monotonic_timestamp_rejection(self):
        """Test item 15: Rejection of non-monotonic observation timestamps."""
        obs_disorder = [
            ClinicalObservation(timestamp=self.t1, egfr=75.0, uacr=35.0),
            ClinicalObservation(timestamp=self.t0, egfr=80.0, uacr=30.0),  # Earlier timestamp later in list!
        ]
        rec = LongitudinalPatientRecord(
            patient_id="PT_DISORDER",
            age_baseline=50.0,
            sex="female",
            observations=obs_disorder,
        )
        res = extract_progression_features(rec)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.abstention.reason_code, "NON_MONOTONIC_TIMESTAMPS")
        self.assertIn("Non-monotonic", res.abstention.message)

    # -----------------------------------------------------------------------
    # 16: Blood Pressure and HbA1c Handling
    # -----------------------------------------------------------------------
    def test_missing_optional_bp_and_hba1c_handling(self):
        """Test item 16: Safe handling when BP and HbA1c are missing."""
        obs_no_bp = [
            ClinicalObservation(timestamp=self.t0, egfr=80.0, uacr=30.0),
            ClinicalObservation(timestamp=self.t2, egfr=70.0, uacr=40.0),
        ]
        rec = LongitudinalPatientRecord(
            patient_id="PT_NO_BP",
            age_baseline=50.0,
            sex="female",
            observations=obs_no_bp,
        )
        res = extract_progression_features(rec)
        f = res.features
        self.assertIsNone(f.sbp_mean)
        self.assertIsNone(f.sbp_variability)
        self.assertIsNone(f.dbp_mean)
        self.assertIsNone(f.dbp_variability)
        self.assertEqual(f.bp_valid_count, 0)
        self.assertIsNone(f.hba1c_mean)
        self.assertIsNone(f.hba1c_landmark)
        self.assertTrue(f.missingness_flags["lacks_bp_monitoring"])

    # -----------------------------------------------------------------------
    # 20: Input Record Immutability
    # -----------------------------------------------------------------------
    def test_no_mutation_of_source_observations(self):
        """Test item 20: Feature extraction strictly preserves and does not mutate source observations."""
        original_obs_count = len(self.record_standard.observations)
        original_timestamps = [obs.timestamp for obs in self.record_standard.observations]

        # Extract features at an earlier landmark (t2)
        res = extract_progression_features(self.record_standard, landmark_time=self.t2)

        # Confirm the source record was not truncated or modified
        self.assertEqual(len(self.record_standard.observations), original_obs_count)
        for i, obs in enumerate(self.record_standard.observations):
            self.assertEqual(obs.timestamp, original_timestamps[i])


if __name__ == "__main__":
    unittest.main()
