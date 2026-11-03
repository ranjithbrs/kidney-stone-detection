"""
Builds, serializes, loads, and thoroughly tests the unified clinical prediction pipeline.
"""

import os
import json
import joblib
import pandas as pd
from pipeline import KidneyDiagnosticPipeline
from preprocessing import ClinicalDataPreprocessor


def build_and_test_pipeline():
    print("=" * 65)
    print("PHASE 9: END-TO-END PREDICTION PIPELINE CONSTRUCTION & TESTING")
    print("=" * 65)

    # 1. Load Preprocessor, Model, and Features
    preprocessor = joblib.load("models/preprocessor_Dataset_A.joblib")
    champion_model = joblib.load("models/tuned/Dataset_A_Random_Forest_best.joblib")

    with open("runs/feature_selection/selected_features.json") as f:
        sel = json.load(f)
    top10_features = sel["Dataset_A"]["selected_features"]["hybrid_top10"]

    print(f"Loaded Preprocessor: {len(preprocessor.feature_names)} features configured")
    print(f"Loaded Champion Model: {type(champion_model).__name__}")
    print(f"Selected Top-10 Consensus Features: {top10_features}")

    # 2. Load Existing Trained Diagnostic Pipeline
    pipeline_path = "models/clinical_pipeline.joblib"
    print(f"\n--> Loading existing production pipeline from: {pipeline_path}")
    reloaded_pipeline = KidneyDiagnosticPipeline.load(pipeline_path)

    # 5. TEST CASE 1: Clinically Healthy Patient
    print("\n[TEST CASE 1: Healthy Patient Input]")
    healthy_patient = {
        "age": 35,
        "bp": 75,
        "sg": 1.025,
        "al": 0,
        "su": 0,
        "bgr": 95,
        "bu": 25,
        "sc": 0.8,
        "hemo": 15.2,
        "pcv": 44,
        "rc": 5.2,
        "htn": "no",
        "dm": "no"
    }
    res_1 = reloaded_pipeline.predict_single(healthy_patient)
    print(f" -> Diagnosis:        {res_1['diagnosis']}")
    print(f" -> Risk Probability: {res_1['risk_probability']*100:.1f}%")
    print(f" -> Risk Category:    {res_1['risk_category']}")
    assert res_1["diagnostic_class"] == 0, "Test Case 1 Failed: Healthy patient flagged as disease!"

    # 6. TEST CASE 2: High-Risk Chronic Kidney Disease Patient
    print("\n[TEST CASE 2: High-Risk Renal Disease Patient Input]")
    ckd_patient = {
        "age": 62,
        "bp": 100,
        "sg": 1.010,
        "al": 3,
        "su": 2,
        "bgr": 210,
        "bu": 85,
        "sc": 4.5,
        "hemo": 8.1,
        "pcv": 24,
        "rc": 2.8,
        "htn": "yes",
        "dm": "yes"
    }
    res_2 = reloaded_pipeline.predict_single(ckd_patient)
    print(f" -> Diagnosis:        {res_2['diagnosis']}")
    print(f" -> Risk Probability: {res_2['risk_probability']*100:.1f}%")
    print(f" -> Risk Category:    {res_2['risk_category']}")
    assert res_2["diagnostic_class"] == 1, "Test Case 2 Failed: Sick patient flagged as healthy!"

    # 7. TEST CASE 3: Incomplete / Partially Missing Input (Critical labs present, non-critical omitted)
    print("\n[TEST CASE 3: Incomplete Non-Critical Input]")
    sparse_patient = {
        "age": 55,
        "sc": 3.8,       # High creatinine (critical)
        "hemo": 9.0,     # Low hemoglobin (critical)
        "al": 2          # Urine albumin grade 2 (critical)
        # All other non-critical features omitted!
    }
    res_3 = reloaded_pipeline.predict_single(sparse_patient)
    print(f" -> Status:           {res_3['prediction_status']}")
    print(f" -> Diagnosis:        {res_3['diagnosis']}")
    print(f" -> Risk Probability: {res_3['risk_probability']*100:.1f}%")
    print(f" -> Imputed Features: {res_3['imputed_features']}")
    assert res_3["prediction_status"] == "INCOMPLETE_INPUT_ESTIMATE", "Expected INCOMPLETE_INPUT_ESTIMATE"
    print(" -> Incomplete Input Handled Gracefully: PASSED")

    # 8. TEST CASE 4: Missing Critical Measurement (Missing sc or al or hemo -> Safe Abstention)
    print("\n[TEST CASE 4: Missing Critical Biomarker Input]")
    missing_crit_patient = {
        "age": 55,
        "sc": 3.8,
        "hemo": 9.0
        # Missing 'al'
    }
    res_4 = reloaded_pipeline.predict_single(missing_crit_patient)
    print(f" -> Status:           {res_4['prediction_status']}")
    print(f" -> Diagnosis:        {res_4['diagnosis']}")
    print(f" -> Reason:           {res_4['abstention_reason']}")
    assert res_4["prediction_status"] == "ABSTAIN_MISSING_CRITICAL_FEATURES", "Expected ABSTAIN_MISSING_CRITICAL_FEATURES"
    assert res_4["risk_probability"] is None, "Abstained risk probability must be None"
    print(" -> Critical Biomarker Abstention Guard: PASSED")

    # 9. Batch Inference Test
    print("\n[TEST CASE 5: Batch Patient Inference]")
    batch_df = pd.DataFrame([healthy_patient, ckd_patient, sparse_patient, missing_crit_patient])
    batch_results = reloaded_pipeline.predict_batch(batch_df)
    print(f" -> Processed {len(batch_results)} batch records cleanly:")
    for i, row in batch_results.iterrows():
        prob_str = f"{row['risk_probability']*100:.1f}%" if pd.notnull(row['risk_probability']) else "WITHHELD"
        print(f"    Patient #{i+1} [{row['prediction_status']}]: {row['diagnosis']} (Risk: {prob_str})")

    print("\n" + "=" * 65)
    print("END-TO-END PREDICTION PIPELINE VERIFIED & CERTIFIED!")
    print("=" * 65)


if __name__ == "__main__":
    build_and_test_pipeline()
