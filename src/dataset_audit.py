import pandas as pd
import numpy as np
import json
import os

datasets = {
    "Dataset A (UCI CKD)": "datasets/clinical/dataset_A_uci_ckd.csv",
    "Dataset B (Kidney Stone Urine)": "datasets/clinical/dataset_B_kidney_stone.csv",
    "Dataset C (Kaggle CKD)": "datasets/clinical/dataset_C_kaggle_ckd.csv"
}

audit_results = {}

for name, path in datasets.items():
    df = pd.read_csv(path)
    # clean extra index column if present
    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])
    if 'id' in df.columns:
        df = df.drop(columns=['id'])
        
    num_rows, num_cols = df.shape
    
    # target detection
    target_col = None
    for cand in ['classification', 'class', 'target', 'success']:
        if cand in df.columns:
            target_col = cand
            break
            
    # missing values
    missing_counts = df.isnull().sum()
    total_missing = int(missing_counts.sum())
    cols_with_missing = {col: int(cnt) for col, cnt in missing_counts.items() if cnt > 0}
    
    # duplicates
    duplicate_count = int(df.duplicated().sum())
    
    # categorical vs numerical
    num_cols_list = list(df.select_dtypes(include=[np.number]).columns)
    cat_cols_list = list(df.select_dtypes(exclude=[np.number]).columns)
    
    # class distribution
    class_dist = {}
    if target_col:
        # strip whitespace in string values if object
        if df[target_col].dtype == object:
            df[target_col] = df[target_col].astype(str).str.strip().str.replace('\t', '')
        val_counts = df[target_col].value_counts().to_dict()
        class_dist = {str(k): int(v) for k, v in val_counts.items()}
        
    audit_results[name] = {
        "rows": num_rows,
        "cols": num_cols,
        "features": list(df.columns),
        "target_col": target_col,
        "total_missing": total_missing,
        "cols_with_missing": cols_with_missing,
        "duplicate_count": duplicate_count,
        "num_features": num_cols_list,
        "cat_features": cat_cols_list,
        "class_distribution": class_dist
    }

print(json.dumps(audit_results, indent=2))

# Save audit results to JSON
os.makedirs("runs/audit", exist_ok=True)
with open("runs/audit/dataset_audit_report.json", "w") as f:
    json.dump(audit_results, f, indent=2)
print("Audit report written to runs/audit/dataset_audit_report.json")
