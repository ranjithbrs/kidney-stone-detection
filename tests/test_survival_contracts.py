"""Unit test suite for Engine 3 survival dataset contracts and competing-risk data pathways.

Verifies:
- Explicit event and censoring coding (0 = Censored, 1 = Kidney Failure, 2 = Competing Death)
- Strict rejection of invalid follow-up durations (negative duration)
- Rejection of event dates preceding landmark observation dates
- Detection and rejection of contradictory event/censoring flags
- Rejection of duplicate (patient_id, landmark_date) records
- Patient-level grouped split isolation (zero patient overlap between train and test)
- Landmark feature observation leakage prevention (temporal sanity checks)
- Competing risk representation via Aalen-Johansen CIF
- Explicit behaviour when Fine-Gray dependencies are unavailable
"""

import datetime
import unittest

import numpy as np

from src.clinical.survival.competing_risk import (
    DeferredFineGrayEstimator,
    FineGrayDependencyUnavailableError,
    calculate_aalen_johansen_cif,
    prepare_fine_gray_dataframe,
)
from src.clinical.survival.survival_contracts import (
    SurvivalDataset,
    SurvivalDataValidationError,
    SurvivalEventType,
    SurvivalLandmarkRecord,
    patient_grouped_train_test_split,
    temporal_cohort_split,
)


class TestSurvivalContracts(unittest.TestCase):
    """Test suite for survival dataset contracts and validation invariants."""

    def setUp(self):
        self.valid_features = {"age": 65.0, "egfr": 35.0, "uacr": 200.0, "male": 1.0}
        self.base_date = datetime.date(2020, 1, 1)
        self.lm_date = datetime.date(2021, 1, 1)
        self.fu_end_date = datetime.date(2023, 1, 1)

    # -----------------------------------------------------------------------
    # 1. Event and Censoring Coding
    # -----------------------------------------------------------------------
    def test_event_and_censoring_coding_valid(self):
        """Verify proper instantiation for Censored, Kidney Failure, and Competing Death."""
        # 0 = Right Censored
        rec_cens = SurvivalLandmarkRecord(
            patient_id="P001",
            landmark_date=self.lm_date,
            baseline_date=self.base_date,
            follow_up_start_date=self.lm_date,
            follow_up_end_date=self.fu_end_date,
            event_type=SurvivalEventType.RIGHT_CENSORED,
            event_kidney_failure=0,
            event_death=0,
            is_censored=1,
            features=self.valid_features,
        )
        self.assertEqual(rec_cens.event_type, SurvivalEventType.RIGHT_CENSORED)
        self.assertEqual(rec_cens.is_censored, 1)
        self.assertEqual(rec_cens.event_kidney_failure, 0)
        self.assertEqual(rec_cens.event_death, 0)
        self.assertAlmostEqual(rec_cens.follow_up_duration_years, 2.0, places=1)

        # 1 = Kidney Failure
        rec_kf = SurvivalLandmarkRecord(
            patient_id="P002",
            landmark_date=self.lm_date,
            baseline_date=self.base_date,
            follow_up_start_date=self.lm_date,
            follow_up_end_date=self.fu_end_date,
            event_type=SurvivalEventType.KIDNEY_FAILURE,
            event_kidney_failure=1,
            event_death=0,
            is_censored=0,
            features=self.valid_features,
        )
        self.assertEqual(rec_kf.event_type, SurvivalEventType.KIDNEY_FAILURE)
        self.assertEqual(rec_kf.event_kidney_failure, 1)
        self.assertEqual(rec_kf.is_censored, 0)

        # 2 = Competing Death
        rec_death = SurvivalLandmarkRecord(
            patient_id="P003",
            landmark_date=self.lm_date,
            baseline_date=self.base_date,
            follow_up_start_date=self.lm_date,
            follow_up_end_date=self.fu_end_date,
            event_type=SurvivalEventType.COMPETING_DEATH,
            event_kidney_failure=0,
            event_death=1,
            is_censored=0,
            features=self.valid_features,
        )
        self.assertEqual(rec_death.event_type, SurvivalEventType.COMPETING_DEATH)
        self.assertEqual(rec_death.event_death, 1)
        self.assertEqual(rec_death.event_kidney_failure, 0)
        self.assertEqual(rec_death.is_censored, 0)

    # -----------------------------------------------------------------------
    # 2. Contradictory Event and Censoring Flags
    # -----------------------------------------------------------------------
    def test_contradictory_flags_rejected(self):
        """Reject contradictory combinations of event_type, is_censored, and event indicators."""
        # Censored event_type but is_censored=0
        with self.assertRaises(SurvivalDataValidationError):
            SurvivalLandmarkRecord(
                patient_id="P_ERR",
                landmark_date=self.lm_date,
                baseline_date=self.base_date,
                follow_up_start_date=self.lm_date,
                follow_up_end_date=self.fu_end_date,
                event_type=SurvivalEventType.RIGHT_CENSORED,
                event_kidney_failure=0,
                event_death=0,
                is_censored=0,  # Contradiction!
                features=self.valid_features,
            )

        # Kidney failure event_type but event_kidney_failure=0
        with self.assertRaises(SurvivalDataValidationError):
            SurvivalLandmarkRecord(
                patient_id="P_ERR2",
                landmark_date=self.lm_date,
                baseline_date=self.base_date,
                follow_up_start_date=self.lm_date,
                follow_up_end_date=self.fu_end_date,
                event_type=SurvivalEventType.KIDNEY_FAILURE,
                event_kidney_failure=0,  # Contradiction!
                event_death=0,
                is_censored=0,
                features=self.valid_features,
            )

        # Competing death event_type but event_kidney_failure=1
        with self.assertRaises(SurvivalDataValidationError):
            SurvivalLandmarkRecord(
                patient_id="P_ERR3",
                landmark_date=self.lm_date,
                baseline_date=self.base_date,
                follow_up_start_date=self.lm_date,
                follow_up_end_date=self.fu_end_date,
                event_type=SurvivalEventType.COMPETING_DEATH,
                event_kidney_failure=1,  # Contradiction!
                event_death=1,
                is_censored=0,
                features=self.valid_features,
            )

    # -----------------------------------------------------------------------
    # 3. Invalid Follow-Up & Temporal Sequencing Rejection
    # -----------------------------------------------------------------------
    def test_negative_follow_up_rejected(self):
        """Reject follow-up where end date precedes start date."""
        with self.assertRaises(SurvivalDataValidationError):
            SurvivalLandmarkRecord(
                patient_id="P_NEG",
                landmark_date=self.lm_date,
                baseline_date=self.base_date,
                follow_up_start_date=datetime.date(2022, 1, 1),
                follow_up_end_date=datetime.date(2021, 1, 1),  # Negative follow-up!
                event_type=SurvivalEventType.RIGHT_CENSORED,
                event_kidney_failure=0,
                event_death=0,
                is_censored=1,
                features=self.valid_features,
            )

    def test_follow_up_before_landmark_rejected(self):
        """Reject follow-up start date preceding the landmark date."""
        with self.assertRaises(SurvivalDataValidationError):
            SurvivalLandmarkRecord(
                patient_id="P_EARLY",
                landmark_date=datetime.date(2022, 1, 1),
                baseline_date=self.base_date,
                follow_up_start_date=datetime.date(2021, 6, 1),  # Before landmark!
                follow_up_end_date=datetime.date(2023, 1, 1),
                event_type=SurvivalEventType.RIGHT_CENSORED,
                event_kidney_failure=0,
                event_death=0,
                is_censored=1,
                features=self.valid_features,
            )

    def test_baseline_after_landmark_rejected(self):
        """Reject baseline enrollment date following the landmark date."""
        with self.assertRaises(SurvivalDataValidationError):
            SurvivalLandmarkRecord(
                patient_id="P_BASE_LATE",
                landmark_date=datetime.date(2020, 1, 1),
                baseline_date=datetime.date(2021, 1, 1),  # Baseline after landmark!
                follow_up_start_date=datetime.date(2020, 1, 1),
                follow_up_end_date=datetime.date(2022, 1, 1),
                event_type=SurvivalEventType.RIGHT_CENSORED,
                event_kidney_failure=0,
                event_death=0,
                is_censored=1,
                features=self.valid_features,
            )

    # -----------------------------------------------------------------------
    # 4. Temporal Feature Leakage Prevention
    # -----------------------------------------------------------------------
    def test_landmark_feature_leakage_prevented(self):
        """Reject records where predictor features were measured AFTER the landmark date."""
        leaked_timestamps = {
            "age": datetime.date(2020, 12, 1),
            "egfr": datetime.date(2021, 1, 1),  # On landmark
            "uacr": datetime.date(2021, 3, 15),  # FUTURE LEAKAGE: 2.5 months after landmark!
        }
        with self.assertRaises(SurvivalDataValidationError) as ctx:
            SurvivalLandmarkRecord(
                patient_id="P_LEAK",
                landmark_date=self.lm_date,  # 2021-01-01
                baseline_date=self.base_date,
                follow_up_start_date=self.lm_date,
                follow_up_end_date=self.fu_end_date,
                event_type=SurvivalEventType.RIGHT_CENSORED,
                event_kidney_failure=0,
                event_death=0,
                is_censored=1,
                features=self.valid_features,
                feature_timestamps=leaked_timestamps,
            )
        self.assertIn("TEMPORAL LEAKAGE DETECTED", str(ctx.exception))

    # -----------------------------------------------------------------------
    # 5. Duplicate Patient-Landmark Rejection & Dataset Management
    # -----------------------------------------------------------------------
    def test_duplicate_patient_landmark_rejected(self):
        """Reject duplicate records for the same patient at the exact same landmark date."""
        rec1 = SurvivalLandmarkRecord(
            patient_id="P100",
            landmark_date=self.lm_date,
            baseline_date=self.base_date,
            follow_up_start_date=self.lm_date,
            follow_up_end_date=self.fu_end_date,
            event_type=SurvivalEventType.RIGHT_CENSORED,
            event_kidney_failure=0,
            event_death=0,
            is_censored=1,
            features=self.valid_features,
        )
        rec2_dup = SurvivalLandmarkRecord(
            patient_id="P100",  # Same patient
            landmark_date=self.lm_date,  # Same landmark
            baseline_date=self.base_date,
            follow_up_start_date=self.lm_date,
            follow_up_end_date=datetime.date(2024, 1, 1),
            event_type=SurvivalEventType.RIGHT_CENSORED,
            event_kidney_failure=0,
            event_death=0,
            is_censored=1,
            features=self.valid_features,
        )
        ds = SurvivalDataset([rec1])
        with self.assertRaises(SurvivalDataValidationError):
            ds.add_record(rec2_dup)

    def test_multiple_landmarks_per_patient_supported(self):
        """Support multiple distinct landmark dates for the same patient."""
        rec_lm1 = SurvivalLandmarkRecord(
            patient_id="P200",
            landmark_date=datetime.date(2021, 1, 1),
            baseline_date=self.base_date,
            follow_up_start_date=datetime.date(2021, 1, 1),
            follow_up_end_date=datetime.date(2024, 1, 1),
            event_type=SurvivalEventType.RIGHT_CENSORED,
            event_kidney_failure=0,
            event_death=0,
            is_censored=1,
            features=self.valid_features,
        )
        rec_lm2 = SurvivalLandmarkRecord(
            patient_id="P200",
            landmark_date=datetime.date(2022, 1, 1),  # Subsequent landmark
            baseline_date=self.base_date,
            follow_up_start_date=datetime.date(2022, 1, 1),
            follow_up_end_date=datetime.date(2024, 1, 1),
            event_type=SurvivalEventType.RIGHT_CENSORED,
            event_kidney_failure=0,
            event_death=0,
            is_censored=1,
            features=self.valid_features,
        )
        ds = SurvivalDataset([rec_lm1, rec_lm2])
        self.assertEqual(len(ds), 2)
        self.assertEqual(ds.n_patients, 1)

    # -----------------------------------------------------------------------
    # 6. Patient-Level Grouped Split Isolation
    # -----------------------------------------------------------------------
    def test_patient_grouped_split_zero_leakage(self):
        """Ensure patient-grouped train/test split has absolute zero patient overlap."""
        records = []
        for p_idx in range(20):
            p_id = f"PAT_{p_idx:03d}"
            # Add 2 landmarks per patient
            for lm_year in [2020, 2021]:
                rec = SurvivalLandmarkRecord(
                    patient_id=p_id,
                    landmark_date=datetime.date(lm_year, 1, 1),
                    baseline_date=datetime.date(2019, 1, 1),
                    follow_up_start_date=datetime.date(lm_year, 1, 1),
                    follow_up_end_date=datetime.date(2024, 1, 1),
                    event_type=SurvivalEventType.RIGHT_CENSORED,
                    event_kidney_failure=0,
                    event_death=0,
                    is_censored=1,
                    features=self.valid_features,
                )
                records.append(rec)

        full_ds = SurvivalDataset(records)
        self.assertEqual(len(full_ds), 40)
        self.assertEqual(full_ds.n_patients, 20)

        train_ds, test_ds = patient_grouped_train_test_split(full_ds, test_size=0.25, random_state=42)

        train_patients = train_ds.get_patient_ids()
        test_patients = test_ds.get_patient_ids()

        # Strict isolation invariant
        overlap = train_patients.intersection(test_patients)
        self.assertEqual(len(overlap), 0, f"Patient overlap detected: {overlap}")
        self.assertEqual(len(train_patients) + len(test_patients), 20)
        self.assertEqual(len(train_ds) + len(test_ds), 40)

    # -----------------------------------------------------------------------
    # 7. Competing Risk Representation & Aalen-Johansen CIF
    # -----------------------------------------------------------------------
    def test_aalen_johansen_cif_mathematical_properties(self):
        """Test that CIF computes non-parametric cumulative incidences properly bounded."""
        records = []
        # Create a synthetic cohort with mixture of KF events, competing deaths, and censorings
        # P0-P4: KF at 1.5 yrs
        # P5-P7: Competing death at 1.0 yrs
        # P8-P19: Censored at 4.0 yrs
        for i in range(20):
            p_id = f"P_{i:02d}"
            if i < 5:
                ev = SurvivalEventType.KIDNEY_FAILURE
                kf, d, c = 1, 0, 0
                end_dt = datetime.date(2022, 7, 1)  # 1.5 yrs
            elif i < 8:
                ev = SurvivalEventType.COMPETING_DEATH
                kf, d, c = 0, 1, 0
                end_dt = datetime.date(2022, 1, 1)  # 1.0 yr
            else:
                ev = SurvivalEventType.RIGHT_CENSORED
                kf, d, c = 0, 0, 1
                end_dt = datetime.date(2025, 1, 1)  # 4.0 yrs

            rec = SurvivalLandmarkRecord(
                patient_id=p_id,
                landmark_date=self.lm_date,
                baseline_date=self.base_date,
                follow_up_start_date=self.lm_date,
                follow_up_end_date=end_dt,
                event_type=ev,
                event_kidney_failure=kf,
                event_death=d,
                is_censored=c,
                features=self.valid_features,
            )
            records.append(rec)

        ds = SurvivalDataset(records)
        cif_res = calculate_aalen_johansen_cif(ds, time_horizons=[0.5, 1.2, 2.0, 5.0])

        self.assertEqual(cif_res.n_at_risk_initial, 20)
        self.assertEqual(cif_res.n_kidney_failure_total, 5)
        self.assertEqual(cif_res.n_competing_death_total, 3)

        # At t=0.5: no events yet
        self.assertEqual(cif_res.cif_kidney_failure[0], 0.0)
        self.assertEqual(cif_res.cif_competing_death[0], 0.0)

        # At t=1.2: 3 deaths occurred out of 20 -> CIF_death = 3/20 = 0.15; CIF_kf = 0
        self.assertAlmostEqual(cif_res.cif_competing_death[1], 0.15, places=2)
        self.assertAlmostEqual(cif_res.cif_kidney_failure[1], 0.0, places=2)

        # At t=2.0: 5 KF events occurred out of 17 at risk -> CIF_kf > 0
        self.assertTrue(cif_res.cif_kidney_failure[2] > 0.0)

        # Sum of CIF_kf + CIF_death + S_overall <= 1.0 at all horizons
        for k in range(len(cif_res.time_horizons)):
            total_prob = (
                cif_res.cif_kidney_failure[k]
                + cif_res.cif_competing_death[k]
                + cif_res.overall_event_free_survival[k]
            )
            self.assertAlmostEqual(total_prob, 1.0, places=3)

    # -----------------------------------------------------------------------
    # 8. Deferred Fine-Gray Estimator and Data Contract
    # -----------------------------------------------------------------------
    def test_deferred_fine_gray_estimator_raises_informative_error(self):
        """Verify that attempting to fit the deferred Fine-Gray model raises informative safety error."""
        estimator = DeferredFineGrayEstimator()
        # Since lifelines is not installed in the environment:
        self.assertFalse(estimator.is_library_available)
        with self.assertRaises(FineGrayDependencyUnavailableError) as ctx:
            estimator.fit()
        self.assertIn("Fine-Gray subdistribution hazards model is DEFERRED", str(ctx.exception))
        self.assertIn("Ordinary Cox regression MUST NOT be used as a substitute", str(ctx.exception))

    def test_prepare_fine_gray_dataframe(self):
        """Verify format of prepared Fine-Gray tabular dataframe."""
        rec = SurvivalLandmarkRecord(
            patient_id="P_FG",
            landmark_date=self.lm_date,
            baseline_date=self.base_date,
            follow_up_start_date=self.lm_date,
            follow_up_end_date=self.fu_end_date,
            event_type=SurvivalEventType.KIDNEY_FAILURE,
            event_kidney_failure=1,
            event_death=0,
            is_censored=0,
            features=self.valid_features,
        )
        ds = SurvivalDataset([rec])
        df = prepare_fine_gray_dataframe(ds)
        self.assertIn("duration", df.columns)
        self.assertIn("event", df.columns)
        self.assertIn("feat_egfr", df.columns)
        self.assertEqual(df["event"].iloc[0], 1)


if __name__ == "__main__":
    unittest.main()
