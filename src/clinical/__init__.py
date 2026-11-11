"""NEFROAI-X Clinical Calculation & Staging Module.

Provides clinical algorithms for:
- eGFR Calculation (CKD-EPI 2021 race-free creatinine equation)
- KDIGO GFR Categories (G1 to G5)
- KDIGO Albuminuria Categories (A1 to A3)
- KDIGO CGA Staging and Composite Risk Matrix
- Longitudinal Time-Aware Clinical Feature Engineering & Trajectory Metrics (Engine 3)
- Tangri 4-Variable Kidney Failure Risk Equation (KFRE) Reference Implementation
"""

from src.clinical.egfr_calculator import (
    calculate_egfr_ckd_epi_2021,
    calculate_egfr_vectorized,
    decode_sex,
)
from src.clinical.kdigo_staging import (
    ALBUMINURIA_CATEGORIES,
    CHRONICITY_DISCLAIMER,
    GFR_CATEGORIES,
    KDIGO_RISK_MATRIX,
    classify_albuminuria_category,
    classify_gfr_category,
    classify_kdigo_composite_risk,
)
from src.clinical.kfre_calculator import (
    KFRE_BASELINE_SURVIVAL,
    KFRE_DISCLAIMER,
    KFRECalibrationProfile,
    KFREInput,
    KFREResult,
    calculate_kfre,
)
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
    ProgressionAbstention,
    ProgressionFeatureResult,
    ProgressionFeatures,
    extract_progression_features,
    resolve_observation_egfr,
    validate_longitudinal_chronology,
)
from src.clinical.lmm_trajectory import (
    LMMConfig,
    LMMTrajectoryResult,
    LinearMixedEffectsTrajectoryModel,
)
from src.clinical.survival import (
    CoxProportionalHazardsModel,
    RandomSurvivalForestModel,
    SurvivalDataset,
    SurvivalEventType,
    SurvivalLandmarkRecord,
    calculate_aalen_johansen_cif,
    evaluate_survival_model,
    patient_grouped_train_test_split,
)
from src.clinical.conformal_calibrator import (
    ConformalCalibrationResult,
    build_calibrated_reliability_mechanism,
    calibrate_conformal_quantile,
    get_calibrated_conformal_result,
)
from src.clinical.xai_live import (
    LiveTreeSHAPResult,
    compute_live_treeshap,
)
from src.clinical.assessment_contracts import (
    UNIFIED_ASSESSMENT_DISCLAIMER,
    ClinicalDiscrepancy,
    Demographics,
    Engine1Result,
    Engine1ScreeningInput,
    Engine2Result,
    Engine2SeverityInput,
    Engine3ProgressionInput,
    Engine3Result,
    EngineStatus,
    FindingSeverity,
    PatientAssessmentRequest,
    ProvenanceSource,
    UnifiedAssessmentResponse,
    UnifiedFinding,
)

__all__ = [
    "calculate_egfr_ckd_epi_2021",
    "calculate_egfr_vectorized",
    "decode_sex",
    "classify_gfr_category",
    "classify_albuminuria_category",
    "classify_kdigo_composite_risk",
    "GFR_CATEGORIES",
    "ALBUMINURIA_CATEGORIES",
    "KDIGO_RISK_MATRIX",
    "CHRONICITY_DISCLAIMER",
    "ClinicalObservation",
    "LongitudinalPatientRecord",
    "ProgressionFeatures",
    "ProgressionAbstention",
    "ProgressionFeatureResult",
    "extract_progression_features",
    "validate_longitudinal_chronology",
    "resolve_observation_egfr",
    "KFRECalibrationProfile",
    "KFREInput",
    "KFREResult",
    "calculate_kfre",
    "KFRE_BASELINE_SURVIVAL",
    "KFRE_DISCLAIMER",
    "LMMConfig",
    "LMMTrajectoryResult",
    "LinearMixedEffectsTrajectoryModel",
    "SurvivalEventType",
    "SurvivalLandmarkRecord",
    "SurvivalDataset",
    "patient_grouped_train_test_split",
    "CoxProportionalHazardsModel",
    "RandomSurvivalForestModel",
    "calculate_aalen_johansen_cif",
    "evaluate_survival_model",
    "UNIFIED_ASSESSMENT_DISCLAIMER",
    "PatientAssessmentRequest",
    "UnifiedAssessmentResponse",
    "Engine1ScreeningInput",
    "Engine2SeverityInput",
    "Engine3ProgressionInput",
    "Engine1Result",
    "Engine2Result",
    "Engine3Result",
    "Demographics",
    "ClinicalDiscrepancy",
    "UnifiedFinding",
    "ProvenanceSource",
    "EngineStatus",
    "FindingSeverity",
    "ConformalCalibrationResult",
    "calibrate_conformal_quantile",
    "get_calibrated_conformal_result",
    "build_calibrated_reliability_mechanism",
    "LiveTreeSHAPResult",
    "compute_live_treeshap",
]
