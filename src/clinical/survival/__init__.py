"""Survival Analysis & Progression Risk Modelling Subpackage for Engine 3.

Provides:
- Validated survival dataset contracts and landmark record structures
- Competing-risk data pathways and event representations (Aalen-Johansen CIF)
- Interpretable cause-specific Cox Proportional Hazards baseline
- Random Survival Forest (RSF) candidate interface
- Fine-Gray status, blocker documentation, and data preparation
- Time-dependent survival evaluation and KFRE comparison framework
"""

from src.clinical.survival.survival_contracts import (
    SurvivalEventType,
    SurvivalLandmarkRecord,
    SurvivalDataset,
    SurvivalDataValidationError,
    patient_grouped_train_test_split,
    temporal_cohort_split,
)
from src.clinical.survival.cox_model import (
    CoxProportionalHazardsModel,
    CoxPHConfig,
    CoxCoefficientResult,
    SurvivalModelError,
)
from src.clinical.survival.rsf_model import (
    RandomSurvivalForestModel,
    RSFConfig,
)
from src.clinical.survival.competing_risk import (
    CumulativeIncidenceResult,
    calculate_aalen_johansen_cif,
    prepare_fine_gray_dataframe,
    DeferredFineGrayEstimator,
    FineGrayDependencyUnavailableError,
    CauseSpecificCIFPrediction,
    CauseSpecificCumulativeIncidenceModel,
)
from src.clinical.survival.evaluation import (
    CalibrationGroup,
    TimeDependentEvaluationResult,
    calculate_harrell_c_index,
    calculate_uno_c_index,
    calculate_time_dependent_auc,
    calculate_brier_score_at_horizon,
    calculate_calibration_by_quantiles,
    calculate_cause_specific_calibration_by_quantiles,
    calculate_competing_risk_calibration_by_quantiles,
    calculate_cause_specific_calibration_slope_and_intercept,
    calculate_competing_risk_calibration_slope_and_intercept,
    evaluate_survival_model,
    compare_models_with_kfre_on_cohort,
)

__all__ = [
    # Contracts
    "SurvivalEventType",
    "SurvivalLandmarkRecord",
    "SurvivalDataset",
    "SurvivalDataValidationError",
    "patient_grouped_train_test_split",
    "temporal_cohort_split",
    # Cox PH
    "CoxProportionalHazardsModel",
    "CoxPHConfig",
    "CoxCoefficientResult",
    "SurvivalModelError",
    # RSF
    "RandomSurvivalForestModel",
    "RSFConfig",
    # Competing Risk
    "CumulativeIncidenceResult",
    "calculate_aalen_johansen_cif",
    "prepare_fine_gray_dataframe",
    "DeferredFineGrayEstimator",
    "FineGrayDependencyUnavailableError",
    "CauseSpecificCIFPrediction",
    "CauseSpecificCumulativeIncidenceModel",
    # Evaluation
    "CalibrationGroup",
    "TimeDependentEvaluationResult",
    "calculate_harrell_c_index",
    "calculate_uno_c_index",
    "calculate_time_dependent_auc",
    "calculate_brier_score_at_horizon",
    "calculate_calibration_by_quantiles",
    "calculate_cause_specific_calibration_by_quantiles",
    "calculate_competing_risk_calibration_by_quantiles",
    "calculate_cause_specific_calibration_slope_and_intercept",
    "calculate_competing_risk_calibration_slope_and_intercept",
    "evaluate_survival_model",
    "compare_models_with_kfre_on_cohort",
]
