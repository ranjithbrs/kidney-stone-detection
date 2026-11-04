"""Unit tests for cohort-independent longitudinal data infrastructure and CRIC adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from src.clinical.survival.survival_contracts import SurvivalEventType
from src.data_sources.longitudinal_loader import (
    CRICLongitudinalAdapter,
    LongitudinalCohort,
    LongitudinalPatientHistory,
    LongitudinalVisit,
    load_longitudinal_from_dataframe,
)


class TestLongitudinalLoader(unittest.TestCase):
    """Test suite for longitudinal data parsing, landmark creation, and CRIC adapter."""

    def setUp(self):
        # Create a sample DataFrame with 3 patients
        rows = [
            # Patient 1: 3 visits, progresses to KF at 2.5 years
            {"patient_id": "P001", "visit_date": "2020-01-01", "serum_creatinine": 1.2, "egfr": 65.0, "uacr": 30.0, "systolic_bp": 120.0, "age": 60, "sex": "male", "diabetes": 0, "event_type": 1, "duration_years": 2.5},
            {"patient_id": "P001", "visit_date": "2020-07-01", "serum_creatinine": 1.5, "egfr": 50.0, "uacr": 80.0, "systolic_bp": 125.0, "age": 60, "sex": "male", "diabetes": 0, "event_type": 1, "duration_years": 2.5},
            {"patient_id": "P001", "visit_date": "2021-01-01", "serum_creatinine": 2.0, "egfr": 35.0, "uacr": 200.0, "systolic_bp": 135.0, "age": 60, "sex": "male", "diabetes": 0, "event_type": 1, "duration_years": 2.5},
            # Patient 2: 2 visits, censored at 3.0 years
            {"patient_id": "P002", "visit_date": "2020-03-01", "serum_creatinine": 0.9, "egfr": 90.0, "uacr": 10.0, "systolic_bp": 115.0, "age": 45, "sex": "female", "diabetes": 0, "event_type": 0, "duration_years": 3.0},
            {"patient_id": "P002", "visit_date": "2020-09-01", "serum_creatinine": 1.0, "egfr": 85.0, "uacr": 15.0, "systolic_bp": 118.0, "age": 45, "sex": "female", "diabetes": 0, "event_type": 0, "duration_years": 3.0},
            # Patient 3: 1 visit only (insufficient prior visits at landmark)
            {"patient_id": "P003", "visit_date": "2020-05-01", "serum_creatinine": 1.8, "egfr": 40.0, "uacr": 150.0, "systolic_bp": 140.0, "age": 70, "sex": "male", "diabetes": 1, "event_type": 2, "duration_years": 1.5},
        ]
        self.df_sample = pd.DataFrame(rows)

    def test_load_from_dataframe_success(self):
        """Verify successful ingestion of generic longitudinal DataFrame."""
        cohort = load_longitudinal_from_dataframe(self.df_sample, cohort_name="TestCohort")
        self.assertEqual(len(cohort), 3)
        self.assertEqual(cohort.total_visits(), 6)

        p1 = cohort.get_patient("P001")
        self.assertIsNotNone(p1)
        self.assertEqual(len(p1.visits), 3)
        self.assertEqual(p1.event_type, SurvivalEventType.KIDNEY_FAILURE)
        self.assertEqual(p1.follow_up_duration_years, 2.5)

    def test_on_the_fly_egfr_calculation(self):
        """Verify eGFR calculation when only serum creatinine is supplied."""
        df_no_egfr = pd.DataFrame([
            {"patient_id": "P_CALC", "visit_date": "2021-01-01", "serum_creatinine": 1.5, "age": 60, "sex": "male"}
        ])
        cohort = load_longitudinal_from_dataframe(df_no_egfr, egfr_col=None)
        p = cohort.get_patient("P_CALC")
        self.assertIsNotNone(p)
        self.assertIsNotNone(p.visits[0].egfr)
        self.assertTrue(40.0 < p.visits[0].egfr < 65.0)

    def test_biological_boundaries_and_warnings(self):
        """Values outside biological plausibility boundaries generate warnings."""
        df_bad = pd.DataFrame([
            {"patient_id": "P_BOUND", "visit_date": "2021-01-01", "serum_creatinine": 55.0, "age": 50, "sex": "male"}
        ])
        cohort = load_longitudinal_from_dataframe(df_bad)
        p = cohort.get_patient("P_BOUND")
        self.assertIsNotNone(p)
        v = p.visits[0]
        self.assertIsNone(v.serum_creatinine)  # Nullified due to boundary violation
        self.assertTrue(any("outside physiological bounds" in w for w in v.validation_warnings))

    def test_create_landmark_survival_dataset(self):
        """Test leak-free landmarking and forward follow-up calculation."""
        cohort = load_longitudinal_from_dataframe(self.df_sample)
        lm_date = datetime(2020, 10, 1, tzinfo=timezone.utc)

        ds = cohort.create_landmark_survival_dataset(
            landmark_time=lm_date,
            followup_horizon_years=2.0,
            min_prior_observations=2,
        )

        # Patient 1 and Patient 2 have >= 2 visits prior to Oct 2020. Patient 3 has only 1 visit -> excluded.
        self.assertEqual(len(ds), 2)
        p_ids = [r.patient_id for r in ds.records]
        self.assertIn("P001", p_ids)
        self.assertIn("P002", p_ids)
        self.assertNotIn("P003", p_ids)

        # Check features
        r1 = next(r for r in ds.records if r.patient_id == "P001")
        self.assertIn("egfr_slope", r1.features)
        self.assertIn("egfr", r1.features)
        self.assertEqual(r1.features["obs_count"], 2)  # Only 2 visits occurred on or before Oct 2020

    def test_conversion_to_progression_record(self):
        """Test conversion from LongitudinalPatientHistory to LongitudinalPatientRecord."""
        cohort = load_longitudinal_from_dataframe(self.df_sample)
        p1 = cohort.get_patient("P001")
        prog_rec = p1.to_progression_record()
        self.assertEqual(prog_rec.patient_id, "P001")
        self.assertEqual(len(prog_rec.observations), 3)
        self.assertEqual(prog_rec.age_baseline, 60.0)

    def test_cric_adapter_checks_and_error(self):
        """CRIC adapter correctly identifies missing directory and raises descriptive error."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertFalse(CRICLongitudinalAdapter.is_cric_available(tmp_dir))
            with self.assertRaises(FileNotFoundError) as ctx:
                CRICLongitudinalAdapter.load_cric_cohort(tmp_dir)
            self.assertIn("Data Governance Notice", str(ctx.exception))
            self.assertIn("NIDDK Data Use Agreements", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
