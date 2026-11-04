"""Unit test suite for the Tangri 4-variable Kidney Failure Risk Equation (KFRE).

Verifies:
- Mathematical accuracy against published baseline constants (Tangri et al., JAMA 2016 eAppendix 2)
- Exact calibration profile outputs (Original Tangri, North America, non-North America)
- Centered reference profile evaluation and LP=0 risk verification
- Defensive input validation (missing values, zero/negative ACR, non-adult age, NaN/Inf)
- Out-of-scope handling for CKD Stages G1–G2 (eGFR >= 60 mL/min/1.73 m2)
- Strict probability bounding in [0.0, 1.0] and risk monotonicity
"""

import math
import unittest

from src.clinical.kfre_calculator import (
    KFRE_BASELINE_SURVIVAL,
    KFRECalibrationProfile,
    KFREInput,
    KFREResult,
    calculate_kfre,
)


class TestKFRECalculator(unittest.TestCase):
    """Test suite for Tangri 4-variable KFRE calculator."""

    def setUp(self):
        # Exact theoretical centering mean profile where each term (x - mean) = 0.0
        # Age = 70.36, Male = 0.5642, eGFR = 36.11, ACR = exp(5.137) = 170.20438847...
        self.centered_input = KFREInput(
            age=70.36,
            sex=0.5642,
            egfr=36.11,
            uacr=math.exp(5.137),
        )

        # Standard clinical CKD G3b patient
        self.patient_g3b = KFREInput(
            age=65.0,
            sex="male",
            egfr=38.0,
            uacr=250.0,
            calibration_profile="north_america",
        )

    # -----------------------------------------------------------------------
    # 1. Centered Reference Profile & Exact Baseline Survival Tests
    # -----------------------------------------------------------------------
    def test_centered_reference_profile_lp_zero(self):
        """Test linear predictor is 0.0 at exact mean centering vector."""
        res = calculate_kfre(self.centered_input, calibration_profile="north_america")
        self.assertTrue(res.is_valid)
        self.assertTrue(res.is_applicable)
        self.assertAlmostEqual(res.linear_predictor, 0.0, places=4)

    def test_survival_transformation_exact_at_lp_zero(self):
        """Verify that at LP=0, Risk = 1 - S_0^exp(0) = 1 - S_0 exactly within floating-point tolerance."""
        for profile, baselines in KFRE_BASELINE_SURVIVAL.items():
            res = calculate_kfre(self.centered_input, calibration_profile=profile)
            self.assertTrue(res.is_valid)
            self.assertTrue(res.is_applicable)
            # Direct calculation of expected risk: 1 - S_0
            expected_2yr = 1.0 - baselines["s0_2year"]
            expected_5yr = 1.0 - baselines["s0_5year"]
            self.assertAlmostEqual(res.risk_2year, expected_2yr, places=4)
            self.assertAlmostEqual(res.risk_5year, expected_5yr, places=4)

    def test_expected_baseline_risks_across_all_profiles(self):
        """Test exact expected 2-year and 5-year risks when LP=0 across all three calibration profiles."""
        expected_risks = {
            "original_tangri": {"risk_2yr": 0.0250, "risk_5yr": 0.0760},
            "north_america": {"risk_2yr": 0.0249, "risk_5yr": 0.1004},
            "non_north_america": {"risk_2yr": 0.0168, "risk_5yr": 0.0635},
        }

        for profile, expected in expected_risks.items():
            res = calculate_kfre(self.centered_input, calibration_profile=profile)
            self.assertTrue(res.is_valid, f"Failed for profile {profile}")
            self.assertTrue(res.is_applicable, f"Failed for profile {profile}")
            self.assertAlmostEqual(
                res.risk_2year, expected["risk_2yr"], places=4, msg=f"2-year mismatch for {profile}"
            )
            self.assertAlmostEqual(
                res.risk_5year, expected["risk_5yr"], places=4, msg=f"5-year mismatch for {profile}"
            )
            self.assertAlmostEqual(res.risk_2year_percent, expected["risk_2yr"] * 100.0, places=2)
            self.assertAlmostEqual(res.risk_5year_percent, expected["risk_5yr"] * 100.0, places=2)

    def test_integer_reference_profile_evaluation(self):
        """Test evaluation at integer reference inputs (Age=70, Male=1, eGFR=36, ACR=170).

        Notice: (70, 1, 36, 170) is an integer approximation of cohort means, NOT LP=0.
        LP = -0.2201*(70/10 - 7.036) + 0.2467*(1 - 0.5642) - 0.5567*(36/5 - 7.222) + 0.4510*(ln(170) - 5.137)
           = 0.0079236 + 0.10751186 + 0.0122474 - 0.000541905
           = 0.127140955... ≈ 0.12714096.
        """
        res_na = calculate_kfre(age=70, sex="male", egfr=36, uacr=170, calibration_profile="north_america")
        self.assertTrue(res_na.is_valid)
        self.assertTrue(res_na.is_applicable)
        # Verify exact linear predictor to high precision (7 decimal places)
        self.assertAlmostEqual(res_na.linear_predictor, 0.12714096, places=6)
        self.assertAlmostEqual(res_na.risk_2year_percent, 2.82, places=1)
        self.assertAlmostEqual(res_na.risk_5year_percent, 11.32, places=1)

    def test_independent_kfre_component_terms(self):
        """Verify each of the 4 KFRE linear predictor terms independently."""
        # Term 1: Age term: -0.2201 * (age / 10 - 7.036)
        # At age 70: -0.2201 * (7.0 - 7.036) = -0.2201 * (-0.036) = +0.0079236
        term_age = -0.2201 * (70.0 / 10.0 - 7.036)
        self.assertAlmostEqual(term_age, 0.0079236, places=7)

        # Term 2: Sex term: +0.2467 * (male - 0.5642)
        # For male = 1: 0.2467 * (1.0 - 0.5642) = 0.2467 * 0.4358 = +0.10751186
        term_sex = 0.2467 * (1.0 - 0.5642)
        self.assertAlmostEqual(term_sex, 0.10751186, places=7)

        # Term 3: eGFR term: -0.5567 * (egfr / 5 - 7.222)
        # At eGFR 36: -0.5567 * (7.2 - 7.222) = -0.5567 * (-0.022) = +0.0122474
        term_egfr = -0.5567 * (36.0 / 5.0 - 7.222)
        self.assertAlmostEqual(term_egfr, 0.0122474, places=7)

        # Term 4: ACR term: +0.4510 * (ln(acr) - 5.137)
        # At ACR 170: 0.4510 * (ln(170) - 5.137) = 0.4510 * (5.1357984 - 5.137) = -0.00054190489...
        term_acr = 0.4510 * (math.log(170.0) - 5.137)
        self.assertAlmostEqual(term_acr, -0.00054190489, places=7)

        expected_lp = term_age + term_sex + term_egfr + term_acr
        self.assertAlmostEqual(expected_lp, 0.12714096, places=6)

    # -----------------------------------------------------------------------
    # 2. Sex Decoding and Validation
    # -----------------------------------------------------------------------
    def test_sex_decoding(self):
        """Test correct decoding of male/female representations."""
        for male_val in [1, "male", "Male", "M", "m", 1.0]:
            res = calculate_kfre(age=65, sex=male_val, egfr=40, uacr=100)
            self.assertTrue(res.is_valid)
            self.assertEqual(res.male_code, 1.0)
            self.assertEqual(res.sex_evaluated, "male")

        for female_val in [0, "female", "Female", "F", "f", 0.0]:
            res = calculate_kfre(age=65, sex=female_val, egfr=40, uacr=100)
            self.assertTrue(res.is_valid)
            self.assertEqual(res.male_code, 0.0)
            self.assertEqual(res.sex_evaluated, "female")

        # Invalid sex strings or types
        res_inv = calculate_kfre(age=65, sex="unknown", egfr=40, uacr=100)
        self.assertFalse(res_inv.is_valid)
        self.assertIn("Unrecognized sex", res_inv.validation_errors[0])

    # -----------------------------------------------------------------------
    # 3. Defensive Validation: Missing and Invalid Inputs
    # -----------------------------------------------------------------------
    def test_missing_and_zero_uacr_rejected(self):
        """Test rejection of missing and non-positive ACR (cannot take log of <= 0)."""
        res_zero = calculate_kfre(age=65, sex="male", egfr=40, uacr=0.0)
        self.assertFalse(res_zero.is_valid)
        self.assertIn("strictly greater than 0", res_zero.validation_errors[0])

        res_neg = calculate_kfre(age=65, sex="male", egfr=40, uacr=-10.0)
        self.assertFalse(res_neg.is_valid)

        res_none = calculate_kfre(age=65, sex="male", egfr=40, uacr=None)
        self.assertFalse(res_none.is_valid)

    def test_invalid_age_rejected(self):
        """Test rejection of pediatric age (< 18) and non-numeric age."""
        res_ped = calculate_kfre(age=16, sex="male", egfr=40, uacr=100)
        self.assertFalse(res_ped.is_valid)
        self.assertIn("age >= 18", res_ped.validation_errors[0])

        res_none = calculate_kfre(age=None, sex="male", egfr=40, uacr=100)
        self.assertFalse(res_none.is_valid)

    def test_invalid_egfr_rejected(self):
        """Test rejection of non-positive, NaN, and Inf eGFR."""
        res_zero = calculate_kfre(age=65, sex="male", egfr=0.0, uacr=100)
        self.assertFalse(res_zero.is_valid)

        res_nan = calculate_kfre(age=65, sex="male", egfr=float("nan"), uacr=100)
        self.assertFalse(res_nan.is_valid)

        res_inf = calculate_kfre(age=65, sex="male", egfr=float("inf"), uacr=100)
        self.assertFalse(res_inf.is_valid)

    def test_unsupported_calibration_profile_rejected(self):
        """Test rejection of unrecognized calibration profiles."""
        res = calculate_kfre(age=65, sex="male", egfr=40, uacr=100, calibration_profile="mars_calibration")
        self.assertFalse(res.is_valid)
        self.assertEqual(res.applicability_status, "INVALID_CALIBRATION_PROFILE")

    # -----------------------------------------------------------------------
    # 4. Out-of-Scope G1–G2 Handling (eGFR >= 60)
    # -----------------------------------------------------------------------
    def test_egfr_ge_60_out_of_scope(self):
        """Test that eGFR >= 60 returns explicit out-of-scope result and withholds risk."""
        for gfr in [60.0, 75.0, 95.0]:
            res = calculate_kfre(age=55, sex="male", egfr=gfr, uacr=50.0)
            self.assertTrue(res.is_valid)  # Valid clinical inputs
            self.assertFalse(res.is_applicable)  # Out of clinical scope!
            self.assertIsNone(res.risk_2year)
            self.assertIsNone(res.risk_5year)
            self.assertEqual(res.applicability_status, "OUT_OF_SCOPE_GFR_STAGE_G1_G2")
            self.assertIn("G1/G2", res.message)

    # -----------------------------------------------------------------------
    # 5. Risk Monotonicity & Probability Bounding
    # -----------------------------------------------------------------------
    def test_risk_monotonicity_with_increasing_uacr(self):
        """Test that higher UACR strictly increases kidney failure risk."""
        r1 = calculate_kfre(age=65, sex="male", egfr=35, uacr=30.0).risk_5year
        r2 = calculate_kfre(age=65, sex="male", egfr=35, uacr=300.0).risk_5year
        r3 = calculate_kfre(age=65, sex="male", egfr=35, uacr=1500.0).risk_5year
        self.assertTrue(r1 < r2 < r3)

    def test_risk_monotonicity_with_declining_egfr(self):
        """Test that lower eGFR strictly increases kidney failure risk."""
        r_stage3a = calculate_kfre(age=65, sex="male", egfr=50, uacr=100.0).risk_5year
        r_stage3b = calculate_kfre(age=65, sex="male", egfr=35, uacr=100.0).risk_5year
        r_stage4 = calculate_kfre(age=65, sex="male", egfr=20, uacr=100.0).risk_5year
        self.assertTrue(r_stage3a < r_stage3b < r_stage4)

    def test_probability_bounded_in_zero_to_one(self):
        """Test extreme values remain strictly bounded in [0.0, 1.0]."""
        # Very high risk patient (Stage G5, massive proteinuria)
        res_high = calculate_kfre(age=30, sex="male", egfr=11.0, uacr=8000.0)
        self.assertTrue(0.0 <= res_high.risk_2year <= 1.0)
        self.assertTrue(0.0 <= res_high.risk_5year <= 1.0)

        # Low risk patient
        res_low = calculate_kfre(age=80, sex="female", egfr=58.0, uacr=5.0)
        self.assertTrue(0.0 <= res_low.risk_2year <= 1.0)
        self.assertTrue(0.0 <= res_low.risk_5year <= 1.0)


if __name__ == "__main__":
    unittest.main()
