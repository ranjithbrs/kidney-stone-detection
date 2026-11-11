"""Live Cooperative Game-Theoretic TreeSHAP Explainability Helper.

Computes exact Shapley attributions via `shap.TreeExplainer` for individual
patient records processed by the Engine 1 Random Forest pipeline, preserving
mathematical local accuracy:

    E[f(X)] + sum_i phi_i == f(x)

Strictly distinguishes game-theoretic Shapley attributions from global
Gini/MDI feature importance heuristics.
"""

from __future__ import annotations

import functools
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import shap
from lime.lime_tabular import LimeTabularExplainer
from scipy.stats import spearmanr

from src.clinical.conformal_calibrator import build_calibrated_reliability_mechanism

logger = logging.getLogger("nefroai.clinical.xai_live")

_EXPLAINER_CACHE: Dict[int, shap.TreeExplainer] = {}

BIOMARKER_DISPLAY_LABELS: Dict[str, str] = {
    "hemo": "Hemoglobin (g/dL)",
    "sg": "Specific Gravity",
    "pcv": "Packed Cell Vol (%)",
    "rc": "RBC Count (M/mcL)",
    "al": "Urine Albumin (0-5)",
    "htn": "Hypertension",
    "sc": "Serum Creatinine (mg/dL)",
    "bu": "Blood Urea (mg/dL)",
    "dm": "Diabetes Mellitus",
    "bgr": "Blood Glucose (mg/dL)",
}


@dataclass
class LiveTreeSHAPResult:
    """Exact per-patient cooperative Shapley attribution output."""

    base_value: float
    predicted_probability: float
    additivity_error: float
    feature_names: List[str]
    shap_values: Dict[str, float]
    transformed_values: Dict[str, float]
    raw_display_values: Dict[str, Any]
    top_drivers: List[Dict[str, Any]]
    explanation_object: Any

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable attribution dictionary (omitting raw SHAP object)."""
        return {
            "base_value": round(self.base_value, 6),
            "predicted_probability": round(self.predicted_probability, 6),
            "additivity_error": float(self.additivity_error),
            "feature_names": list(self.feature_names),
            "shap_values": {k: round(float(v), 6) for k, v in self.shap_values.items()},
            "transformed_values": {k: round(float(v), 4) for k, v in self.transformed_values.items()},
            "raw_display_values": dict(self.raw_display_values),
            "top_drivers": list(self.top_drivers),
        }


def get_cached_tree_explainer(model: Any) -> shap.TreeExplainer:
    """Retrieve or build a cached `shap.TreeExplainer` keyed by model instance id."""
    key = id(model)
    explainer = _EXPLAINER_CACHE.get(key)
    if explainer is None:
        explainer = shap.TreeExplainer(model)
        _EXPLAINER_CACHE[key] = explainer
    return explainer


def compute_live_treeshap(
    pipeline: Any,
    patient_record: Dict[str, Any],
) -> Optional[LiveTreeSHAPResult]:
    """Compute exact `shap.TreeExplainer` attributions for a single patient record.

    Returns ``None`` cleanly if the provided pipeline is a non-tree mock or
    lacks required preprocessing/model attributes.
    """
    if pipeline is None or not hasattr(pipeline, "model") or not hasattr(pipeline, "preprocessor"):
        return None
    if not hasattr(pipeline, "selected_features"):
        return None

    model = pipeline.model
    if not hasattr(model, "estimators_") or not hasattr(model, "predict_proba"):
        return None

    selected_features = list(pipeline.selected_features)

    # Sanitize raw inputs using pipeline rules if available
    if hasattr(pipeline, "_sanitize_and_inspect_record"):
        clean_record, _ = pipeline._sanitize_and_inspect_record(patient_record)
    else:
        clean_record = dict(patient_record)

    transformed_df = pipeline.preprocessor.transform_single_record(clean_record)
    X_selected = transformed_df[selected_features]

    explainer = get_cached_tree_explainer(model)
    raw_sv = explainer(X_selected)

    # Select positive CKD class (index 1) for binary Random Forest
    if len(raw_sv.shape) == 3:
        patient_sv = raw_sv[0, :, 1]
    else:
        patient_sv = raw_sv[0]

    phi = np.asarray(patient_sv.values, dtype=float)
    base_val = float(np.asarray(patient_sv.base_values).item())
    pred_prob = float(model.predict_proba(X_selected)[0, 1])
    additivity_err = abs((base_val + float(np.sum(phi))) - pred_prob)

    shap_dict: Dict[str, float] = {}
    z_dict: Dict[str, float] = {}
    display_dict: Dict[str, Any] = {}
    display_data = []
    display_names = []

    for idx, feat in enumerate(selected_features):
        s_val = float(phi[idx])
        z_val = float(X_selected[feat].iloc[0])
        raw_val = clean_record.get(feat, patient_record.get(feat))

        shap_dict[feat] = s_val
        z_dict[feat] = z_val

        if raw_val is None or (isinstance(raw_val, float) and np.isnan(raw_val)):
            disp_val = f"imputed (z={z_val:+.2f})"
            display_data.append(round(z_val, 2))
        else:
            disp_val = raw_val
            display_data.append(raw_val)

        display_dict[feat] = disp_val
        display_names.append(BIOMARKER_DISPLAY_LABELS.get(feat, feat))

    # Build shap.Explanation carrying human-readable values for waterfall rendering
    waterfall_exp = shap.Explanation(
        values=phi,
        base_values=base_val,
        data=np.array(display_data, dtype=object),
        feature_names=display_names,
    )

    drivers = sorted(
        [
            {
                "feature": feat,
                "label": BIOMARKER_DISPLAY_LABELS.get(feat, feat),
                "clinical_value": display_dict[feat],
                "normalized_z": round(z_dict[feat], 3),
                "shap_value": round(shap_dict[feat], 4),
                "abs_shap": round(abs(shap_dict[feat]), 4),
                "direction": "Increases CKD Risk (+)" if shap_dict[feat] >= 0 else "Protective / Reduces Risk (-)",
            }
            for feat in selected_features
        ],
        key=lambda d: d["abs_shap"],
        reverse=True,
    )

    return LiveTreeSHAPResult(
        base_value=base_val,
        predicted_probability=pred_prob,
        additivity_error=additivity_err,
        feature_names=selected_features,
        shap_values=shap_dict,
        transformed_values=z_dict,
        raw_display_values=display_dict,
        top_drivers=drivers,
        explanation_object=waterfall_exp,
    )


@dataclass
class LiveLIMEResult:
    """Live per-patient LIME surrogate explanation."""

    predicted_probability: float
    feature_weights: Dict[str, float]
    rules: List[Dict[str, Any]]
    intercept: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class XAIConcordanceResult:
    """Cross-layer concordance between TreeSHAP, LIME, and KDIGO clinical markers."""

    spearman_rank_corr: Optional[float]
    top3_overlap_count: int
    top3_shap_features: List[str]
    top3_lime_features: List[str]
    sign_agreement_ratio: float
    kdigo_marker_alignment: str
    concordance_status: str  # "HIGH_CONCORDANCE" | "MODERATE_CONCORDANCE" | "DIVERGENT_EXPLANATIONS"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CounterfactualResult:
    """Physiologically-constrained minimal recourse suggestions."""

    initial_probability: float
    initial_conformal_set: List[int]
    target_achieved: bool
    target_probability: Optional[float]
    target_conformal_set: Optional[List[int]]
    suggested_shifts: List[Dict[str, Any]] = field(default_factory=list)
    locked_immutable_features: List[str] = field(default_factory=lambda: ["age", "sex", "htn", "dm"])
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@functools.lru_cache(maxsize=4)
def _get_cached_lime_explainer(features_tuple: tuple[str, ...]) -> Optional[LimeTabularExplainer]:
    """Initialize LimeTabularExplainer strictly on training-partition Dataset_A_X_train.csv."""
    candidates = [
        os.path.join("datasets", "processed", "Dataset_A_X_train.csv"),
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "processed", "Dataset_A_X_train.csv")
        ),
    ]
    train_path = next((p for p in candidates if os.path.exists(p)), None)
    if train_path is None:
        return None
    X_train_df = pd.read_csv(train_path)[list(features_tuple)]
    return LimeTabularExplainer(
        training_data=X_train_df.values,
        feature_names=list(features_tuple),
        class_names=["Healthy (0)", "Chronic Kidney Disease (1)"],
        mode="classification",
        discretize_continuous=True,
        random_state=42,
    )


def compute_live_lime(
    pipeline: Any,
    patient_record: Dict[str, Any],
) -> Optional[LiveLIMEResult]:
    """Compute live deterministic LIME surrogate explanation for a single patient."""
    if pipeline is None or not hasattr(pipeline, "model") or not hasattr(pipeline, "preprocessor"):
        return None
    if not hasattr(pipeline, "selected_features"):
        return None

    selected_features = list(pipeline.selected_features)
    explainer = _get_cached_lime_explainer(tuple(selected_features))
    if explainer is None:
        return None

    if hasattr(pipeline, "_sanitize_and_inspect_record"):
        clean_record, _ = pipeline._sanitize_and_inspect_record(patient_record)
    else:
        clean_record = dict(patient_record)

    transformed_df = pipeline.preprocessor.transform_single_record(clean_record)
    X_selected = transformed_df[selected_features]
    row_arr = X_selected.iloc[0].values

    def _predict_fn(arr: np.ndarray) -> np.ndarray:
        return pipeline.model.predict_proba(pd.DataFrame(arr, columns=selected_features))

    exp = explainer.explain_instance(
        data_row=row_arr,
        predict_fn=_predict_fn,
        num_features=len(selected_features),
        num_samples=600,
    )

    local_map = exp.local_exp.get(1) or exp.local_exp.get(list(exp.local_exp.keys())[0], [])
    feat_weights: Dict[str, float] = {f: 0.0 for f in selected_features}
    for feat_idx, w in local_map:
        if 0 <= feat_idx < len(selected_features):
            feat_weights[selected_features[feat_idx]] = round(float(w), 4)

    rules = [
        {"rule": rule, "weight": round(float(weight), 4)}
        for rule, weight in exp.as_list(label=1)
    ]
    pred_prob = float(pipeline.model.predict_proba(X_selected)[0, 1])
    intercept_val = float(exp.intercept.get(1, 0.0)) if isinstance(exp.intercept, dict) else 0.0

    return LiveLIMEResult(
        predicted_probability=round(pred_prob, 4),
        feature_weights=feat_weights,
        rules=rules,
        intercept=round(intercept_val, 4),
    )


def compute_xai_concordance(
    shap_result: Optional[LiveTreeSHAPResult],
    lime_result: Optional[LiveLIMEResult],
    uacr_mg_g: Optional[float] = None,
) -> Optional[XAIConcordanceResult]:
    """Audit agreement between live TreeSHAP, live LIME, and KDIGO clinical markers."""
    if shap_result is None or lime_result is None:
        return None

    feats = list(shap_result.feature_names)
    shap_abs = [abs(shap_result.shap_values.get(f, 0.0)) for f in feats]
    lime_abs = [abs(lime_result.feature_weights.get(f, 0.0)) for f in feats]

    rho, _ = spearmanr(shap_abs, lime_abs)
    rho_clean = None if np.isnan(rho) else round(float(rho), 3)

    top3_shap = [f for f, _ in sorted(shap_result.shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:3]]
    top3_lime = [f for f, _ in sorted(lime_result.feature_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:3]]
    overlap = len(set(top3_shap) & set(top3_lime))

    sign_matches = 0
    non_zero_count = 0
    for f in feats:
        sv = shap_result.shap_values.get(f, 0.0)
        lv = lime_result.feature_weights.get(f, 0.0)
        if abs(sv) > 1e-4 and abs(lv) > 1e-4:
            non_zero_count += 1
            if (sv > 0) == (lv > 0):
                sign_matches += 1
    sign_ratio = round(sign_matches / non_zero_count, 3) if non_zero_count else 1.0

    renal_core = {"sc", "al", "hemo", "pcv", "sg"}
    kdigo_align = (
        "Aligned with KDIGO renal markers"
        if (set(top3_shap) & renal_core) and (set(top3_lime) & renal_core)
        else "Driven primarily by systemic/metabolic markers"
    )
    if uacr_mg_g is not None and uacr_mg_g >= 30.0 and "al" not in set(top3_shap):
        kdigo_align += " (elevated uACR detected via Engine 2)"

    if (rho_clean is not None and rho_clean >= 0.60) and overlap >= 2 and sign_ratio >= 0.70:
        status = "HIGH_CONCORDANCE"
    elif (rho_clean is not None and rho_clean >= 0.30) or overlap >= 1:
        status = "MODERATE_CONCORDANCE"
    else:
        status = "DIVERGENT_EXPLANATIONS"

    return XAIConcordanceResult(
        spearman_rank_corr=rho_clean,
        top3_overlap_count=overlap,
        top3_shap_features=top3_shap,
        top3_lime_features=top3_lime,
        sign_agreement_ratio=sign_ratio,
        kdigo_marker_alignment=kdigo_align,
        concordance_status=status,
    )


def generate_clinical_counterfactuals(
    pipeline: Any,
    patient_record: Dict[str, Any],
    target_max_risk: float = 0.20,
    max_changes: int = 2,
) -> Optional[CounterfactualResult]:
    """Find minimal physiologically feasible biomarker shifts toward Low-Risk {0}.

    Locks immutable variables (`age`, `sex`, `htn`, `dm`) and evaluates bounded
    candidate reference targets over mutable analytes (`hemo`, `sc`, `al`, `pcv`,
    `rc`, `sg`, `bu`, `bgr`) through both the classifier and conformal gate.
    """
    if pipeline is None or not hasattr(pipeline, "predict_single"):
        return None

    init_pred = pipeline.predict_single(patient_record, include_attributions=False)
    init_prob = init_pred.get("risk_probability")
    if init_prob is None:
        return None

    mech, _ = build_calibrated_reliability_mechanism()
    init_gate = mech.evaluate_conformal_gate([1.0 - init_prob, init_prob], 1.0)
    init_set = list(init_gate.get("conformal_set", [0, 1]))

    if init_prob <= target_max_risk and init_set == [0]:
        return CounterfactualResult(
            initial_probability=round(float(init_prob), 4),
            initial_conformal_set=init_set,
            target_achieved=True,
            target_probability=round(float(init_prob), 4),
            target_conformal_set=init_set,
            suggested_shifts=[],
            notes="Patient presentation already satisfies decisive Low-Risk conformal set {0}.",
        )

    sanitized = dict(init_pred.get("sanitized_inputs", {}))
    base_rec = dict(patient_record)
    base_rec.update(sanitized)

    # Immutable clinical history / demographics remain strictly locked
    candidate_targets: Dict[str, List[float]] = {
        "hemo": [13.5, 14.5],
        "sc": [1.0, 0.85],
        "al": [0.0],
        "pcv": [41.0, 44.0],
        "sg": [1.020, 1.025],
        "bu": [30.0],
        "bgr": [105.0],
        "rc": [4.8],
    }

    best_single: Optional[Tuple[float, List[int], List[Dict[str, Any]]]] = None
    best_pair: Optional[Tuple[float, List[int], List[Dict[str, Any]]]] = None

    def _eval_candidate(mod_map: Dict[str, float]) -> Tuple[float, List[int]]:
        cand = dict(base_rec)
        cand.update(mod_map)
        out = pipeline.predict_single(cand, include_attributions=False)
        p = out.get("risk_probability")
        if p is None:
            return (1.0, [0, 1])
        g = mech.evaluate_conformal_gate([1.0 - p, p], 1.0)
        return (float(p), list(g.get("conformal_set", [0, 1])))

    def _shift_entry(feat: str, new_v: float) -> Dict[str, Any]:
        old_v = base_rec.get(feat)
        return {
            "feature": feat,
            "label": BIOMARKER_DISPLAY_LABELS.get(feat, feat),
            "current_value": old_v,
            "target_value": new_v,
        }

    # 1. Single-analyte feasible moves
    for feat, vals in candidate_targets.items():
        cur = base_rec.get(feat)
        for tgt in vals:
            if cur is not None and abs(float(cur) - tgt) < 1e-6:
                continue
            p, cset = _eval_candidate({feat: tgt})
            if best_single is None or p < best_single[0]:
                best_single = (p, cset, [_shift_entry(feat, tgt)])
            if p <= target_max_risk and cset == [0]:
                return CounterfactualResult(
                    initial_probability=round(float(init_prob), 4),
                    initial_conformal_set=init_set,
                    target_achieved=True,
                    target_probability=round(p, 4),
                    target_conformal_set=cset,
                    suggested_shifts=[_shift_entry(feat, tgt)],
                    notes="Single mutable biomarker target resolves risk to decisive {0}.",
                )

    # 2. Pairwise feasible moves (up to max_changes=2)
    if max_changes >= 2:
        keys = list(candidate_targets.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                f1, f2 = keys[i], keys[j]
                t1 = candidate_targets[f1][0]
                t2 = candidate_targets[f2][0]
                p, cset = _eval_candidate({f1: t1, f2: t2})
                if best_pair is None or p < best_pair[0]:
                    best_pair = (p, cset, [_shift_entry(f1, t1), _shift_entry(f2, t2)])
                if p <= target_max_risk and cset == [0]:
                    return CounterfactualResult(
                        initial_probability=round(float(init_prob), 4),
                        initial_conformal_set=init_set,
                        target_achieved=True,
                        target_probability=round(p, 4),
                        target_conformal_set=cset,
                        suggested_shifts=[_shift_entry(f1, t1), _shift_entry(f2, t2)],
                        notes="2-biomarker feasible adjustment resolves risk to decisive {0}.",
                    )

    fallback = best_pair if (best_pair and (not best_single or best_pair[0] < best_single[0])) else best_single
    if fallback is None:
        return CounterfactualResult(
            initial_probability=round(float(init_prob), 4),
            initial_conformal_set=init_set,
            target_achieved=False,
            target_probability=None,
            target_conformal_set=None,
            notes="No 1- or 2-biomarker perturbation reduced risk below target threshold while keeping immutable history locked.",
        )

    return CounterfactualResult(
        initial_probability=round(float(init_prob), 4),
        initial_conformal_set=init_set,
        target_achieved=False,
        target_probability=round(fallback[0], 4),
        target_conformal_set=fallback[1],
        suggested_shifts=fallback[2],
        notes=(
            f"Best sensitivity reduction achieved ({init_prob:.1%} -> {fallback[0]:.1%}); "
            "immutable clinical comorbidities (`htn`/`dm`) or remaining markers sustain residual risk."
        ),
    )

