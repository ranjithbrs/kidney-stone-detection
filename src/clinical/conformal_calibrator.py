"""Dynamic Conformal Calibration for CD-CIRPVM (NephroGuard-AI).

Computes finite-sample inductive split-conformal and stratified cross-conformal
(out-of-fold) non-conformity quantiles strictly from the UCI CKD training
partition (`N=320`), leaving the held-out test partition (`N=80`) untouched.

All preprocessing (median/mode imputation, StandardScaler) and SMOTE class
rebalancing are fitted strictly inside each proper-training fold to prevent
data leakage into calibration residuals.
"""

from __future__ import annotations

import functools
import logging
import math
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, train_test_split

from src.clinical_input_reliability_mechanism import ClinicalInputReliabilityMechanism
from src.pipeline import TOP_10_CONSENSUS_FEATURES
from src.preprocessing import ClinicalDataPreprocessor

logger = logging.getLogger("nefroai.clinical.conformal_calibrator")

DEFAULT_DATASET_PATH = os.path.join("datasets", "clinical", "dataset_A_uci_ckd.csv")
DEFAULT_FALLBACK_QUANTILE = 0.261


@dataclass(frozen=True)
class ConformalCalibrationResult:
    """Typed summary of a dynamically fitted conformal calibration run."""

    conformal_quantile: float
    alpha: float
    coverage_target: float
    calibration_samples: int
    calibration_method: str
    empirical_coverage_on_calibration: float
    nonconformity_summary: Dict[str, float]
    train_partition_size: int
    held_out_test_excluded: bool = True
    fallback_used: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _resolve_dataset_path(dataset_path: str) -> Optional[str]:
    """Resolve dataset path from cwd or project root."""
    if os.path.exists(dataset_path):
        return dataset_path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate = os.path.join(root, dataset_path)
    if os.path.exists(candidate):
        return candidate
    return None


def _prepare_raw_uci_training_split(
    dataset_path: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.Series, list[str], list[str]]:
    """Reproduce the exact stratified 80/20 split and discard the held-out test set."""
    raw_df = pd.read_csv(dataset_path)
    helper = ClinicalDataPreprocessor(
        target_col="classification",
        scale_type="standard",
        apply_smote=True,
        random_state=random_state,
    )
    clean_df = helper._sanitize_raw_df(raw_df)
    target_col = "classification"
    if target_col not in clean_df.columns:
        raise ValueError(f"Expected target column '{target_col}' in {dataset_path}")

    y_raw = clean_df[target_col].astype(str).str.strip().str.lower()
    y = y_raw.map({"ckd": 1, "notckd": 0, "1": 1, "0": 0})
    if y.isnull().any():
        y = y.fillna(y.mode()[0])
    y = y.astype(int)

    X = clean_df.drop(columns=[target_col])
    num_cols = list(X.select_dtypes(include=[np.number]).columns)
    cat_cols = list(X.select_dtypes(exclude=[np.number]).columns)

    # Stratified split identical to preprocessing.py; X_test_raw / y_test_raw discarded immediately
    X_train_raw, _, y_train_raw, _ = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )
    return X_train_raw.reset_index(drop=True), y_train_raw.reset_index(drop=True), num_cols, cat_cols


def _fit_fold_and_score_calibration(
    X_proper: pd.DataFrame,
    y_proper: pd.Series,
    X_cal: pd.DataFrame,
    y_cal: pd.Series,
    num_cols: list[str],
    cat_cols: list[str],
    base_estimator: Any,
    selected_features: list[str],
    random_state: int = 42,
) -> np.ndarray:
    """Fit fold preprocessor + SMOTE strictly on proper-train and score calibration residuals."""
    fold_prep = ClinicalDataPreprocessor(
        target_col="classification",
        scale_type="standard",
        apply_smote=True,
        random_state=random_state,
    )
    fold_prep.num_cols = list(num_cols)
    fold_prep.cat_cols = list(cat_cols)
    fold_prep.feature_names = list(num_cols) + list(cat_cols)

    X_prop_arr = fold_prep._fit_transform_features(X_proper)
    y_prop_arr = np.asarray(y_proper, dtype=int)

    if len(np.unique(y_prop_arr)) > 1:
        X_prop_res, y_prop_res = fold_prep.smote.fit_resample(X_prop_arr, y_prop_arr)
    else:
        X_prop_res, y_prop_res = X_prop_arr, y_prop_arr

    X_prop_df = pd.DataFrame(X_prop_res, columns=fold_prep.feature_names)[selected_features]
    X_cal_arr = fold_prep._transform_features(X_cal)
    X_cal_df = pd.DataFrame(X_cal_arr, columns=fold_prep.feature_names)[selected_features]

    clf = clone(base_estimator)
    clf.fit(X_prop_df, y_prop_res)

    probs = clf.predict_proba(X_cal_df)
    y_cal_arr = np.asarray(y_cal, dtype=int)
    # Non-conformity score: s_i = 1 - p(y_i | x_i)
    return 1.0 - probs[np.arange(len(y_cal_arr)), y_cal_arr]


def calibrate_conformal_quantile(
    model_estimator: Optional[Any] = None,
    dataset_path: str = DEFAULT_DATASET_PATH,
    alpha: float = 0.05,
    method: str = "oof",
    n_splits: int = 5,
    cal_fraction: float = 0.25,
    random_state: int = 42,
    selected_features: Optional[list[str]] = None,
) -> ConformalCalibrationResult:
    """Compute a dynamically calibrated conformal non-conformity quantile.

    Parameters
    ----------
    model_estimator : Optional[Any]
        Unfitted or fitted sklearn estimator to clone for fold calibration.
        Defaults to the champion `RandomForestClassifier(n_estimators=50, random_state=42)`.
    dataset_path : str
        Path to the UCI CKD ground-truth CSV (`dataset_A_uci_ckd.csv`).
    alpha : float, default=0.05
        Target miscoverage rate (1 - alpha = 95% finite-sample coverage guarantee).
    method : str, default="oof"
        `"oof"` for Stratified K-Fold cross-conformal calibration across the full
        320-patient training partition, or `"split"` for single inductive split
        calibration inside the training partition.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must lie strictly in (0, 1); got {alpha}")
    if method not in ("oof", "split"):
        raise ValueError(f"method must be 'oof' or 'split'; got {method!r}")

    resolved_path = _resolve_dataset_path(dataset_path)
    if resolved_path is None:
        logger.warning(
            "Dataset %s not found; falling back to default quantile %.3f.",
            dataset_path,
            DEFAULT_FALLBACK_QUANTILE,
        )
        return ConformalCalibrationResult(
            conformal_quantile=DEFAULT_FALLBACK_QUANTILE,
            alpha=alpha,
            coverage_target=round(1.0 - alpha, 4),
            calibration_samples=0,
            calibration_method=f"{method}_fallback",
            empirical_coverage_on_calibration=1.0 - alpha,
            nonconformity_summary={},
            train_partition_size=0,
            held_out_test_excluded=True,
            fallback_used=True,
            notes="Training dataset unavailable; fallback conformal quantile applied.",
        )

    estimator = (
        model_estimator
        if model_estimator is not None
        else RandomForestClassifier(n_estimators=50, random_state=random_state)
    )
    feats = list(selected_features or TOP_10_CONSENSUS_FEATURES)

    X_train_raw, y_train_raw, num_cols, cat_cols = _prepare_raw_uci_training_split(
        resolved_path, test_size=0.2, random_state=random_state
    )

    if method == "oof":
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        cal_scores = np.zeros(len(X_train_raw), dtype=float)
        for tr_idx, cal_idx in skf.split(X_train_raw, y_train_raw):
            cal_scores[cal_idx] = _fit_fold_and_score_calibration(
                X_proper=X_train_raw.iloc[tr_idx],
                y_proper=y_train_raw.iloc[tr_idx],
                X_cal=X_train_raw.iloc[cal_idx],
                y_cal=y_train_raw.iloc[cal_idx],
                num_cols=num_cols,
                cat_cols=cat_cols,
                base_estimator=estimator,
                selected_features=feats,
                random_state=random_state,
            )
        method_label = f"oof_stratified_{n_splits}fold"
    else:
        X_prop, X_cal, y_prop, y_cal = train_test_split(
            X_train_raw,
            y_train_raw,
            test_size=cal_fraction,
            stratify=y_train_raw,
            random_state=random_state,
        )
        cal_scores = _fit_fold_and_score_calibration(
            X_proper=X_prop,
            y_proper=y_prop,
            X_cal=X_cal,
            y_cal=y_cal,
            num_cols=num_cols,
            cat_cols=cat_cols,
            base_estimator=estimator,
            selected_features=feats,
            random_state=random_state,
        )
        method_label = f"inductive_split_{int(round((1 - cal_fraction) * 100))}_{int(round(cal_fraction * 100))}"

    n_cal = len(cal_scores)
    # Finite-sample conformal quantile: ceil((n + 1)(1 - alpha)) / n
    finite_sample_level = min(math.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal, 1.0)
    q_hat = float(np.quantile(cal_scores, finite_sample_level, method="higher"))
    q_hat = round(max(0.0, min(1.0, q_hat)), 4)

    empirical_cov = round(float(np.mean(cal_scores <= q_hat)), 4)
    summary = {
        "min": round(float(np.min(cal_scores)), 4),
        "median": round(float(np.median(cal_scores)), 4),
        "p90": round(float(np.quantile(cal_scores, 0.90)), 4),
        "p95": round(float(np.quantile(cal_scores, 0.95)), 4),
        "max": round(float(np.max(cal_scores)), 4),
    }

    return ConformalCalibrationResult(
        conformal_quantile=q_hat,
        alpha=alpha,
        coverage_target=round(1.0 - alpha, 4),
        calibration_samples=n_cal,
        calibration_method=method_label,
        empirical_coverage_on_calibration=empirical_cov,
        nonconformity_summary=summary,
        train_partition_size=len(X_train_raw),
        held_out_test_excluded=True,
        fallback_used=False,
        notes=(
            f"Calibrated strictly on {n_cal} training-partition residuals "
            f"(80 held-out test records excluded) via {method_label}."
        ),
    )


@functools.lru_cache(maxsize=8)
def get_calibrated_conformal_result(
    alpha: float = 0.05,
    method: str = "oof",
) -> ConformalCalibrationResult:
    """Cached accessor for the default UCI CKD training-split conformal calibration."""
    return calibrate_conformal_quantile(alpha=alpha, method=method)


def build_calibrated_reliability_mechanism(
    alpha: float = 0.05,
    reliability_threshold: float = 0.60,
    method: str = "oof",
) -> Tuple[ClinicalInputReliabilityMechanism, ConformalCalibrationResult]:
    """Instantiate CD-CIRPVM with a dynamically calibrated conformal quantile."""
    cal_result = get_calibrated_conformal_result(alpha=alpha, method=method)
    mechanism = ClinicalInputReliabilityMechanism(
        conformal_quantile=cal_result.conformal_quantile,
        alpha=alpha,
        reliability_threshold=reliability_threshold,
    )
    return mechanism, cal_result


def evaluate_consensus_cirpvm(
    raw_biomarkers: Dict[str, Any],
    reliability_mechanism: ClinicalInputReliabilityMechanism,
    selected_features: list[str],
    risk_probability: Optional[float],
    prediction_status: str = "PREDICTION_AVAILABLE",
    sanitized_from_pipe: Optional[Dict[str, Any]] = None,
    feature_anomalies: Optional[Dict[str, Any]] = None,
    calibration_method: str = "configured_quantile",
) -> Dict[str, Any]:
    """Shared CD-CIRPVM evaluation over the Top-10 consensus screening panel.

    Computes MIDR unit audit, consensus-panel Clinical Reliability Index (CRI),
    and split/cross-conformal prediction set gate without spuriously penalizing
    absent auxiliary 24-panel analytes (e.g., bp, sod, pot, wc, su).
    """
    sanitized_pipe = sanitized_from_pipe or {}
    anomalies = feature_anomalies or {}

    cirpvm_input = dict(raw_biomarkers)
    for k, raw_v in raw_biomarkers.items():
        if isinstance(raw_v, str) and k in sanitized_pipe:
            cirpvm_input[k] = sanitized_pipe[k]

    reconciled, unit_audit = reliability_mechanism.reconcile_units(cirpvm_input)
    _, _, bounds_audit, _ = reliability_mechanism.sanitize_and_score_reliability(reconciled)

    cri = 1.00
    relevant_bounds: Dict[str, Any] = {}
    for feat in selected_features:
        b_info = bounds_audit.get(feat)
        if b_info is not None:
            status = b_info.get("status")
            if status == "IMPUTED_DEFAULT":
                cri -= 0.12
                relevant_bounds[feat] = b_info
            elif status in ("NAN_INF_INTERCEPTED", "PARSING_ERROR_DEFAULT"):
                cri -= 0.15
                relevant_bounds[feat] = b_info
            elif status in ("CLAMPED_BELOW_PHYSIOLOGICAL_MIN", "CLAMPED_ABOVE_PHYSIOLOGICAL_MAX"):
                cri -= 0.08
                relevant_bounds[feat] = b_info
        elif feat in ("htn", "dm"):
            raw_cat = raw_biomarkers.get(feat)
            if raw_cat is None or str(raw_cat).strip() in ("", "?", "nan", "NaN", "None", "null"):
                cri -= 0.08
                relevant_bounds[feat] = {"status": "MISSING_CATEGORICAL"}

    for feat, b_info in bounds_audit.items():
        if feat not in selected_features and feat in raw_biomarkers and raw_biomarkers.get(feat) is not None:
            status = b_info.get("status")
            if status in ("NAN_INF_INTERCEPTED", "PARSING_ERROR_DEFAULT"):
                cri -= 0.12
                relevant_bounds[feat] = b_info
            elif status in ("CLAMPED_BELOW_PHYSIOLOGICAL_MIN", "CLAMPED_ABOVE_PHYSIOLOGICAL_MAX"):
                cri -= 0.08
                relevant_bounds[feat] = b_info

    for feat, anom in anomalies.items():
        if anom.get("status") in ("INVALID_REPRESENTATION", "UNSUPPORTED_UNIT", "UNPARSEABLE", "OUT_OF_DOMAIN"):
            if feat not in relevant_bounds:
                cri -= 0.12
                relevant_bounds[feat] = anom

    cri_score = max(0.0, min(1.0, round(cri, 2)))

    if risk_probability is None:
        gate_res = {
            "decision": "ABSTAIN",
            "gate_status": prediction_status or "REJECTED_UNRELIABLE_DATA",
            "conformal_set": [0, 1],
        }
    else:
        gate_res = reliability_mechanism.evaluate_conformal_gate(
            [1.0 - float(risk_probability), float(risk_probability)],
            cri_score,
        )

    non_native_units = {
        k: v for k, v in unit_audit.items() if v.get("status") != "native_standard"
    }

    return {
        "clinical_reliability_index": cri_score,
        "conformal_set": list(gate_res.get("conformal_set", [])),
        "conformal_gate_decision": gate_res.get("decision"),
        "conformal_gate_status": gate_res.get("gate_status"),
        "conformal_quantile": float(reliability_mechanism.conformal_quantile),
        "conformal_coverage_target": round(1.0 - float(reliability_mechanism.alpha), 4),
        "conformal_calibration_method": calibration_method,
        "unit_reconciliation_audit": non_native_units,
        "bounds_clamping_audit": relevant_bounds,
    }


@dataclass(frozen=True)
class MondrianCalibrationResult:
    """Class-conditional (Mondrian) finite-sample conformal quantiles on training OOF split."""

    q_healthy: float
    q_ckd: float
    alpha: float
    coverage_target: float
    n_healthy: int
    n_ckd: int
    empirical_coverage_healthy: float
    empirical_coverage_ckd: float
    calibration_method: str
    held_out_test_excluded: bool = True
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calibrate_mondrian_conformal(
    model_estimator: Optional[Any] = None,
    dataset_path: str = DEFAULT_DATASET_PATH,
    alpha: float = 0.05,
    n_splits: int = 5,
    random_state: int = 42,
    selected_features: Optional[list[str]] = None,
) -> MondrianCalibrationResult:
    """Compute separate finite-sample (1 - alpha) non-conformity quantiles per true class."""
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must lie strictly in (0, 1); got {alpha}")

    resolved_path = _resolve_dataset_path(dataset_path)
    if resolved_path is None:
        return MondrianCalibrationResult(
            q_healthy=DEFAULT_FALLBACK_QUANTILE,
            q_ckd=DEFAULT_FALLBACK_QUANTILE,
            alpha=alpha,
            coverage_target=round(1.0 - alpha, 4),
            n_healthy=0,
            n_ckd=0,
            empirical_coverage_healthy=1.0 - alpha,
            empirical_coverage_ckd=1.0 - alpha,
            calibration_method="mondrian_oof_fallback",
            held_out_test_excluded=True,
            fallback_used=True,
        )

    estimator = (
        model_estimator
        if model_estimator is not None
        else RandomForestClassifier(n_estimators=50, random_state=random_state)
    )
    feats = list(selected_features or TOP_10_CONSENSUS_FEATURES)

    X_train_raw, y_train_raw, num_cols, cat_cols = _prepare_raw_uci_training_split(
        resolved_path, test_size=0.2, random_state=random_state
    )

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    oof_scores = np.zeros(len(X_train_raw), dtype=float)
    for tr_idx, cal_idx in skf.split(X_train_raw, y_train_raw):
        oof_scores[cal_idx] = _fit_fold_and_score_calibration(
            X_proper=X_train_raw.iloc[tr_idx],
            y_proper=y_train_raw.iloc[tr_idx],
            X_cal=X_train_raw.iloc[cal_idx],
            y_cal=y_train_raw.iloc[cal_idx],
            num_cols=num_cols,
            cat_cols=cat_cols,
            base_estimator=estimator,
            selected_features=feats,
            random_state=random_state,
        )

    y_arr = np.asarray(y_train_raw, dtype=int)
    s0 = oof_scores[y_arr == 0]
    s1 = oof_scores[y_arr == 1]

    def _finite_q(scores: np.ndarray) -> float:
        n = len(scores)
        if n == 0:
            return DEFAULT_FALLBACK_QUANTILE
        lvl = min(math.ceil((n + 1) * (1.0 - alpha)) / n, 1.0)
        return round(max(0.0, min(1.0, float(np.quantile(scores, lvl, method="higher")))), 4)

    q0 = _finite_q(s0)
    q1 = _finite_q(s1)

    return MondrianCalibrationResult(
        q_healthy=q0,
        q_ckd=q1,
        alpha=alpha,
        coverage_target=round(1.0 - alpha, 4),
        n_healthy=int(len(s0)),
        n_ckd=int(len(s1)),
        empirical_coverage_healthy=round(float(np.mean(s0 <= q0)), 4) if len(s0) else 0.0,
        empirical_coverage_ckd=round(float(np.mean(s1 <= q1)), 4) if len(s1) else 0.0,
        calibration_method=f"mondrian_oof_stratified_{n_splits}fold",
        held_out_test_excluded=True,
        fallback_used=False,
    )


@functools.lru_cache(maxsize=8)
def get_calibrated_mondrian_result(alpha: float = 0.05) -> MondrianCalibrationResult:
    """Cached accessor for Mondrian class-conditional conformal quantiles."""
    return calibrate_mondrian_conformal(alpha=alpha)


def evaluate_mondrian_prediction_set(
    risk_probability: Optional[float],
    mondrian_cal: MondrianCalibrationResult,
) -> list[int]:
    """Construct class-conditional Mondrian prediction set C_alpha(x)."""
    if risk_probability is None:
        return [0, 1]
    p1 = float(risk_probability)
    p0 = 1.0 - p1
    c_set: list[int] = []
    if (1.0 - p0) <= mondrian_cal.q_healthy:
        c_set.append(0)
    if (1.0 - p1) <= mondrian_cal.q_ckd:
        c_set.append(1)
    return c_set if c_set else [0, 1]
