# Phase 6: Model Improvement & Hyperparameter Tuning Report

This report summarizes the **Stratified 5-Fold Cross-Validation** tuning results on training data only.

## UCI Chronic Kidney Disease (Primary) (Dataset_A)

| Model | Untuned Accuracy | Tuned Accuracy | Untuned F1 | Tuned F1 | Tuned ROC-AUC | Best Hyperparameters |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Random Forest** | 100.00% | **100.00%** | 1.0000 | **1.0000** | 1.0000 | `criterion=gini`, `max_depth=None`, `min_samples_split=2`, `n_estimators=50` |
| **Support Vector Machine** | 100.00% | **100.00%** | 1.0000 | **1.0000** | 1.0000 | `C=1.0`, `gamma=scale`, `kernel=rbf` |
| **Gradient Boosting** | 100.00% | **100.00%** | 1.0000 | **1.0000** | 1.0000 | `learning_rate=0.05`, `max_depth=3`, `n_estimators=150` |
| **Logistic Regression** | 100.00% | **100.00%** | 1.0000 | **1.0000** | 1.0000 | `C=10.0`, `solver=lbfgs` |
| **K Nearest Neighbors** | 98.75% | **98.75%** | 0.9899 | **0.9899** | 0.9997 | `metric=euclidean`, `n_neighbors=5`, `weights=uniform` |

## Kidney Stone Urinalysis (Dataset_B)

| Model | Untuned Accuracy | Tuned Accuracy | Untuned F1 | Tuned F1 | Tuned ROC-AUC | Best Hyperparameters |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Random Forest** | 61.11% | **61.11%** | 0.6667 | **0.6667** | 0.7716 | `criterion=gini`, `max_depth=None`, `min_samples_split=2`, `n_estimators=200` |
| **Support Vector Machine** | 72.22% | 61.11% | 0.7368 | 0.6667 | 0.7160 | `C=10.0`, `gamma=scale`, `kernel=rbf` |
| **Gradient Boosting** | 66.67% | **72.22%** | 0.7000 | **0.7368** | 0.7778 | `learning_rate=0.2`, `max_depth=3`, `n_estimators=150` |
| **Logistic Regression** | 77.78% | 72.22% | 0.8000 | 0.7619 | 0.8395 | `C=0.1`, `solver=lbfgs` |
| **K Nearest Neighbors** | 50.00% | **61.11%** | 0.5714 | **0.6316** | 0.7037 | `metric=manhattan`, `n_neighbors=5`, `weights=distance` |

