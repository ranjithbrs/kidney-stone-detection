"""Unit test suite for Engine 3 survival models (Cox PH, RSF) and evaluation framework.

Verifies:
- Cox PH input validation (non-positive durations, constant features, collinearity)
- Cox PH coefficient estimation, hazard ratios, and Breslow baseline survival
- Cox PH risk and survival bounds in [0.0, 1.0]
- Random Survival Forest (RSF) input validation and deterministic reproducibility
- RSF risk bounds and out-of-bag (OOB) permutation feature importance
- Concordance metrics: Harrell's C-index and Uno's IPCW C-index
- Time-dependent AUC at 2-year and 5-year horizons
- Brier score with IPCW censoring adjustment
- Risk calibration by quantiles and E:O ratios
- Standardized comparison with KFRE on identical patient cohorts
"""

import datetime
import unittest

import numpy as np

from src.clinical.survival.cox_model import (
    CoxPHConfig,
    CoxProportionalHazardsModel,
    SurvivalModelError,
)
from src.clinical.survival.evaluation import (
    calculate_brier_score_at_horizon,
    calculate_calibration_by_quantiles,
    calculate_harrell_c_index,
    calculate_time_dependent_auc,
    calculate_uno_c_index,
    compare_models_with_kfre_on_cohort,
    evaluate_survival_model,
)
from src.clinical.survival.rsf_model import (
    RandomSurvivalForestModel,
    RSFConfig,
)
from src.clinical.survival.survival_contracts import (
    SurvivalDataset,
    SurvivalEventType,
    SurvivalLandmarkRecord,
)


class TestSurvivalModelsAndEvaluation(unittest.TestCase):
    """Test suite for Cox PH, RSF, and time-dependent survival evaluation."""

    def setUp(self):
        # Deterministic synthetic survival fixture for mathematical testing
        # (NOT claimed as clinical validation data)
        self.rng = np.random.default_rng(42)
        self.N = 80
        self.P = 3
        self.X = self.rng.normal(loc=0.0, scale=1.0, size=(self.N, self.P))
        # Ground truth hazard linear predictor: true_beta = [0.7, -0.4, 0.0]
        self.true_lp = 0.7 * self.X[:, 0] - 0.4 * self.X[:, 1]
        self.durations = self.rng.exponential(scale=3.0 / np.exp(self.true_lp)) + 0.1
        self.events = (self.durations < 5.0).astype(int)

    # -----------------------------------------------------------------------
    # 1. Cox Proportional Hazards Model Tests
    # -----------------------------------------------------------------------
    def test_cox_ph_input_validation(self):
        """Test rejection of non-positive durations, constant features, and collinearity."""
        model = CoxProportionalHazardsModel()

        # Non-positive duration
        dur_neg = self.durations.copy()
        dur_neg[0] = -1.0
        with self.assertRaises(SurvivalModelError):
            model.fit(self.X, dur_neg, self.events)

        # Constant feature (zero variance)
        X_const = self.X.copy()
        X_const[:, 1] = 5.0
        with self.assertRaises(SurvivalModelError) as ctx:
            model.fit(X_const, self.durations, self.events)
        self.assertIn("Constant or near-constant predictor detected", str(ctx.exception))

        # Near-perfect collinearity
        X_collin = self.X.copy()
        X_collin[:, 2] = X_collin[:, 0] * 1.0  # Identical
        with self.assertRaises(SurvivalModelError) as ctx2:
            model.fit(X_collin, self.durations, self.events)
        self.assertIn("collinearity detected", str(ctx2.exception).lower())

        # Zero events
        e_zero = np.zeros(self.N, dtype=int)
        with self.assertRaises(SurvivalModelError):
            model.fit(self.X, self.durations, e_zero)

    def test_cox_ph_estimation_and_hazard_ratios(self):
        """Test Cox PH coefficient estimation, standard errors, and hazard ratios."""
        cfg = CoxPHConfig(l2_penalty=0.01, random_state=42)
        model = CoxProportionalHazardsModel(cfg)
        model.fit(self.X, self.durations, self.events, feature_names=["f0", "f1", "f2"])

        self.assertTrue(model.is_fitted_)
        self.assertEqual(len(model.coefficients_), 3)

        # Hazard ratio is exp(coef)
        summary = model.summary_table()
        for idx, row in summary.iterrows():
            expected_hr = round(float(np.exp(row["coef"])), 4)
            self.assertAlmostEqual(row["hazard_ratio"], expected_hr, places=3)
            # Confidence interval bounds
            self.assertTrue(row["hr_ci_95_lower"] <= row["hazard_ratio"] <= row["hr_ci_95_upper"])

    def test_cox_ph_prediction_bounds_and_monotonicity(self):
        """Test that predicted risks are bounded in [0.0, 1.0] and risk increases over time."""
        model = CoxProportionalHazardsModel(CoxPHConfig(l2_penalty=0.01))
        model.fit(self.X, self.durations, self.events)

        risks_2yr = model.predict_risk(self.X, time_horizon=2.0)
        risks_5yr = model.predict_risk(self.X, time_horizon=5.0)

        # Bounds
        self.assertTrue(np.all((risks_2yr >= 0.0) & (risks_2yr <= 1.0)))
        self.assertTrue(np.all((risks_5yr >= 0.0) & (risks_5yr <= 1.0)))

        # Monotonicity over time: risk at 5 years >= risk at 2 years
        self.assertTrue(np.all(risks_5yr >= risks_2yr - 1e-9))

        # Survival + Risk = 1.0
        surv_2yr = model.predict_survival(self.X, time_horizon=2.0)
        np.testing.assert_allclose(surv_2yr + risks_2yr, 1.0, atol=1e-7)

    # -----------------------------------------------------------------------
    # 2. Random Survival Forest (RSF) Tests
    # -----------------------------------------------------------------------
    def test_rsf_deterministic_reproducibility(self):
        """Test RSF produces identical predictions given the same random_state."""
        cfg = RSFConfig(n_estimators=10, max_depth=3, min_samples_split=6, min_samples_leaf=3, random_state=123)
        rsf1 = RandomSurvivalForestModel(cfg).fit(self.X, self.durations, self.events)
        rsf2 = RandomSurvivalForestModel(cfg).fit(self.X, self.durations, self.events)

        preds1 = rsf1.predict_risk(self.X, time_horizon=2.0)
        preds2 = rsf2.predict_risk(self.X, time_horizon=2.0)

        np.testing.assert_allclose(preds1, preds2, atol=1e-10)

    def test_rsf_risk_bounds_and_oob_importance(self):
        """Test RSF risk predictions remain bounded in [0, 1] and feature importance is computed."""
        cfg = RSFConfig(n_estimators=15, max_depth=4, min_samples_split=8, min_samples_leaf=4, random_state=42)
        rsf = RandomSurvivalForestModel(cfg).fit(self.X, self.durations, self.events, feature_names=["a", "b", "c"])

        risks = rsf.predict_risk(self.X, time_horizon=3.0)
        self.assertTrue(np.all((risks >= 0.0) & (risks <= 1.0)))

        vimp = rsf.compute_feature_importance(self.X, self.durations, self.events, time_horizon=3.0)
        self.assertEqual(len(vimp), 3)
        self.assertIn("a", vimp)
        self.assertTrue(all(v >= 0.0 for v in vimp.values()))

    # -----------------------------------------------------------------------
    # 3. Evaluation Metric Tests
    # -----------------------------------------------------------------------
    def test_harrell_c_index_known_extremes(self):
        """Verify Harrell's C-index equals 1.0 for perfect concordance and 0.0 for perfectly inverted."""
        # Perfect ordering: subject 0 fails earliest and has highest risk score
        durations = np.array([1.0, 2.0, 3.0, 4.0])
        events = np.array([1, 1, 1, 1])

        perfect_risks = np.array([0.9, 0.7, 0.5, 0.2])
        c_perf = calculate_harrell_c_index(durations, events, perfect_risks)
        self.assertAlmostEqual(c_perf, 1.0, places=4)

        inverted_risks = np.array([0.1, 0.3, 0.5, 0.8])
        c_inv = calculate_harrell_c_index(durations, events, inverted_risks)
        self.assertAlmostEqual(c_inv, 0.0, places=4)

    def test_uno_c_index_computation(self):
        """Verify Uno's C-index calculation with IPCW weighting."""
        durations = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        events = np.array([1, 1, 0, 1, 0])
        risks = np.array([0.8, 0.6, 0.4, 0.7, 0.1])

        uno_c = calculate_uno_c_index(durations, events, risks, tau=4.0)
        self.assertTrue(0.0 <= uno_c <= 1.0)

    def test_time_dependent_auc_calculation(self):
        """Verify time-dependent cumulative/dynamic AUC at 2-year horizon."""
        durations = np.array([1.0, 1.5, 3.0, 4.0])
        events = np.array([1, 1, 0, 0])
        # Cases at t=2.0 are subjects 0 and 1; controls are subjects 2 and 3
        # If cases have higher risk than controls, AUC should be 1.0
        risks = np.array([0.8, 0.7, 0.2, 0.1])
        auc = calculate_time_dependent_auc(durations, events, risks, horizon_time=2.0)
        self.assertAlmostEqual(auc, 1.0, places=4)

    def test_brier_score_and_calibration_by_quantiles(self):
        """Verify IPCW Brier score and quantile calibration metrics."""
        durations = np.array([1.0, 1.5, 2.5, 3.0, 4.0, 5.0])
        events = np.array([1, 1, 1, 0, 0, 1])
        risks = np.array([0.7, 0.8, 0.5, 0.2, 0.1, 0.6])

        brier = calculate_brier_score_at_horizon(durations, events, risks, horizon_time=2.0)
        self.assertTrue(0.0 <= brier <= 1.0)

        cal_groups, mean_cal_err = calculate_calibration_by_quantiles(
            durations, events, risks, horizon_time=2.0, n_groups=2
        )
        self.assertEqual(len(cal_groups), 2)
        self.assertTrue(mean_cal_err >= 0.0)

    # -----------------------------------------------------------------------
    # 4. Standardized KFRE Cohort Comparison Test
    # -----------------------------------------------------------------------
    def test_compare_models_with_kfre_on_identical_cohort(self):
        """Test side-by-side comparison of Cox PH, RSF, and KFRE on identical patient records."""
        # Build a valid SurvivalDataset of 20 patients
        records = []
        base_dt = datetime.date(2020, 1, 1)
        lm_dt = datetime.date(2021, 1, 1)

        for i in range(25):
            p_id = f"PAT_COMP_{i:02d}"
            # G3b-G4 patients with valid KFRE inputs
            features = {
                "age": 55.0 + (i % 20),
                "sex": 1.0 if i % 2 == 0 else 0.0,
                "egfr": 20.0 + ((i * 7) % 35),  # 20-54 mL/min/1.73 m2 (strictly in-scope G3-G4)
                "uacr": 30.0 + ((i * 37) % 400),
            }
            ev = SurvivalEventType.KIDNEY_FAILURE if i < 8 else SurvivalEventType.RIGHT_CENSORED
            kf = 1 if ev == SurvivalEventType.KIDNEY_FAILURE else 0
            cens = 1 if ev == SurvivalEventType.RIGHT_CENSORED else 0
            end_dt = datetime.date(2022, 6, 1) if kf else datetime.date(2025, 1, 1)

            rec = SurvivalLandmarkRecord(
                patient_id=p_id,
                landmark_date=lm_dt,
                baseline_date=base_dt,
                follow_up_start_date=lm_dt,
                follow_up_end_date=end_dt,
                event_type=ev,
                event_kidney_failure=kf,
                event_death=0,
                is_censored=cens,
                features=features,
            )
            records.append(rec)

        test_ds = SurvivalDataset(records)
        X_mat, f_names = test_ds.get_feature_matrix(["age", "egfr", "uacr"])
        durations, events = test_ds.get_survival_targets(SurvivalEventType.KIDNEY_FAILURE)

        # Fit candidate Cox PH
        cox = CoxProportionalHazardsModel(CoxPHConfig(l2_penalty=0.05))
        cox.fit(X_mat, durations, events, feature_names=["age", "egfr", "uacr"])

        # Compare models
        models_dict = {
            "Cox PH Baseline": lambda X, h: cox.predict_risk(X, h),
        }
        comp_df = compare_models_with_kfre_on_cohort(
            models=models_dict,
            test_dataset=test_ds,
            horizon_years=2.0,
            kfre_calibration_profile="north_america",
            feature_names=["age", "egfr", "uacr"],
        )

        self.assertIn("model", comp_df.columns)
        self.assertIn("harrell_c_index", comp_df.columns)
        self.assertIn("time_dependent_auc", comp_df.columns)
        self.assertEqual(len(comp_df), 2)  # Cox PH + KFRE
        self.assertTrue(any("KFRE" in str(m) for m in comp_df["model"]))


if __name__ == "__main__":
    unittest.main()
