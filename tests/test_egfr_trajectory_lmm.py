"""Unit tests for LinearMixedEffectsTrajectoryModel (LMM) in Engine 3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

import numpy as np

from src.clinical.lmm_trajectory import (
    LMMConfig,
    LMMTrajectoryResult,
    LinearMixedEffectsTrajectoryModel,
)
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
)


class TestEGFRTrajectoryLMM(unittest.TestCase):
    """Test suite for population linear mixed-effects eGFR decline estimation."""

    def setUp(self):
        self.rng = np.random.RandomState(42)

    def _create_synthetic_patient(
        self,
        patient_id: str,
        n_obs: int,
        interval_days: int = 120,
        baseline_egfr: float = 65.0,
        annual_decline: float = -3.0,
    ) -> LongitudinalPatientRecord:
        """Create a synthetic patient record for testing."""
        t0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
        obs = []
        for i in range(n_obs):
            ts = t0 + timedelta(days=i * interval_days)
            t_yr = (i * interval_days) / 365.25
            val = baseline_egfr + annual_decline * t_yr + self.rng.normal(0, 1.0)
            obs.append(ClinicalObservation(timestamp=ts, egfr=round(max(5.0, val), 1)))

        return LongitudinalPatientRecord(
            patient_id=patient_id,
            age_baseline=60.0,
            sex="male",
            observations=obs,
            is_synthetic=True,
            provenance="TEST_LMM_FIXTURE",
        )

    def test_lmm_default_initialization(self):
        """Model initializes with clinically plausible reference values."""
        model = LinearMixedEffectsTrajectoryModel()
        summary = model.summary()
        self.assertAlmostEqual(summary["fixed_intercept"], 65.0, places=1)
        self.assertAlmostEqual(summary["fixed_slope"], -2.5, places=1)
        self.assertFalse(summary["is_fitted"])

    def test_lmm_fit_on_cohort(self):
        """Model fits on small cohort of longitudinal records without errors."""
        records = [
            self._create_synthetic_patient(f"P{i:02d}", n_obs=5, annual_decline=-2.0 - (i % 3))
            for i in range(6)
        ]
        model = LinearMixedEffectsTrajectoryModel(LMMConfig(max_iterations=50))
        model.fit(records)

        self.assertTrue(model.is_fitted)
        self.assertEqual(model.n_patients_fitted_, 6)
        self.assertEqual(model.n_observations_fitted_, 30)

        summary = model.summary()
        self.assertTrue(-10.0 < summary["fixed_slope"] < 0.0)
        self.assertTrue(summary["sigma_random_slope"] > 0.0)

    def test_predict_patient_trajectory_eligible(self):
        """Eligible patient with 4 observations receives Empirical Bayes BLUP slope."""
        patient = self._create_synthetic_patient("P_ELIGIBLE", n_obs=4, interval_days=180, annual_decline=-4.5)
        model = LinearMixedEffectsTrajectoryModel()

        res = model.predict_patient_trajectory(patient)
        self.assertTrue(res.is_eligible)
        self.assertEqual(res.status, "ESTIMATED_EMPIRICAL_BAYES_RANDOM_SLOPE")
        self.assertEqual(res.obs_count, 4)
        self.assertTrue(res.followup_days >= 500)

        # Check slope estimates
        self.assertLess(res.patient_slope, 0.0)
        self.assertTrue(res.slope_ci_lower <= res.patient_slope <= res.slope_ci_upper)
        self.assertGreater(res.slope_standard_error, 0.0)

    def test_predict_patient_trajectory_ineligible_fallback(self):
        """Patient with only 2 observations falls back to population shrinkage."""
        patient = self._create_synthetic_patient("P_INELIGIBLE", n_obs=2, interval_days=60)
        model = LinearMixedEffectsTrajectoryModel()

        res = model.predict_patient_trajectory(patient)
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.status, "INSUFFICIENT_OBSERVATIONS_POPULATION_SHRINKAGE")
        self.assertEqual(res.patient_slope, res.population_slope)
        self.assertEqual(res.random_slope, 0.0)

    def test_shrinkage_behavior(self):
        """A patient with noisy or extreme slope is shrunken towards the population mean."""
        # Patient with 3 points that show extreme steep slope (-15 mL/min/year)
        patient_extreme = self._create_synthetic_patient(
            "P_EXTREME", n_obs=3, interval_days=90, annual_decline=-15.0
        )
        model = LinearMixedEffectsTrajectoryModel()

        res = model.predict_patient_trajectory(patient_extreme)
        # BLUP slope should be less extreme than -15 due to shrinkage towards population mean (-2.5)
        self.assertGreater(res.patient_slope, -15.0)

    def test_to_dict_serialization(self):
        """Result serializes to valid dictionary representation."""
        patient = self._create_synthetic_patient("P_DICT", n_obs=4, interval_days=100)
        model = LinearMixedEffectsTrajectoryModel()
        res = model.predict_patient_trajectory(patient)
        d = res.to_dict()
        self.assertEqual(d["patient_id"], "P_DICT")
        self.assertIn("patient_slope", d)
        self.assertIn("slope_ci_lower", d)
        self.assertIn("slope_ci_upper", d)


if __name__ == "__main__":
    unittest.main()
