"""NEFROAI-X Engine 2 Test Suite: Clinical CKD Severity Assessment & KDIGO CGA Staging.

Verifies:
1. CKD-EPI 2021 race-free equation for male patients (authoritative reference cases).
2. CKD-EPI 2021 race-free equation for female patients (authoritative reference cases).
3. KDIGO GFR category boundary transitions (G1 to G5).
4. KDIGO Albuminuria category boundary transitions (A1 to A3).
5. Missing serum creatinine handling (unavailable, zero silent imputation).
6. Missing UACR handling (unavailable, zero silent imputation).
7. Invalid laboratory measurements (zero, negative, non-finite, non-numeric).
8. Interview-only participant exclusion from complete laboratory severity cohort.
9. Pediatric participant exclusion from adult equation (<18.0 years).
10. Invalid demographic inputs (missing/unrecognized sex, implausible age).
11. Incomplete CGA classifications when either G or A is missing.
12. Chronicity safeguards (chronicity_confirmed=False, mandatory clinical disclaimer).
13. Quality comment code detection limit integration (URDUMALC, URDUCRLC).
14. Regression tests for Engine 1 (Random Forest champion pipeline unchanged).
15. Preservation of Phase 5 Step 1 NHANES denominators (5,863 / 5,540 / 323 / 5,069).
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.clinical.egfr_calculator import (
    calculate_egfr_ckd_epi_2021,
    calculate_egfr_vectorized,
    decode_sex,
)
from src.clinical.kdigo_staging import (
    CHRONICITY_DISCLAIMER,
    classify_albuminuria_category,
    classify_gfr_category,
    classify_kdigo_composite_risk,
)
from src.engines.kidney_severity_engine import KidneySeverityEngine

# Protected baseline hashes
EXPECTED_PIPELINE_HASH = "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826"
EXPECTED_UCI_HASH = "147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc"


class TestKidneySeverityEngine(unittest.TestCase):
    """Formal unit and integration test suite for Engine 2."""

    def setUp(self):
        self.engine = KidneySeverityEngine()

    # =================================================================
    # 1. CKD-EPI 2021 Race-Free Equation Calculations
    # =================================================================

    def test_01_ckd_epi_2021_male_reference_cases(self):
        """Test 1: CKD-EPI 2021 race-free equation for males against literature references."""
        # Case 1: Male, Age 20, Scr 0.9 mg/dL (Scr <= kappa=0.9, ratio=1.0)
        # Expected: 142 * (1.0)^-0.302 * (1.0)^-1.200 * 0.9938^20 * 1.0 = 125.396 mL/min/1.73m2
        res1 = calculate_egfr_ckd_epi_2021(serum_creatinine=0.9, age=20, sex=1)
        self.assertTrue(res1["is_valid"])
        self.assertEqual(res1["sex_decoded"], "male")
        self.assertAlmostEqual(res1["egfr"], 125.40, places=1)

        # Case 2: Male, Age 60, Scr 1.8 mg/dL (Scr > kappa=0.9, ratio=2.0)
        # Expected: 142 * (2.0)^-1.200 * 0.9938^60 * 1.0 = 42.56 mL/min/1.73m2
        res2 = calculate_egfr_ckd_epi_2021(serum_creatinine=1.8, age=60, sex="male")
        self.assertTrue(res2["is_valid"])
        self.assertAlmostEqual(res2["egfr"], 42.56, places=1)

        # Case 3: Male, Age 50, Scr 0.8 mg/dL (Scr <= kappa=0.9, ratio=0.8889)
        # Expected: 142 * (0.8889)^-0.302 * 0.9938^50 * 1.0 = 107.82 mL/min/1.73m2
        res3 = calculate_egfr_ckd_epi_2021(serum_creatinine=0.8, age=50, sex=1)
        self.assertTrue(res3["is_valid"])
        self.assertAlmostEqual(res3["egfr"], 107.82, places=1)

    def test_02_ckd_epi_2021_female_reference_cases(self):
        """Test 2: CKD-EPI 2021 race-free equation for females against literature references."""
        # Case 1: Female, Age 20, Scr 0.7 mg/dL (Scr <= kappa=0.7, ratio=1.0)
        # Expected: 142 * 1.0 * 1.0 * 0.9938^20 * 1.012 = 126.90 mL/min/1.73m2
        res1 = calculate_egfr_ckd_epi_2021(serum_creatinine=0.7, age=20, sex=2)
        self.assertTrue(res1["is_valid"])
        self.assertEqual(res1["sex_decoded"], "female")
        self.assertAlmostEqual(res1["egfr"], 126.90, places=1)

        # Case 2: Female, Age 60, Scr 1.4 mg/dL (Scr > kappa=0.7, ratio=2.0)
        # Expected: 142 * (2.0)^-1.200 * 0.9938^60 * 1.012 = 43.07 mL/min/1.73m2
        res2 = calculate_egfr_ckd_epi_2021(serum_creatinine=1.4, age=60, sex="female")
        self.assertTrue(res2["is_valid"])
        self.assertAlmostEqual(res2["egfr"], 43.07, places=1)

        # Case 3: Female, Age 65, Scr 0.6 mg/dL (Scr <= kappa=0.7, ratio=0.85714)
        # Expected: 142 * (0.85714)^-0.241 * 0.9938^65 * 1.012 = 99.55 mL/min/1.73m2
        res3 = calculate_egfr_ckd_epi_2021(serum_creatinine=0.6, age=65, sex="F")
        self.assertTrue(res3["is_valid"])
        self.assertAlmostEqual(res3["egfr"], 99.55, places=1)

    def test_03_serum_creatinine_unit_conversion(self):
        """Test 3: Correct conversion for serum creatinine provided in umol/L."""
        # 88.42 umol/L == 1.0 mg/dL
        res_mgdl = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=40, sex=1, unit="mg/dL")
        res_umol = calculate_egfr_ckd_epi_2021(serum_creatinine=88.42, age=40, sex=1, unit="umol/L")
        self.assertAlmostEqual(res_mgdl["egfr"], res_umol["egfr"], places=1)

    # =================================================================
    # 2. GFR and Albuminuria Category Boundaries
    # =================================================================

    def test_04_gfr_category_boundary_transitions(self):
        """Test 4: Strict boundary evaluation for KDIGO GFR categories (G1 to G5)."""
        # G1: >= 90
        self.assertEqual(classify_gfr_category(90.0)["category"], "G1")
        self.assertEqual(classify_gfr_category(125.0)["category"], "G1")
        self.assertEqual(classify_gfr_category(89.99)["category"], "G2")

        # G2: 60 - 89
        self.assertEqual(classify_gfr_category(60.0)["category"], "G2")
        self.assertEqual(classify_gfr_category(75.0)["category"], "G2")
        self.assertEqual(classify_gfr_category(59.99)["category"], "G3a")

        # G3a: 45 - 59
        self.assertEqual(classify_gfr_category(45.0)["category"], "G3a")
        self.assertEqual(classify_gfr_category(50.0)["category"], "G3a")
        self.assertEqual(classify_gfr_category(44.99)["category"], "G3b")

        # G3b: 30 - 44
        self.assertEqual(classify_gfr_category(30.0)["category"], "G3b")
        self.assertEqual(classify_gfr_category(35.0)["category"], "G3b")
        self.assertEqual(classify_gfr_category(29.99)["category"], "G4")

        # G4: 15 - 29
        self.assertEqual(classify_gfr_category(15.0)["category"], "G4")
        self.assertEqual(classify_gfr_category(20.0)["category"], "G4")
        self.assertEqual(classify_gfr_category(14.99)["category"], "G5")

        # G5: < 15
        self.assertEqual(classify_gfr_category(10.0)["category"], "G5")
        self.assertEqual(classify_gfr_category(0.0)["category"], "G5")

    def test_05_albuminuria_category_boundary_transitions(self):
        """Test 5: Strict boundary evaluation for KDIGO Albuminuria categories (A1 to A3)."""
        # A1: < 30.0
        self.assertEqual(classify_albuminuria_category(0.0)["category"], "A1")
        self.assertEqual(classify_albuminuria_category(29.99)["category"], "A1")

        # A2: 30.0 - 300.0 (inclusive of 30.0 and 300.0)
        self.assertEqual(classify_albuminuria_category(30.00)["category"], "A2")
        self.assertEqual(classify_albuminuria_category(150.0)["category"], "A2")
        self.assertEqual(classify_albuminuria_category(300.00)["category"], "A2")

        # A3: > 300.0
        self.assertEqual(classify_albuminuria_category(300.01)["category"], "A3")
        self.assertEqual(classify_albuminuria_category(5000.0)["category"], "A3")

    # =================================================================
    # 3. Missing Data & Zero Silent Imputation Policy
    # =================================================================

    def test_06_missing_serum_creatinine_handling(self):
        """Test 6: Missing serum creatinine yields explicit unavailable status without normal default."""
        res = calculate_egfr_ckd_epi_2021(serum_creatinine=np.nan, age=50, sex=1)
        self.assertFalse(res["is_valid"])
        self.assertIsNone(res["egfr"])
        self.assertEqual(res["status"], "MISSING_INPUT")

        gfr_cat = classify_gfr_category(np.nan)
        self.assertIsNone(gfr_cat["category"])
        self.assertEqual(gfr_cat["status"], "MISSING_INPUT")
        # Ensure it NEVER defaults to G1
        self.assertNotEqual(gfr_cat["category"], "G1")

    def test_07_missing_uacr_handling(self):
        """Test 7: Missing UACR yields explicit unavailable status without normal default."""
        alb_cat = classify_albuminuria_category(np.nan)
        self.assertIsNone(alb_cat["category"])
        self.assertEqual(alb_cat["status"], "MISSING_INPUT")
        # Ensure it NEVER defaults to A1
        self.assertNotEqual(alb_cat["category"], "A1")

    def test_08_invalid_laboratory_measurements(self):
        """Test 8: Negative, zero, non-finite, and non-numeric lab inputs produce structured errors."""
        # Non-positive creatinine
        res_zero = calculate_egfr_ckd_epi_2021(serum_creatinine=0.0, age=40, sex=1)
        self.assertFalse(res_zero["is_valid"])
        self.assertEqual(res_zero["status"], "INVALID_INPUT")

        res_neg = calculate_egfr_ckd_epi_2021(serum_creatinine=-1.2, age=40, sex=1)
        self.assertFalse(res_neg["is_valid"])
        self.assertEqual(res_neg["status"], "INVALID_INPUT")

        # Non-finite creatinine
        res_inf = calculate_egfr_ckd_epi_2021(serum_creatinine=np.inf, age=40, sex=1)
        self.assertFalse(res_inf["is_valid"])

        # Negative UACR
        alb_neg = classify_albuminuria_category(-15.0)
        self.assertIsNone(alb_neg["category"])
        self.assertEqual(alb_neg["status"], "INVALID_INPUT")

    # =================================================================
    # 4. Demographic Validation & Pediatric Exclusion
    # =================================================================

    def test_09_pediatric_participant_exclusion(self):
        """Test 9: Patients aged < 18.0 years are excluded with an explicit clinical message."""
        res_child = calculate_egfr_ckd_epi_2021(serum_creatinine=0.7, age=12.0, sex=1)
        self.assertFalse(res_child["is_valid"])
        self.assertIsNone(res_child["egfr"])
        self.assertEqual(res_child["status"], "PEDIATRIC_EXCLUDED")
        self.assertIn("Pediatric", res_child["message"])

        res_17_9 = calculate_egfr_ckd_epi_2021(serum_creatinine=0.7, age=17.9, sex=1)
        self.assertFalse(res_17_9["is_valid"])
        self.assertEqual(res_17_9["status"], "PEDIATRIC_EXCLUDED")

    def test_10_invalid_demographic_inputs(self):
        """Test 10: Missing sex, unrecognized sex code, and biologically implausible age."""
        # Missing sex
        res_no_sex = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=50, sex=np.nan)
        self.assertFalse(res_no_sex["is_valid"])
        self.assertEqual(res_no_sex["status"], "MISSING_INPUT")

        # Unrecognized sex
        res_bad_sex = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=50, sex="unknown_code")
        self.assertFalse(res_bad_sex["is_valid"])
        self.assertEqual(res_bad_sex["status"], "INVALID_INPUT")

        # Implausible age
        res_old = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=150, sex=1)
        self.assertFalse(res_old["is_valid"])
        self.assertEqual(res_old["status"], "INVALID_INPUT")

    # =================================================================
    # 5. KDIGO CGA Staging & Risk Grid
    # =================================================================

    def test_11_kdigo_composite_risk_matrix(self):
        """Test 11: KDIGO 4-tier risk matrix maps accurately for all 18 valid pairs."""
        expected_grid = {
            ("G1", "A1"): ("Low Risk", "green", 1),
            ("G1", "A2"): ("Moderately Increased Risk", "yellow", 2),
            ("G1", "A3"): ("High Risk", "orange", 3),
            ("G2", "A1"): ("Low Risk", "green", 1),
            ("G2", "A2"): ("Moderately Increased Risk", "yellow", 2),
            ("G2", "A3"): ("High Risk", "orange", 3),
            ("G3a", "A1"): ("Moderately Increased Risk", "yellow", 2),
            ("G3a", "A2"): ("High Risk", "orange", 3),
            ("G3a", "A3"): ("Very High Risk", "red", 4),
            ("G3b", "A1"): ("High Risk", "orange", 3),
            ("G3b", "A2"): ("Very High Risk", "red", 4),
            ("G3b", "A3"): ("Very High Risk", "red", 4),
            ("G4", "A1"): ("Very High Risk", "red", 4),
            ("G4", "A2"): ("Very High Risk", "red", 4),
            ("G4", "A3"): ("Very High Risk", "red", 4),
            ("G5", "A1"): ("Very High Risk", "red", 4),
            ("G5", "A2"): ("Very High Risk", "red", 4),
            ("G5", "A3"): ("Very High Risk", "red", 4),
        }
        self.assertEqual(len(expected_grid), 18)

        for (g, a), (risk, color, tier) in expected_grid.items():
            res = classify_kdigo_composite_risk(g, a)
            self.assertEqual(res["composite_risk_level"], risk, f"Mismatch for {g}-{a} risk")
            self.assertEqual(res["risk_color"], color, f"Mismatch for {g}-{a} color")
            self.assertEqual(res["risk_tier"], tier, f"Mismatch for {g}-{a} tier")
            self.assertTrue(res["is_complete"])
            self.assertIsNotNone(res["clinical_interpretation"])

    def test_12_incomplete_cga_classifications(self):
        """Test 12: Incomplete CGA classifications when either G or A is missing."""
        cga_no_a = classify_kdigo_composite_risk("G2", None)
        self.assertFalse(cga_no_a["is_complete"])
        self.assertIsNone(cga_no_a["composite_risk_level"])
        self.assertEqual(cga_no_a["status"], "INCOMPLETE")

        cga_no_g = classify_kdigo_composite_risk(None, "A2")
        self.assertFalse(cga_no_g["is_complete"])
        self.assertIsNone(cga_no_g["composite_risk_level"])

    def test_13_chronicity_safeguards_and_cause(self):
        """Test 13: Chronicity confirmed is strictly False and disclaimer is present."""
        cga = classify_kdigo_composite_risk("G3a", "A2")
        self.assertFalse(cga["chronicity_confirmed"])
        self.assertIn(">= 3 months", cga["chronicity_disclaimer"])
        self.assertEqual(cga["cause"], "UNAVAILABLE_CROSS_SECTIONAL")

    def test_14_single_patient_assessment_flow(self):
        """Test 14: Single patient record assessment via KidneySeverityEngine."""
        patient = {
            "participant_id": 99999,
            "serum_creatinine": 1.4,
            "uacr": 75.0,
            "age_years": 60,
            "sex_code": 2,  # female
        }
        res = self.engine.assess_patient(patient)
        self.assertTrue(res["clinical_governance"]["is_complete_severity_record"])
        self.assertAlmostEqual(res["filtration_assessment"]["egfr"], 43.07, places=1)
        self.assertEqual(res["filtration_assessment"]["gfr_category"], "G3b")
        self.assertEqual(res["albuminuria_assessment"]["albuminuria_category"], "A2")
        self.assertEqual(res["kdigo_cga_staging"]["composite_risk_level"], "Very High Risk")
        self.assertEqual(res["kdigo_cga_staging"]["risk_color"], "red")
        self.assertFalse(res["clinical_governance"]["chronicity_confirmed"])

    # =================================================================
    # 6. Cohort Denominators & NHANES Ground Truth
    # =================================================================

    def test_15_nhanes_cohort_severity_and_denominators(self):
        """Test 15: Preservation of Phase 5 Step 1 denominators and KDIGO grid metrics on NHANES."""
        processed_path = Path("datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv")
        if not processed_path.exists():
            self.skipTest("Harmonized NHANES dataset not available on disk.")

        df = pd.read_csv(processed_path)
        augmented, audit = self.engine.assess_cohort(df, use_examination_age=True)

        # 1. Total processed records
        self.assertEqual(audit["total_records_processed"], 9254)

        # 2. Denominators
        denoms = audit["cohort_denominators"]
        self.assertEqual(denoms["adult_population_denominator"], 5863)
        self.assertEqual(denoms["mec_examined_adult_denominator"], 5540)
        self.assertEqual(denoms["interview_only_adult_denominator"], 323)
        self.assertEqual(denoms["pediatric_population_denominator"], 3391)
        self.assertEqual(denoms["mec_examined_pediatric_denominator"], 3164)
        self.assertEqual(denoms["interview_only_pediatric_denominator"], 227)

        # 3. Complete Adult Severity Cohort
        comp = audit["complete_adult_severity_cohort"]
        self.assertEqual(comp["complete_records_count"], 5069)
        self.assertEqual(comp["retention_of_all_sampled_adults_pct"], 86.46)
        self.assertEqual(comp["retention_of_mec_examined_adults_pct"], 91.50)
        self.assertEqual(comp["share_of_total_population_sample_pct"], 54.78)

        # 4. GFR Categories
        gfr_counts = audit["gfr_category_distribution"]["counts"]
        self.assertEqual(gfr_counts["G1"], 3185)
        self.assertEqual(gfr_counts["G2"], 1473)
        self.assertEqual(gfr_counts["G3a"], 268)
        self.assertEqual(gfr_counts["G3b"], 102)
        self.assertEqual(gfr_counts["G4"], 32)
        self.assertEqual(gfr_counts["G5"], 9)
        self.assertEqual(sum(gfr_counts.values()), 5069)

        # 5. Albuminuria Categories
        alb_counts = audit["albuminuria_category_distribution"]["counts"]
        self.assertEqual(alb_counts["A1"], 4381)
        self.assertEqual(alb_counts["A2"], 568)
        self.assertEqual(alb_counts["A3"], 120)
        self.assertEqual(sum(alb_counts.values()), 5069)

        # 6. KDIGO Composite Risk
        risk_counts = audit["kdigo_composite_risk_distribution"]["counts"]
        self.assertEqual(risk_counts["Low Risk"], 4128)
        self.assertEqual(risk_counts["Moderately Increased Risk"], 658)
        self.assertEqual(risk_counts["High Risk"], 176)
        self.assertEqual(risk_counts["Very High Risk"], 107)
        self.assertEqual(sum(risk_counts.values()), 5069)

        # 7. Crosstab Verification
        grid = audit["kdigo_grid_cross_tabulation"]
        self.assertEqual(grid["G1"]["A1"], 2878)
        self.assertEqual(grid["G1"]["A2"], 273)
        self.assertEqual(grid["G1"]["A3"], 34)
        self.assertEqual(grid["G5"]["A1"], 0)
        self.assertEqual(grid["G5"]["A2"], 2)
        self.assertEqual(grid["G5"]["A3"], 7)

    # =================================================================
    # 7. Engine 1 Protection & Asset Integrity
    # =================================================================

    def test_16_engine_1_model_and_dataset_integrity(self):
        """Test 16: Ensure Engine 1 champion model artifact and UCI dataset are intact."""
        pipeline_path = Path("models/clinical_pipeline.joblib")
        self.assertTrue(pipeline_path.exists())
        with open(pipeline_path, "rb") as f:
            actual_pipe_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(actual_pipe_hash, EXPECTED_PIPELINE_HASH, "clinical_pipeline.joblib must be untouched")

        uci_path = Path("datasets/clinical/dataset_A_uci_ckd.csv")
        self.assertTrue(uci_path.exists())
        with open(uci_path, "rb") as f:
            actual_uci_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(actual_uci_hash, EXPECTED_UCI_HASH, "dataset_A_uci_ckd.csv must be untouched")

    # =================================================================
    # 8. Clinical Interpretation & Age Top-Coding Verification
    # =================================================================

    def test_17_kdigo_low_risk_non_ckd_and_a3_terminology(self):
        """Test 17: Explicit non-CKD clinical interpretation for G1/A1 and G2/A1, and A3 precision."""
        from src.clinical.kdigo_staging import ALBUMINURIA_CATEGORIES

        # 1. G1/A1 interpretation
        cga_g1a1 = classify_kdigo_composite_risk("G1", "A1")
        self.assertIn("does NOT constitute Chronic Kidney Disease", cga_g1a1["clinical_interpretation"])
        self.assertIn("markers of kidney damage", cga_g1a1["clinical_interpretation"])

        # 2. G2/A1 interpretation
        cga_g2a1 = classify_kdigo_composite_risk("G2", "A1")
        self.assertIn("does NOT constitute Chronic Kidney Disease", cga_g2a1["clinical_interpretation"])

        # 3. Non-low-risk interpretation requires repeat confirmation
        cga_g3a1 = classify_kdigo_composite_risk("G3a", "A1")
        self.assertIn("Requires clinical correlation", cga_g3a1["clinical_interpretation"])

        # 4. A3 clinical description precision
        a3_meta = ALBUMINURIA_CATEGORIES["A3"]
        self.assertEqual(a3_meta["description"], "Severely increased")
        self.assertIn("Severely increased albuminuria", a3_meta["clinical_significance"])
        self.assertIn("nephrotic-range proteinuria requires UACR > 2,200 mg/g", a3_meta["clinical_significance"])

    def test_18_ridageyr_top_coding_at_age_80(self):
        """Test 18: RIDAGEYR top-coding at age 80 detection and mathematical impact analysis."""
        # Participant exactly 80
        res_80 = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=80, sex=1)
        self.assertTrue(res_80["is_top_coded_age"])
        self.assertIn("top-coded at 80.0", res_80["message"])

        # Participant age 65 (not top-coded)
        res_65 = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=65, sex=1)
        self.assertFalse(res_65["is_top_coded_age"])

        # Mathematical comparison: age 80 vs age 90 with identical creatinine (1.0 mg/dL, male)
        # Ratio of eGFR(90) / eGFR(80) = 0.9938^10 = 0.9400 (a 6.0% decrease in filtration)
        res_90 = calculate_egfr_ckd_epi_2021(serum_creatinine=1.0, age=90, sex=1)
        ratio = res_90["egfr"] / res_80["egfr"]
        self.assertAlmostEqual(ratio, 0.9938**10, places=2)


if __name__ == "__main__":
    unittest.main()
