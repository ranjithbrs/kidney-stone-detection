"""NEFROAI-X Clinical Assessment Data Contracts.

Defines shared typed dataclasses, enums, and response models for coordinating
the three clinical engines:
- Engine 1: CKD Screening & Binary Classification
- Engine 2: KDIGO CGA Severity Staging
- Engine 3: Longitudinal Progression & KFRE Risk Prediction

Preserves provenance, explicit measurement units, observation timestamps,
and original input values without silent imputation.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from src.clinical.kdigo_staging import CHRONICITY_DISCLAIMER
from src.clinical.kfre_calculator import KFRE_DISCLAIMER, KFRECalibrationProfile, KFREInput
from src.clinical.progression_features import ClinicalObservation, LongitudinalPatientRecord

UNIFIED_ASSESSMENT_DISCLAIMER = (
    "DISCLAIMER: NefroAI-X Unified Clinical Decision Support System (CDSS) is an investigational "
    "research software framework. It integrates screening, severity staging, and longitudinal progression "
    "evaluations for clinical decision support. It does NOT provide definitive medical diagnoses, clinical "
    "trial eligibility determinations, or therapeutic prescriptions. All outputs must be evaluated alongside "
    "comprehensive clinical history and board-certified nephrologist clinical judgment."
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProvenanceSource(str, Enum):
    """Origin and collection modality of patient clinical measurements."""
    CLINICAL_EHR = "CLINICAL_EHR"
    UCI_CKD_SCREENING = "UCI_CKD_SCREENING"
    NHANES_CROSS_SECTIONAL = "NHANES_CROSS_SECTIONAL"
    CRIC_LONGITUDINAL = "CRIC_LONGITUDINAL"
    SYNTHETIC_SIMULATOR = "SYNTHETIC_SIMULATOR"
    SYNTHETIC_DEMONSTRATION = "SYNTHETIC_DEMONSTRATION"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    UNSPECIFIED = "UNSPECIFIED"


class EngineStatus(str, Enum):
    """Operational execution and availability status for individual engines."""
    AVAILABLE = "AVAILABLE"
    PREDICTION_AVAILABLE = "PREDICTION_AVAILABLE"
    INCOMPLETE_INPUT_ESTIMATE = "INCOMPLETE_INPUT_ESTIMATE"
    ABSTAINED = "ABSTAINED"
    DEFERRED = "DEFERRED"
    NOT_REQUESTED = "NOT_REQUESTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REJECTED_INVALID_SCHEMA = "REJECTED_INVALID_SCHEMA"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class FindingSeverity(str, Enum):
    """Clinical significance and alert level for unified findings."""
    INFO = "INFO"
    WARNING = "WARNING"
    DISCREPANCY = "DISCREPANCY"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Input Contracts
# ---------------------------------------------------------------------------

@dataclass
class Demographics:
    """Core patient demographic descriptors."""
    age: Optional[float] = None
    sex: Optional[Union[str, int]] = None  # 'male'/'female', 'M'/'F', or 1/2
    race_ethnicity: Optional[str] = None   # Retained for documentation; CKD-EPI 2021 is race-free
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Engine1ScreeningInput:
    """Input payload for Engine 1 (UCI-trained Random Forest screening model)."""
    biomarkers: Dict[str, Any] = field(default_factory=dict)
    observation_date: Optional[Union[datetime, date, str]] = None
    provenance: str = ProvenanceSource.UNSPECIFIED.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        obs_d = self.observation_date.isoformat() if hasattr(self.observation_date, "isoformat") else self.observation_date
        return {
            "biomarkers": dict(self.biomarkers),
            "observation_date": obs_d,
            "provenance": self.provenance,
            "metadata": dict(self.metadata),
        }


@dataclass
class Engine2SeverityInput:
    """Input payload for Engine 2 (KDIGO CGA Staging & Severity Engine)."""
    serum_creatinine: Optional[float] = None
    serum_creatinine_unit: str = "mg/dL"
    uacr: Optional[float] = None
    uacr_unit: str = "mg/g"
    age: Optional[float] = None
    sex: Optional[Union[str, int]] = None
    observation_date_scr: Optional[Union[datetime, date, str]] = None
    observation_date_uacr: Optional[Union[datetime, date, str]] = None
    cause: str = "UNAVAILABLE_CROSS_SECTIONAL"
    provenance: str = ProvenanceSource.UNSPECIFIED.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d_scr = self.observation_date_scr.isoformat() if hasattr(self.observation_date_scr, "isoformat") else self.observation_date_scr
        d_uacr = self.observation_date_uacr.isoformat() if hasattr(self.observation_date_uacr, "isoformat") else self.observation_date_uacr
        return {
            "serum_creatinine": self.serum_creatinine,
            "serum_creatinine_unit": self.serum_creatinine_unit,
            "uacr": self.uacr,
            "uacr_unit": self.uacr_unit,
            "age": self.age,
            "sex": self.sex,
            "observation_date_scr": d_scr,
            "observation_date_uacr": d_uacr,
            "cause": self.cause,
            "provenance": self.provenance,
            "metadata": dict(self.metadata),
        }


@dataclass
class Engine3ProgressionInput:
    """Input payload for Engine 3 (Longitudinal progression, LMM, and KFRE)."""
    longitudinal_record: Optional[LongitudinalPatientRecord] = None
    landmark_time: Optional[datetime] = None
    kfre_input: Optional[Union[KFREInput, Dict[str, Any]]] = None
    kfre_calibration: str = KFRECalibrationProfile.NON_NORTH_AMERICA.value
    provenance: str = ProvenanceSource.UNSPECIFIED.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        l_time = self.landmark_time.isoformat() if self.landmark_time else None
        k_in = self.kfre_input.to_dict() if hasattr(self.kfre_input, "to_dict") else self.kfre_input
        return {
            "has_longitudinal_record": self.longitudinal_record is not None,
            "landmark_time": l_time,
            "kfre_input": k_in,
            "kfre_calibration": self.kfre_calibration,
            "provenance": self.provenance,
            "metadata": dict(self.metadata),
        }


@dataclass
class PatientAssessmentRequest:
    """Central structured assessment request submitted to UnifiedAssessmentEngine."""
    patient_id: str
    request_id: str = field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:12].upper()}")
    assessment_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    demographics: Optional[Demographics] = None
    engine1_input: Optional[Union[Engine1ScreeningInput, Dict[str, Any]]] = None
    engine2_input: Optional[Union[Engine2SeverityInput, Dict[str, Any]]] = None
    engine3_input: Optional[Union[Engine3ProgressionInput, LongitudinalPatientRecord, Dict[str, Any]]] = None
    requested_engines: Optional[List[str]] = None  # None = auto-detect based on provided inputs
    provenance: str = ProvenanceSource.UNSPECIFIED.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        e1_dict = self.engine1_input.to_dict() if hasattr(self.engine1_input, "to_dict") else self.engine1_input
        e2_dict = self.engine2_input.to_dict() if hasattr(self.engine2_input, "to_dict") else self.engine2_input
        e3_dict = self.engine3_input.to_dict() if hasattr(self.engine3_input, "to_dict") else (
            self.engine3_input.to_dict() if hasattr(self.engine3_input, "to_dict") else self.engine3_input
        )
        return {
            "patient_id": self.patient_id,
            "request_id": self.request_id,
            "assessment_timestamp": self.assessment_timestamp.isoformat(),
            "demographics": self.demographics.to_dict() if self.demographics else None,
            "engine1_input": e1_dict,
            "engine2_input": e2_dict,
            "engine3_input": e3_dict,
            "requested_engines": self.requested_engines,
            "provenance": self.provenance,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Output Contracts
# ---------------------------------------------------------------------------

@dataclass
class Engine1Result:
    """Structured output from Engine 1 (Screening & Binary Classification)."""
    status: str
    diagnostic_class: Optional[int] = None
    diagnosis: Optional[str] = None
    risk_probability: Optional[float] = None
    confidence_score: Optional[float] = None
    risk_category: Optional[str] = None
    abstention_reason: Optional[str] = None
    data_completeness_ratio: float = 0.0
    full_panel_completeness_ratio: float = 0.0
    missing_features: List[str] = field(default_factory=list)
    imputed_features: List[str] = field(default_factory=list)
    feature_anomalies: Dict[str, Any] = field(default_factory=dict)
    feature_attributions: Optional[Dict[str, Any]] = None
    sanitized_inputs: Dict[str, Any] = field(default_factory=dict)
    model_version: str = "1.0.0-champion-rf"
    provenance: str = "UNKNOWN"
    warnings: List[str] = field(default_factory=list)
    # CD-CIRPVM Conformal Reliability & Live TreeSHAP extensions
    clinical_reliability_index: Optional[float] = None
    conformal_set: Optional[List[int]] = None
    conformal_gate_decision: Optional[str] = None
    conformal_gate_status: Optional[str] = None
    conformal_quantile: Optional[float] = None
    conformal_coverage_target: Optional[float] = None
    conformal_calibration_method: Optional[str] = None
    unit_reconciliation_audit: Dict[str, Any] = field(default_factory=dict)
    bounds_clamping_audit: Dict[str, Any] = field(default_factory=dict)
    live_shap_attributions: Optional[Dict[str, Any]] = None
    # Mondrian conformal, Stacking Disagreement & Cross-Analyte Coherence extensions
    mondrian_conformal_set: Optional[List[int]] = None
    mondrian_quantiles: Optional[Dict[str, float]] = None
    stacking_probability: Optional[float] = None
    stacking_base_probabilities: Optional[Dict[str, float]] = None
    ensemble_disagreement_spread: Optional[float] = None
    has_architecture_disagreement: Optional[bool] = None
    coherence_audit: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "diagnostic_class": self.diagnostic_class,
            "diagnosis": self.diagnosis,
            "risk_probability": self.risk_probability,
            "confidence_score": self.confidence_score,
            "risk_category": self.risk_category,
            "abstention_reason": self.abstention_reason,
            "data_completeness_ratio": self.data_completeness_ratio,
            "full_panel_completeness_ratio": self.full_panel_completeness_ratio,
            "missing_features": list(self.missing_features),
            "imputed_features": list(self.imputed_features),
            "feature_anomalies": dict(self.feature_anomalies),
            "feature_attributions": self.feature_attributions,
            "sanitized_inputs": dict(self.sanitized_inputs),
            "model_version": self.model_version,
            "provenance": self.provenance,
            "warnings": list(self.warnings),
            "clinical_reliability_index": self.clinical_reliability_index,
            "conformal_set": list(self.conformal_set) if self.conformal_set is not None else None,
            "conformal_gate_decision": self.conformal_gate_decision,
            "conformal_gate_status": self.conformal_gate_status,
            "conformal_quantile": self.conformal_quantile,
            "conformal_coverage_target": self.conformal_coverage_target,
            "conformal_calibration_method": self.conformal_calibration_method,
            "unit_reconciliation_audit": dict(self.unit_reconciliation_audit),
            "bounds_clamping_audit": dict(self.bounds_clamping_audit),
            "live_shap_attributions": self.live_shap_attributions,
            "mondrian_conformal_set": list(self.mondrian_conformal_set) if self.mondrian_conformal_set is not None else None,
            "mondrian_quantiles": dict(self.mondrian_quantiles) if self.mondrian_quantiles is not None else None,
            "stacking_probability": self.stacking_probability,
            "stacking_base_probabilities": dict(self.stacking_base_probabilities) if self.stacking_base_probabilities is not None else None,
            "ensemble_disagreement_spread": self.ensemble_disagreement_spread,
            "has_architecture_disagreement": self.has_architecture_disagreement,
            "coherence_audit": dict(self.coherence_audit) if self.coherence_audit is not None else None,
        }


@dataclass
class Engine2Result:
    """Structured output from Engine 2 (KDIGO CGA Severity Staging)."""
    status: str
    is_adult: bool = True
    age_evaluated_years: Optional[float] = None
    sex_decoded: Optional[str] = None
    egfr: Optional[float] = None
    egfr_unit: str = "mL/min/1.73m²"
    gfr_category: Optional[str] = None
    gfr_description: Optional[str] = None
    uacr: Optional[float] = None
    uacr_unit: str = "mg/g"
    albuminuria_category: Optional[str] = None
    albuminuria_description: Optional[str] = None
    cga_string: Optional[str] = None
    composite_risk_level: Optional[str] = None
    risk_tier: Optional[str] = None
    risk_color: Optional[str] = None
    is_complete_severity_record: bool = False
    chronicity_confirmed: bool = False
    same_day_measurement: Optional[bool] = None
    observation_date_scr: Optional[str] = None
    observation_date_uacr: Optional[str] = None
    disclaimer: str = CHRONICITY_DISCLAIMER
    warnings: List[str] = field(default_factory=list)
    provenance: str = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_adult": self.is_adult,
            "age_evaluated_years": self.age_evaluated_years,
            "sex_decoded": self.sex_decoded,
            "egfr": self.egfr,
            "egfr_unit": self.egfr_unit,
            "gfr_category": self.gfr_category,
            "gfr_description": self.gfr_description,
            "uacr": self.uacr,
            "uacr_unit": self.uacr_unit,
            "albuminuria_category": self.albuminuria_category,
            "albuminuria_description": self.albuminuria_description,
            "cga_string": self.cga_string,
            "composite_risk_level": self.composite_risk_level,
            "risk_tier": self.risk_tier,
            "risk_color": self.risk_color,
            "is_complete_severity_record": self.is_complete_severity_record,
            "chronicity_confirmed": self.chronicity_confirmed,
            "same_day_measurement": self.same_day_measurement,
            "observation_date_scr": self.observation_date_scr,
            "observation_date_uacr": self.observation_date_uacr,
            "disclaimer": self.disclaimer,
            "warnings": list(self.warnings),
            "provenance": self.provenance,
        }


@dataclass
class Engine3Result:
    """Structured output from Engine 3 (Longitudinal Progression, LMM, and KFRE)."""
    status: str
    is_eligible: bool = False
    should_abstain: bool = False
    abstention_reasons: List[str] = field(default_factory=list)
    historical_egfr_slope: Optional[float] = None
    slope_status: str = "NO_RECORD"
    lmm_annual_slope: Optional[float] = None
    lmm_slope_ci_lower: Optional[float] = None
    lmm_slope_ci_upper: Optional[float] = None
    lmm_status: str = "NO_RECORD"
    kfre_2year_risk: Optional[float] = None
    kfre_5year_risk: Optional[float] = None
    kfre_calibration_profile: Optional[str] = None
    kfre_is_applicable: bool = False
    kfre_applicability_explanation: Optional[str] = None
    survival_status: str = "DEFERRED_PENDING_APPROVED_COHORT"
    survival_predictions: Dict[str, Any] = field(default_factory=dict)
    competing_risk_profile: Dict[str, Any] = field(default_factory=dict)
    clinical_reliability: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    provenance: str = "UNKNOWN"
    chronicity_aki_assessment: Optional[Dict[str, Any]] = None
    trajectory_backtest: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_eligible": self.is_eligible,
            "should_abstain": self.should_abstain,
            "abstention_reasons": list(self.abstention_reasons),
            "historical_egfr_slope": self.historical_egfr_slope,
            "slope_status": self.slope_status,
            "lmm_annual_slope": self.lmm_annual_slope,
            "lmm_slope_ci_lower": self.lmm_slope_ci_lower,
            "lmm_slope_ci_upper": self.lmm_slope_ci_upper,
            "lmm_status": self.lmm_status,
            "kfre_2year_risk": self.kfre_2year_risk,
            "kfre_5year_risk": self.kfre_5year_risk,
            "kfre_calibration_profile": self.kfre_calibration_profile,
            "kfre_is_applicable": self.kfre_is_applicable,
            "kfre_applicability_explanation": self.kfre_applicability_explanation,
            "survival_status": self.survival_status,
            "survival_predictions": dict(self.survival_predictions),
            "competing_risk_profile": dict(self.competing_risk_profile),
            "clinical_reliability": dict(self.clinical_reliability),
            "warnings": list(self.warnings),
            "provenance": self.provenance,
            "chronicity_aki_assessment": dict(self.chronicity_aki_assessment) if self.chronicity_aki_assessment is not None else None,
            "trajectory_backtest": dict(self.trajectory_backtest) if self.trajectory_backtest is not None else None,
        }


@dataclass
class ClinicalDiscrepancy:
    """Documented inconsistency or discordance between engines requiring clinician review."""
    discrepancy_id: str
    title: str
    involved_engines: List[str]
    severity: str  # FindingSeverity
    description: str
    clinical_action: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UnifiedFinding:
    """Key clinical observation, alert, or algorithmic insight assembled by the orchestrator."""
    engine: str
    finding_type: str
    summary: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UnifiedAssessmentResponse:
    """Master integrated clinical response coordinating Engine 1, Engine 2, and Engine 3."""
    assessment_id: str
    patient_id: str
    assessment_timestamp: str
    orchestrator_version: str = "7.0.0-unified"
    engine_versions: Dict[str, str] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    engines_executed: List[str] = field(default_factory=list)
    engines_skipped: Dict[str, str] = field(default_factory=dict)
    overall_completeness: Dict[str, Any] = field(default_factory=dict)
    engine1_result: Optional[Engine1Result] = None
    engine2_result: Optional[Engine2Result] = None
    engine3_result: Optional[Engine3Result] = None
    summary_findings: List[Dict[str, Any]] = field(default_factory=list)
    clinical_discrepancies: List[Dict[str, Any]] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)
    disclaimer: str = UNIFIED_ASSESSMENT_DISCLAIMER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "patient_id": self.patient_id,
            "assessment_timestamp": self.assessment_timestamp,
            "orchestrator_version": self.orchestrator_version,
            "engine_versions": dict(self.engine_versions),
            "provenance": dict(self.provenance),
            "engines_executed": list(self.engines_executed),
            "engines_skipped": dict(self.engines_skipped),
            "overall_completeness": dict(self.overall_completeness),
            "engine1_result": self.engine1_result.to_dict() if self.engine1_result else None,
            "engine2_result": self.engine2_result.to_dict() if self.engine2_result else None,
            "engine3_result": self.engine3_result.to_dict() if self.engine3_result else None,
            "summary_findings": list(self.summary_findings),
            "clinical_discrepancies": list(self.clinical_discrepancies),
            "safety_warnings": list(self.safety_warnings),
            "disclaimer": self.disclaimer,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export serialized unified assessment to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
