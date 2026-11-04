"""Survival dataset representation and validation contracts for Engine 3.

Provides typed, defensive data structures for survival and competing-risk analysis
in Chronic Kidney Disease (CKD) progression.

Key capabilities:
- Landmark observation anchoring with strict temporal leakage prevention
- Explicit event and censoring coding (0 = Censored, 1 = Kidney Failure, 2 = Competing Death)
- Strict validation of follow-up consistency, event ordering, and absence of contradictory flags
- Support for multiple landmark records per patient while maintaining patient identity
- Patient-level grouped train/test splitting to prevent intra-patient data leakage
- Temporal cohort splitting by index/recruitment date
"""

from __future__ import annotations

import datetime
from enum import IntEnum
import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd


class SurvivalEventType(IntEnum):
    """Explicit clinical event type classification for CKD progression survival cohorts.

    Definitions:
        RIGHT_CENSORED (0): Patient completed follow-up or was lost to follow-up without
            experiencing kidney failure (KRT) or death. Non-informative right censoring.
        KIDNEY_FAILURE (1): Primary clinical progression endpoint. Patient initiated
            maintenance dialysis or received a preemptive kidney transplant (KRT),
            or reached confirmed eGFR < 10-15 mL/min/1.73 m2.
        COMPETING_DEATH (2): Competing clinical endpoint. Patient died prior to reaching
            kidney failure / KRT. In competing-risk analysis, this precludes future
            observation of kidney failure. Must NOT be silently treated as ordinary
            non-informative censoring.
    """

    RIGHT_CENSORED = 0
    KIDNEY_FAILURE = 1
    COMPETING_DEATH = 2


class SurvivalDataValidationError(ValueError):
    """Raised when a survival record or dataset violates validation rules or temporal consistency."""

    pass


def _parse_date(val: Union[datetime.date, datetime.datetime, str]) -> datetime.date:
    """Normalize input to datetime.date object."""
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        val_clean = val.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.datetime.strptime(val_clean, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.date.fromisoformat(val_clean)
        except Exception:
            pass
    raise SurvivalDataValidationError(f"Could not parse valid date from: {repr(val)}")


class SurvivalLandmarkRecord:
    """Validated survival observation record anchored at a specific clinical landmark.

    Attributes:
        patient_id: Unique patient identifier.
        landmark_date: Observation date at which retrospective baseline features are evaluated.
        baseline_date: Cohort enrollment / study baseline date (baseline_date <= landmark_date).
        follow_up_start_date: Start date of follow-up interval (typically equals landmark_date).
        follow_up_end_date: Event date or censoring date (follow_up_end_date >= follow_up_start_date).
        follow_up_duration_days: Non-negative elapsed days from follow_up_start_date to follow_up_end_date.
        follow_up_duration_years: Non-negative elapsed years (duration_days / 365.25).
        event_kidney_failure: 1 if kidney failure (KRT) occurred during follow-up, 0 otherwise.
        event_death: 1 if death occurred prior to kidney failure during follow-up, 0 otherwise.
        is_censored: 1 if right-censored without kidney failure or death, 0 otherwise.
        event_type: Explicit SurvivalEventType enum (0=Censored, 1=Kidney Failure, 2=Competing Death).
        features: Dictionary of numerical clinical predictor values available at or before landmark_date.
        feature_timestamps: Optional dictionary mapping feature name to observation date, to verify
            zero temporal leakage (observation date <= landmark_date).
        cohort_id: Identifier of the source clinical cohort (e.g., 'CRIC', 'NHANES_LONGITUDINAL', 'INTERNAL').
        provenance: Description of clinical laboratory source, extraction run, or protocol.
    """

    def __init__(
        self,
        patient_id: str,
        landmark_date: Union[datetime.date, str],
        baseline_date: Union[datetime.date, str],
        follow_up_start_date: Union[datetime.date, str],
        follow_up_end_date: Union[datetime.date, str],
        event_type: Union[SurvivalEventType, int],
        event_kidney_failure: int,
        event_death: int,
        is_censored: int,
        features: Dict[str, float],
        feature_timestamps: Optional[Dict[str, Union[datetime.date, str]]] = None,
        cohort_id: str = "UNKNOWN_COHORT",
        provenance: str = "RESEARCH_CDSS_CONTRACT",
    ):
        if not patient_id or not str(patient_id).strip():
            raise SurvivalDataValidationError("patient_id must be a non-empty string.")

        self.patient_id = str(patient_id).strip()
        self.landmark_date = _parse_date(landmark_date)
        self.baseline_date = _parse_date(baseline_date)
        self.follow_up_start_date = _parse_date(follow_up_start_date)
        self.follow_up_end_date = _parse_date(follow_up_end_date)

        # Temporal ordering validations
        if self.baseline_date > self.landmark_date:
            raise SurvivalDataValidationError(
                f"Patient {self.patient_id}: baseline_date ({self.baseline_date}) cannot be strictly "
                f"after landmark_date ({self.landmark_date})."
            )

        if self.follow_up_start_date < self.landmark_date:
            raise SurvivalDataValidationError(
                f"Patient {self.patient_id}: follow_up_start_date ({self.follow_up_start_date}) cannot "
                f"precede landmark_date ({self.landmark_date}). Future follow-up must begin at/after landmark."
            )

        if self.follow_up_end_date < self.follow_up_start_date:
            raise SurvivalDataValidationError(
                f"Patient {self.patient_id}: follow_up_end_date ({self.follow_up_end_date}) precedes "
                f"follow_up_start_date ({self.follow_up_start_date}). Negative follow-up duration is invalid."
            )

        delta_days = (self.follow_up_end_date - self.follow_up_start_date).days
        self.follow_up_duration_days = float(delta_days)
        self.follow_up_duration_years = float(delta_days) / 365.25

        # Event type validation
        try:
            self.event_type = SurvivalEventType(int(event_type))
        except ValueError:
            raise SurvivalDataValidationError(
                f"Patient {self.patient_id}: Invalid event_type {event_type}. "
                f"Must be 0 (Censored), 1 (Kidney Failure), or 2 (Competing Death)."
            )

        self.event_kidney_failure = int(event_kidney_failure)
        self.event_death = int(event_death)
        self.is_censored = int(is_censored)

        # Defensive flag consistency checks
        self._validate_flag_consistency()

        # Features validation
        if not isinstance(features, dict) or len(features) == 0:
            raise SurvivalDataValidationError(
                f"Patient {self.patient_id}: features dictionary must be non-empty."
            )

        clean_features: Dict[str, float] = {}
        for k, v in features.items():
            if v is None or math.isnan(float(v)) or math.isinf(float(v)):
                raise SurvivalDataValidationError(
                    f"Patient {self.patient_id}: Feature '{k}' has invalid/missing numeric value: {v}."
                )
            clean_features[k] = float(v)
        self.features = clean_features

        # Temporal leakage check on feature observation timestamps
        self.feature_timestamps: Dict[str, datetime.date] = {}
        if feature_timestamps:
            for feat_name, ts in feature_timestamps.items():
                parsed_ts = _parse_date(ts)
                if parsed_ts > self.landmark_date:
                    raise SurvivalDataValidationError(
                        f"Patient {self.patient_id}: TEMPORAL LEAKAGE DETECTED! Feature '{feat_name}' "
                        f"was measured on {parsed_ts}, which is after landmark_date ({self.landmark_date})."
                    )
                self.feature_timestamps[feat_name] = parsed_ts

        self.cohort_id = str(cohort_id)
        self.provenance = str(provenance)

    def _validate_flag_consistency(self) -> None:
        """Enforce strict mutual exclusivity and mathematical consistency between event flags."""
        if self.event_type == SurvivalEventType.RIGHT_CENSORED:
            if self.is_censored != 1 or self.event_kidney_failure != 0 or self.event_death != 0:
                raise SurvivalDataValidationError(
                    f"Patient {self.patient_id}: Contradictory flags for RIGHT_CENSORED (0). "
                    f"Expected is_censored=1, event_kf=0, event_death=0; "
                    f"Got is_censored={self.is_censored}, event_kf={self.event_kidney_failure}, "
                    f"event_death={self.event_death}."
                )
        elif self.event_type == SurvivalEventType.KIDNEY_FAILURE:
            if self.is_censored != 0 or self.event_kidney_failure != 1 or self.event_death != 0:
                raise SurvivalDataValidationError(
                    f"Patient {self.patient_id}: Contradictory flags for KIDNEY_FAILURE (1). "
                    f"Expected is_censored=0, event_kf=1, event_death=0; "
                    f"Got is_censored={self.is_censored}, event_kf={self.event_kidney_failure}, "
                    f"event_death={self.event_death}."
                )
        elif self.event_type == SurvivalEventType.COMPETING_DEATH:
            if self.is_censored != 0 or self.event_kidney_failure != 0 or self.event_death != 1:
                raise SurvivalDataValidationError(
                    f"Patient {self.patient_id}: Contradictory flags for COMPETING_DEATH (2). "
                    f"Expected is_censored=0, event_kf=0, event_death=1; "
                    f"Got is_censored={self.is_censored}, event_kf={self.event_kidney_failure}, "
                    f"event_death={self.event_death}."
                )

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to flattened dictionary representation."""
        row = {
            "patient_id": self.patient_id,
            "landmark_date": self.landmark_date.isoformat(),
            "baseline_date": self.baseline_date.isoformat(),
            "follow_up_start_date": self.follow_up_start_date.isoformat(),
            "follow_up_end_date": self.follow_up_end_date.isoformat(),
            "follow_up_duration_days": self.follow_up_duration_days,
            "follow_up_duration_years": self.follow_up_duration_years,
            "event_type": int(self.event_type),
            "event_kidney_failure": self.event_kidney_failure,
            "event_death": self.event_death,
            "is_censored": self.is_censored,
            "cohort_id": self.cohort_id,
            "provenance": self.provenance,
        }
        for k, v in self.features.items():
            row[f"feat_{k}"] = v
        return row


class SurvivalDataset:
    """Container and validator for a cohort of SurvivalLandmarkRecords.

    Enforces:
    - No duplicate (patient_id, landmark_date) records.
    - Uniform feature availability across cohort records.
    - Tabular export for survival modeling.
    """

    def __init__(self, records: Optional[List[SurvivalLandmarkRecord]] = None):
        self.records: List[SurvivalLandmarkRecord] = []
        self._seen_keys: Set[Tuple[str, datetime.date]] = set()

        if records:
            for rec in records:
                self.add_record(rec)

    def add_record(self, record: SurvivalLandmarkRecord) -> None:
        """Add a validated record to the dataset, checking for duplicate patient-landmark pairs."""
        if not isinstance(record, SurvivalLandmarkRecord):
            raise SurvivalDataValidationError(
                f"Expected SurvivalLandmarkRecord instance, got {type(record)}."
            )

        key = (record.patient_id, record.landmark_date)
        if key in self._seen_keys:
            raise SurvivalDataValidationError(
                f"Duplicate record rejected: Patient '{record.patient_id}' already has a record "
                f"anchored at landmark_date '{record.landmark_date}'."
            )

        self._seen_keys.add(key)
        self.records.append(record)

    def __len__(self) -> int:
        return len(self.records)

    @property
    def n_records(self) -> int:
        return len(self.records)

    @property
    def n_patients(self) -> int:
        return len({r.patient_id for r in self.records})

    def get_patient_ids(self) -> Set[str]:
        return {r.patient_id for r in self.records}

    def event_summary(self) -> Dict[str, Any]:
        """Provide detailed event count and censoring distribution summary."""
        n_censored = sum(1 for r in self.records if r.event_type == SurvivalEventType.RIGHT_CENSORED)
        n_kf = sum(1 for r in self.records if r.event_type == SurvivalEventType.KIDNEY_FAILURE)
        n_death = sum(1 for r in self.records if r.event_type == SurvivalEventType.COMPETING_DEATH)
        n_total = len(self.records)

        durations_yr = [r.follow_up_duration_years for r in self.records]

        return {
            "total_records": n_total,
            "unique_patients": self.n_patients,
            "n_right_censored": n_censored,
            "pct_right_censored": (n_censored / n_total * 100.0) if n_total > 0 else 0.0,
            "n_kidney_failure_events": n_kf,
            "pct_kidney_failure_events": (n_kf / n_total * 100.0) if n_total > 0 else 0.0,
            "n_competing_deaths": n_death,
            "pct_competing_deaths": (n_death / n_total * 100.0) if n_total > 0 else 0.0,
            "median_follow_up_years": float(np.median(durations_yr)) if durations_yr else 0.0,
            "iqr_follow_up_years": [
                float(np.percentile(durations_yr, 25)),
                float(np.percentile(durations_yr, 75)),
            ] if durations_yr else [0.0, 0.0],
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Convert all records to a structured pandas DataFrame."""
        if not self.records:
            return pd.DataFrame()
        rows = [r.to_dict() for r in self.records]
        return pd.DataFrame(rows)

    def get_feature_matrix(self, feature_names: Optional[List[str]] = None) -> Tuple[np.ndarray, List[str]]:
        """Extract a 2D numpy array of predictor features across all records.

        Returns:
            X: 2D array of shape (N, P).
            selected_features: Ordered list of feature names.
        """
        if not self.records:
            raise SurvivalDataValidationError("Dataset is empty; cannot extract feature matrix.")

        all_keys = sorted(list(self.records[0].features.keys()))
        selected = feature_names if feature_names is not None else all_keys

        X_rows = []
        for rec in self.records:
            row = []
            for f in selected:
                if f not in rec.features:
                    raise SurvivalDataValidationError(
                        f"Record {rec.patient_id} @ {rec.landmark_date} is missing expected feature '{f}'."
                    )
                row.append(rec.features[f])
            X_rows.append(row)

        return np.array(X_rows, dtype=np.float64), selected

    def get_survival_targets(
        self, cause_specific_event: SurvivalEventType = SurvivalEventType.KIDNEY_FAILURE
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Extract (durations_years, event_indicators) for standard cause-specific survival analysis.

        In cause-specific survival:
        - Events matching cause_specific_event are coded as 1.
        - Competing events and non-informative censoring are both coded as 0 (censored).
        """
        durations = np.array([r.follow_up_duration_years for r in self.records], dtype=np.float64)
        events = np.array(
            [1 if r.event_type == cause_specific_event else 0 for r in self.records],
            dtype=np.int32,
        )
        return durations, events


def patient_grouped_train_test_split(
    dataset: SurvivalDataset,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[SurvivalDataset, SurvivalDataset]:
    """Split a SurvivalDataset into train and test partitions by grouping on patient_id.

    Guarantees:
    - No patient appears in both train and test partitions.
    - All landmark observations belonging to a patient reside strictly in either train OR test.
    - Deterministic split based on random_state.

    Args:
        dataset: The SurvivalDataset to partition.
        test_size: Fraction of unique patients to assign to test set (0.0 < test_size < 1.0).
        random_state: Seed for reproducible patient shuffling.

    Returns:
        (train_dataset, test_dataset)
    """
    if not (0.0 < test_size < 1.0):
        raise ValueError(f"test_size must be strictly between 0.0 and 1.0, got {test_size}")

    unique_patients = sorted(list(dataset.get_patient_ids()))
    n_patients = len(unique_patients)
    if n_patients < 2:
        raise SurvivalDataValidationError(
            f"Cannot perform patient-grouped split with only {n_patients} unique patient(s)."
        )

    rng = np.random.default_rng(random_state)
    shuffled_patients = np.array(unique_patients)
    rng.shuffle(shuffled_patients)

    n_test = max(1, int(round(n_patients * test_size)))
    test_patient_set = set(shuffled_patients[:n_test])
    train_patient_set = set(shuffled_patients[n_test:])

    # Strict isolation check
    overlap = train_patient_set.intersection(test_patient_set)
    if overlap:
        raise RuntimeError(f"FATAL: Patient split overlap detected: {overlap}")

    train_ds = SurvivalDataset()
    test_ds = SurvivalDataset()

    for rec in dataset.records:
        if rec.patient_id in train_patient_set:
            train_ds.add_record(rec)
        elif rec.patient_id in test_patient_set:
            test_ds.add_record(rec)
        else:
            raise RuntimeError(f"Patient {rec.patient_id} unassigned during grouped split.")

    return train_ds, test_ds


def temporal_cohort_split(
    dataset: SurvivalDataset,
    cutoff_date: Union[datetime.date, str],
) -> Tuple[SurvivalDataset, SurvivalDataset]:
    """Split cohort temporally based on baseline_date (enrollment/index period).

    Patients enrolled on or before cutoff_date form the historical training partition;
    patients enrolled after cutoff_date form the prospective validation partition.
    """
    cutoff = _parse_date(cutoff_date)
    train_ds = SurvivalDataset()
    test_ds = SurvivalDataset()

    for rec in dataset.records:
        if rec.baseline_date <= cutoff:
            train_ds.add_record(rec)
        else:
            test_ds.add_record(rec)

    return train_ds, test_ds
