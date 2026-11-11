"""Batch Clinical Screening Service with Strict Schema Validation & CD-CIRPVM.

Coordinates cohort CSV ingestion, strict schema rejection of non-renal
datasets, pipeline batch inference, per-row CD-CIRPVM conformal gating,
and CWE-1236 formula-safe CSV export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from src.clinical.conformal_calibrator import (
    build_calibrated_reliability_mechanism,
    evaluate_consensus_cirpvm,
)
from src.clinical.drift_monitor import BatchDriftReport, evaluate_batch_covariate_drift
from src.clinical_input_reliability_mechanism import ClinicalInputReliabilityMechanism
from src.pipeline import TOP_10_CONSENSUS_FEATURES
from src.ui.components.report_export import sanitize_csv_cell

MAX_BATCH_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_BATCH_ROWS = 500

SAMPLE_BATCH_ROWS: List[Dict[str, Any]] = [
    {
        "patient_id": "PT-DEMO-HEALTHY",
        "hemo": 15.2,
        "sg": 1.025,
        "pcv": 45.0,
        "rc": 5.2,
        "al": 0,
        "htn": "no",
        "sc": 0.85,
        "bu": 22.0,
        "dm": "no",
        "bgr": 95.0,
    },
    {
        "patient_id": "PT-DEMO-HIGH-RISK",
        "hemo": 9.8,
        "sg": 1.012,
        "pcv": 30.0,
        "rc": 3.3,
        "al": 3,
        "htn": "yes",
        "sc": 2.4,
        "bu": 72.0,
        "dm": "yes",
        "bgr": 185.0,
    },
    {
        "patient_id": "PT-DEMO-UNIT-SPEC",
        "hemo": "148 g/L",
        "sg": 1.020,
        "pcv": 43.0,
        "rc": 4.9,
        "al": 0,
        "htn": "no",
        "sc": "88.42 umol/L",
        "bu": 26.0,
        "dm": "no",
        "bgr": "5.3 mmol/L",
    },
    {
        "patient_id": "PT-DEMO-MISSING-CRIT",
        "hemo": 13.5,
        "sg": 1.020,
        "pcv": 40.0,
        "rc": 4.6,
        "al": None,
        "htn": "no",
        "sc": None,
        "bu": 28.0,
        "dm": "no",
        "bgr": 102.0,
    },
]


@dataclass
class BatchScreeningSummary:
    """Structured output of a batch CKD screening CSV run."""

    schema_valid: bool
    schema_message: str
    results_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    total_rows: int = 0
    predictions_available: int = 0
    incomplete_estimates: int = 0
    abstained_rows: int = 0
    conformal_abstentions: int = 0
    high_or_critical_risk: int = 0
    mean_cri: float = 0.0
    conformal_quantile: float = 0.20
    drift_report: Optional[BatchDriftReport] = None

    def to_sanitized_csv(self) -> str:
        """Export batch results as CSV neutralized against formula injection (CWE-1236)."""
        if self.results_df.empty:
            return ""
        safe_df = self.results_df.copy()
        for col in safe_df.columns:
            safe_df[col] = safe_df[col].apply(
                lambda v: sanitize_csv_cell(str(v) if isinstance(v, (list, dict)) else v)
            )
        return safe_df.to_csv(index=False)


def get_sample_batch_csv() -> str:
    """Generate a non-PII synthetic sample cohort CSV template."""
    return pd.DataFrame(SAMPLE_BATCH_ROWS).to_csv(index=False)


def run_batch_clinical_screening(
    df: pd.DataFrame,
    pipeline: Any,
    reliability_mechanism: Optional[ClinicalInputReliabilityMechanism] = None,
    max_rows: int = MAX_BATCH_ROWS,
) -> BatchScreeningSummary:
    """Validate schema, run batch Engine 1 inference, and attach CD-CIRPVM gating."""
    if df is None or len(df) == 0:
        return BatchScreeningSummary(
            schema_valid=False,
            schema_message="Uploaded CSV contains zero patient rows.",
        )

    if len(df) > max_rows:
        return BatchScreeningSummary(
            schema_valid=False,
            schema_message=(
                f"Uploaded CSV contains {len(df)} rows, exceeding the maximum batch limit of {max_rows} rows."
            ),
        )

    df_clean = df.copy()
    df_clean.columns = [str(c).strip() for c in df_clean.columns]

    is_valid, reason = pipeline.validate_schema(df_clean)
    if not is_valid:
        return BatchScreeningSummary(
            schema_valid=False,
            schema_message=reason,
            total_rows=len(df_clean),
        )

    batch_preds = pipeline.predict_batch(df_clean, raise_on_invalid_schema=False)

    if reliability_mechanism is None:
        mech, cal = build_calibrated_reliability_mechanism()
        cal_method = cal.calibration_method
    else:
        mech = reliability_mechanism
        cal_method = "configured_quantile"

    selected_feats = list(getattr(pipeline, "selected_features", TOP_10_CONSENSUS_FEATURES))
    raw_records = df_clean.to_dict(orient="records")

    cri_list: List[float] = []
    conf_set_list: List[str] = []
    gate_dec_list: List[str] = []
    gate_stat_list: List[str] = []
    unit_audit_list: List[str] = []

    for idx, raw_rec in enumerate(raw_records):
        pred_row = batch_preds.iloc[idx]
        risk_prob = pred_row.get("risk_probability")
        if pd.isna(risk_prob):
            risk_prob = None
        else:
            risk_prob = float(risk_prob)

        sanitized_pipe = {}
        anomalies = {}
        if hasattr(pipeline, "_sanitize_and_inspect_record"):
            clean_rec, meta = pipeline._sanitize_and_inspect_record(raw_rec)
            sanitized_pipe = {k: v for k, v in clean_rec.items() if pd.notna(v)}
            anomalies = meta.get("feature_anomalies", {})

        rel = evaluate_consensus_cirpvm(
            raw_biomarkers=raw_rec,
            reliability_mechanism=mech,
            selected_features=selected_feats,
            risk_probability=risk_prob,
            prediction_status=str(pred_row.get("prediction_status", "")),
            sanitized_from_pipe=sanitized_pipe,
            feature_anomalies=anomalies,
            calibration_method=cal_method,
        )
        cri_list.append(rel["clinical_reliability_index"])
        conf_set_list.append(str(rel["conformal_set"]))
        gate_dec_list.append(str(rel["conformal_gate_decision"]))
        gate_stat_list.append(str(rel["conformal_gate_status"]))
        unit_keys = list(rel["unit_reconciliation_audit"].keys())
        if not unit_keys:
            # Also detect explicit unit strings parsed by the pipeline (e.g., "88.42 umol/L")
            explicit_units = [
                k for k, v in raw_rec.items()
                if isinstance(v, str) and k in sanitized_pipe and any(u in v.lower() for u in ("umol", "µmol", "g/l", "mmol"))
            ]
            unit_keys = explicit_units
        unit_audit_list.append(", ".join(unit_keys) if unit_keys else "Native")

    enriched_df = batch_preds.copy()
    enriched_df["clinical_reliability_index"] = cri_list
    enriched_df["conformal_set"] = conf_set_list
    enriched_df["conformal_gate_decision"] = gate_dec_list
    enriched_df["conformal_gate_status"] = gate_stat_list
    enriched_df["unit_conversions_detected"] = unit_audit_list

    drift_report = evaluate_batch_covariate_drift(df_clean)
    enriched_df["mahalanobis_distance"] = drift_report.per_row_mahalanobis
    enriched_df["mahalanobis_ood_flag"] = drift_report.per_row_ood_flag

    statuses = enriched_df["prediction_status"].astype(str)
    pred_avail = int((statuses == "PREDICTION_AVAILABLE").sum())
    inc_est = int((statuses == "INCOMPLETE_INPUT_ESTIMATE").sum())
    abstained = int((statuses.str.startswith("ABSTAIN") | statuses.str.startswith("REJECTED")).sum())
    conf_abstain = int(sum(1 for d in gate_dec_list if d == "ABSTAIN"))
    high_crit = int(
        enriched_df["risk_category"]
        .astype(str)
        .str.contains("High Risk|Critical Risk", case=False, regex=True)
        .sum()
    )
    mean_cri = round(float(sum(cri_list) / len(cri_list)), 3) if cri_list else 0.0

    return BatchScreeningSummary(
        schema_valid=True,
        schema_message=reason,
        results_df=enriched_df,
        total_rows=len(enriched_df),
        predictions_available=pred_avail,
        incomplete_estimates=inc_est,
        abstained_rows=abstained,
        conformal_abstentions=conf_abstain,
        high_or_critical_risk=high_crit,
        mean_cri=mean_cri,
        conformal_quantile=float(mech.conformal_quantile),
        drift_report=drift_report,
    )
