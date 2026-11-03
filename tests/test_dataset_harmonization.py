"""Automated Unit & Integration Tests for NHANES Dataset Harmonization Engine.

Verifies:
1. Loading of synthetic NHANES XPT fixtures.
2. Missing source file handling.
3. Empty/corrupted source file handling.
4. Missing SEQN participant identifier rejection.
5. Duplicate participant ID detection.
6. One-to-one merge validation.
7. Left-join demographic cohort preservation.
8. Correct source-to-feature mapping.
9. Correct unit metadata and semantic distinctions (BUN vs bu).
10. Preservation of original laboratory values.
11. Correct UACR variable selection (URDACT).
12. Detection of missing laboratory measurements.
13. Detection of non-finite values.
14. Prevention of accidental duplicate participants.
15. Exclusion of IDs and survey variables from predictive features.
16. Prevention of automatic NHANES CKD label manufacture.
17. Preservation of UCI CKD dataset integrity.
18. Preservation of trained model artifact (clinical_pipeline.joblib).
19. Preservation of raw downloaded NHANES source files.
20. Reproducibility of merge and dataset manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.data_sources.nhanes_loader import (
    OFFICIAL_NHANES_URLS,
    STANDARDIZED_FEATURE_MAPPING,
    calculate_adult_severity_cohort,
    compute_sha256,
    extract_harmonized_ckd_features,
    generate_nhanes_data_quality_report,
    load_nhanes_file,
    merge_nhanes_components,
    validate_nhanes_source_schema,
    verify_uacr_agreement,
)

# Known baseline hashes
UCI_CKD_EXPECTED_SHA256 = "147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc"
MODEL_PIPELINE_EXPECTED_SHA256 = "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826"


class TestDatasetHarmonization(unittest.TestCase):
    """Test suite for clinical data harmonization and NHANES ingestion."""

    def setUp(self):
        """Create synthetic test fixtures for deterministic testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Synthetic demographic fixture (100 participants)
        np.random.seed(42)
        n = 100
        seqn = np.arange(10001, 10001 + n)
        self.synthetic_demo = pd.DataFrame({
            "SEQN": seqn,
            "RIDAGEYR": np.random.randint(18, 81, size=n).astype(float),
            "RIAGENDR": np.random.choice([1.0, 2.0], size=n),
            "RIDSTATR": np.full(n, 2.0),
            "RIDEXAGM": np.full(n, np.nan),
            "WTMEC2YR": np.random.uniform(5000.0, 50000.0, size=n),
            "WTINT2YR": np.random.uniform(5000.0, 50000.0, size=n),
            "SDMVSTRA": np.random.randint(130, 150, size=n).astype(float),
            "SDMVPSU": np.random.choice([1.0, 2.0], size=n),
        })

        # Synthetic biopro profile fixture (70 participants - simulating unexamined/under-12 subset)
        biopro_seqn = seqn[:70]
        self.synthetic_biopro = pd.DataFrame({
            "SEQN": biopro_seqn,
            "LBXSCR": np.round(np.random.uniform(0.5, 3.5, size=70), 2),
            "LBDSCRSI": np.round(np.random.uniform(44.0, 310.0, size=70), 1),
            "LBXSGL": np.round(np.random.uniform(70.0, 250.0, size=70), 0),
            "LBDSGLSI": np.round(np.random.uniform(3.9, 13.9, size=70), 2),
            "LBXSBU": np.round(np.random.uniform(7.0, 45.0, size=70), 1),
            "LBDSBUSI": np.round(np.random.uniform(2.5, 16.0, size=70), 2),
            "LBXSNASI": np.round(np.random.uniform(135.0, 145.0, size=70), 0),
            "LBXSKSI": np.round(np.random.uniform(3.5, 5.2, size=70), 1),
        })

        # Synthetic urine albumin/creatinine fixture (85 participants)
        alb_cr_seqn = seqn[:85]
        alb = np.round(np.random.uniform(3.0, 300.0, size=85), 1)
        cr = np.round(np.random.uniform(30.0, 300.0, size=85), 1)
        uacr = np.round((alb / cr) * 100.0, 2)
        self.synthetic_alb_cr = pd.DataFrame({
            "SEQN": alb_cr_seqn,
            "URXUMA": alb,
            "URXUMS": alb,
            "URXUCR": cr,
            "URXCRS": cr * 88.4,
            "URDACT": uacr,
            "URDUMALC": np.zeros(85),
            "URDUCRLC": np.zeros(85),
        })

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_01_successful_loading_synthetic_fixtures(self):
        """Test 1: Successful loading of synthetic NHANES XPT fixtures."""
        dummy_file = self.test_dir / "dummy.xpt"
        dummy_file.write_text("dummy content")

        with patch("pandas.read_sas", return_value=self.synthetic_demo.copy()):
            df = load_nhanes_file(dummy_file)
            self.assertIsInstance(df, pd.DataFrame)
            self.assertEqual(len(df), 100)
            self.assertIn("SEQN", df.columns)
            self.assertIn("RIDAGEYR", df.columns)

    def test_02_missing_source_file_handling(self):
        """Test 2: Proper FileNotFoundError handling when file does not exist."""
        non_existent = self.test_dir / "non_existent_file.xpt"
        with self.assertRaises(FileNotFoundError):
            load_nhanes_file(non_existent)

    def test_03_empty_or_corrupted_file_handling(self):
        """Test 3: Empty (0 bytes) or corrupted file handling."""
        empty_file = self.test_dir / "empty.xpt"
        empty_file.touch()
        with self.assertRaises(ValueError) as ctx:
            load_nhanes_file(empty_file)
        self.assertIn("empty", str(ctx.exception).lower())

        corrupt_file = self.test_dir / "corrupted.xpt"
        corrupt_file.write_bytes(b"\x00\x01\x02\x03\xFF\xFE")
        with self.assertRaises(ValueError):
            load_nhanes_file(corrupt_file)

    def test_04_missing_seqn_rejection(self):
        """Test 4: Schema validation raises ValueError when SEQN is missing."""
        df_no_seqn = self.synthetic_demo.drop(columns=["SEQN"])
        with self.assertRaises(ValueError) as ctx:
            validate_nhanes_source_schema(df_no_seqn, ["SEQN", "RIDAGEYR"], "DEMO_TEST")
        self.assertIn("SEQN", str(ctx.exception))

    def test_05_duplicate_participant_id_detection(self):
        """Test 5: Detection and rejection of duplicate participant IDs."""
        df_dup = self.synthetic_demo.copy()
        df_dup.iloc[1, df_dup.columns.get_loc("SEQN")] = df_dup.iloc[0]["SEQN"]
        with self.assertRaises(ValueError) as ctx:
            validate_nhanes_source_schema(df_dup, ["SEQN", "RIDAGEYR"], "DEMO_TEST")
        self.assertIn("Duplicate participant IDs", str(ctx.exception))

    def test_06_one_to_one_merge_validation(self):
        """Test 6: One-to-one merge validation succeeds and prevents row multiplication."""
        merged, stats = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        self.assertEqual(len(merged), 100)
        self.assertEqual(stats["demographic_cohort_count"], 100)
        self.assertEqual(stats["biopro_matched_count"], 70)
        self.assertEqual(stats["alb_cr_matched_count"], 85)
        self.assertEqual(stats["complete_cases_all_three_components"], 70)

    def test_07_left_join_row_preservation(self):
        """Test 7: Demographic cohort is completely preserved through left joins."""
        merged, stats = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        # All 100 original participants must be present
        self.assertEqual(set(merged["SEQN"]), set(self.synthetic_demo["SEQN"]))
        # Participants 71-100 must have NaN for unadministered biopro tests
        unmatched_biopro = merged[merged["SEQN"] > 10070]
        self.assertTrue(unmatched_biopro["LBXSCR"].isna().all())

    def test_08_correct_source_to_feature_mapping(self):
        """Test 8: Correct source-to-harmonized feature mappings."""
        merged, _ = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        features = extract_harmonized_ckd_features(merged)

        expected_features = [
            "participant_id", "age_years", "sex_code",
            "serum_creatinine", "serum_glucose", "blood_urea_nitrogen",
            "sodium", "potassium", "urine_albumin", "urine_creatinine",
            "uacr", "urine_albumin_comment_code", "urine_creatinine_comment_code",
            "survey_weight", "survey_stratum", "survey_psu",
            "data_source",
        ]
        for f in expected_features:
            self.assertIn(f, features.columns, f"Missing harmonized feature: {f}")

    def test_09_correct_unit_metadata_and_bun_semantic_distinction(self):
        """Test 9: Unit metadata and BUN vs blood urea semantic distinction."""
        self.assertEqual(STANDARDIZED_FEATURE_MAPPING["LBXSBU"]["canonical_unit"], "mg/dL")
        desc = STANDARDIZED_FEATURE_MAPPING["LBXSBU"]["description"]
        self.assertIn("SEMANTIC DISTINCTION", desc)
        self.assertIn("BUN is not UCI whole blood urea", desc)

        # Serum creatinine vs urine creatinine distinction
        self.assertIn("serum", STANDARDIZED_FEATURE_MAPPING["LBXSCR"]["harmonized_name"])
        self.assertIn("urine", STANDARDIZED_FEATURE_MAPPING["URXUCR"]["harmonized_name"])

    def test_10_preservation_of_original_laboratory_values(self):
        """Test 10: Original numerical values are preserved without scaling or alteration."""
        merged, _ = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        features = extract_harmonized_ckd_features(merged)

        # Check exact equality for first participant
        self.assertEqual(float(features.iloc[0]["serum_creatinine"]), float(self.synthetic_biopro.iloc[0]["LBXSCR"]))
        self.assertEqual(float(features.iloc[0]["age_years"]), float(self.synthetic_demo.iloc[0]["RIDAGEYR"]))
        self.assertEqual(float(features.iloc[0]["uacr"]), float(self.synthetic_alb_cr.iloc[0]["URDACT"]))

    def test_11_correct_uacr_variable_selection(self):
        """Test 11: Official published URDACT is preserved and verified."""
        uacr_metrics = verify_uacr_agreement(self.synthetic_alb_cr, tolerance=0.05)
        self.assertEqual(uacr_metrics["valid_triplet_count"], 85)
        self.assertEqual(uacr_metrics["agreement_percentage"], 100.0)
        self.assertLess(uacr_metrics["max_absolute_difference"], 0.1)

    def test_12_detection_of_missing_laboratory_measurements(self):
        """Test 12: Accurate detection of missing laboratory measurements."""
        merged, _ = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        report = generate_nhanes_data_quality_report(merged)

        # 30 participants out of 100 did not receive biopro (LBXSCR)
        scr_missing = report["missingness"]["columns"]["LBXSCR"]["missing_count"]
        self.assertEqual(scr_missing, 30)
        # 15 participants did not receive alb_cr (URDACT)
        uacr_missing = report["missingness"]["columns"]["URDACT"]["missing_count"]
        self.assertEqual(uacr_missing, 15)

    def test_13_detection_of_non_finite_values(self):
        """Test 13: Accurate detection of non-finite (inf, -inf) values."""
        df_inf = self.synthetic_biopro.copy()
        df_inf.iloc[0, df_inf.columns.get_loc("LBXSCR")] = np.inf
        df_inf.iloc[1, df_inf.columns.get_loc("LBXSCR")] = -np.inf

        merged, _ = merge_nhanes_components(
            self.synthetic_demo,
            df_inf,
            self.synthetic_alb_cr,
        )
        report = generate_nhanes_data_quality_report(merged)
        self.assertEqual(report["numerical_distributions"]["LBXSCR"]["non_finite_count"], 2)

    def test_14_prevention_of_accidental_duplicate_participants(self):
        """Test 14: Accidental duplicate participants in biopro raises ValueError."""
        dup_biopro = self.synthetic_biopro.copy()
        # Duplicate row 0
        dup_biopro = pd.concat([dup_biopro, dup_biopro.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError) as ctx:
            merge_nhanes_components(self.synthetic_demo, dup_biopro, self.synthetic_alb_cr)
        self.assertIn("Duplicate SEQN detected", str(ctx.exception))

    def test_15_exclusion_of_identifiers_and_survey_variables_from_model_features(self):
        """Test 15: Identifiers and complex survey variables are flagged as excluded from predictive model."""
        excluded_vars = [
            k for k, v in STANDARDIZED_FEATURE_MAPPING.items()
            if v.get("exclude_from_model", False)
        ]
        self.assertIn("SEQN", excluded_vars)
        self.assertIn("WTMEC2YR", excluded_vars)
        self.assertIn("SDMVSTRA", excluded_vars)
        self.assertIn("SDMVPSU", excluded_vars)

        # Verify clinical predictors are NOT excluded
        clinical_predictors = [
            k for k, v in STANDARDIZED_FEATURE_MAPPING.items()
            if not v.get("exclude_from_model", False)
        ]
        self.assertIn("LBXSCR", clinical_predictors)
        self.assertIn("URDACT", clinical_predictors)
        self.assertIn("RIDAGEYR", clinical_predictors)

    def test_16_prevention_of_automatic_nhanes_ckd_label_generation(self):
        """Test 16: Harmonized NHANES dataset must never manufacture CKD target labels."""
        merged, _ = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        features = extract_harmonized_ckd_features(merged)

        forbidden_cols = ["classification", "class", "ckd", "target", "label", "outcome"]
        for col in forbidden_cols:
            self.assertNotIn(col, features.columns, f"Manufactured label column {col} detected!")

    def test_17_uci_dataset_files_remain_unchanged(self):
        """Test 17: Ground-truth UCI CKD dataset file remains unmodified."""
        uci_path = Path("datasets/clinical/dataset_A_uci_ckd.csv")
        self.assertTrue(uci_path.exists(), "UCI CKD dataset missing")
        current_sha = compute_sha256(uci_path)
        self.assertEqual(
            current_sha,
            UCI_CKD_EXPECTED_SHA256,
            f"UCI CKD dataset was modified! SHA256: {current_sha}",
        )

    def test_18_existing_trained_model_artifact_remains_unchanged(self):
        """Test 18: Serialized production model artifact remains unmodified."""
        model_path = Path("models/clinical_pipeline.joblib")
        self.assertTrue(model_path.exists(), "clinical_pipeline.joblib missing")
        current_sha = compute_sha256(model_path)
        self.assertEqual(
            current_sha,
            MODEL_PIPELINE_EXPECTED_SHA256,
            f"Production model artifact was modified! SHA256: {current_sha}",
        )

    def test_19_raw_nhanes_files_remain_unchanged_after_processing(self):
        """Test 19: Raw NHANES transport files match manifest hashes."""
        manifest_path = Path("datasets/external/nhanes_2017_2018/metadata/dataset_manifest.json")
        if not manifest_path.exists():
            self.skipTest("Manifest does not exist; skipping real raw file hash test.")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for name, meta in manifest.items():
            if meta.get("status") in ["downloaded", "cached"]:
                raw_path = Path(meta["path"])
                self.assertTrue(raw_path.exists(), f"Raw file missing: {raw_path}")
                actual_sha = compute_sha256(raw_path)
                self.assertEqual(
                    actual_sha,
                    meta["sha256"],
                    f"Raw file {name} has changed since download!",
                )

    def test_20_reproducibility_of_merge_and_dataset_manifest(self):
        """Test 20: Merging the same components repeatedly yields identical results."""
        merged1, stats1 = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        merged2, stats2 = merge_nhanes_components(
            self.synthetic_demo,
            self.synthetic_biopro,
            self.synthetic_alb_cr,
        )
        pd.testing.assert_frame_equal(merged1, merged2)
        self.assertEqual(stats1["merged_row_count"], stats2["merged_row_count"])
        self.assertEqual(stats1["complete_cases_all_three_components"], stats2["complete_cases_all_three_components"])

    def test_21_adult_eligibility_filtering_and_counts(self):
        """Test 21: Verify adult eligibility filtering (age >= 18) separates adult and pediatric cohorts."""
        # Create cohort with mixed ages
        df_mixed = pd.DataFrame({
            "SEQN": [1, 2, 3, 4, 5],
            "RIDAGEYR": [10.0, 17.5, 18.0, 45.0, 80.0],
            "RIAGENDR": [1.0, 2.0, 1.0, 2.0, 1.0],
            "LBXSCR": [0.6, 0.7, 0.9, 1.1, 1.3],
            "URDACT": [10.0, 12.0, 15.0, 20.0, 25.0],
        })
        metrics = calculate_adult_severity_cohort(df_mixed)
        self.assertEqual(metrics["total_participants"], 5)
        self.assertEqual(metrics["adult_participants_age_18_and_older"], 3)  # ages 18, 45, 80
        self.assertEqual(metrics["pediatric_participants_age_under_18"], 2)  # ages 10, 17.5
        self.assertEqual(metrics["complete_adult_severity_cohort"], 3)
        self.assertEqual(metrics["complete_pediatric_cases_with_both_measurements"], 2)

    def test_22_complete_adult_severity_cohort_calculation(self):
        """Test 22: Verify adult severity calculation when measurements are missing."""
        df_adults = pd.DataFrame({
            "age_years": [25.0, 35.0, 45.0, 55.0, 12.0],  # 4 adults, 1 child
            "sex_code": [1.0, 2.0, 1.0, 2.0, 1.0],
            "serum_creatinine": [0.9, np.nan, 1.2, np.nan, 0.8],  # adult 2 and 4 missing
            "uacr": [15.0, 25.0, np.nan, np.nan, 10.0],          # adult 3 and 4 missing
        })
        metrics = calculate_adult_severity_cohort(df_adults)
        self.assertEqual(metrics["adult_participants_age_18_and_older"], 4)
        self.assertEqual(metrics["adults_missing_creatinine"], 2)
        self.assertEqual(metrics["adults_missing_uacr"], 2)
        self.assertEqual(metrics["adults_missing_both_creatinine_and_uacr"], 1)  # adult 4
        self.assertEqual(metrics["adults_excluded_missing_measurements"], 3)     # adults 2, 3, 4
        self.assertEqual(metrics["complete_adult_severity_cohort"], 1)           # only adult 1

        # Verify against real processed dataset if present on disk
        processed_path = Path("datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv")
        if processed_path.exists():
            real_df = pd.read_csv(processed_path)

            # 1. Primary evaluation using exact MEC examination age (RIDEXAGM >= 216 months)
            real_metrics_exam = calculate_adult_severity_cohort(real_df, use_examination_age=True)
            self.assertEqual(real_metrics_exam["total_participants"], 9254)
            self.assertEqual(real_metrics_exam["adult_participants_age_18_and_older"], 5863)
            self.assertEqual(real_metrics_exam["complete_adult_severity_cohort"], 5069)
            self.assertEqual(real_metrics_exam["pediatric_participants_age_under_18"], 3391)
            self.assertEqual(real_metrics_exam["adults_excluded_missing_measurements"], 794)
            self.assertEqual(real_metrics_exam["adults_missing_creatinine"], 703)
            self.assertEqual(real_metrics_exam["adults_missing_uacr"], 469)
            self.assertEqual(real_metrics_exam["adults_missing_both_creatinine_and_uacr"], 378)
            self.assertEqual(real_metrics_exam["total_excluded_from_adult_severity"], 4185)
            self.assertEqual(real_metrics_exam["adult_severity_retention_rate_pct"], 86.46)
            self.assertEqual(real_metrics_exam["adult_severity_share_of_total_pct"], 54.78)

            # 2. Comparison against baseline screening age (RIDAGEYR >= 18)
            real_metrics_screen = calculate_adult_severity_cohort(real_df, use_examination_age=False)
            self.assertEqual(real_metrics_screen["adult_participants_age_18_and_older"], 5856)
            self.assertEqual(real_metrics_screen["complete_adult_severity_cohort"], 5063)
            self.assertEqual(real_metrics_screen["pediatric_participants_age_under_18"], 3398)
            self.assertEqual(real_metrics_screen["adults_excluded_missing_measurements"], 793)
            self.assertEqual(real_metrics_screen["adults_missing_creatinine"], 702)
            self.assertEqual(real_metrics_screen["adults_missing_uacr"], 469)
            self.assertEqual(real_metrics_screen["adults_missing_both_creatinine_and_uacr"], 378)
            self.assertEqual(real_metrics_screen["total_excluded_from_adult_severity"], 4191)

    def test_23_detection_limit_metadata_preservation(self):
        """Test 23: Verify detection-limit comment codes (URDUMALC, URDUCRLC) are preserved in harmonized features."""
        df_test = self.synthetic_demo.copy()
        df_test["URDUMALC"] = [5.397605346934028e-79] * 99 + [1.0]
        df_test["URDUCRLC"] = [5.397605346934028e-79] * 99 + [1.0]

        features = extract_harmonized_ckd_features(df_test)
        self.assertIn("urine_albumin_comment_code", features.columns)
        self.assertIn("urine_creatinine_comment_code", features.columns)
        # Denormal zeros normalized to clean 0.0
        self.assertEqual(features["urine_albumin_comment_code"].iloc[0], 0.0)
        self.assertEqual(features["urine_creatinine_comment_code"].iloc[0], 0.0)
        # Below detection limit code 1.0 preserved
        self.assertEqual(features["urine_albumin_comment_code"].iloc[-1], 1.0)
        self.assertEqual(features["urine_creatinine_comment_code"].iloc[-1], 1.0)

    def test_24_exclusion_of_qc_fields_from_predictor_features(self):
        """Test 24: QC comment codes are strictly excluded from predictive model feature sets."""
        self.assertTrue(STANDARDIZED_FEATURE_MAPPING["URDUMALC"]["exclude_from_model"])
        self.assertTrue(STANDARDIZED_FEATURE_MAPPING["URDUCRLC"]["exclude_from_model"])
        self.assertEqual(STANDARDIZED_FEATURE_MAPPING["URDUMALC"]["role"], "qc_metadata")
        self.assertEqual(STANDARDIZED_FEATURE_MAPPING["URDUCRLC"]["role"], "qc_metadata")

    def test_25_distinction_between_component_membership_and_valid_measurements(self):
        """Test 25: Distinction between file component membership and valid non-missing laboratory measurements."""
        report_path = Path("datasets/external/nhanes_2017_2018/metadata/data_quality_report.json")
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                rep = json.load(f)
            comp = rep.get("component_intersection_and_completeness", {})
            self.assertEqual(comp["demo_participant_count"], 9254)
            self.assertEqual(comp["interview_only_participants"], 550)
            self.assertEqual(comp["mec_examined_participants"], 8704)
            self.assertEqual(comp["biopro_component_membership"], 6401)
            self.assertEqual(comp["alb_cr_component_membership"], 7936)
            self.assertEqual(comp["records_with_valid_serum_creatinine"], 5903)
            self.assertEqual(comp["records_missing_creatinine_within_biopro"], 498)
            self.assertEqual(comp["records_with_valid_uacr"], 7632)
            self.assertEqual(comp["records_missing_uacr_within_alb_cr"], 304)
            self.assertEqual(comp["records_with_both_valid_measurements_all_ages"], 5800)
            self.assertEqual(comp["complete_adult_severity_records"], 5069)

    def test_26_screening_vs_examination_age_reconciliation(self):
        """Test 26: Screening age vs. examination age reconciliation metrics on real NHANES cohort."""
        processed_path = Path("datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv")
        if processed_path.exists():
            df = pd.read_csv(processed_path)
            metrics = calculate_adult_severity_cohort(df, use_examination_age=True)
            recon = metrics.get("screening_vs_exam_age_reconciliation", {})
            self.assertEqual(recon["adults_using_screening_age"], 5856)
            self.assertEqual(recon["adults_using_examination_age"], 5863)
            self.assertEqual(recon["participants_transitioned_at_boundary"], 7)
            self.assertEqual(recon["complete_adults_using_screening_age"], 5063)
            self.assertEqual(recon["complete_adults_using_examination_age"], 5069)
            self.assertEqual(recon["reconciled_delta_complete_adults"], 6)

    def test_27_participants_around_18_year_boundary(self):
        """Test 27: Verify participants around the exact 18-year (216-month) examination-age boundary."""
        # Edge cases:
        # P1: Screened at 17, examined at 215 months (17.92 yrs) -> Pediatric
        # P2: Screened at 17, examined at 216 months (18.00 yrs) -> Adult (transitioned!)
        # P3: Screened at 17, examined at 217 months (18.08 yrs) -> Adult (transitioned!)
        # P4: Screened at 18, examined at 216 months (18.00 yrs) -> Adult
        # P5: Screened at 18, examined at 228 months (19.00 yrs) -> Adult
        df_boundary = pd.DataFrame({
            "participant_id": [101, 102, 103, 104, 105],
            "age_years": [17.0, 17.0, 17.0, 18.0, 18.0],
            "age_months_exam": [215.0, 216.0, 217.0, 216.0, 228.0],
            "sex_code": [1.0, 2.0, 1.0, 2.0, 1.0],
            "serum_creatinine": [0.8, 0.9, 1.0, 1.1, 1.2],
            "uacr": [10.0, 15.0, 20.0, 25.0, 30.0],
        })

        metrics = calculate_adult_severity_cohort(df_boundary, use_examination_age=True)
        self.assertEqual(metrics["total_participants"], 5)
        self.assertEqual(metrics["adult_participants_age_18_and_older"], 4)  # P2, P3, P4, P5
        self.assertEqual(metrics["pediatric_participants_age_under_18"], 1)  # P1
        self.assertEqual(metrics["complete_adult_severity_cohort"], 4)
        self.assertEqual(metrics["complete_pediatric_cases_with_both_measurements"], 1)

        # Contrast with screening-age only:
        metrics_screening = calculate_adult_severity_cohort(df_boundary, use_examination_age=False)
        self.assertEqual(metrics_screening["adult_participants_age_18_and_older"], 2)  # only P4, P5
        self.assertEqual(metrics_screening["pediatric_participants_age_under_18"], 3)  # P1, P2, P3
        self.assertEqual(metrics_screening["complete_adult_severity_cohort"], 2)

    def test_28_handling_missing_examination_age(self):
        """Test 28: Correct fallback to screening age when examination age is missing (e.g. age >= 20)."""
        df_missing_exam = pd.DataFrame({
            "participant_id": [201, 202, 203, 204],
            "age_years": [25.0, 80.0, 10.0, 17.0],
            "age_months_exam": [np.nan, np.nan, np.nan, np.nan],  # No exam age recorded
            "sex_code": [1.0, 2.0, 1.0, 2.0],
            "serum_creatinine": [0.9, 1.2, 0.6, 0.7],
            "uacr": [12.0, 24.0, 8.0, 10.0],
        })

        metrics = calculate_adult_severity_cohort(df_missing_exam, use_examination_age=True)
        self.assertEqual(metrics["adult_participants_age_18_and_older"], 2)  # ages 25, 80 fallback
        self.assertEqual(metrics["pediatric_participants_age_under_18"], 2)  # ages 10, 17 fallback
        self.assertEqual(metrics["complete_adult_severity_cohort"], 2)

    def test_29_official_cdc_interview_only_count_verification(self):
        """Test 29: Official CDC interview-only (550) vs MEC-examined (8,704) count verification."""
        demo_path = Path("datasets/external/nhanes_2017_2018/raw/DEMO_J.xpt")
        if demo_path.exists():
            demo_df = pd.read_sas(demo_path)
            statr_counts = demo_df["RIDSTATR"].value_counts()
            self.assertEqual(statr_counts.get(1.0, 0), 550, "Official CDC interview-only count must be exactly 550")
            self.assertEqual(statr_counts.get(2.0, 0), 8704, "Official CDC MEC-examined count must be exactly 8,704")
            self.assertEqual(len(demo_df), 9254, "Total NHANES sample must be 9,254")

            # Verify that erroneous count 569 is not present in status codes
            self.assertNotEqual(statr_counts.get(1.0, 0), 569)

    def test_30_adult_cohort_reproducibility(self):
        """Test 30: Adult cohort calculations are strictly reproducible across multiple runs."""
        processed_path = Path("datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv")
        if processed_path.exists():
            df = pd.read_csv(processed_path)
            run1 = calculate_adult_severity_cohort(df, use_examination_age=True)
            run2 = calculate_adult_severity_cohort(df, use_examination_age=True)
            self.assertEqual(run1["complete_adult_severity_cohort"], run2["complete_adult_severity_cohort"])
            self.assertEqual(run1["complete_adult_severity_cohort"], 5069)
            self.assertEqual(run1["adult_severity_retention_rate_pct"], 86.46)
            self.assertEqual(run1["adult_severity_share_of_total_pct"], 54.78)
            self.assertEqual(run1["total_excluded_from_adult_severity"], 4185)

    def test_31_interview_only_participants_age_18_19(self):
        """Test 31: Verify participants with RIDSTATR=1, RIDAGEYR in [18, 19], and missing RIDEXAGM.

        Verifies:
        1. Exact count is 19 on real NHANES 2017-2018 cohort.
        2. All 19 are classified as Adult (not silently classified as pediatric).
        3. All 19 are excluded from complete lab severity cohort (5,069) due to missing MEC examination.
        4. Synthetic behavior conforms to the same safety invariants.
        """
        # Synthetic unit test
        df_synth = pd.DataFrame({
            "participant_id": [301, 302, 303],
            "age_years": [18.0, 19.0, 17.0],
            "age_months_exam": [np.nan, np.nan, np.nan],  # All missing exam age
            "sex_code": [1.0, 2.0, 1.0],
            "serum_creatinine": [np.nan, np.nan, np.nan],  # No MEC labs
            "uacr": [np.nan, np.nan, np.nan],
            "interview_exam_status": [1.0, 1.0, 1.0],      # Interview only
        })
        synth_metrics = calculate_adult_severity_cohort(df_synth, use_examination_age=True)
        self.assertEqual(synth_metrics["adult_population_denominator"], 2)  # 18.0 and 19.0 are adults
        self.assertEqual(synth_metrics["pediatric_participants_age_under_18"], 1)  # 17.0 is pediatric
        self.assertEqual(synth_metrics["complete_adult_severity_cohort"], 0)  # Missing labs -> excluded
        self.assertEqual(synth_metrics["interview_only_adult_denominator"], 2)

        # Real dataset verification if present
        processed_path = Path("datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv")
        if processed_path.exists():
            df = pd.read_csv(processed_path)
            metrics = calculate_adult_severity_cohort(df, use_examination_age=True)
            inv = metrics.get("interview_only_18_19_investigation", {})
            self.assertEqual(inv["count"], 19, "Exact count of RIDSTATR=1 with RIDAGEYR in [18, 19] must be 19")
            self.assertEqual(inv["classified_as_adult"], 19, "All 19 must be classified as adults")
            self.assertEqual(inv["classified_as_pediatric"], 0, "Zero must be classified as pediatric")
            self.assertEqual(inv["has_laboratory_records"], False, "None have laboratory records")

    def test_32_separate_population_and_mec_adult_denominators(self):
        """Test 32: Adult population denominator and MEC-examined denominator are reported separately."""
        processed_path = Path("datasets/external/nhanes_2017_2018/processed/nhanes_2017_2018_ckd_features.csv")
        if processed_path.exists():
            df = pd.read_csv(processed_path)
            metrics = calculate_adult_severity_cohort(df, use_examination_age=True)

            # Denominators
            self.assertEqual(metrics["adult_population_denominator"], 5863)
            self.assertEqual(metrics["mec_examined_adult_denominator"], 5540)
            self.assertEqual(metrics["interview_only_adult_denominator"], 323)
            self.assertEqual(metrics["complete_adult_severity_cohort"], 5069)

            # Missing laboratory denominators
            labs = metrics.get("missing_laboratory_denominators", {})
            self.assertEqual(labs["all_adults_denominator"], 5863)
            self.assertEqual(labs["all_adults_missing_creatinine_count"], 703)
            self.assertEqual(labs["all_adults_missing_uacr_count"], 469)
            self.assertEqual(labs["all_adults_missing_both_count"], 378)
            self.assertEqual(labs["all_adults_excluded_missing_labs_count"], 794)

            self.assertEqual(labs["mec_examined_adults_denominator"], 5540)
            self.assertEqual(labs["mec_adults_missing_creatinine_count"], 380)
            self.assertEqual(labs["mec_adults_missing_uacr_count"], 146)
            self.assertEqual(labs["mec_adults_missing_both_count"], 55)
            self.assertEqual(labs["mec_adults_excluded_missing_labs_count"], 471)

            # Retention rate among MEC-examined adults is 91.50%
            self.assertEqual(metrics["adult_severity_retention_of_mec_adults_pct"], 91.50)
            self.assertEqual(metrics["adult_severity_retention_of_all_adults_pct"], 86.46)


if __name__ == "__main__":
    unittest.main()
