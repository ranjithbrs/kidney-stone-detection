"""4-Family Leak-Free Stacking Ensemble, Calibration & Subgroup Benchmarking.

Implements Synopsis Section 4.4 & Section 7:
- Base Learner 1: Random Forest (Bagging Decision Trees)
- Base Learner 2: XGBoost (or HistGradientBoosting fallback)
- Base Learner 3: Support Vector Machine (RBF Kernel with Platt probabilities)
- Base Learner 4: Multi-Layer Perceptron (Artificial Neural Network)
- Meta-Learner: Logistic Regression trained on 5-fold stratified out-of-fold base probabilities

All preprocessing (median/mode imputation, StandardScaler, OrdinalEncoder) and
SMOTE class rebalancing are encapsulated inside `imblearn.pipeline.Pipeline` per
base learner so cross-validation folds inside `StackingClassifier` experience
zero data leakage, and the 20% held-out test set (N=80) is strictly reserved
for final evaluation only.
"""

from __future__ import annotations

import functools
import logging
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, StackingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.svm import SVC

from src.pipeline import TOP_10_CONSENSUS_FEATURES
from src.preprocessing import ClinicalDataPreprocessor

try:
    from xgboost import XGBClassifier

    HAS_XGBOOST = True
except ImportError:
    XGBClassifier = None
    HAS_XGBOOST = False

logger = logging.getLogger("nefroai.clinical.stacking_ensemble")

DEFAULT_DATASET_PATH = os.path.join("datasets", "clinical", "dataset_A_uci_ckd.csv")
DEFAULT_STACKING_CACHE_PATH = os.path.join("models", "stacking_ensemble.joblib")
TOP_10_NUM_COLS = ["hemo", "sg", "pcv", "rc", "al", "sc", "bu", "bgr"]
TOP_10_CAT_COLS = ["htn", "dm"]


def _resolve_dataset_path(dataset_path: str) -> str:
    if os.path.exists(dataset_path):
        return dataset_path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate = os.path.join(root, dataset_path)
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(f"Dataset not found: {dataset_path}")


def _make_fold_preprocessor(num_cols: List[str], cat_cols: List[str]) -> ColumnTransformer:
    """Create an unfitted ColumnTransformer for fold-isolated preprocessing."""
    num_pipe = ImbPipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    cat_pipe = ImbPipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    return ColumnTransformer(
        transformers=[
            ("num", num_pipe, num_cols),
            ("cat", cat_pipe, cat_cols),
        ],
        remainder="drop",
    )


def _wrap_in_leak_free_pipeline(estimator: Any, num_cols: List[str], cat_cols: List[str], random_state: int = 42) -> ImbPipeline:
    """Wrap preprocessing, SMOTE, and classifier inside an imblearn Pipeline."""
    return ImbPipeline([
        ("prep", _make_fold_preprocessor(num_cols, cat_cols)),
        ("smote", SMOTE(random_state=random_state)),
        ("clf", estimator),
    ])


def _prepare_raw_top10_split(
    dataset_path: str = DEFAULT_DATASET_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    """Perform exact stratified 80/20 split BEFORE any imputation, scaling, or SMOTE."""
    resolved = _resolve_dataset_path(dataset_path)
    raw_df = pd.read_csv(resolved)
    helper = ClinicalDataPreprocessor(target_col="classification", random_state=random_state)
    clean_df = helper._sanitize_raw_df(raw_df)

    y = (
        clean_df["classification"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"ckd": 1, "notckd": 0, "1": 1, "0": 0})
    )
    if y.isnull().any():
        y = y.fillna(y.mode()[0])
    y_arr = y.astype(int).values

    X_full = clean_df.drop(columns=["classification"])
    X_top10 = X_full[TOP_10_CONSENSUS_FEATURES].copy()
    # Keep normalized string categories ('yes'/'no') cleanly for OrdinalEncoder
    for cat_c in TOP_10_CAT_COLS:
        X_top10[cat_c] = X_top10[cat_c].where(X_top10[cat_c].notna(), np.nan)

    X_train_raw, X_test_raw, y_train, y_test, idx_train, idx_test = train_test_split(
        X_top10,
        y_arr,
        np.arange(len(X_top10)),
        test_size=test_size,
        stratify=y_arr,
        random_state=random_state,
    )
    test_context_df = X_full.iloc[idx_test].reset_index(drop=True)
    return (
        X_train_raw.reset_index(drop=True),
        X_test_raw.reset_index(drop=True),
        y_train,
        y_test,
        test_context_df,
    )


def _compute_bootstrap_cis(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
    n_boot: int = 400,
    seed: int = 42,
) -> Dict[str, Tuple[float, float]]:
    """Compute percentile 95% bootstrap confidence intervals on evaluation metrics."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    aucs, pr_aucs, f1s, senss, specs = [], [], [], [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        yp = y_prob[idx]
        yd = y_pred[idx]
        if len(np.unique(yt)) < 2:
            continue
        aucs.append(roc_auc_score(yt, yp))
        pr_aucs.append(average_precision_score(yt, yp))
        f1s.append(f1_score(yt, yd, average="macro", zero_division=0))
        cm = confusion_matrix(yt, yd, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        senss.append(tp / (tp + fn) if (tp + fn) > 0 else 0.0)
        specs.append(tn / (tn + fp) if (tn + fp) > 0 else 0.0)

    def _ci(arr: List[float]) -> Tuple[float, float]:
        if not arr:
            return (0.0, 1.0)
        return (round(float(np.quantile(arr, 0.025)), 4), round(float(np.quantile(arr, 0.975)), 4))

    return {
        "roc_auc_ci95": _ci(aucs),
        "pr_auc_ci95": _ci(pr_aucs),
        "macro_f1_ci95": _ci(f1s),
        "sensitivity_ci95": _ci(senss),
        "specificity_ci95": _ci(specs),
    }


def _evaluate_binary_classifier(
    name: str,
    model: Any,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
) -> Dict[str, Any]:
    """Compute full classification, calibration, curve, and bootstrap CI metrics."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    roc_auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else float("nan")
    pr_auc = float(average_precision_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else float("nan")
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_prob)
    prob_true, prob_pred = calibration_curve(y_test, y_prob, n_bins=5, strategy="quantile")

    return {
        "model_name": name,
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "sensitivity": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "specificity": round(float(spec), 4),
        "macro_f1": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(float(brier_score_loss(y_test, y_prob)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "roc_curve": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
        "pr_curve": {"precision": prec_curve.tolist(), "recall": rec_curve.tolist()},
        "calibration_curve": {"prob_true": prob_true.tolist(), "prob_pred": prob_pred.tolist()},
        "bootstrap_ci95": _compute_bootstrap_cis(y_test, y_prob, y_pred),
        "y_prob": y_prob.tolist(),
        "y_pred": y_pred.tolist(),
    }


def _evaluate_subgroups(
    y_test: np.ndarray,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
    context_df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """Evaluate classification sensitivity/specificity/Brier across clinical subgroups."""
    subgroups: List[Tuple[str, pd.Series]] = []

    if "age" in context_df.columns:
        age_num = pd.to_numeric(context_df["age"], errors="coerce")
        subgroups.append(("Age < 50 yrs", age_num < 50))
        subgroups.append(("Age >= 50 yrs", age_num >= 50))
    if "htn" in context_df.columns:
        htn_str = context_df["htn"].astype(str).str.strip().str.lower()
        subgroups.append(("Hypertension = yes", htn_str == "yes"))
        subgroups.append(("Hypertension = no", htn_str == "no"))
    if "dm" in context_df.columns:
        dm_str = context_df["dm"].astype(str).str.strip().str.lower()
        subgroups.append(("Diabetes = yes", dm_str == "yes"))
        subgroups.append(("Diabetes = no", dm_str == "no"))

    rows: List[Dict[str, Any]] = []
    for label, mask in subgroups:
        m = mask.fillna(False).values
        n_sub = int(m.sum())
        if n_sub == 0:
            continue
        yt = y_test[m]
        yp = y_prob[m]
        yd = y_pred[m]
        cm = confusion_matrix(yt, yd, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        rows.append({
            "subgroup": label,
            "n": n_sub,
            "ckd_prevalence": round(float(np.mean(yt)), 3),
            "accuracy": round(float(accuracy_score(yt, yd)), 4),
            "sensitivity": round(float(tp / (tp + fn)), 4) if (tp + fn) > 0 else None,
            "specificity": round(float(tn / (tn + fp)), 4) if (tn + fp) > 0 else None,
            "macro_f1": round(float(f1_score(yt, yd, average="macro", zero_division=0)), 4),
            "brier_score": round(float(brier_score_loss(yt, yp)), 4),
        })
    return rows


class StackingClinicalEnsemble:
    """4-Family Stacking Ensemble with leak-free OOF meta-learning and disagreement metrics."""

    def __init__(self, dataset_path: str = DEFAULT_DATASET_PATH, random_state: int = 42) -> None:
        self.dataset_path = dataset_path
        self.random_state = random_state
        self.boost_family_name = "XGBoost" if HAS_XGBOOST else "HistGradientBoosting"

        X_train_raw, X_test_raw, y_train, y_test, test_ctx = _prepare_raw_top10_split(
            dataset_path=dataset_path, test_size=0.2, random_state=random_state
        )
        self.X_train_raw = X_train_raw
        self.X_test_raw = X_test_raw
        self.y_train = y_train
        self.y_test = y_test
        self.test_context_df = test_ctx

        # 4 distinct model architectures wrapped in leak-free imblearn pipelines
        rf_est = RandomForestClassifier(n_estimators=100, random_state=random_state)
        if HAS_XGBOOST and XGBClassifier is not None:
            gb_est = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.08,
                eval_metric="logloss",
                random_state=random_state,
            )
        else:
            gb_est = HistGradientBoostingClassifier(max_iter=100, random_state=random_state)

        svm_est = SVC(C=10.0, kernel="rbf", probability=True, random_state=random_state)
        mlp_est = MLPClassifier(
            hidden_layer_sizes=(64, 32),
            alpha=0.1,
            max_iter=800,
            random_state=random_state,
        )

        self.base_estimators: List[Tuple[str, ImbPipeline]] = [
            ("Random Forest", _wrap_in_leak_free_pipeline(rf_est, TOP_10_NUM_COLS, TOP_10_CAT_COLS, random_state)),
            (self.boost_family_name, _wrap_in_leak_free_pipeline(gb_est, TOP_10_NUM_COLS, TOP_10_CAT_COLS, random_state)),
            ("SVM (RBF)", _wrap_in_leak_free_pipeline(svm_est, TOP_10_NUM_COLS, TOP_10_CAT_COLS, random_state)),
            ("ANN (MLP)", _wrap_in_leak_free_pipeline(mlp_est, TOP_10_NUM_COLS, TOP_10_CAT_COLS, random_state)),
        ]
        self.baseline_lr = _wrap_in_leak_free_pipeline(
            LogisticRegression(max_iter=1000, random_state=random_state),
            TOP_10_NUM_COLS,
            TOP_10_CAT_COLS,
            random_state,
        )
        self.stacking_clf = StackingClassifier(
            estimators=self.base_estimators,
            final_estimator=LogisticRegression(max_iter=1000, random_state=random_state),
            cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state),
            stack_method="predict_proba",
            passthrough=False,
        )

        # Fit strictly on X_train_raw, y_train (320 training patients only)
        self.baseline_lr.fit(X_train_raw, y_train)
        self.stacking_clf.fit(X_train_raw, y_train)

        # Compute held-out evaluation report on untouched 80 test patients
        self.evaluation_report = self._compute_evaluation_report()

    def _compute_evaluation_report(self) -> Dict[str, Any]:
        models_metrics: Dict[str, Dict[str, Any]] = {}
        models_metrics["Logistic Regression (Baseline)"] = _evaluate_binary_classifier(
            "Logistic Regression (Baseline)", self.baseline_lr, self.X_test_raw, self.y_test
        )
        for (name, _), fitted_est in zip(self.base_estimators, self.stacking_clf.estimators_):
            models_metrics[name] = _evaluate_binary_classifier(
                name, fitted_est, self.X_test_raw, self.y_test
            )

        stack_metrics = _evaluate_binary_classifier(
            "Stacking Ensemble (Meta-LR)", self.stacking_clf, self.X_test_raw, self.y_test
        )
        models_metrics["Stacking Ensemble (Meta-LR)"] = stack_metrics

        meta_lr = self.stacking_clf.final_estimator_
        meta_weights = {
            name: round(float(coef), 4)
            for (name, _), coef in zip(self.base_estimators, meta_lr.coef_[0])
        }

        subgroups = _evaluate_subgroups(
            y_test=self.y_test,
            y_prob=np.asarray(stack_metrics["y_prob"], dtype=float),
            y_pred=np.asarray(stack_metrics["y_pred"], dtype=int),
            context_df=self.test_context_df,
        )

        return {
            "train_samples": int(len(self.X_train_raw)),
            "test_samples": int(len(self.X_test_raw)),
            "xgboost_active": HAS_XGBOOST,
            "meta_learner_weights": meta_weights,
            "models": models_metrics,
            "subgroup_analysis": subgroups,
        }

    def _record_to_top10_df(self, record: Dict[str, Any]) -> pd.DataFrame:
        row: Dict[str, Any] = {}
        for col in TOP_10_NUM_COLS:
            val = record.get(col, np.nan)
            try:
                row[col] = float(val) if val is not None and str(val).strip() not in ("", "?", "nan", "None") else np.nan
            except (ValueError, TypeError):
                row[col] = np.nan
        for col in TOP_10_CAT_COLS:
            val = record.get(col, np.nan)
            if val is None or str(val).strip() in ("", "?", "nan", "None"):
                row[col] = np.nan
            else:
                s = str(val).strip().lower()
                row[col] = "yes" if s in ("1", "true", "t", "yes", "y", "present") else (
                    "no" if s in ("0", "false", "f", "no", "n", "absent", "notpresent") else s
                )
        return pd.DataFrame([row], columns=TOP_10_CONSENSUS_FEATURES)

    def predict_with_disagreement(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Predict CKD probability with the Stacking Ensemble and compute cross-architecture disagreement."""
        X_df = self._record_to_top10_df(record)
        stack_prob = float(self.stacking_clf.predict_proba(X_df)[0, 1])
        stack_cls = int(stack_prob >= 0.50)

        base_probs: Dict[str, float] = {}
        votes_ckd = 0
        for (name, _), fitted_est in zip(self.base_estimators, self.stacking_clf.estimators_):
            p = float(fitted_est.predict_proba(X_df)[0, 1])
            base_probs[name] = round(p, 4)
            if p >= 0.50:
                votes_ckd += 1

        prob_vals = list(base_probs.values())
        spread = round(float(max(prob_vals) - min(prob_vals)), 4)
        std_dev = round(float(np.std(prob_vals)), 4)

        p_clip = min(max(stack_prob, 1e-9), 1.0 - 1e-9)
        entropy = round(float(-(p_clip * math.log2(p_clip) + (1.0 - p_clip) * math.log2(1.0 - p_clip))), 4)

        votes_healthy = len(prob_vals) - votes_ckd
        split_votes = 0 < votes_ckd < len(prob_vals)
        has_disagreement = split_votes or (spread >= 0.45)

        return {
            "stacking_probability": round(stack_prob, 4),
            "stacking_class": stack_cls,
            "base_probabilities": base_probs,
            "disagreement_spread": spread,
            "disagreement_std": std_dev,
            "predictive_entropy_bits": entropy,
            "vote_split": {"ckd": votes_ckd, "healthy": votes_healthy},
            "has_architecture_disagreement": has_disagreement,
        }


@functools.lru_cache(maxsize=2)
def get_stacking_ensemble(
    dataset_path: str = DEFAULT_DATASET_PATH,
    cache_path: str = DEFAULT_STACKING_CACHE_PATH,
) -> StackingClinicalEnsemble:
    """Cached singleton accessor for the 4-family leak-free Stacking Ensemble."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    resolved_cache = cache_path if os.path.exists(cache_path) else os.path.join(root, cache_path)
    if dataset_path == DEFAULT_DATASET_PATH and os.path.exists(resolved_cache):
        try:
            loaded = joblib.load(resolved_cache)
            if isinstance(loaded, StackingClinicalEnsemble) and loaded.evaluation_report.get("xgboost_active") == HAS_XGBOOST:
                return loaded
        except Exception as ex:
            logger.warning("Failed loading cached stacking ensemble (%s); rebuilding cleanly.", ex)

    ens = StackingClinicalEnsemble(dataset_path=dataset_path)
    if dataset_path == DEFAULT_DATASET_PATH:
        try:
            target_cache = cache_path if os.path.isabs(cache_path) else os.path.join(root, cache_path)
            os.makedirs(os.path.dirname(target_cache), exist_ok=True)
            joblib.dump(ens, target_cache)
        except Exception as ex:
            logger.warning("Could not persist stacking cache: %s", ex)
    return ens
