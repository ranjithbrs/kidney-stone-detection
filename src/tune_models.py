"""
Phase 6: Model Improvement & Hyperparameter Tuning (NefroAI Implementation)
Performs Stratified 5-Fold Cross-Validation on training data only to tune:
1. Random Forest Classifier
2. Support Vector Machine (SVC)
3. Gradient Boosting Classifier (Tree Boosting)
4. Logistic Regression
5. K-Nearest Neighbors Classifier
Compares untuned vs tuned models, saves best configurations.
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
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

os.makedirs("models/tuned", exist_ok=True)
os.makedirs("runs/tuning", exist_ok=True)


def get_hyperparameter_grids(random_state=42):
    """Defines candidate models and their respective hyperparameter search grids."""
    return {
        "Random_Forest": {
            "model": RandomForestClassifier(random_state=random_state),
            "param_grid": {
                "n_estimators": [50, 100, 200],
                "max_depth": [None, 5, 10, 15],
                "min_samples_split": [2, 5],
                "criterion": ["gini", "entropy"]
            }
        },
        "Support_Vector_Machine": {
            "model": SVC(probability=True, random_state=random_state),
            "param_grid": {
                "C": [0.1, 1.0, 10.0, 50.0],
                "kernel": ["rbf", "linear"],
                "gamma": ["scale", "auto"]
            }
        },
        "Gradient_Boosting": {
            "model": GradientBoostingClassifier(random_state=random_state),
            "param_grid": {
                "n_estimators": [50, 100, 150],
                "learning_rate": [0.05, 0.1, 0.2],
                "max_depth": [3, 5]
            }
        },
        "Logistic_Regression": {
            "model": LogisticRegression(max_iter=1000, random_state=random_state),
            "param_grid": {
                "C": [0.01, 0.1, 1.0, 10.0],
                "solver": ["liblinear", "lbfgs"]
            }
        },
        "K_Nearest_Neighbors": {
            "model": KNeighborsClassifier(),
            "param_grid": {
                "n_neighbors": [3, 5, 7, 9],
                "weights": ["uniform", "distance"],
                "metric": ["euclidean", "manhattan"]
            }
        }
    }


def compute_metrics(model, X_test, y_test):
    """Evaluates a model on test data and returns clinical metrics."""
    y_pred = model.predict(X_test)
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
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
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
    }


def tune_dataset_models(dataset_prefix, dataset_name, use_selected_features=False):
    """Executes 5-fold cross-validation tuning on the dataset training fold."""
    print(f"\n{'='*65}")
    print(f"HYPERPARAMETER TUNING: {dataset_name} ({dataset_prefix})")
    print(f"{'='*65}")

    X_train = pd.read_csv(f"datasets/processed/{dataset_prefix}_X_train.csv")
    X_test = pd.read_csv(f"datasets/processed/{dataset_prefix}_X_test.csv")
    y_train = pd.read_csv(f"datasets/processed/{dataset_prefix}_y_train.csv").values.ravel()
    y_test = pd.read_csv(f"datasets/processed/{dataset_prefix}_y_test.csv").values.ravel()

    # If requested, filter to top consensus features from Phase 5
    if use_selected_features and os.path.exists("runs/feature_selection/selected_features.json"):
        with open("runs/feature_selection/selected_features.json") as f:
            sel = json.load(f)
        if dataset_prefix in sel:
            feats = sel[dataset_prefix]["selected_features"].get("hybrid_top10") or sel[dataset_prefix]["selected_features"].get("hybrid_top4")
            if feats:
                print(f"Applying Top-{len(feats)} selected features: {feats}")
                X_train = X_train[feats]
                X_test = X_test[feats]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    model_configs = get_hyperparameter_grids(random_state=42)

    tuning_summary = {}

    for model_name, cfg in model_configs.items():
        base_model = cfg["model"]
        param_grid = cfg["param_grid"]

        print(f"\n--> Tuning {model_name}...")

        # 1. Evaluate Untuned Baseline
        base_model.fit(X_train, y_train)
        untuned_metrics = compute_metrics(base_model, X_test, y_test)

        # 2. Perform Grid Search with Stratified 5-Fold CV (Training Data ONLY)
        grid_search = GridSearchCV(
            estimator=cfg["model"],
            param_grid=param_grid,
            cv=cv,
            scoring="f1",
            n_jobs=-1,
            refit=True
        )
        grid_search.fit(X_train, y_train)

        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_
        best_cv_score = grid_search.best_score_

        # 3. Evaluate Tuned Model on Held-out Test Set
        tuned_metrics = compute_metrics(best_model, X_test, y_test)

        print(f"    Best CV F1:     {best_cv_score:.4f}")
        print(f"    Best Params:    {best_params}")
        print(f"    Untuned Test:   Acc={untuned_metrics['accuracy']*100:.2f}%, F1={untuned_metrics['f1_score']:.4f}, AUC={untuned_metrics['roc_auc']:.4f}")
        print(f"    Tuned Test:     Acc={tuned_metrics['accuracy']*100:.2f}%, F1={tuned_metrics['f1_score']:.4f}, AUC={tuned_metrics['roc_auc']:.4f}")

        # Save best model checkpoint
        save_path = f"models/tuned/{dataset_prefix}_{model_name}_best.joblib"
        joblib.dump(best_model, save_path)

        tuning_summary[model_name] = {
            "best_params": best_params,
            "best_cv_f1_score": round(float(best_cv_score), 4),
            "untuned_metrics": untuned_metrics,
            "tuned_metrics": tuned_metrics,
            "checkpoint_path": save_path
        }

    return tuning_summary


def main():
    experiments = [
        ("Dataset_A", "UCI Chronic Kidney Disease (Primary)"),
        ("Dataset_B", "Kidney Stone Urinalysis")
    ]

    results = {}
    for prefix, name in experiments:
        results[prefix] = {
            "name": name,
            "models": tune_dataset_models(prefix, name, use_selected_features=True)
        }

    # Save JSON summary
    with open("runs/tuning/tuning_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n[OK] Tuning results saved to: runs/tuning/tuning_results.json")

    # Generate Markdown Comparison Report
    md = "# Phase 6: Model Improvement & Hyperparameter Tuning Report\n\n"
    md += "This report summarizes the **Stratified 5-Fold Cross-Validation** tuning results on training data only.\n\n"

    for prefix, data in results.items():
        ds_name = data["name"]
        models_data = data["models"]

        md += f"## {ds_name} ({prefix})\n\n"
        md += "| Model | Untuned Accuracy | Tuned Accuracy | Untuned F1 | Tuned F1 | Tuned ROC-AUC | Best Hyperparameters |\n"
        md += "| :--- | :---: | :---: | :---: | :---: | :---: | :--- |\n"

        for m_name, info in models_data.items():
            u = info["untuned_metrics"]
            t = info["tuned_metrics"]
            params_str = ", ".join([f"`{k}={v}`" for k, v in info["best_params"].items()])
            formatted_name = m_name.replace("_", " ")

            acc_display = f"**{t['accuracy']*100:.2f}%**" if t['accuracy'] >= u['accuracy'] else f"{t['accuracy']*100:.2f}%"
            f1_display = f"**{t['f1_score']:.4f}**" if t['f1_score'] >= u['f1_score'] else f"{t['f1_score']:.4f}"

            md += (
                f"| **{formatted_name}** | {u['accuracy']*100:.2f}% | {acc_display} | "
                f"{u['f1_score']:.4f} | {f1_display} | {t['roc_auc']:.4f} | {params_str} |\n"
            )
        md += "\n"

    with open("runs/tuning/tuning_report.md", "w") as f:
        f.write(md)
    print("[OK] Tuning report generated at: runs/tuning/tuning_report.md")


if __name__ == "__main__":
    main()
