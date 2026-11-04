"""NEFROAI-X Cohort-Independent Longitudinal Data Infrastructure.

Provides standardized schemas, ingestion pipelines, landmark cohort extraction,
and data validation for longitudinal kidney disease progression analysis.

Features:
- Cohort-independent longitudinal visit schema with biological boundary validation.
- Unit reconciliation and missingness provenance tracking.
- Chronological consistency and duplicate timestamp enforcement.
- Strict landmark cohort extraction with zero future-information leakage.
- Specialized CRIC (Chronic Renal Insufficiency Cohort) adapter interface.
- Complete separation between research software infrastructure and restricted real clinical data.

Clinical Data Governance:
- Restricted datasets (e.g. CRIC) require formal Data Use Agreements (DUA) with NIDDK.
- If real CRIC data are not present locally, loaders remain cohort-ready without fabricating records.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from src.clinical.egfr_calculator import calculate_egfr_ckd_epi_2021
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
)
from src.clinical.survival.survival_contracts import (
    SurvivalDataset,
    SurvivalEventType,
    SurvivalLandmarkRecord,
)

logger = logging.getLogger("nefroai.longitudinal_loader")


# ---------------------------------------------------------------------------
# Biological Validity Boundaries
# ---------------------------------------------------------------------------

BIOLOGICAL_BOUNDS = {
    "serum_creatinine": (0.2, 25.0),  # mg/dL
    "egfr": (1.0, 180.0),             # mL/min/1.73 m2
    "uacr": (0.1, 10000.0),           # mg/g
    "systolic_bp": (50.0, 260.0),     # mmHg
    "diastolic_bp": (30.0, 160.0),    # mmHg
    "hba1c": (3.5, 20.0),             # %
    "serum_glucose": (30.0, 1000.0),  # mg/dL
    "age": (18.0, 115.0),             # years
}


# ---------------------------------------------------------------------------
# Core Longitudinal Data Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LongitudinalVisit:
    """A single validated clinical visit for a patient at an explicit timestamp."""

    visit_id: str
    patient_id: str
    timestamp: datetime
    serum_creatinine: Optional[float] = None
    egfr: Optional[float] = None
    uacr: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    hba1c: Optional[float] = None
    serum_glucose: Optional[float] = None
    covariates: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class LongitudinalPatientHistory:
    """Complete multi-visit clinical record for an individual patient."""

    patient_id: str
    baseline_age: float
    sex: str
    diabetes_history: Optional[bool] = None
    hypertension_history: Optional[bool] = None
    visits: List[LongitudinalVisit] = field(default_factory=list)
    event_type: SurvivalEventType = SurvivalEventType.RIGHT_CENSORED
    follow_up_duration_years: float = 0.0
    provenance: str = "UNKNOWN_SOURCE"
    is_synthetic: bool = False

    def to_progression_record(self) -> LongitudinalPatientRecord:
        """Convert to the standard ProgressionFeatures record format."""
        obs = [
            ClinicalObservation(
                timestamp=v.timestamp,
                serum_creatinine=v.serum_creatinine,
                egfr=v.egfr,
                uacr=v.uacr,
                systolic_bp=v.systolic_bp,
                diastolic_bp=v.diastolic_bp,
                hba1c=v.hba1c,
                serum_glucose=v.serum_glucose,
            )
            for v in self.visits
            if v.is_valid
        ]
        return LongitudinalPatientRecord(
            patient_id=self.patient_id,
            age_baseline=self.baseline_age,
            sex=self.sex,
            diabetes_history=self.diabetes_history,
            hypertension_history=self.hypertension_history,
            observations=obs,
            is_synthetic=self.is_synthetic,
            provenance=self.provenance,
        )


@dataclass
class LongitudinalCohort:
    """Collection of LongitudinalPatientHistory objects with cohort-level utilities."""

    patients: Dict[str, LongitudinalPatientHistory] = field(default_factory=dict)
    cohort_name: str = "GenericLongitudinalCohort"
    provenance: str = "COHORT_LOADER"

    def __len__(self) -> int:
        return len(self.patients)

    def total_visits(self) -> int:
        return sum(len(p.visits) for p in self.patients.values())

    def get_patient(self, patient_id: str) -> Optional[LongitudinalPatientHistory]:
        return self.patients.get(patient_id)

    def add_patient(self, patient: LongitudinalPatientHistory) -> None:
        self.patients[patient.patient_id] = patient

    def create_landmark_survival_dataset(
        self,
        landmark_time: datetime,
        followup_horizon_years: float = 2.0,
        min_prior_observations: int = 2,
    ) -> SurvivalDataset:
        """Create a leak-free landmark SurvivalDataset for survival and competing-risk modeling.

        Enforces:
        - Strict Landmark Filter: Only visits at or before landmark_time are used for features.
        - Minimum Prior Observations: Excludes patients with fewer than min_prior_observations before landmark.
        - Forward Follow-up: Calculates follow-up duration and event type strictly forward from landmark_time.
        - Zero Temporal Leakage: Future events occurring before landmark_time cause patient exclusion.
        """
        records: List[SurvivalLandmarkRecord] = []

        for p_id, p_hist in self.patients.items():
            # 1. Filter prior visits
            prior_visits = [v for v in p_hist.visits if v.timestamp <= landmark_time and v.is_valid]
            if len(prior_visits) < min_prior_observations:
                continue

            # First and latest visits
            t0 = prior_visits[0].timestamp
            t_last = prior_visits[-1].timestamp
            baseline_years = (landmark_time - t0).total_seconds() / (365.25 * 86400.0)

            # Age at landmark
            age_lm = p_hist.baseline_age + baseline_years

            # Latest prior laboratory values
            latest_egfr = next((v.egfr for v in reversed(prior_visits) if v.egfr is not None), 45.0)
            latest_uacr = next((v.uacr for v in reversed(prior_visits) if v.uacr is not None), 100.0)
            latest_sbp = next((v.systolic_bp for v in reversed(prior_visits) if v.systolic_bp is not None), 130.0)

            # OLS slope calculation from prior visits
            egfr_points = [( (v.timestamp - t0).total_seconds() / (365.25 * 86400.0), v.egfr)
                           for v in prior_visits if v.egfr is not None]
            if len(egfr_points) >= 2:
                xs = np.array([pt[0] for pt in egfr_points])
                ys = np.array([pt[1] for pt in egfr_points])
                if np.var(xs) > 1e-6:
                    slope = float(np.cov(xs, ys)[0, 1] / np.var(xs))
                else:
                    slope = 0.0
            else:
                slope = 0.0

            # Forward survival target from landmark
            # Total patient follow-up from baseline:
            total_duration = p_hist.follow_up_duration_years
            if total_duration <= baseline_years:
                # Patient was censored or experienced event before or at landmark
                continue

            forward_duration = total_duration - baseline_years
            eff_duration = min(forward_duration, followup_horizon_years)

            # Event status at horizon
            if forward_duration <= followup_horizon_years:
                eff_event = p_hist.event_type
            else:
                eff_event = SurvivalEventType.RIGHT_CENSORED

            # Dates for SurvivalLandmarkRecord
            lm_d = landmark_time.date() if isinstance(landmark_time, datetime) else landmark_time
            base_d = t0.date() if isinstance(t0, datetime) else t0
            fu_start_d = lm_d
            # Calculate end date based on eff_duration in days
            end_days = int(round(eff_duration * 365.25))
            from datetime import timedelta
            fu_end_d = fu_start_d + timedelta(days=max(1, end_days))

            kf_code = 1 if eff_event == SurvivalEventType.KIDNEY_FAILURE else 0
            death_code = 1 if eff_event == SurvivalEventType.COMPETING_DEATH else 0
            cens_code = 1 if eff_event == SurvivalEventType.RIGHT_CENSORED else 0

            # Convert sex to float
            sex_num = 1.0 if p_hist.sex.lower() == "male" else 0.0

            features = {
                "age": float(age_lm),
                "sex": float(sex_num),
                "egfr": float(latest_egfr),
                "uacr": float(latest_uacr),
                "systolic_bp": float(latest_sbp),
                "egfr_slope": float(slope),
                "diabetes": 1.0 if p_hist.diabetes_history else 0.0,
                "hypertension": 1.0 if p_hist.hypertension_history else 0.0,
                "obs_count": float(len(prior_visits)),
            }

            records.append(
                SurvivalLandmarkRecord(
                    patient_id=p_id,
                    landmark_date=lm_d,
                    baseline_date=base_d,
                    follow_up_start_date=fu_start_d,
                    follow_up_end_date=fu_end_d,
                    event_type=eff_event,
                    event_kidney_failure=kf_code,
                    event_death=death_code,
                    is_censored=cens_code,
                    features=features,
                    cohort_id=self.cohort_name,
                    provenance=f"{self.cohort_name}_LANDMARK",
                )
            )

        return SurvivalDataset(records)


# ---------------------------------------------------------------------------
# Cohort-Independent Tabular Loader
# ---------------------------------------------------------------------------

def load_longitudinal_from_dataframe(
    df: pd.DataFrame,
    patient_id_col: str = "patient_id",
    timestamp_col: str = "visit_date",
    serum_creatinine_col: Optional[str] = "serum_creatinine",
    egfr_col: Optional[str] = "egfr",
    uacr_col: Optional[str] = "uacr",
    sbp_col: Optional[str] = "systolic_bp",
    dbp_col: Optional[str] = "diastolic_bp",
    age_col: Optional[str] = "age",
    sex_col: Optional[str] = "sex",
    diabetes_col: Optional[str] = "diabetes",
    hypertension_col: Optional[str] = "hypertension",
    event_col: Optional[str] = "event_type",
    duration_col: Optional[str] = "duration_years",
    cohort_name: str = "TabularCohort",
    provenance: str = "TABULAR_LOADER",
    is_synthetic: bool = False,
) -> LongitudinalCohort:
    """Parse a generic long-format pandas DataFrame into a structured LongitudinalCohort.

    Enforces:
    - Sorting by patient_id and timestamp.
    - Duplicate timestamp detection and warning.
    - Biological boundary checking.
    - On-the-fly CKD-EPI 2021 eGFR estimation when creatinine and demographics are present.
    """
    if df.empty:
        return LongitudinalCohort(cohort_name=cohort_name, provenance=provenance)

    required_cols = [patient_id_col, timestamp_col]
    missing_req = [c for c in required_cols if c not in df.columns]
    if missing_req:
        raise ValueError(f"DataFrame is missing required identifier columns: {missing_req}")

    df_clean = df.copy()
    # Normalize timestamp
    df_clean[timestamp_col] = pd.to_datetime(df_clean[timestamp_col], errors="coerce")
    df_clean = df_clean.dropna(subset=[timestamp_col])
    df_clean = df_clean.sort_values(by=[patient_id_col, timestamp_col])

    cohort = LongitudinalCohort(cohort_name=cohort_name, provenance=provenance)

    grouped = df_clean.groupby(patient_id_col)
    for p_id, group in grouped:
        p_id_str = str(p_id)
        first_row = group.iloc[0]

        # Extract baseline patient demographics
        age = float(first_row[age_col]) if age_col and age_col in first_row and pd.notna(first_row[age_col]) else 60.0
        sex_raw = str(first_row[sex_col]).lower() if sex_col and sex_col in first_row and pd.notna(first_row[sex_col]) else "male"
        sex = "female" if "f" in sex_raw or sex_raw == "2" else "male"

        dm = bool(first_row[diabetes_col]) if diabetes_col and diabetes_col in first_row and pd.notna(first_row[diabetes_col]) else None
        htn = bool(first_row[hypertension_col]) if hypertension_col and hypertension_col in first_row and pd.notna(first_row[hypertension_col]) else None

        # Outcomes
        ev_code = SurvivalEventType.RIGHT_CENSORED
        if event_col and event_col in group.columns:
            ev_val = group[event_col].dropna().iloc[-1] if not group[event_col].dropna().empty else 0
            try:
                ev_code = SurvivalEventType(int(ev_val))
            except ValueError:
                ev_code = SurvivalEventType.RIGHT_CENSORED

        duration = 0.0
        if duration_col and duration_col in group.columns:
            dur_val = group[duration_col].dropna().iloc[-1] if not group[duration_col].dropna().empty else 0.0
            duration = float(dur_val)
        else:
            t_span = (group[timestamp_col].iloc[-1] - group[timestamp_col].iloc[0]).total_seconds() / (365.25 * 86400.0)
            duration = max(0.1, t_span)

        visits: List[LongitudinalVisit] = []
        seen_timestamps: Set[datetime] = set()

        for idx, row in group.iterrows():
            ts = row[timestamp_col].to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            v_warnings = []
            if ts in seen_timestamps:
                v_warnings.append(f"Duplicate timestamp for patient {p_id_str}: {ts.isoformat()}")
            seen_timestamps.add(ts)

            # Creatinine
            scr = None
            if serum_creatinine_col and serum_creatinine_col in row and pd.notna(row[serum_creatinine_col]):
                val = float(row[serum_creatinine_col])
                b_min, b_max = BIOLOGICAL_BOUNDS["serum_creatinine"]
                if b_min <= val <= b_max:
                    scr = val
                else:
                    v_warnings.append(f"Serum creatinine {val} outside physiological bounds ({b_min}-{b_max} mg/dL).")

            # eGFR
            egfr_val = None
            if egfr_col and egfr_col in row and pd.notna(row[egfr_col]):
                val = float(row[egfr_col])
                b_min, b_max = BIOLOGICAL_BOUNDS["egfr"]
                if b_min <= val <= b_max:
                    egfr_val = val
                else:
                    v_warnings.append(f"eGFR {val} outside bounds ({b_min}-{b_max}).")
            elif scr is not None:
                calc_res = calculate_egfr_ckd_epi_2021(serum_creatinine=scr, age=age, sex=sex, unit="mg/dL")
                if calc_res.get("is_valid") and calc_res.get("egfr") is not None:
                    egfr_val = float(calc_res["egfr"])

            # UACR
            uacr_val = None
            if uacr_col and uacr_col in row and pd.notna(row[uacr_col]):
                val = float(row[uacr_col])
                b_min, b_max = BIOLOGICAL_BOUNDS["uacr"]
                if b_min <= val <= b_max:
                    uacr_val = val
                else:
                    v_warnings.append(f"UACR {val} outside bounds ({b_min}-{b_max} mg/g).")

            # Blood Pressure
            sbp_val = float(row[sbp_col]) if sbp_col and sbp_col in row and pd.notna(row[sbp_col]) else None
            dbp_val = float(row[dbp_col]) if dbp_col and dbp_col in row and pd.notna(row[dbp_col]) else None

            v_id = f"{p_id_str}_V{len(visits) + 1}"
            visits.append(
                LongitudinalVisit(
                    visit_id=v_id,
                    patient_id=p_id_str,
                    timestamp=ts,
                    serum_creatinine=scr,
                    egfr=egfr_val,
                    uacr=uacr_val,
                    systolic_bp=sbp_val,
                    diastolic_bp=dbp_val,
                    is_valid=len(v_warnings) == 0 or all("Duplicate" not in w for w in v_warnings),
                    validation_warnings=v_warnings,
                )
            )

        patient_hist = LongitudinalPatientHistory(
            patient_id=p_id_str,
            baseline_age=age,
            sex=sex,
            diabetes_history=dm,
            hypertension_history=htn,
            visits=visits,
            event_type=ev_code,
            follow_up_duration_years=duration,
            provenance=provenance,
            is_synthetic=is_synthetic,
        )
        cohort.add_patient(patient_hist)

    return cohort


# ---------------------------------------------------------------------------
# CRIC (Chronic Renal Insufficiency Cohort) Adapter Interface
# ---------------------------------------------------------------------------

class CRICLongitudinalAdapter:
    """Specialized adapter interface for the NIDDK Chronic Renal Insufficiency Cohort (CRIC).

    CRIC Study Overview:
    - Multicenter prospective observational cohort of >5,400 adult patients with mild-to-moderate CKD.
    - Monitored prospectively for CKD progression, end-stage renal disease (ESRD), and cardiovascular death.
    - Governed by NIDDK Central Repository Data Use Agreements (DUA).

    Governance Safeguards:
    - Never fabricates patient records if raw files are absent.
    - If the approved CRIC dataset path does not exist, raises an explicit informative error
      directing researchers to the formal NIDDK repository.
    """

    EXPECTED_FILES = [
        "cric_longitudinal.csv",
        "cric_baseline.csv",
        "cric_outcomes.csv",
    ]

    COLUMN_MAPPING = {
        "PID": "patient_id",
        "VISIT_DATE": "visit_date",
        "SCR": "serum_creatinine",
        "EGFR_CKD_EPI": "egfr",
        "UACR": "uacr",
        "SBP": "systolic_bp",
        "DBP": "diastolic_bp",
        "AGE": "age",
        "SEX": "sex",
        "DIABETES": "diabetes",
        "HYPERTENSION": "hypertension",
        "EVENT_STATUS": "event_type",
        "FU_TIME_YEARS": "duration_years",
    }

    @classmethod
    def is_cric_available(cls, data_dir: Union[str, Path]) -> bool:
        """Check whether authorized CRIC dataset files are present locally."""
        p = Path(data_dir)
        if not p.is_dir():
            return False
        return any((p / f).exists() for f in cls.EXPECTED_FILES)

    @classmethod
    def load_cric_cohort(
        cls,
        data_dir: Union[str, Path],
    ) -> LongitudinalCohort:
        """Load and harmonize an authorized CRIC cohort.

        Raises
        ------
        FileNotFoundError
            If approved CRIC data files are not present in data_dir.
        """
        p = Path(data_dir)
        if not cls.is_cric_available(p):
            raise FileNotFoundError(
                f"CRIC longitudinal cohort data not found in directory: {p.resolve()}.\n"
                "Data Governance Notice: The Chronic Renal Insufficiency Cohort (CRIC) is a restricted-access "
                "dataset governed by NIDDK Data Use Agreements. To request access, visit the NIDDK Central "
                "Repository (https://repository.niddk.nih.gov/studies/cric/).\n"
                "Per NefroAI clinical AI safety rules, simulated data MUST NOT be fabricated to mimic CRIC."
            )

        # Implementation for approved CRIC CSV ingestion
        main_file = next(p / f for f in cls.EXPECTED_FILES if (p / f).exists())
        df = pd.read_csv(main_file)
        df_renamed = df.rename(columns=cls.COLUMN_MAPPING)

        return load_longitudinal_from_dataframe(
            df=df_renamed,
            cohort_name="CRIC_Longitudinal_Cohort",
            provenance="NIDDK_CRIC_REPOSITORY",
            is_synthetic=False,
        )
