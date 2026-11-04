"""NEFROAI-X Time-Aware Clinical Feature Engineering Module for Engine 3.

Provides data structures, time-aware feature extraction, landmarking safeguards,
and selective abstention gates for longitudinal kidney disease progression monitoring.

Clinical Standards:
- KDIGO 2012 / 2024 Clinical Practice Guidelines for CKD Evaluation and Management.
- CKD-EPI 2021 Race-Free Creatinine Equation (Inker et al., NEJM 2021).
- Landmark Survival Analysis Methodology (van Houwelingen & Putter, 2012).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from src.clinical.egfr_calculator import calculate_egfr_ckd_epi_2021

logger = logging.getLogger("nefroai.progression_features")


# ---------------------------------------------------------------------------
# Data Contracts & Schemas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClinicalObservation:
    """Represents a single clinical laboratory visit at a specific timestamp.

    Attributes
    ----------
    timestamp : datetime
        Date and time of the observation. Timezone-aware or UTC-normalized.
    serum_creatinine : Optional[float]
        Serum creatinine in mg/dL (conventional unit).
    egfr : Optional[float]
        Precomputed or lab-reported eGFR in mL/min/1.73 m2. If None, will be
        calculated on-the-fly using CKD-EPI 2021 race-free equation if
        serum_creatinine and patient demographics are available.
    uacr : Optional[float]
        Urine Albumin-to-Creatinine Ratio (UACR) in mg/g.
    systolic_bp : Optional[float]
        Systolic Blood Pressure in mmHg.
    diastolic_bp : Optional[float]
        Diastolic Blood Pressure in mmHg.
    hba1c : Optional[float]
        Hemoglobin A1c in percentage (%).
    serum_glucose : Optional[float]
        Serum glucose in mg/dL.
    notes : Optional[str]
        Clinical context, visit comments, or laboratory QA flags.
    """

    timestamp: datetime
    serum_creatinine: Optional[float] = None
    egfr: Optional[float] = None
    uacr: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    hba1c: Optional[float] = None
    serum_glucose: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class LongitudinalPatientRecord:
    """Represents a patient's historical longitudinal clinical record.

    Attributes
    ----------
    patient_id : str
        Unique patient identifier.
    age_baseline : float
        Patient age in years at the baseline (first) observation.
    sex : str
        Biological sex at birth ('male', 'female', or numeric code 1/2).
    diabetes_history : Optional[bool]
        Documented clinical history of diabetes mellitus (None if unknown).
    hypertension_history : Optional[bool]
        Documented clinical history of hypertension (None if unknown).
    observations : List[ClinicalObservation]
        Chronological list of clinical observations.
    is_synthetic : bool
        Flag indicating if record is a synthetic software test fixture.
    provenance : str
        Data source provenance string (e.g. 'CLINICAL_EHR', 'SYNTHETIC_TEST_FIXTURE').
    """

    patient_id: str
    age_baseline: float
    sex: str
    diabetes_history: Optional[bool] = None
    hypertension_history: Optional[bool] = None
    observations: List[ClinicalObservation] = field(default_factory=list)
    is_synthetic: bool = False
    provenance: str = "CLINICAL_EHR"


@dataclass(frozen=True)
class ProgressionAbstention:
    """Structured clinical abstention verdict when longitudinal history is insufficient.

    Attributes
    ----------
    should_abstain : bool
        True if the record does not meet the minimum criteria for progression modeling.
    reason_code : str
        Machine-readable reason code (e.g. 'INSUFFICIENT_OBSERVATION_COUNT').
    message : str
        Detailed, clinician-facing explanation.
    insufficient_criteria : List[str]
        List of specific clinical data criteria that were violated.
    """

    should_abstain: bool
    reason_code: str
    message: str
    insufficient_criteria: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProgressionFeatures:
    """Structured, immutable time-aware progression features extracted at landmark time.

    Contains all derived trajectory, exposure, and clinical covariates required
    for Engine 3 longitudinal progression estimation.
    """

    # Identification & Landmarking
    patient_id: str
    landmark_time: datetime
    is_synthetic: bool
    provenance: str

    # Observation History
    obs_count: int
    total_followup_days: float
    median_visit_interval_days: Optional[float]
    first_observation_time: datetime
    last_observation_time: datetime

    # Baseline Demographics & Clinical Context
    age_at_landmark: float
    sex: str
    diabetes_history: Optional[bool]
    hypertension_history: Optional[bool]

    # eGFR Trajectory
    egfr_baseline: float
    egfr_landmark: float
    egfr_delta_absolute: float
    egfr_historical_slope: Optional[float]
    egfr_slope_status: str
    egfr_recent_slope: Optional[float]
    egfr_recent_slope_status: str
    egfr_recent_acceleration: Optional[float]
    egfr_variability_cv: Optional[float]
    egfr_valid_obs_count: int

    # Albuminuria (UACR) History
    uacr_baseline: Optional[float]
    uacr_landmark: Optional[float]
    uacr_valid_count: int
    uacr_missing_count: int
    uacr_coverage_ratio: float
    uacr_time_weighted_mean: Optional[float]
    uacr_time_weighted_status: str
    uacr_progression_ratio: Optional[float]

    # Hemodynamic Control
    sbp_mean: Optional[float]
    sbp_variability: Optional[float]
    dbp_mean: Optional[float]
    dbp_variability: Optional[float]
    bp_valid_count: int

    # Glycemic Markers
    hba1c_landmark: Optional[float]
    hba1c_mean: Optional[float]
    hba1c_valid_count: int

    # Quality & Missingness Indicators
    missingness_flags: Dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ProgressionFeatureResult:
    """Wrapper holding either valid extracted features or an abstention verdict."""

    is_eligible: bool
    features: Optional[ProgressionFeatures]
    abstention: Optional[ProgressionAbstention]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a comprehensive dictionary representation."""
        if not self.is_eligible and self.abstention is not None:
            return {
                "is_eligible": False,
                "abstention": {
                    "should_abstain": self.abstention.should_abstain,
                    "reason_code": self.abstention.reason_code,
                    "message": self.abstention.message,
                    "insufficient_criteria": self.abstention.insufficient_criteria,
                },
                "features": None,
            }
        elif self.features is not None:
            return {
                "is_eligible": True,
                "abstention": None,
                "features": {
                    "patient_id": self.features.patient_id,
                    "landmark_time": self.features.landmark_time.isoformat(),
                    "is_synthetic": self.features.is_synthetic,
                    "provenance": self.features.provenance,
                    "obs_count": self.features.obs_count,
                    "total_followup_days": self.features.total_followup_days,
                    "median_visit_interval_days": self.features.median_visit_interval_days,
                    "first_observation_time": self.features.first_observation_time.isoformat(),
                    "last_observation_time": self.features.last_observation_time.isoformat(),
                    "age_at_landmark": self.features.age_at_landmark,
                    "sex": self.features.sex,
                    "diabetes_history": self.features.diabetes_history,
                    "hypertension_history": self.features.hypertension_history,
                    "egfr_baseline": self.features.egfr_baseline,
                    "egfr_landmark": self.features.egfr_landmark,
                    "egfr_delta_absolute": self.features.egfr_delta_absolute,
                    "egfr_historical_slope": self.features.egfr_historical_slope,
                    "egfr_slope_status": self.features.egfr_slope_status,
                    "egfr_recent_slope": self.features.egfr_recent_slope,
                    "egfr_recent_slope_status": self.features.egfr_recent_slope_status,
                    "egfr_recent_acceleration": self.features.egfr_recent_acceleration,
                    "egfr_variability_cv": self.features.egfr_variability_cv,
                    "egfr_valid_obs_count": self.features.egfr_valid_obs_count,
                    "uacr_baseline": self.features.uacr_baseline,
                    "uacr_landmark": self.features.uacr_landmark,
                    "uacr_valid_count": self.features.uacr_valid_count,
                    "uacr_missing_count": self.features.uacr_missing_count,
                    "uacr_coverage_ratio": self.features.uacr_coverage_ratio,
                    "uacr_time_weighted_mean": self.features.uacr_time_weighted_mean,
                    "uacr_time_weighted_status": self.features.uacr_time_weighted_status,
                    "uacr_progression_ratio": self.features.uacr_progression_ratio,
                    "sbp_mean": self.features.sbp_mean,
                    "sbp_variability": self.features.sbp_variability,
                    "dbp_mean": self.features.dbp_mean,
                    "dbp_variability": self.features.dbp_variability,
                    "bp_valid_count": self.features.bp_valid_count,
                    "hba1c_landmark": self.features.hba1c_landmark,
                    "hba1c_mean": self.features.hba1c_mean,
                    "hba1c_valid_count": self.features.hba1c_valid_count,
                    "missingness_flags": self.features.missingness_flags,
                },
            }
        return {"is_eligible": False, "abstention": None, "features": None}


# ---------------------------------------------------------------------------
# Validation & Chronology Helpers
# ---------------------------------------------------------------------------

def validate_longitudinal_chronology(
    observations: List[ClinicalObservation],
) -> Tuple[bool, Optional[str]]:
    """Validate that observations form a strictly monotonic chronological sequence.

    Rejects duplicate timestamps and non-monotonic sequences.
    Does NOT mutate or rearrange the list.

    Returns
    -------
    Tuple[bool, Optional[str]]
        (is_valid, error_message). If valid, error_message is None.
    """
    if not observations:
        return True, None

    for i in range(len(observations) - 1):
        t_curr = observations[i].timestamp
        t_next = observations[i + 1].timestamp

        if t_next == t_curr:
            return (
                False,
                f"Duplicate timestamp detected at index {i} and {i+1}: {t_curr.isoformat()}.",
            )
        if t_next < t_curr:
            return (
                False,
                f"Non-monotonic timestamp sequence: observation {i+1} ({t_next.isoformat()}) "
                f"is earlier than observation {i} ({t_curr.isoformat()}).",
            )

    return True, None


def resolve_observation_egfr(
    obs: ClinicalObservation,
    patient_age: float,
    patient_sex: str,
) -> Optional[float]:
    """Resolve or compute eGFR for a single clinical observation.

    Prefers direct observation eGFR if valid (> 0); otherwise calculates
    on-the-fly using CKD-EPI 2021 race-free equation if serum creatinine is valid.
    Never silently imputes missing measurements.

    Returns
    -------
    Optional[float]
        Valid eGFR in mL/min/1.73 m2, or None if uncomputable.
    """
    if obs.egfr is not None and not math.isnan(obs.egfr) and obs.egfr > 0.0:
        return float(obs.egfr)

    if (
        obs.serum_creatinine is not None
        and not math.isnan(obs.serum_creatinine)
        and obs.serum_creatinine > 0.0
    ):
        res = calculate_egfr_ckd_epi_2021(
            serum_creatinine=obs.serum_creatinine,
            age=patient_age,
            sex=patient_sex,
            unit="mg/dL",
        )
        if res.get("is_valid") and res.get("egfr") is not None:
            return float(res["egfr"])

    return None


# ---------------------------------------------------------------------------
# Core Time-Aware Feature Engineering Engine
# ---------------------------------------------------------------------------

def extract_progression_features(
    record: LongitudinalPatientRecord,
    landmark_time: Optional[datetime] = None,
) -> ProgressionFeatureResult:
    """Extract time-aware progression features at an explicit landmark timestamp.

    Enforces:
    1. Zero Temporal Leakage: Only observations at or before landmark_time are used.
    2. Chronology Validation: Disordered or duplicate timestamps trigger abstention.
    3. Longitudinal Sufficiency: Requires >= 2 observations and >= 90 days follow-up.
    4. Descriptive OLS Slope: Requires >= 3 valid eGFR points spanning >= 365 days.
    5. Zero Mutation: The input record and its observations are never mutated.

    Parameters
    ----------
    record : LongitudinalPatientRecord
        The patient's longitudinal record.
    landmark_time : Optional[datetime]
        The evaluation cut-off time. If None, defaults to the timestamp of the
        latest observation in the record.

    Returns
    -------
    ProgressionFeatureResult
        Result containing either the extracted ProgressionFeatures or a structured
        ProgressionAbstention.
    """
    # 1. Chronology and Timestamp Integrity Check
    is_valid_chrono, chrono_err = validate_longitudinal_chronology(record.observations)
    if not is_valid_chrono:
        abstention = ProgressionAbstention(
            should_abstain=True,
            reason_code="NON_MONOTONIC_TIMESTAMPS",
            message=f"Observation chronology is invalid: {chrono_err}",
            insufficient_criteria=["monotonic_timestamps"],
        )
        return ProgressionFeatureResult(
            is_eligible=False, features=None, abstention=abstention
        )

    if not record.observations:
        abstention = ProgressionAbstention(
            should_abstain=True,
            reason_code="INSUFFICIENT_OBSERVATION_COUNT",
            message="Patient record contains zero observations.",
            insufficient_criteria=["minimum_2_observations"],
        )
        return ProgressionFeatureResult(
            is_eligible=False, features=None, abstention=abstention
        )

    # 2. Establish Landmark Cut-off Time
    if landmark_time is None:
        eff_landmark = record.observations[-1].timestamp
    else:
        eff_landmark = landmark_time

    # 3. Filter Observations (Strict Landmarking: <= landmark_time)
    # Never mutate record.observations
    eligible_obs = [obs for obs in record.observations if obs.timestamp <= eff_landmark]

    # 4. Evaluate Basic Longitudinal Sufficiency Gates
    # Gate A: Minimum Observation Count (>= 2)
    if len(eligible_obs) < 2:
        abstention = ProgressionAbstention(
            should_abstain=True,
            reason_code="INSUFFICIENT_OBSERVATION_COUNT",
            message=(
                f"Patient has only {len(eligible_obs)} observation(s) on or before landmark "
                f"({eff_landmark.isoformat()}). A minimum of 2 observations is clinically required "
                f"to establish a longitudinal trajectory."
            ),
            insufficient_criteria=["minimum_2_observations"],
        )
        return ProgressionFeatureResult(
            is_eligible=False, features=None, abstention=abstention
        )

    # Gate B: Minimum Follow-up Duration (>= 90 days)
    t0 = eligible_obs[0].timestamp
    t_last = eligible_obs[-1].timestamp
    total_followup_days = (t_last - t0).total_seconds() / 86400.0

    if total_followup_days < 90.0:
        abstention = ProgressionAbstention(
            should_abstain=True,
            reason_code="INSUFFICIENT_FOLLOWUP_DURATION",
            message=(
                f"Total follow-up duration of {total_followup_days:.1f} days is shorter than the "
                f"90-day minimum required by KDIGO guidelines to differentiate chronic progression "
                f"from acute transient kidney injury."
            ),
            insufficient_criteria=["minimum_90_days_followup"],
        )
        return ProgressionFeatureResult(
            is_eligible=False, features=None, abstention=abstention
        )

    # 5. Temporal Intervals & Spacing
    intervals_days = [
        (eligible_obs[i + 1].timestamp - eligible_obs[i].timestamp).total_seconds() / 86400.0
        for i in range(len(eligible_obs) - 1)
    ]
    median_interval = float(np.median(intervals_days)) if intervals_days else None

    # Age at Landmark Time (pro-rated in years)
    age_at_landmark = record.age_baseline + ((eff_landmark - t0).total_seconds() / (365.25 * 86400.0))

    # 6. eGFR Trajectory Extraction
    # Map each observation to (time_in_years_from_t0, egfr_value)
    egfr_points: List[Tuple[float, float]] = []
    for obs in eligible_obs:
        t_years = (obs.timestamp - t0).total_seconds() / (365.25 * 86400.0)
        obs_age = record.age_baseline + t_years
        val = resolve_observation_egfr(obs, patient_age=obs_age, patient_sex=record.sex)
        if val is not None:
            egfr_points.append((t_years, val))

    if len(egfr_points) < 2:
        abstention = ProgressionAbstention(
            should_abstain=True,
            reason_code="INVALID_CLINICAL_INPUTS",
            message=(
                f"Patient has only {len(egfr_points)} valid eGFR observation(s) on or before landmark. "
                f"At least 2 valid filtration readings are required to evaluate renal progression."
            ),
            insufficient_criteria=["minimum_2_valid_egfr_observations"],
        )
        return ProgressionFeatureResult(
            is_eligible=False, features=None, abstention=abstention
        )

    egfr_baseline = egfr_points[0][1]
    egfr_landmark = egfr_points[-1][1]
    egfr_delta_abs = egfr_landmark - egfr_baseline

    # eGFR Coefficient of Variation (CV = SD / Mean)
    egfr_vals = [pt[1] for pt in egfr_points]
    egfr_mean = float(np.mean(egfr_vals))
    if len(egfr_vals) >= 2 and egfr_mean > 0.0:
        egfr_sd = float(np.std(egfr_vals, ddof=1))
        egfr_cv = round(egfr_sd / egfr_mean, 4)
    else:
        egfr_cv = None

    # Historical eGFR OLS Slope
    # Stricter requirement: >= 3 points spanning >= 365 days
    egfr_span_days = (eligible_obs[-1].timestamp - eligible_obs[0].timestamp).total_seconds() / 86400.0
    egfr_slope: Optional[float] = None
    if len(egfr_points) < 3:
        egfr_slope_status = "INSUFFICIENT_OBSERVATION_COUNT_FOR_SLOPE (requires >= 3)"
    elif egfr_span_days < 365.0:
        egfr_slope_status = "INSUFFICIENT_FOLLOWUP_FOR_SLOPE (requires >= 365 days)"
    else:
        # Compute Ordinary Least Squares Slope
        t_arr = np.array([pt[0] for pt in egfr_points])
        y_arr = np.array([pt[1] for pt in egfr_points])
        t_var = np.var(t_arr)
        if t_var > 1e-9:
            slope_val = np.cov(t_arr, y_arr, ddof=0)[0, 1] / t_var
            egfr_slope = round(float(slope_val), 3)
            egfr_slope_status = "CALCULATED_OLS_ANNUAL_SLOPE"
        else:
            egfr_slope_status = "ZERO_TIME_VARIANCE"

    # Recent Slope (Within last 365 days before landmark)
    recent_cutoff = eff_landmark.timestamp() - (365.25 * 86400.0)
    recent_points = [
        pt for idx, pt in enumerate(egfr_points)
        if eligible_obs[idx].timestamp.timestamp() >= recent_cutoff
    ]
    egfr_recent_slope: Optional[float] = None
    if len(recent_points) < 2:
        egfr_recent_slope_status = "INSUFFICIENT_RECENT_POINTS (requires >= 2 in last 12 mo)"
    else:
        # Check recent span >= 90 days
        rec_t_span = (recent_points[-1][0] - recent_points[0][0]) * 365.25
        if rec_t_span < 90.0:
            egfr_recent_slope_status = "RECENT_SPAN_TOO_SHORT (requires >= 90 days)"
        else:
            rec_t = np.array([pt[0] for pt in recent_points])
            rec_y = np.array([pt[1] for pt in recent_points])
            rec_var = np.var(rec_t)
            if rec_var > 1e-9:
                rec_slope_val = np.cov(rec_t, rec_y, ddof=0)[0, 1] / rec_var
                egfr_recent_slope = round(float(rec_slope_val), 3)
                egfr_recent_slope_status = "CALCULATED_RECENT_OLS_SLOPE"
            else:
                egfr_recent_slope_status = "ZERO_RECENT_TIME_VARIANCE"

    # Recent Trajectory Acceleration (recent_slope - historical_slope)
    if egfr_recent_slope is not None and egfr_slope is not None:
        egfr_recent_acc = round(egfr_recent_slope - egfr_slope, 3)
    else:
        egfr_recent_acc = None

    # 7. Albuminuria (UACR) History & Time-Weighted Exposure
    # Filter observations with valid positive UACR
    uacr_points: List[Tuple[datetime, float]] = []
    for obs in eligible_obs:
        if obs.uacr is not None and not math.isnan(obs.uacr) and obs.uacr >= 0.0:
            uacr_points.append((obs.timestamp, float(obs.uacr)))

    uacr_valid_count = len(uacr_points)
    uacr_missing_count = len(eligible_obs) - uacr_valid_count
    uacr_coverage_ratio = round(uacr_valid_count / len(eligible_obs), 4)

    uacr_baseline = uacr_points[0][1] if uacr_points else None
    uacr_landmark = uacr_points[-1][1] if uacr_points else None

    # UACR Progression Ratio (landmark / baseline)
    # Strictly check denominator > 0 to prevent division by zero
    if (
        uacr_baseline is not None
        and uacr_landmark is not None
        and uacr_baseline > 0.0
    ):
        uacr_prog_ratio = round(uacr_landmark / uacr_baseline, 4)
    else:
        uacr_prog_ratio = None

    # Trapezoidal Time-Weighted Mean UACR
    uacr_twm: Optional[float] = None
    if uacr_valid_count >= 2:
        total_time_sec = (uacr_points[-1][0] - uacr_points[0][0]).total_seconds()
        if total_time_sec > 0:
            area = sum(
                0.5
                * (uacr_points[i][1] + uacr_points[i + 1][1])
                * (uacr_points[i + 1][0] - uacr_points[i][0]).total_seconds()
                for i in range(uacr_valid_count - 1)
            )
            uacr_twm = round(area / total_time_sec, 2)
            uacr_twm_status = "TRAPEZOIDAL_TIME_WEIGHTED_MEAN"
        else:
            uacr_twm = uacr_points[0][1]
            uacr_twm_status = "IDENTICAL_TIMESTAMP_POINTS"
    elif uacr_valid_count == 1:
        uacr_twm = uacr_points[0][1]
        uacr_twm_status = "SINGLE_OBSERVATION_POINT_VALUE"
    else:
        uacr_twm = None
        uacr_twm_status = "NO_VALID_UACR_OBSERVATIONS"

    # 8. Hemodynamic Blood Pressure Analysis
    sbp_vals = [
        float(obs.systolic_bp)
        for obs in eligible_obs
        if obs.systolic_bp is not None
        and not math.isnan(obs.systolic_bp)
        and obs.systolic_bp > 0
    ]
    dbp_vals = [
        float(obs.diastolic_bp)
        for obs in eligible_obs
        if obs.diastolic_bp is not None
        and not math.isnan(obs.diastolic_bp)
        and obs.diastolic_bp > 0
    ]

    bp_valid_count = len(sbp_vals)
    sbp_mean = round(float(np.mean(sbp_vals)), 1) if sbp_vals else None
    dbp_mean = round(float(np.mean(dbp_vals)), 1) if dbp_vals else None

    sbp_var = (
        round(float(np.std(sbp_vals, ddof=1)), 2) if len(sbp_vals) >= 2 else None
    )
    dbp_var = (
        round(float(np.std(dbp_vals, ddof=1)), 2) if len(dbp_vals) >= 2 else None
    )

    # 9. Glycemic Markers (HbA1c)
    hba1c_vals = [
        float(obs.hba1c)
        for obs in eligible_obs
        if obs.hba1c is not None
        and not math.isnan(obs.hba1c)
        and obs.hba1c > 0
    ]
    hba1c_valid_count = len(hba1c_vals)
    hba1c_mean = round(float(np.mean(hba1c_vals)), 2) if hba1c_vals else None
    hba1c_landmark = hba1c_vals[-1] if hba1c_vals else None

    # 10. Missingness Summary Indicators
    missingness = {
        "has_missing_uacr": uacr_missing_count > 0,
        "lacks_uacr_baseline": uacr_baseline is None,
        "lacks_uacr_landmark": uacr_landmark is None,
        "lacks_bp_monitoring": bp_valid_count == 0,
        "lacks_hba1c": hba1c_valid_count == 0,
        "has_slope": egfr_slope is not None,
    }

    features = ProgressionFeatures(
        patient_id=record.patient_id,
        landmark_time=eff_landmark,
        is_synthetic=record.is_synthetic,
        provenance=record.provenance,
        obs_count=len(eligible_obs),
        total_followup_days=round(total_followup_days, 1),
        median_visit_interval_days=round(median_interval, 1) if median_interval else None,
        first_observation_time=t0,
        last_observation_time=t_last,
        age_at_landmark=round(age_at_landmark, 2),
        sex=record.sex,
        diabetes_history=record.diabetes_history,
        hypertension_history=record.hypertension_history,
        egfr_baseline=round(egfr_baseline, 2),
        egfr_landmark=round(egfr_landmark, 2),
        egfr_delta_absolute=round(egfr_delta_abs, 2),
        egfr_historical_slope=egfr_slope,
        egfr_slope_status=egfr_slope_status,
        egfr_recent_slope=egfr_recent_slope,
        egfr_recent_slope_status=egfr_recent_slope_status,
        egfr_recent_acceleration=egfr_recent_acc,
        egfr_variability_cv=egfr_cv,
        egfr_valid_obs_count=len(egfr_points),
        uacr_baseline=round(uacr_baseline, 2) if uacr_baseline is not None else None,
        uacr_landmark=round(uacr_landmark, 2) if uacr_landmark is not None else None,
        uacr_valid_count=uacr_valid_count,
        uacr_missing_count=uacr_missing_count,
        uacr_coverage_ratio=uacr_coverage_ratio,
        uacr_time_weighted_mean=uacr_twm,
        uacr_time_weighted_status=uacr_twm_status,
        uacr_progression_ratio=uacr_prog_ratio,
        sbp_mean=sbp_mean,
        sbp_variability=sbp_var,
        dbp_mean=dbp_mean,
        dbp_variability=dbp_var,
        bp_valid_count=bp_valid_count,
        hba1c_landmark=hba1c_landmark,
        hba1c_mean=hba1c_mean,
        hba1c_valid_count=hba1c_valid_count,
        missingness_flags=missingness,
    )

    return ProgressionFeatureResult(
        is_eligible=True, features=features, abstention=None
    )
