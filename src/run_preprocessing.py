"""
Executes and validates the preprocessing pipeline on Datasets A, B, and C.
Saves clean processed train/test splits and serialized pipelines.
"""

import os
import pandas as pd
from preprocessing import ClinicalDataPreprocessor

os.makedirs("datasets/processed", exist_ok=True)
os.makedirs("models", exist_ok=True)

datasets_to_process = [
    {
        "id": "Dataset_A",
        "name": "UCI Chronic Kidney Disease",
        "path": "datasets/clinical/dataset_A_uci_ckd.csv",
        "target": "classification"
    },
    {
        "id": "Dataset_B",
        "name": "Kidney Stone Urinalysis",
        "path": "datasets/clinical/dataset_B_kidney_stone.csv",
        "target": "target"
    },
    {
        "id": "Dataset_C",
        "name": "Kaggle CKD Cohort",
        "path": "datasets/clinical/dataset_C_kaggle_ckd.csv",
        "target": "classification"
    }
]

print("=" * 60)
print("PHASE 3: EXECUTING CLINICAL DATA PREPROCESSING PIPELINE")
print("=" * 60)

for item in datasets_to_process:
    ds_id = item["id"]
    ds_name = item["name"]
    file_path = item["path"]
    target_col = item["target"]

    print(f"\n[Processing {ds_id}: {ds_name}]")
    print(f"Reading from: {file_path}")

    # Initialize Preprocessor
    preprocessor = ClinicalDataPreprocessor(
        target_col=target_col,
        scale_type="standard",
        apply_smote=True,
        random_state=42
    )

    # Execute full leak-free preparation
    X_train, X_test, y_train, y_test = preprocessor.prepare_data(file_path, test_size=0.2)

    # Validation Checks
    print(f" -> Features: {len(preprocessor.feature_names)} ({len(preprocessor.num_cols)} numerical, {len(preprocessor.cat_cols)} categorical)")
    print(f" -> Train split shape (post-SMOTE): X_train={X_train.shape}, y_train={y_train.shape}")
    print(f" -> Test split shape (pristine):   X_test={X_test.shape}, y_test={y_test.shape}")
    print(f" -> Train class distribution:     {dict(pd.Series(y_train).value_counts())}")
    print(f" -> Test class distribution:      {dict(pd.Series(y_test).value_counts())}")
    print(f" -> Missing values in X_train:    {X_train.isnull().sum().sum()}")
    print(f" -> Missing values in X_test:     {X_test.isnull().sum().sum()}")

    assert X_train.isnull().sum().sum() == 0, f"Error: X_train has missing values in {ds_id}"
    assert X_test.isnull().sum().sum() == 0, f"Error: X_test has missing values in {ds_id}"

    # Save processed splits
    X_train.to_csv(f"datasets/processed/{ds_id}_X_train.csv", index=False)
    X_test.to_csv(f"datasets/processed/{ds_id}_X_test.csv", index=False)
    pd.DataFrame({"target": y_train}).to_csv(f"datasets/processed/{ds_id}_y_train.csv", index=False)
    pd.DataFrame({"target": y_test}).to_csv(f"datasets/processed/{ds_id}_y_test.csv", index=False)

    # Save fitted preprocessor pipeline
    pipeline_save_path = f"models/preprocessor_{ds_id}.joblib"
    preprocessor.save_pipeline(pipeline_save_path)

    # Verify single record real-time transform capability
    test_record = X_test.iloc[0].to_dict()
    transformed_rec = preprocessor.transform_single_record(test_record)
    assert transformed_rec.shape[1] == len(preprocessor.feature_names)
    print(f" -> Single-record real-time inference transform test: PASSED (shape: {transformed_rec.shape})")

print("\n" + "=" * 60)
print("ALL PREPROCESSING PIPELINES EXECUTED AND VERIFIED!")
print("=" * 60)
