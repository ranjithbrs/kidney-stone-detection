"""NEFROAI-X Clinical Engines Module.

Provides:
- Engine 1: CKD Screening & Binary Classification (pipeline)
- Engine 2: KidneySeverityEngine (KDIGO CGA Staging & Severity Assessment)
- Engine 3: KidneyProgressionEngine (Longitudinal Trajectory & KFRE Progression Prediction)
- Unified: UnifiedAssessmentEngine (Three-Engine Orchestrator)
"""

from src.engines.kidney_progression_engine import (
    ENGINE_3_DISCLAIMER,
    KidneyProgressionEngine,
    ProgressionEngineResult,
)
from src.engines.kidney_severity_engine import KidneySeverityEngine
from src.engines.unified_assessment_engine import (
    UnifiedAssessmentEngine,
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
    "KidneySeverityEngine",
    "KidneyProgressionEngine",
    "ProgressionEngineResult",
    "ENGINE_3_DISCLAIMER",
    "UnifiedAssessmentEngine",
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
]

