"""Training-Anchored Batch Covariate-Shift & Mahalanobis OOD Monitor.

Fits statistical reference baselines strictly on the 320-patient UCI CKD
training partition (never touching the 80 held-out test records), then
evaluates incoming batch screening CSVs for:
1. Population Stability Index (PSI) per numeric consensus biomarker
2. Two-sample Kolmogorov-Smirnov (KS) shift statistics
3. Per-patient Mahalanobis OOD distance against the 99th training percentile
"""

from __future__ import annotations

import functools
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.preprocessing import ClinicalDataPreprocessor

DEFAULT_DATASET_PATH = os.path.join("datasets", "clinical", "dataset_A_uci_ckd.csv")
NUMERIC_MONITORED_FEATURES = ["hemo", "sg", "pcv", "rc", "al", "sc", "bu", "bgr"]


@dataclass
class BatchDriftReport:
    """Population-level covariate drift and row-level Mahalanobis OOD summary."""

    overall_drift_status: str  # "IN_DISTRIBUTION" | "MODERATE_COVARIATE_SHIFT" | "SEVERE_COVARIATE_SHIFT"
    max_psi: float
    mean_psi: float
    drifted_features: List[str]
    feature_drift_details: List[Dict[str, Any]]
    mahalanobis_threshold_p99: float
    ood_row_count: int
    ood_row_fraction: float
    per_row_mahalanobis: List[float] = field(default_factory=list)
    per_row_ood_flag: List[bool] = field(default_factory=list)
    reference_train_samples: int = 320
    held_out_test_excluded: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _resolve_dataset_path(dataset_path: str) -> str:
    if os.path.exists(dataset_path):
        return dataset_path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(root, dataset_path)


@functools.lru_cache(maxsize=2)
def get_training_drift_reference(dataset_path: str = DEFAULT_DATASET_PATH) -> Dict[str, Any]:
    """Compute reference feature distributions strictly from UCI CKD X_train (N=320)."""
    resolved = _resolve_dataset_path(dataset_path)
    raw_df = pd.read_csv(resolved)
    helper = ClinicalDataPreprocessor(target_col="classification", random_state=42)
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
    X = clean_df.drop(columns=["classification"])

    X_train_raw, _, _, _ = train_test_split(
        X[NUMERIC_MONITORED_FEATURES],
        y.astype(int),
        test_size=0.2,
        stratify=y.astype(int),
        random_state=42,
    )

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_imp = imputer.fit_transform(X_train_raw)
    X_std = scaler.fit_transform(X_imp)

    cov = np.cov(X_std, rowvar=False) + 1e-3 * np.eye(X_std.shape[1])
    inv_cov = np.linalg.pinv(cov)
    mean_vec = np.mean(X_std, axis=0)

    train_dists = np.array([
        float(np.sqrt(max(0.0, (row - mean_vec) @ inv_cov @ (row - mean_vec))))
        for row in X_std
    ])
    p99_thresh = float(np.quantile(train_dists, 0.99))

    feature_refs: Dict[str, Dict[str, Any]] = {}
    for idx, feat in enumerate(NUMERIC_MONITORED_FEATURES):
        col_vals = X_train_raw[feat].dropna().values.astype(float)
        edges = np.unique(np.quantile(col_vals, np.linspace(0.0, 1.0, 6)))
        if len(edges) < 3:
            edges = np.array([float(np.min(col_vals)), float(np.median(col_vals)), float(np.max(col_vals)) + 1e-6])
        edges[0] = -np.inf
        edges[-1] = np.inf
        counts, _ = np.histogram(col_vals, bins=edges)
        props = np.maximum(counts / max(1, len(col_vals)), 1e-4)
        props = props / props.sum()
        feature_refs[feat] = {
            "values": col_vals,
            "edges": edges,
            "train_props": props,
            "train_mean": round(float(np.mean(col_vals)), 3),
            "train_std": round(float(np.std(col_vals)), 3),
        }

    return {
        "n_train": int(len(X_train_raw)),
        "imputer": imputer,
        "scaler": scaler,
        "mean_vec": mean_vec,
        "inv_cov": inv_cov,
        "mahalanobis_p99": p99_thresh,
        "feature_refs": feature_refs,
    }


def evaluate_batch_covariate_drift(
    df_batch: pd.DataFrame,
    dataset_path: str = DEFAULT_DATASET_PATH,
) -> BatchDriftReport:
    """Evaluate PSI, KS drift, and per-row Mahalanobis OOD distance on a batch CSV."""
    ref = get_training_drift_reference(dataset_path)
    df_work = pd.DataFrame(index=df_batch.index)
    for feat in NUMERIC_MONITORED_FEATURES:
        if feat in df_batch.columns:
            # Strip unit strings if present (extract leading number)
            extracted = df_batch[feat].astype(str).str.extract(r"([+-]?\d+(?:\.\d+)?)", expand=False)
            df_work[feat] = pd.to_numeric(extracted, errors="coerce")
        else:
            df_work[feat] = np.nan

    # Per-row Mahalanobis distance in training-standardized space
    X_imp = ref["imputer"].transform(df_work[NUMERIC_MONITORED_FEATURES])
    X_std = ref["scaler"].transform(X_imp)
    mean_vec = ref["mean_vec"]
    inv_cov = ref["inv_cov"]
    p99 = ref["mahalanobis_p99"]

    row_dists: List[float] = []
    row_flags: List[bool] = []
    for row in X_std:
        diff = row - mean_vec
        dist = float(np.sqrt(max(0.0, diff @ inv_cov @ diff)))
        row_dists.append(round(dist, 3))
        row_flags.append(bool(dist > p99))

    # Per-feature PSI & KS shift
    feature_details: List[Dict[str, Any]] = []
    drifted_feats: List[str] = []
    psi_vals: List[float] = []

    for feat in NUMERIC_MONITORED_FEATURES:
        f_ref = ref["feature_refs"][feat]
        batch_vals = df_work[feat].dropna().values.astype(float)
        if len(batch_vals) == 0:
            feature_details.append({
                "feature": feat,
                "psi": None,
                "ks_stat": None,
                "ks_pvalue": None,
                "batch_mean": None,
                "train_mean": f_ref["train_mean"],
                "status": "NO_OBSERVED_VALUES",
            })
            continue

        counts, _ = np.histogram(batch_vals, bins=f_ref["edges"])
        batch_props = np.maximum(counts / max(1, len(batch_vals)), 1e-4)
        batch_props = batch_props / batch_props.sum()
        train_props = f_ref["train_props"]

        psi = float(np.sum((batch_props - train_props) * np.log(batch_props / train_props)))
        ks_res = ks_2samp(f_ref["values"], batch_vals)

        if psi >= 0.25:
            f_status = "SEVERE_SHIFT"
            drifted_feats.append(feat)
        elif psi >= 0.10:
            f_status = "MODERATE_SHIFT"
            drifted_feats.append(feat)
        else:
            f_status = "STABLE"

        psi_vals.append(psi)
        feature_details.append({
            "feature": feat,
            "psi": round(psi, 4),
            "ks_stat": round(float(ks_res.statistic), 4),
            "ks_pvalue": round(float(ks_res.pvalue), 4),
            "batch_mean": round(float(np.mean(batch_vals)), 3),
            "train_mean": f_ref["train_mean"],
            "status": f_status,
        })

    max_psi = round(float(max(psi_vals)), 4) if psi_vals else 0.0
    mean_psi = round(float(np.mean(psi_vals)), 4) if psi_vals else 0.0
    ood_count = sum(1 for fl in row_flags if fl)
    ood_frac = round(ood_count / max(1, len(row_flags)), 4)

    if max_psi >= 0.25 or ood_frac > 0.30:
        overall = "SEVERE_COVARIATE_SHIFT"
    elif max_psi >= 0.10 or ood_frac > 0.15:
        overall = "MODERATE_COVARIATE_SHIFT"
    else:
        overall = "IN_DISTRIBUTION"

    return BatchDriftReport(
        overall_drift_status=overall,
        max_psi=max_psi,
        mean_psi=mean_psi,
        drifted_features=drifted_feats,
        feature_drift_details=feature_details,
        mahalanobis_threshold_p99=round(p99, 3),
        ood_row_count=ood_count,
        ood_row_fraction=ood_frac,
        per_row_mahalanobis=row_dists,
        per_row_ood_flag=row_flags,
        reference_train_samples=ref["n_train"],
        held_out_test_excluded=True,
    )

