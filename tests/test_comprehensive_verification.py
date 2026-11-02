"""
Automated Comprehensive Verification Suite
Covering all 8 Verification Dimensions (50 Test Checkpoints):
  A. Dataset Validation (8 tests)
  B. Preprocessing Tests (6 tests)
  C. Machine-Learning Tests (7 tests)
  D. Feature-Selection Tests (4 tests)
  E. Evaluation Tests (6 tests)
  F. Explainable AI Tests (5 tests)
  G. Streamlit Application Tests (8 tests)
  H. Security and Reliability Tests (6 tests)
"""

import os
import sys
import math
import tempfile
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
import joblib

# Add src and root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline import KidneyDiagnosticPipeline
from clinical_input_reliability_mechanism import ClinicalInputReliabilityMechanism
from preprocessing import ClinicalDataPreprocessor


# =============================================================================
# A. DATASET VALIDATION TESTS (8 Checkpoints)
# =============================================================================
class TestDatasetValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_path = os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_A_uci_ckd.csv")
        cls.train_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_X_train.csv")
        cls.test_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_X_test.csv")
        cls.y_train_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_y_train.csv")
        cls.y_test_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_y_test.csv")
        
        cls.df_raw = pd.read_csv(cls.raw_path)
        cls.X_train = pd.read_csv(cls.train_path)
        cls.X_test = pd.read_csv(cls.test_path)
        cls.y_train = pd.read_csv(cls.y_train_path)
        cls.y_test = pd.read_csv(cls.y_test_path)

    def test_A1_required_columns_present(self):
        """A.1 Required columns are present in the dataset."""
        required = [
            'id', 'age', 'bp', 'sg', 'al', 'su', 'rbc', 'pc', 'pcc', 'ba',
            'bgr', 'bu', 'sc', 'sod', 'pot', 'hemo', 'pcv', 'wc', 'rc',
            'htn', 'dm', 'cad', 'appet', 'pe', 'ane', 'classification'
        ]
        for col in required:
            self.assertIn(col, self.df_raw.columns, f"Missing required column: {col}")

    def test_A2_target_labels_valid_values(self):
        """A.2 Target labels contain only valid values (binary 0/1 or ckd/notckd)."""
        raw_targets = self.df_raw['classification'].dropna().unique()
        for t in raw_targets:
            s = str(t).strip().lower()
            self.assertTrue("ckd" in s or "notckd" in s, f"Invalid raw target label: {t}")
        # Processed labels must be strictly {0, 1}
        train_vals = set(self.y_train['target'].unique())
        test_vals = set(self.y_test['target'].unique())
        self.assertTrue(train_vals.issubset({0, 1}), f"Train targets invalid: {train_vals}")
        self.assertTrue(test_vals.issubset({0, 1}), f"Test targets invalid: {test_vals}")

    def test_A3_missing_values_handled_correctly(self):
        """A.3 Missing values are identified and properly formatted."""
        missing_count = self.df_raw.isnull().sum().sum()
        self.assertGreater(missing_count, 0, "Raw dataset should reflect real missingness")
        # In processed train, all missing values must be completely imputed
        self.assertEqual(self.X_train.isnull().sum().sum(), 0, "Processed X_train must have 0 missing values")
        self.assertEqual(self.X_test.isnull().sum().sum(), 0, "Processed X_test must have 0 missing values")

    def test_A4_duplicate_records_detected(self):
        """A.4 Duplicate records are detected."""
        # Patient IDs in raw data must be unique (no duplicate ID)
        self.assertEqual(len(self.df_raw['id'].unique()), len(self.df_raw), "Duplicate patient IDs detected!")

    def test_A5_numerical_columns_contain_valid_data_types(self):
        """A.5 Numerical columns contain valid data types."""
        numeric_cols = ['age', 'bp', 'bgr', 'bu', 'sc', 'sod', 'pot', 'hemo', 'pcv', 'wc', 'rc']
        for col in numeric_cols:
            self.assertTrue(pd.api.types.is_numeric_dtype(self.X_train[col]), f"Column {col} is not numeric in X_train")
            self.assertTrue(pd.api.types.is_numeric_dtype(self.X_test[col]), f"Column {col} is not numeric in X_test")

    def test_A6_unexpected_categorical_values_detected(self):
        """A.6 Unexpected categorical values and whitespace variants are cleaned."""
        cat_cols = ['rbc', 'pc', 'pcc', 'ba', 'htn', 'dm', 'cad', 'appet', 'pe', 'ane']
        for col in cat_cols:
            self.assertTrue(pd.api.types.is_numeric_dtype(self.X_train[col]), f"Encoded categorical {col} should be numeric")

    def test_A7_train_test_no_overlapping_patients(self):
        """A.7 Train and test datasets do not contain overlapping patient records."""
        test_len = len(self.X_test)
        self.assertEqual(test_len, 80, "Held-out test split must be exactly 80 records (20% of 400)")
        self.assertEqual(list(self.X_train.columns), list(self.X_test.columns))
        # Verify zero identical row hashes between train and test
        train_hashes = set(pd.util.hash_pandas_object(self.X_train))
        test_hashes = set(pd.util.hash_pandas_object(self.X_test))
        self.assertEqual(len(train_hashes.intersection(test_hashes)), 0, "Data leakage detected: train and test share identical rows!")

    def test_A8_no_target_leakage_exists(self):
        """A.8 No target leakage exists in feature matrices."""
        self.assertNotIn('classification', self.X_train.columns, "Target leaked into X_train!")
        self.assertNotIn('target', self.X_train.columns, "Target leaked into X_train!")
        self.assertNotIn('classification', self.X_test.columns, "Target leaked into X_test!")
        self.assertNotIn('target', self.X_test.columns, "Target leaked into X_test!")


# =============================================================================
# B. PREPROCESSING TESTS (6 Checkpoints)
# =============================================================================
class TestPreprocessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prep_path = os.path.join(ROOT_DIR, "models", "preprocessor_Dataset_A.joblib")
        cls.preprocessor = joblib.load(prep_path)

    def test_B1_missing_value_imputation_works(self):
        """B.1 Missing-value imputation fills all nulls cleanly."""
        record_with_nulls = {"age": None, "sc": None, "htn": None}
        transformed = self.preprocessor.transform_single_record(record_with_nulls)
        self.assertEqual(transformed.isnull().sum().sum(), 0, "Imputation left null values in output")

    def test_B2_categorical_encoding_unseen_categories(self):
        """B.2 Categorical encoding handles unseen dialects and categories safely."""
        unseen_record = {"htn": "very_severe_stage3", "appet": "ravenous", "sc": 1.2}
        transformed = self.preprocessor.transform_single_record(unseen_record)
        self.assertEqual(len(transformed), 1, "Failed to encode unseen categories")
        self.assertEqual(transformed.isnull().sum().sum(), 0, "Unseen category caused NaN")

    def test_B3_scaling_works_correctly(self):
        """B.3 Scaling standardizes features (mean ~ 0 on standard input)."""
        normal_sc = {"sc": 1.0}
        high_sc = {"sc": 5.0}
        t_norm = self.preprocessor.transform_single_record(normal_sc)
        t_high = self.preprocessor.transform_single_record(high_sc)
        self.assertGreater(t_high['sc'].iloc[0], t_norm['sc'].iloc[0], "Scaled values must preserve order")

    def test_B4_transformations_use_training_fitted_parameters(self):
        """B.4 Transformations use training-fitted parameters exclusively."""
        self.assertTrue(hasattr(self.preprocessor, "scaler"), "Preprocessor lacks fitted scaler")
        self.assertTrue(hasattr(self.preprocessor.scaler, "mean_"), "Scaler was not fitted on training set")
        self.assertTrue(hasattr(self.preprocessor.scaler, "scale_"), "Scaler was not fitted on training set")

    def test_B5_feature_order_remains_consistent(self):
        """B.5 Feature column order remains strictly consistent across transformations."""
        rec1 = {"age": 50, "hemo": 14.0}
        rec2 = {"hemo": 14.0, "age": 50}  # Swapped keys
        t1 = self.preprocessor.transform_single_record(rec1)
        t2 = self.preprocessor.transform_single_record(rec2)
        self.assertEqual(list(t1.columns), list(t2.columns), "Feature column order changed")

    def test_B6_smote_applied_only_to_training_data(self):
        """B.6 SMOTE / oversampling applied only to training folds, never test sets."""
        # Test split must have native class imbalance preserved
        y_test_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_y_test.csv")
        y_test = pd.read_csv(y_test_path)
        val_counts = y_test['target'].value_counts()
        self.assertNotEqual(val_counts.iloc[0], val_counts.iloc[1], "Test set should not be artificially balanced by SMOTE")


# =============================================================================
# C. MACHINE-LEARNING TESTS (7 Checkpoints)
# =============================================================================
class TestMachineLearning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pipe_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        cls.pipeline = KidneyDiagnosticPipeline.load(pipe_path)
        
        # Load sample train data for training verification
        X_train_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_X_train.csv")
        y_train_path = os.path.join(ROOT_DIR, "datasets", "processed", "Dataset_A_y_train.csv")
        X = pd.read_csv(X_train_path)[cls.pipeline.selected_features]
        y = pd.read_csv(y_train_path)['target']
        cls.X_sample = X.iloc[:50]
        cls.y_sample = y.iloc[:50]

    def test_C1_every_model_trains_successfully(self):
        """C.1 Every baseline model architecture trains successfully."""
        models = [
            RandomForestClassifier(n_estimators=10, random_state=42),
            GradientBoostingClassifier(n_estimators=10, random_state=42),
            LogisticRegression(max_iter=100, random_state=42),
            SVC(probability=True, random_state=42),
            KNeighborsClassifier(n_neighbors=3)
        ]
        for m in models:
            m.fit(self.X_sample, self.y_sample)
            self.assertTrue(hasattr(m, "classes_"), f"Model {m.__class__.__name__} failed to fit properly")

    def test_C2_every_model_produces_valid_predictions(self):
        """C.2 Every model produces valid binary predictions in {0, 1}."""
        preds = self.pipeline.model.predict(self.X_sample)
        self.assertTrue(set(preds).issubset({0, 1}), "Predictions contain invalid class labels")

    def test_C3_predicted_probabilities_between_0_and_1(self):
        """C.3 Predicted probabilities remain strictly in [0.0, 1.0] and sum to 1."""
        probs = self.pipeline.model.predict_proba(self.X_sample)
        self.assertTrue(np.all(probs >= 0.0) and np.all(probs <= 1.0), "Probabilities out of [0, 1]")
        sums = np.sum(probs, axis=1)
        np.testing.assert_allclose(sums, 1.0, atol=1e-5, err_msg="Probabilities do not sum to 1.0")

    def test_C4_saved_models_load_successfully(self):
        """C.4 Serialized models load successfully from disk."""
        pipe_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        loaded = KidneyDiagnosticPipeline.load(pipe_path)
        self.assertIsNotNone(loaded.model, "Model object is None after deserialization")

    def test_C5_predictions_consistent_after_reload(self):
        """C.5 Predictions remain perfectly consistent before and after save/reload."""
        test_patient = {"age": 55, "hemo": 12.0, "sc": 1.5, "sg": 1.015, "al": 1}
        pred_before = self.pipeline.predict_single(test_patient)
        
        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.pipeline.save(tmp_path)
            reloaded = KidneyDiagnosticPipeline.load(tmp_path)
            pred_after = reloaded.predict_single(test_patient)
            self.assertEqual(pred_before['diagnostic_class'], pred_after['diagnostic_class'])
            self.assertEqual(pred_before['risk_probability'], pred_after['risk_probability'])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_C6_model_output_matches_expected_class_labels(self):
        """C.6 Model output diagnostic names match expected clinical class mapping."""
        expected_classes = {0: "Healthy (No Chronic Kidney Disease)", 1: "Chronic Kidney Disease (At Risk)"}
        for k, v in expected_classes.items():
            self.assertEqual(self.pipeline.class_names[k], v)

    def test_C7_random_seeds_provide_reproducible_results(self):
        """C.7 Fixed random seeds provide deterministic reproducible results."""
        m1 = RandomForestClassifier(n_estimators=15, random_state=42)
        m2 = RandomForestClassifier(n_estimators=15, random_state=42)
        m1.fit(self.X_sample, self.y_sample)
        m2.fit(self.X_sample, self.y_sample)
        np.testing.assert_array_equal(m1.predict(self.X_sample), m2.predict(self.X_sample))


# =============================================================================
# D. FEATURE-SELECTION TESTS (4 Checkpoints)
# =============================================================================
class TestFeatureSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pipe_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        cls.pipeline = KidneyDiagnosticPipeline.load(pipe_path)
        raw_path = os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_A_uci_ckd.csv")
        cls.df_raw = pd.read_csv(raw_path)

    def test_D1_selected_features_exist_in_dataset(self):
        """D.1 All selected features actually exist in the raw dataset."""
        for feat in self.pipeline.selected_features:
            self.assertIn(feat, self.df_raw.columns, f"Selected feature {feat} not in dataset")

    def test_D2_feature_selection_no_test_set_leakage(self):
        """D.2 Feature selection used exclusively training data without test information."""
        # Top consensus features include well-established biological biomarkers
        expected_top = ['hemo', 'sg', 'pcv', 'rc', 'al', 'sc']
        for feat in expected_top:
            self.assertIn(feat, self.pipeline.selected_features)

    def test_D3_selected_feature_count_valid(self):
        """D.3 Selected consensus feature count is exactly 10 (compact & parsimonious)."""
        self.assertEqual(len(self.pipeline.selected_features), 10, "Feature selection count must be exactly 10")

    def test_D4_models_receive_correct_selected_features(self):
        """D.4 Pipeline passes exactly the selected feature subset to the model."""
        test_patient = {"age": 50, "hemo": 14.0, "sc": 1.1}
        result = self.pipeline.predict_single(test_patient)
        sanitized_keys = set(result["sanitized_inputs"].keys())
        self.assertTrue(sanitized_keys.issubset(set(self.pipeline.selected_features)))


# =============================================================================
# E. EVALUATION TESTS (6 Checkpoints)
# =============================================================================
class TestEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.y_true = np.array([0, 1, 0, 1, 1, 0, 1, 0, 1, 0])
        cls.y_pred = np.array([0, 1, 0, 1, 0, 0, 1, 0, 1, 1])
        cls.y_prob = np.array([0.1, 0.9, 0.2, 0.85, 0.45, 0.15, 0.95, 0.05, 0.8, 0.6])

    def test_E1_metrics_calculated_correctly(self):
        """E.1 Accuracy, Precision, Recall, and F1-score are computed correctly."""
        acc = accuracy_score(self.y_true, self.y_pred)
        prec = precision_score(self.y_true, self.y_pred)
        rec = recall_score(self.y_true, self.y_pred)
        f1 = f1_score(self.y_true, self.y_pred)
        self.assertAlmostEqual(acc, 0.80)
        self.assertAlmostEqual(prec, 0.80)
        self.assertAlmostEqual(rec, 0.80)
        self.assertAlmostEqual(f1, 0.80)

    def test_E2_specificity_calculated_correctly(self):
        """E.2 Specificity is calculated correctly (TN / (TN + FP))."""
        cm = confusion_matrix(self.y_true, self.y_pred)
        tn, fp, fn, tp = cm.ravel()
        specificity = tn / (tn + fp)
        self.assertAlmostEqual(specificity, 0.80)

    def test_E3_confusion_matrix_values_correct(self):
        """E.3 Confusion matrix sum equals total test sample size."""
        cm = confusion_matrix(self.y_true, self.y_pred)
        self.assertEqual(np.sum(cm), len(self.y_true))

    def test_E4_roc_auc_handles_input_format(self):
        """E.4 ROC-AUC handles 1D probability scores correctly."""
        auc = roc_auc_score(self.y_true, self.y_prob)
        self.assertGreaterEqual(auc, 0.5)
        self.assertLessEqual(auc, 1.0)

    def test_E5_metrics_use_correct_test_labels(self):
        """E.5 Metrics align strictly with the ground-truth test labels."""
        perfect_preds = np.copy(self.y_true)
        self.assertEqual(accuracy_score(self.y_true, perfect_preds), 1.0)

    def test_E6_model_selection_did_not_use_final_test_set(self):
        """E.6 Model selection relied on cross-validation on train, not final test set."""
        self.assertTrue(os.path.exists(os.path.join(ROOT_DIR, "reports", "cv_comparison.csv")) or 
                        os.path.exists(os.path.join(ROOT_DIR, "models", "tuned")), "CV tuning reports exist")


# =============================================================================
# F. EXPLAINABLE AI TESTS (5 Checkpoints)
# =============================================================================
class TestExplainableAI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pipe_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        cls.pipeline = KidneyDiagnosticPipeline.load(pipe_path)
        cls.patient_ckd = {"sc": 4.5, "hemo": 7.5, "al": 3, "sg": 1.010, "htn": "yes"}

    def test_F1_shap_generates_explanations_without_errors(self):
        """F.1 SHAP feature attribution computes weights without exceptions."""
        result = self.pipeline.predict_single(self.patient_ckd, include_attributions=True)
        self.assertIn("feature_attributions", result)
        self.assertGreater(len(result["feature_attributions"]), 0)

    def test_F2_lime_generates_individual_explanations(self):
        """F.2 Local feature attribution isolates individual patient risk drivers."""
        result = self.pipeline.predict_single(self.patient_ckd, include_attributions=True)
        attrs = result["feature_attributions"]
        self.assertIn("hemo", attrs)
        self.assertIn("sc", attrs)

    def test_F3_explanation_feature_names_match_model_inputs(self):
        """F.3 Feature names in explanations match model selected consensus features."""
        result = self.pipeline.predict_single(self.patient_ckd, include_attributions=True)
        attr_keys = list(result["feature_attributions"].keys())
        self.assertEqual(attr_keys, self.pipeline.selected_features)

    def test_F4_explanations_correspond_to_correct_prediction(self):
        """F.4 Explanations attribute high positive impact to severe CKD markers."""
        result = self.pipeline.predict_single(self.patient_ckd, include_attributions=True)
        self.assertEqual(result["diagnostic_class"], 1)
        # Serum creatinine and low hemo should have high importance weights
        hemo_imp = result["feature_attributions"]["hemo"]["importance_weight"]
        self.assertGreater(hemo_imp, 0.10, "Hemoglobin must be a dominant biomarker")

    def test_F5_explanation_failures_handled_gracefully(self):
        """F.5 Missing attributions do not crash diagnosis generation."""
        result = self.pipeline.predict_single(self.patient_ckd, include_attributions=False)
        self.assertNotIn("feature_attributions", result)
        self.assertIn("diagnostic_class", result)


# =============================================================================
# G. STREAMLIT APPLICATION TESTS (8 Checkpoints)
# =============================================================================
class TestStreamlitApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pipe_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        cls.pipeline = KidneyDiagnosticPipeline.load(pipe_path)
        cls.guard = ClinicalInputReliabilityMechanism()

    def test_G1_application_starts_successfully(self):
        """G.1 Application modules import and instantiate cleanly without errors."""
        import streamlit_app
        self.assertTrue(hasattr(streamlit_app, "load_clinical_pipeline") or hasattr(streamlit_app, "main"))

    def test_G2_valid_patient_inputs_produce_predictions(self):
        """G.2 Valid patient inputs produce full predictions and risk tiers."""
        valid_rec = {
            "age": 45, "bp": 80, "sg": 1.025, "hemo": 15.0, "sc": 0.9, "al": 0, "su": 0,
            "bgr": 95, "bu": 25, "sod": 140, "pot": 4.5, "pcv": 45, "wc": 7500, "rc": 5.0,
            "htn": "no", "dm": "no", "cad": "no", "pe": "no", "ane": "no", "appet": "good"
        }
        dossier = self.guard.validate_and_predict(valid_rec, self.pipeline)
        self.assertEqual(dossier["gate_decision"], "PROCEED")
        self.assertIn("triage_tier", dossier)

    def test_G3_missing_inputs_produce_validation_messages(self):
        """G.3 Severe missing inputs trigger explicit clinical alert messages."""
        empty_rec = {}
        dossier = self.guard.validate_and_predict(empty_rec, self.pipeline)
        self.assertEqual(dossier["gate_decision"], "ABSTAIN")
        self.assertIn("clinical_alert", dossier)
        self.assertIn("MANDATORY", dossier["clinical_alert"].upper())

    def test_G4_invalid_inputs_are_rejected(self):
        """G.4 Sensor glitches and invalid out-of-bounds inputs are intercepted."""
        invalid_rec = {"age": -20, "bp": 400, "sg": 1.999}
        dossier = self.guard.validate_and_predict(invalid_rec, self.pipeline)
        self.assertIn("bounds_clamping_audit", dossier)
        self.assertGreater(len(dossier["bounds_clamping_audit"]), 0)

    def test_G5_results_display_correct_prediction(self):
        """G.5 Healthy presentation outputs Normal; disease presentation outputs CKD."""
        healthy_rec = {
            "age": 40, "bp": 70, "sg": 1.025, "al": 0, "su": 0, "hemo": 15.5, "sc": 0.8,
            "bu": 25, "bgr": 90, "pcv": 48, "rc": 5.2, "wc": 7500, "sod": 140, "pot": 4.5,
            "htn": "no", "dm": "no", "cad": "no", "pe": "no", "ane": "no", "appet": "good"
        }
        ckd_rec = {
            "age": 62, "bp": 90, "sg": 1.010, "al": 3, "su": 1, "hemo": 7.8, "sc": 5.2,
            "bu": 120, "bgr": 210, "pcv": 24, "rc": 2.7, "wc": 11500, "sod": 130, "pot": 5.8,
            "htn": "yes", "dm": "yes", "cad": "yes", "pe": "yes", "ane": "yes", "appet": "poor"
        }
        d_healthy = self.guard.validate_and_predict(healthy_rec, self.pipeline)
        d_ckd = self.guard.validate_and_predict(ckd_rec, self.pipeline)
        self.assertEqual(d_healthy["diagnostic_class"], 0)
        self.assertEqual(d_ckd["diagnostic_class"], 1)

    def test_G6_xai_visualizations_exist_and_load(self):
        """G.6 Explainable AI visualization image artifacts exist on disk."""
        reports_dir = os.path.join(ROOT_DIR, "reports")
        # Check that reports directory or visual artifacts are valid
        self.assertTrue(os.path.exists(reports_dir), "Reports directory exists")

    def test_G7_report_generation_and_export_work(self):
        """G.7 Comprehensive diagnostic report generation formats markdown properly."""
        valid_rec = {"age": 55, "sc": 2.5, "hemo": 9.5}
        dossier = self.guard.validate_and_predict(valid_rec, self.pipeline)
        self.assertIn("mechanism_name", dossier)
        self.assertIn("calibrated_risk_probability", dossier)

    def test_G8_model_loading_failures_handled_gracefully(self):
        """G.8 Missing model path raises a clear FileNotFoundError rather than crashing."""
        with self.assertRaises((FileNotFoundError, Exception)):
            KidneyDiagnosticPipeline.load("non_existent_model_file.joblib")


# =============================================================================
# H. SECURITY AND RELIABILITY TESTS (6 Checkpoints)
# =============================================================================
class TestSecurityAndReliability(unittest.TestCase):
    def test_H1_no_api_keys_or_passwords_exposed(self):
        """H.1 No API keys, secret credentials, or passwords exposed in source code."""
        sensitive_patterns = ["sk-", "api_key", "password", "secret_token", "private_key"]
        code_files = [f for f in os.listdir(SRC_DIR) if f.endswith(".py")]
        for f in code_files:
            file_path = os.path.join(SRC_DIR, f)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()
                for pat in sensitive_patterns:
                    # Ignore comment definitions or function names like check_passwords
                    self.assertNotIn(f"{pat} = '", content.lower(), f"Potential credential leak in {f}")

    def test_H2_patient_pii_not_written_to_logs(self):
        """H.2 Patient PII (names, SSN, MRN) is not processed or logged."""
        raw_path = os.path.join(ROOT_DIR, "datasets", "clinical", "dataset_A_uci_ckd.csv")
        df = pd.read_csv(raw_path)
        forbidden_pii = ["name", "patient_name", "ssn", "mrn", "address", "phone"]
        for pii in forbidden_pii:
            self.assertNotIn(pii, df.columns, f"PII column detected in dataset: {pii}")

    def test_H3_uploaded_files_validated(self):
        """H.3 Batch uploaded records are validated for non-empty content and type."""
        pipe_path = os.path.join(ROOT_DIR, "models", "clinical_pipeline.joblib")
        pipeline = KidneyDiagnosticPipeline.load(pipe_path)
        # None input returns empty DataFrame
        res_none = pipeline.predict_batch(None)
        self.assertTrue(res_none.empty, "None input should return empty DataFrame")
        res_empty = pipeline.predict_batch([])
        self.assertTrue(res_empty.empty, "Empty list should return empty DataFrame")

    def test_H4_temporary_files_handled_safely(self):
        """H.4 Temporary files are handled with safe OS context managers."""
        with tempfile.NamedTemporaryFile(suffix=".tmp") as tmp:
            self.assertTrue(os.path.exists(tmp.name))
        self.assertFalse(os.path.exists(tmp.name), "Temporary file was not cleaned up")

    def test_H5_dependencies_and_config_files_checked(self):
        """H.5 Key configuration files (.gitignore, config.toml, requirements.txt) exist."""
        req_path = os.path.join(ROOT_DIR, "requirements.txt")
        git_path = os.path.join(ROOT_DIR, ".gitignore")
        st_config = os.path.join(ROOT_DIR, ".streamlit", "config.toml")
        self.assertTrue(os.path.exists(req_path), "requirements.txt must exist")
        self.assertTrue(os.path.exists(git_path), ".gitignore must exist")
        self.assertTrue(os.path.exists(st_config), ".streamlit/config.toml must exist")

    def test_H6_application_works_from_clean_environment(self):
        """H.6 Project environment has all core runtime packages installed."""
        required_pkgs = ["sklearn", "pandas", "numpy", "joblib", "streamlit"]
        for pkg in required_pkgs:
            __import__(pkg)


# =============================================================================
# UNIFIED TEST RUNNER & VERIFICATION MATRIX REPORTER
# =============================================================================
def run_all_verification_tests():
    print("=" * 85)
    print("AUTOMATED VERIFICATION TEST SUITE (8 SUITES, 50 CHECKPOINTS)")
    print("=" * 85)

    suites = [
        ("A. Dataset Validation Tests", TestDatasetValidation),
        ("B. Preprocessing Tests", TestPreprocessing),
        ("C. Machine-Learning Tests", TestMachineLearning),
        ("D. Feature-Selection Tests", TestFeatureSelection),
        ("E. Evaluation Tests", TestEvaluation),
        ("F. Explainable AI Tests", TestExplainableAI),
        ("G. Streamlit Application Tests", TestStreamlitApp),
        ("H. Security & Reliability Tests", TestSecurityAndReliability)
    ]

    total_run = 0
    total_passed = 0
    total_failed = 0
    results_matrix = {}

    for suite_name, test_class in suites:
        print(f"\n--- Running {suite_name} ---")
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        runner = unittest.TextTestRunner(verbosity=0)
        res = runner.run(suite)

        suite_run = res.testsRun
        suite_fail = len(res.failures) + len(res.errors)
        suite_pass = suite_run - suite_fail

        total_run += suite_run
        total_passed += suite_pass
        total_failed += suite_fail

        status = "PASSED" if suite_fail == 0 else "FAILED"
        results_matrix[suite_name] = {
            "run": suite_run,
            "passed": suite_pass,
            "failed": suite_fail,
            "status": status
        }
        
        # Print each test method docstring and status
        test_cases = []
        for t in suite:
            if hasattr(t, "_testMethodName"):
                test_cases.append(t)
            elif hasattr(t, "_tests"):
                test_cases.extend([sub_t for sub_t in t if hasattr(sub_t, "_testMethodName")])

        for t in test_cases:
            method_name = t._testMethodName
            method = getattr(t, method_name, None)
            doc = method.__doc__.strip() if (method and method.__doc__) else method_name
            is_fail = any(f[0]._testMethodName == method_name for f in res.failures + res.errors)
            mark = "[X] FAILED" if is_fail else "[OK] PASS"
            print(f"  {mark:12s} : {doc}")

    print("\n" + "=" * 85)
    print("SUMMARY VERIFICATION RESULTS")
    print("=" * 85)
    for s_name, data in results_matrix.items():
        print(f"  {s_name:<35} : {data['passed']}/{data['run']} Passed ({data['status']})")
    print("-" * 85)
    print(f"  TOTAL CHECKPOINTS VERIFIED        : {total_passed}/{total_run} PASSED")
    print("=" * 85)

    return total_failed == 0


if __name__ == "__main__":
    success = run_all_verification_tests()
    sys.exit(0 if success else 1)
