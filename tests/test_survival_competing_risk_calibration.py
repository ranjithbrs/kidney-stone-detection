"""Mathematical and unit verification suite for competing-risk calibration in Engine 3.

Validates:
1. Exact equality between Aalen-Johansen CIF and 1 - Kaplan-Meier when competing deaths are absent.
2. Strict inequality 1 - S_KM(t) > CIF_AJ(t) when competing deaths occur before or at horizon.
3. Quantile calibration grouping and observed CIF calculations across risk tiers.
4. Robust handling of sparse events (0 events in bin) and all-censored groups.
5. Right censoring before horizon handled consistently without complete-case bias.
6. Leave-one-out jackknife pseudo-observation identity (mean(theta) == overall_cif).
7. Competing-risk calibration slope and intercept behavior via pseudo-observation regression.
8. Estimand separation between cause-specific net risk and actual cumulative incidence.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from src.clinical.survival.evaluation import (
    CalibrationGroup,
    TimeDependentEvaluationResult,
    calculate_cause_specific_calibration_by_quantiles,
    calculate_cause_specific_calibration_slope_and_intercept,
    calculate_competing_risk_calibration_by_quantiles,
    calculate_competing_risk_calibration_slope_and_intercept,
    evaluate_survival_model,
    _calculate_aj_cif_and_se_at_horizon,
)
from src.clinical.survival.survival_contracts import SurvivalEventType


class TestSurvivalCompetingRiskCalibration(unittest.TestCase):
    """Rigorous mathematical tests for competing-risk calibration consistency."""

    def setUp(self):
        self.rng = np.random.RandomState(42)

    def test_01_kf_with_no_competing_deaths_matches_km(self):
        """When competing deaths are absent (d2 = 0), AJ CIF identically equals KM failure (1 - S_KM)."""
        durations = np.array([1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0])
        event_types = np.array([1, 0, 1, 1, 0, 1, 0])  # Only event 1 or 0
        horizon = 3.5

        # 1. Aalen-Johansen CIF
        aj_cif, aj_se = _calculate_aj_cif_and_se_at_horizon(durations, event_types, horizon)

        # 2. Hand-calculated Kaplan-Meier failure at horizon 3.5:
        # t=1.0: n=7, d=1 -> S = 6/7
        # t=1.5: censored (n=6 -> 5)
        # t=2.0: n=5, d=1 -> S = (6/7) * (4/5) = 24/35
        # t=3.0: n=4, d=1 -> S = (24/35) * (3/4) = 18/35
        # 1 - S = 1 - 18/35 = 17/35 = 0.485714...
        expected_km_failure = 1.0 - (18.0 / 35.0)

        # Greenwood variance:
        # sum = 1/(7*6) + 1/(5*4) + 1/(4*3) = 1/42 + 1/20 + 1/12
        gw_sum = (1.0 / 42.0) + (1.0 / 20.0) + (1.0 / 12.0)
        expected_km_se = (18.0 / 35.0) * math.sqrt(gw_sum)

        self.assertAlmostEqual(aj_cif, expected_km_failure, places=8)
        self.assertAlmostEqual(aj_se, expected_km_se, places=8)

        # Also test via quantile calibration with 1 group
        groups, err = calculate_competing_risk_calibration_by_quantiles(
            durations, event_types, np.full_like(durations, 0.5), horizon, n_groups=1
        )
        self.assertEqual(len(groups), 1)
        self.assertAlmostEqual(groups[0].observed_event_rate, round(expected_km_failure, 4), places=4)

    def test_02_kf_with_competing_deaths_aj_strictly_less_than_km(self):
        """When competing deaths occur, AJ CIF is strictly lower than 1 - S_KM (KM overestimates)."""
        durations = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0])
        # Subject at 1.5 experiences competing death (event code 2)
        event_types = np.array([1, 2, 1, 0, 1, 2, 0])
        horizon = 3.5

        aj_cif, _ = _calculate_aj_cif_and_se_at_horizon(durations, event_types, horizon)

        # Naive cause-specific KM (treating event code 2 as censored):
        # t=1.0: n=7, d1=1 -> S_km = 6/7
        # t=1.5: censored in KM (n=6 -> 5)
        # t=2.0: n=5, d1=1 -> S_km = (6/7) * (4/5) = 24/35
        # t=2.5: censored (n=4 -> 3)
        # t=3.0: n=3, d1=1 -> S_km = (24/35) * (2/3) = 16/35
        # 1 - S_km = 1 - 16/35 = 19/35 = 0.542857
        km_failure = 1.0 - (16.0 / 35.0)

        # Exact Aalen-Johansen CIF:
        # t=1.0: n=7, d1=1, d2=0 -> S_prev=1.0, S=(6/7), cif = 1/7
        # t=1.5: n=6, d1=0, d2=1 -> S_prev=6/7, S=(6/7)*(5/6)=5/7, cif = 1/7
        # t=2.0: n=5, d1=1, d2=0 -> S_prev=5/7, S=(5/7)*(4/5)=4/7, cif = 1/7 + (5/7)*(1/5) = 2/7
        # t=2.5: censored (n=4 -> 3)
        # t=3.0: n=3, d1=1, d2=0 -> S_prev=4/7, S=(4/7)*(2/3)=8/21, cif = 2/7 + (4/7)*(1/3) = 10/21 = 0.476190...
        expected_aj_cif = 10.0 / 21.0

        self.assertAlmostEqual(aj_cif, expected_aj_cif, places=8)
        self.assertLess(aj_cif, km_failure)
        self.assertGreater(km_failure - aj_cif, 0.05)  # Meaningful bias (> 5 percentage points)

    def test_03_competing_risk_vs_cause_specific_quantile_calibration(self):
        """Verify calibration discrepancy: KM falsely reports underprediction when AJ confirms calibration."""
        durations = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0])
        event_types = np.array([1, 2, 1, 2, 1, 0, 0, 1])
        # True CIF is ~0.40. A model predicting 0.40 is well-calibrated.
        pred_cif = np.array([0.40] * len(durations))
        horizon = 3.5

        groups_cr, err_cr = calculate_competing_risk_calibration_by_quantiles(
            durations, event_types, pred_cif, horizon, n_groups=1
        )
        groups_cs, err_cs = calculate_cause_specific_calibration_by_quantiles(
            durations, (event_types == 1).astype(int), pred_cif, horizon, n_groups=1
        )

        obs_cr = groups_cr[0].observed_event_rate
        obs_cs = groups_cs[0].observed_event_rate

        # KM observed rate is higher than AJ CIF because of competing deaths
        self.assertGreater(obs_cs, obs_cr)
        # Calibration error against KM is artificially inflated
        self.assertGreater(err_cs, err_cr)

    def test_04_quantile_grouping_and_monotonicity(self):
        """Quantile calibration groups predictions into ordered risk bins and calculates valid metrics."""
        N = 50
        durations = self.rng.uniform(0.5, 6.0, size=N)
        event_types = self.rng.choice([0, 1, 2], size=N, p=[0.4, 0.4, 0.2])
        # Risk predictions correlated with event 1
        predicted_cifs = np.clip(0.1 + 0.7 * (event_types == 1) + self.rng.normal(0, 0.05, size=N), 0.01, 0.99)

        groups, mean_err = calculate_competing_risk_calibration_by_quantiles(
            durations, event_types, predicted_cifs, horizon_time=3.0, n_groups=5
        )

        self.assertEqual(len(groups), 5)
        # Groups are ordered by predicted risk
        for i in range(len(groups) - 1):
            self.assertLessEqual(groups[i].mean_predicted_risk, groups[i + 1].mean_predicted_risk)

        for g in groups:
            self.assertGreaterEqual(g.observed_event_rate, 0.0)
            self.assertLessEqual(g.observed_event_rate, 1.0)
            self.assertGreaterEqual(g.ci_lower, 0.0)
            self.assertLessEqual(g.ci_upper, 1.0)
            self.assertLessEqual(g.ci_lower, g.observed_event_rate)
            self.assertGreaterEqual(g.ci_upper, g.observed_event_rate)
            self.assertGreater(g.n_patients, 0)

        self.assertGreaterEqual(mean_err, 0.0)

    def test_05_sparse_event_counts_and_zero_events_in_bin(self):
        """Bins with zero kidney failure events produce observed rate 0.0 with CI [0.0, 0.0] without crashing."""
        durations = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        # First 3 have only censoring or competing death, next 3 have events
        event_types = np.array([0, 2, 0, 1, 1, 1])
        predicted_cifs = np.array([0.05, 0.10, 0.15, 0.70, 0.80, 0.90])

        groups, mean_err = calculate_competing_risk_calibration_by_quantiles(
            durations, event_types, predicted_cifs, horizon_time=3.0, n_groups=2
        )

        self.assertEqual(len(groups), 2)
        # Low risk bin has 0 kidney failure events
        low_bin = groups[0]
        self.assertEqual(low_bin.observed_event_rate, 0.0)
        self.assertEqual(low_bin.ci_lower, 0.0)
        self.assertEqual(low_bin.ci_upper, 0.0)
        self.assertEqual(low_bin.expected_to_observed_ratio, 1.0)  # Graceful fallback

    def test_06_right_censoring_before_prediction_horizon(self):
        """Patients right-censored before horizon are included in risk sets without complete-case bias."""
        # 10 patients: 5 censored early (t < 2.0), 5 followed past horizon
        durations = np.array([0.5, 0.8, 1.0, 1.2, 1.5, 3.0, 4.0, 5.0, 5.0, 5.0])
        event_types = np.array([0, 0, 0, 0, 0, 1, 2, 1, 0, 0])
        predicted_cifs = np.array([0.2] * 10)

        groups, _ = calculate_competing_risk_calibration_by_quantiles(
            durations, event_types, predicted_cifs, horizon_time=2.0, n_groups=1
        )
        self.assertEqual(len(groups), 1)
        # No events occurred on or before 2.0
        self.assertEqual(groups[0].observed_event_rate, 0.0)

    def test_07_all_censored_groups_return_zero_without_exceptions(self):
        """Group with all observations censored returns 0.0 observed rate without errors."""
        durations = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        event_types = np.array([0, 0, 0, 0, 0])
        predicted_cifs = np.array([0.1, 0.2, 0.3, 0.4, 0.5])

        groups, mean_err = calculate_competing_risk_calibration_by_quantiles(
            durations, event_types, predicted_cifs, horizon_time=3.0, n_groups=1
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].observed_event_rate, 0.0)
        self.assertEqual(groups[0].ci_lower, 0.0)
        self.assertEqual(groups[0].ci_upper, 0.0)

    def test_08_jackknife_pseudo_observation_identity(self):
        """Jackknife leave-one-out pseudo-values satisfy sum(theta_i)/N == overall_CIF identically."""
        N = 30
        durations = self.rng.uniform(0.5, 8.0, size=N)
        event_types = self.rng.choice([0, 1, 2], size=N, p=[0.3, 0.4, 0.3])
        horizon = 4.0

        overall_cif, _ = _calculate_aj_cif_and_se_at_horizon(durations, event_types, horizon)

        pseudo_obs = []
        for i in range(N):
            d_minus = np.delete(durations, i)
            e_minus = np.delete(event_types, i)
            cif_minus, _ = _calculate_aj_cif_and_se_at_horizon(d_minus, e_minus, horizon)
            theta_i = N * overall_cif - (N - 1) * cif_minus
            pseudo_obs.append(theta_i)

        mean_pseudo = float(np.mean(pseudo_obs))
        self.assertAlmostEqual(mean_pseudo, overall_cif, places=12)

    def test_09_competing_risk_calibration_slope_and_intercept(self):
        """Pseudo-observation regression yields slope ~1.0 and intercept ~0.0 for calibrated predictions."""
        N = 40
        durations = self.rng.uniform(0.5, 6.0, size=N)
        event_types = self.rng.choice([0, 1, 2], size=N, p=[0.3, 0.4, 0.3])
        horizon = 3.0

        overall_cif, _ = _calculate_aj_cif_and_se_at_horizon(durations, event_types, horizon)

        # Generate leave-one-out pseudo-observations
        pseudo_obs = np.empty(N)
        for i in range(N):
            d_minus = np.delete(durations, i)
            e_minus = np.delete(event_types, i)
            cif_minus, _ = _calculate_aj_cif_and_se_at_horizon(d_minus, e_minus, horizon)
            pseudo_obs[i] = N * overall_cif - (N - 1) * cif_minus

        # Test A: perfectly calibrated predictions (aligned with pseudo-observations)
        p_calibrated = pseudo_obs.copy()
        slope, intercept = calculate_competing_risk_calibration_slope_and_intercept(
            durations, event_types, p_calibrated, horizon
        )
        self.assertIsNotNone(slope)
        self.assertIsNotNone(intercept)
        self.assertAlmostEqual(slope, 1.0, places=3)
        self.assertAlmostEqual(intercept, 0.0, places=3)

        # Test B: over-dispersed predictions (multiplied by 1.25 -> slope should be 1/1.25 = 0.80)
        p_overdispersed = 0.02 + 1.25 * pseudo_obs
        slope_od, intercept_od = calculate_competing_risk_calibration_slope_and_intercept(
            durations, event_types, p_overdispersed, horizon
        )
        self.assertIsNotNone(slope_od)
        self.assertAlmostEqual(slope_od, 0.80, places=2)

        # Test C: zero variance in predictions -> returns None, None
        p_flat = np.full(N, 0.30)
        s_flat, i_flat = calculate_competing_risk_calibration_slope_and_intercept(
            durations, event_types, p_flat, horizon
        )
        self.assertIsNone(s_flat)
        self.assertIsNone(i_flat)

    def test_10_invalid_and_edge_case_inputs(self):
        """Input validation catches length mismatches, empty arrays, and small samples."""
        # Length mismatch
        with self.assertRaises(ValueError):
            calculate_competing_risk_calibration_by_quantiles([1.0], [1, 2], [0.5], 2.0)

        # Empty array
        with self.assertRaises(ValueError):
            calculate_competing_risk_calibration_by_quantiles([], [], [], 2.0)

        # Non-positive horizon
        with self.assertRaises(ValueError):
            calculate_competing_risk_calibration_by_quantiles([1.0], [1], [0.5], 0.0)

        # Sample size < n_groups returns empty list
        groups, err = calculate_competing_risk_calibration_by_quantiles([1.0, 2.0], [1, 0], [0.2, 0.8], 2.0, n_groups=5)
        self.assertEqual(groups, [])
        self.assertEqual(err, 0.0)

        # Sample size < 10 for slope/intercept returns None, None
        slope, intercept = calculate_competing_risk_calibration_slope_and_intercept(
            [1.0, 2.0, 3.0], [1, 2, 0], [0.1, 0.2, 0.3], 2.0
        )
        self.assertIsNone(slope)
        self.assertIsNone(intercept)

    def test_11_evaluate_survival_model_estimand_types(self):
        """evaluate_survival_model correctly dispatches between cause_specific and competing_risk estimands."""
        N = 25
        durations = self.rng.uniform(0.5, 5.0, size=N)
        event_types = self.rng.choice([0, 1, 2], size=N, p=[0.3, 0.4, 0.3])
        X = self.rng.normal(0, 1, size=(N, 3))

        def dummy_predictor(x_mat: np.ndarray, h: float) -> np.ndarray:
            return np.clip(0.3 + 0.1 * x_mat[:, 0], 0.05, 0.85)

        # 1. Cause-specific evaluation
        res_cs = evaluate_survival_model(
            model_name="Dummy_CS",
            predict_risk_fn=dummy_predictor,
            X=X,
            durations=durations,
            events=event_types,
            time_horizon_years=2.0,
            estimand_type="cause_specific_survival",
        )
        self.assertEqual(res_cs.estimand_type, "cause_specific_survival")
        self.assertTrue(len(res_cs.calibration_groups) > 0)

        # 2. Competing-risk CIF evaluation
        res_cr = evaluate_survival_model(
            model_name="Dummy_CR",
            predict_risk_fn=dummy_predictor,
            X=X,
            durations=durations,
            events=event_types,
            time_horizon_years=2.0,
            estimand_type="competing_risk_cif",
        )
        self.assertEqual(res_cr.estimand_type, "competing_risk_cif")
        self.assertTrue(len(res_cr.calibration_groups) > 0)

    def test_12_cause_specific_cumulative_incidence_model(self):
        """CauseSpecificCumulativeIncidenceModel integrates cause-specific hazards into personalized CIF."""
        from datetime import date
        from src.clinical.survival.competing_risk import CauseSpecificCumulativeIncidenceModel
        from src.clinical.survival.survival_contracts import (
            SurvivalDataset,
            SurvivalEventType,
            SurvivalLandmarkRecord,
        )

        records = []
        base_d = date(2020, 1, 1)
        lm_d = date(2021, 1, 1)

        for i in range(30):
            # Assign alternating event types (KF, Death, Censored)
            ev = [SurvivalEventType.KIDNEY_FAILURE, SurvivalEventType.COMPETING_DEATH, SurvivalEventType.RIGHT_CENSORED][i % 3]
            kf = 1 if ev == SurvivalEventType.KIDNEY_FAILURE else 0
            death = 1 if ev == SurvivalEventType.COMPETING_DEATH else 0
            cens = 1 if ev == SurvivalEventType.RIGHT_CENSORED else 0
            end_d = date(2022, 1 + (i % 11), 1)

            feats = {
                "age": 50.0 + (i % 25),
                "egfr": 25.0 + (i % 20),
                "uacr": 30.0 + ((i * 37) % 300),
            }
            rec = SurvivalLandmarkRecord(
                patient_id=f"PAT_CIF_{i:02d}",
                landmark_date=lm_d,
                baseline_date=base_d,
                follow_up_start_date=lm_d,
                follow_up_end_date=end_d,
                event_type=ev,
                event_kidney_failure=kf,
                event_death=death,
                is_censored=cens,
                features=feats,
            )
            records.append(rec)

        ds = SurvivalDataset(records)
        model = CauseSpecificCumulativeIncidenceModel(feature_names=["age", "egfr", "uacr"])
        model.fit(ds)

        self.assertTrue(model.is_fitted)
        self.assertIsNotNone(model.model_kf)
        self.assertIsNotNone(model.model_death)

        # Predict personalized CIF for record 0
        pred = model.predict_patient(records[0], time_horizon_years=2.0)
        self.assertGreaterEqual(pred.cif_kidney_failure, 0.0)
        self.assertLessEqual(pred.cif_kidney_failure, 1.0)
        self.assertGreaterEqual(pred.cif_competing_death, 0.0)
        self.assertLessEqual(pred.cif_competing_death, 1.0)
        self.assertLessEqual(pred.cif_kidney_failure + pred.cif_competing_death, 1.0)

        # Crucial competing risk identity: cause-specific net risk >= actual CIF
        self.assertGreaterEqual(pred.cause_specific_net_risk_kf, pred.cif_kidney_failure)
        self.assertAlmostEqual(pred.competing_risk_reduction, pred.cause_specific_net_risk_kf - pred.cif_kidney_failure, places=4)


if __name__ == "__main__":
    unittest.main()
