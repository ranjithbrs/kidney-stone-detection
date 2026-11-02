"""
Phase 4: Baseline Machine Learning Models
Trains and evaluates 5 baseline classifiers:
1. Logistic Regression
2. Decision Tree
3. Random Forest
4. Support Vector Machine (SVM)
5. K-Nearest Neighbors (KNN)
Saves models and records evaluation metrics.
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    matthews_corrcoef,
    confusion_matrix
)

# Output directories
os.makedirs("models/baselines", exist_ok=True)
os.makedirs("runs/baseline", exist_ok=True)


def get_baseline_models(random_state=42):
    """Instantiates the 5 baseline machine-learning algorithms."""
    return {
        "Logistic_Regression": LogisticRegression(
            max_iter=1000,
            random_state=random_state
        ),
        "Decision_Tree": DecisionTreeClassifier(
            random_state=random_state
        ),
        "Random_Forest": RandomForestClassifier(
            n_estimators=100,
            random_state=random_state
        ),
        "Support_Vector_Machine": SVC(
            kernel='rbf',
            probability=True,
            random_state=random_state
        ),
        "K_Nearest_Neighbors": KNeighborsClassifier(
            n_neighbors=5
        )
    }


def evaluate_model(model, X_test, y_test):
    """Computes standard medical evaluation metrics for a trained classifier."""
    y_pred = model.predict(X_test)
    
    # Predict probabilities for ROC-AUC
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
    elif hasattr(model, "decision_function"):
        y_prob = model.decision_function(X_test)
    else:
        y_prob = y_pred

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_test, y_prob)
    except Exception:
        auc = float('nan')
    mcc = matthews_corrcoef(y_test, y_pred)

    return {
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall_sensitivity": round(float(rec), 4),
        "specificity": round(float(specificity), 4),
        "f1_score": round(float(f1), 4),
        "roc_auc": round(float(auc), 4),
        "mcc": round(float(mcc), 4),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp)
        }
    }


def train_and_evaluate_dataset(dataset_prefix, dataset_name):
    """Loads processed splits, trains all 5 baseline models, saves them, and returns metrics."""
    print(f"\n{'='*60}")
    print(f"Training Baseline Models on: {dataset_name} ({dataset_prefix})")
    print(f"{'='*60}")

    # Load preprocessed splits
    X_train = pd.read_csv(f"datasets/processed/{dataset_prefix}_X_train.csv")
    X_test = pd.read_csv(f"datasets/processed/{dataset_prefix}_X_test.csv")
    y_train = pd.read_csv(f"datasets/processed/{dataset_prefix}_y_train.csv").values.ravel()
    y_test = pd.read_csv(f"datasets/processed/{dataset_prefix}_y_test.csv").values.ravel()

    print(f"Loaded: X_train={X_train.shape}, X_test={X_test.shape}")

    models = get_baseline_models(random_state=42)
    results = {}

    for model_name, model in models.items():
        print(f"\n--> Training {model_name}...")
        model.fit(X_train, y_train)

        # Evaluate on test set
        metrics = evaluate_model(model, X_test, y_test)
        results[model_name] = metrics

        # Print summary line
        print(f"    Accuracy:    {metrics['accuracy']*100:.2f}%")
        print(f"    Recall/Sens: {metrics['recall_sensitivity']*100:.2f}%")
        print(f"    Precision:   {metrics['precision']*100:.2f}%")
        print(f"    F1-Score:    {metrics['f1_score']:.4f}")
        print(f"    ROC-AUC:     {metrics['roc_auc']:.4f}")
        print(f"    Confusion:   TP={metrics['confusion_matrix']['tp']}, FP={metrics['confusion_matrix']['fp']}, TN={metrics['confusion_matrix']['tn']}, FN={metrics['confusion_matrix']['fn']}")

        # Save model checkpoint
        save_path = f"models/baselines/{dataset_prefix}_{model_name}.joblib"
        joblib.dump(model, save_path)
        print(f"    Saved model checkpoint: {save_path}")

    return results


def main():
    datasets = [
        ("Dataset_A", "UCI Chronic Kidney Disease (Primary)"),
        ("Dataset_B", "Kidney Stone Urinalysis"),
        ("Dataset_C", "Kaggle CKD Cohort")
    ]

    all_results = {}
    for prefix, name in datasets:
        all_results[prefix] = {
            "name": name,
            "metrics": train_and_evaluate_dataset(prefix, name)
        }

    # Save JSON results
    json_path = "runs/baseline/baseline_results.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[OK] Full baseline metrics recorded to: {json_path}")

    # Generate Markdown Table Report
    md_content = "# Baseline Machine Learning Models Evaluation Report\n\n"
    md_content += "**Phase 4 Baseline Benchmarking** across 5 classifiers:\n"
    md_content += "1. Logistic Regression\n2. Decision Tree\n3. Random Forest\n4. Support Vector Machine (SVM)\n5. K-Nearest Neighbors (KNN)\n\n"

    for prefix, data in all_results.items():
        ds_name = data["name"]
        metrics_dict = data["metrics"]
        md_content += f"## {ds_name} ({prefix})\n\n"
        md_content += "| Model | Accuracy | Precision | Recall (Sens.) | Specificity | F1-Score | ROC-AUC | MCC |\n"
        md_content += "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"

        for model_name, m in metrics_dict.items():
            formatted_name = model_name.replace("_", " ")
            md_content += (
                f"| **{formatted_name}** | {m['accuracy']*100:.2f}% | {m['precision']*100:.2f}% | "
                f"{m['recall_sensitivity']*100:.2f}% | {m['specificity']*100:.2f}% | {m['f1_score']:.4f} | "
                f"{m['roc_auc']:.4f} | {m['mcc']:.4f} |\n"
            )
        md_content += "\n"

    md_path = "runs/baseline/baseline_results.md"
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"[OK] Markdown report generated: {md_path}")


if __name__ == "__main__":
    main()
