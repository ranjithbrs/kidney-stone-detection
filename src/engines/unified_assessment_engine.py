"""NEFROAI-X Unified Clinical Assessment Engine (Orchestrator).

Coordinates the three independent clinical engines:
- Engine 1: CKD Screening and Binary Classification (UCI Champion Model)
- Engine 2: Kidney Disease Severity Staging (KDIGO CGA 2024 Framework)
- Engine 3: Longitudinal Progression & KFRE Risk Prediction

Maintains engine independence, safe abstention, transparent discrepancy detection,
and strict data provenance with zero silent imputation.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

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
from src.clinical.attestation import (
    arbitrate_clinical_action,
    compute_assessment_attestation,
)
from src.clinical.coherence_verifier import verify_cross_analyte_coherence
from src.clinical.conformal_calibrator import (
    ConformalCalibrationResult,
    build_calibrated_reliability_mechanism,
    evaluate_consensus_cirpvm,
    evaluate_mondrian_prediction_set,
    get_calibrated_mondrian_result,
)
from src.clinical.kdigo_staging import CHRONICITY_DISCLAIMER
from src.clinical.kfre_calculator import KFRE_DISCLAIMER, KFRECalibrationProfile, KFREInput
from src.clinical.progression_features import (
    ClinicalObservation,
    LongitudinalPatientRecord,
)
from src.clinical.stacking_ensemble import get_stacking_ensemble
from src.clinical.xai_live import compute_live_treeshap
from src.clinical_input_reliability_mechanism import ClinicalInputReliabilityMechanism
from src.engines.kidney_progression_engine import (
    ENGINE_3_DISCLAIMER,
    KidneyProgressionEngine,
    ProgressionEngineResult,
)
from src.engines.kidney_severity_engine import KidneySeverityEngine

logger = logging.getLogger("nefroai.engines.unified_assessment_engine")


class UnifiedAssessmentEngine:
    """Central orchestration layer coordinating Engine 1, Engine 2, and Engine 3.

    Enforces:
    1. Independent engine execution (failure or abstention in one never suppresses others).
    2. Strict input validation with zero silent imputation of clinical measurements.
    3. Transparent cross-engine discrepancy reporting (preferring disagreement over forced consensus).
    4. Model loading efficiency via memory caching of the production pipeline.
    5. Complete traceability of provenance and timestamps.
    """

    orchestrator_name: str = "NEFROAI-X Unified Assessment Orchestrator"
    orchestrator_version: str = "7.0.0-unified"
    disclaimer: str = UNIFIED_ASSESSMENT_DISCLAIMER

    # Class-level cache for production diagnostic pipeline
    _cached_pipeline: Optional[Any] = None

    def __init__(
        self,
        pipeline: Optional[Any] = None,
        severity_engine: Optional[KidneySeverityEngine] = None,
        progression_engine: Optional[KidneyProgressionEngine] = None,
        pipeline_path: str = "models/clinical_pipeline.joblib",
        reliability_mechanism: Optional[ClinicalInputReliabilityMechanism] = None,
    ) -> None:
        self.pipeline_path = pipeline_path
        self._pipeline = pipeline
        self.severity_engine = severity_engine or KidneySeverityEngine()
        self.progression_engine = progression_engine or KidneyProgressionEngine()
        if reliability_mechanism is not None:
            self.reliability_mechanism = reliability_mechanism
            self.conformal_calibration: Optional[ConformalCalibrationResult] = None
        else:
            self.reliability_mechanism, self.conformal_calibration = build_calibrated_reliability_mechanism()

    def get_pipeline(self) -> Optional[Any]:
        """Retrieve or lazily load the production diagnostic pipeline."""
        if self._pipeline is not None:
            return self._pipeline

        if UnifiedAssessmentEngine._cached_pipeline is not None:
            self._pipeline = UnifiedAssessmentEngine._cached_pipeline
            return self._pipeline

        if os.path.exists(self.pipeline_path):
            try:
                # Ensure pickle aliases exist for models serialized from src/
                import src.pipeline as _pipe_mod
                import src.preprocessing as _prep_mod
                sys.modules.setdefault("pipeline", _pipe_mod)
                sys.modules.setdefault("preprocessing", _prep_mod)

                from src.pipeline import KidneyDiagnosticPipeline
                loaded = KidneyDiagnosticPipeline.load(self.pipeline_path)
                UnifiedAssessmentEngine._cached_pipeline = loaded
                self._pipeline = loaded
                logger.info("Successfully loaded production pipeline from %s", self.pipeline_path)
                return self._pipeline
            except Exception as ex:
                logger.warning("Failed to load production pipeline from %s: %s", self.pipeline_path, ex)
                return None
        return None

    # -----------------------------------------------------------------------
    # Main Orchestration Entry Point
    # -----------------------------------------------------------------------

    def assess_patient(
        self,
        request: Union[PatientAssessmentRequest, Dict[str, Any]],
    ) -> UnifiedAssessmentResponse:
        """Execute a comprehensive, coordinated clinical assessment.

        Parameters
        ----------
        request : Union[PatientAssessmentRequest, Dict[str, Any]]
            Structured request or dictionary representing patient data.

        Returns
        -------
        UnifiedAssessmentResponse
            Coordinated assessment with individual engine outputs, cross-engine
            discrepancy analysis, and safety warnings.
        """
        # 1. Normalize request
        norm_req = self._normalize_request(request)

        # 2. Determine target engines
        engines_to_run = self._determine_engines_to_execute(norm_req)

        engines_executed: List[str] = []
        engines_skipped: Dict[str, str] = {}
        safety_warnings: List[str] = []
        summary_findings: List[Dict[str, Any]] = []

        # 3. Execute Engine 1 (Screening)
        e1_result: Optional[Engine1Result] = None
        if "engine1" in engines_to_run:
            try:
                e1_result, e1_warnings = self._execute_engine1(norm_req)
                engines_executed.append("engine1")
                safety_warnings.extend(e1_warnings)
                if e1_result.diagnosis:
                    summary_findings.append(
                        UnifiedFinding(
                            engine="Engine 1 (Screening)",
                            finding_type="DIAGNOSTIC_RISK",
                            summary=f"{e1_result.diagnosis} ({e1_result.risk_category})",
                            detail=f"Predicted Risk Probability: {e1_result.risk_probability:.1%}" if e1_result.risk_probability is not None else "Screening prediction withheld",
                        ).to_dict()
                    )
            except Exception as ex:
                logger.error("Engine 1 unexpected execution failure: %s", ex, exc_info=True)
                e1_result = Engine1Result(
                    status=EngineStatus.EXECUTION_ERROR.value,
                    diagnosis="EXECUTION_ERROR",
                    abstention_reason=f"Engine 1 failed with unexpected exception: {ex}",
                    warnings=[str(ex)],
                )
                engines_executed.append("engine1")
                safety_warnings.append(f"Engine 1 execution error: {ex}")
        else:
            engines_skipped["engine1"] = self._explain_skip_reason("engine1", norm_req)

        # 4. Execute Engine 2 (Severity / Staging)
        e2_result: Optional[Engine2Result] = None
        if "engine2" in engines_to_run:
            try:
                e2_result, e2_warnings = self._execute_engine2(norm_req)
                engines_executed.append("engine2")
                safety_warnings.extend(e2_warnings)
                if e2_result.cga_string:
                    summary_findings.append(
                        UnifiedFinding(
                            engine="Engine 2 (Severity)",
                            finding_type="KDIGO_CGA_STAGING",
                            summary=f"KDIGO Stage: {e2_result.cga_string} ({e2_result.composite_risk_level})",
                            detail=f"eGFR: {e2_result.egfr:.1f} mL/min/1.73m² ({e2_result.gfr_category}), uACR: {e2_result.uacr} mg/g ({e2_result.albuminuria_category})" if e2_result.egfr is not None else "Incomplete severity panel",
                        ).to_dict()
                    )
            except Exception as ex:
                logger.error("Engine 2 unexpected execution failure: %s", ex, exc_info=True)
                e2_result = Engine2Result(
                    status=EngineStatus.EXECUTION_ERROR.value,
                    warnings=[str(ex)],
                )
                engines_executed.append("engine2")
                safety_warnings.append(f"Engine 2 execution error: {ex}")
        else:
            engines_skipped["engine2"] = self._explain_skip_reason("engine2", norm_req)

        # 5. Execute Engine 3 (Progression / KFRE)
        e3_result: Optional[Engine3Result] = None
        if "engine3" in engines_to_run:
            try:
                e3_result, e3_warnings = self._execute_engine3(norm_req)
                engines_executed.append("engine3")
                safety_warnings.extend(e3_warnings)
                if e3_result.historical_egfr_slope is not None:
                    summary_findings.append(
                        UnifiedFinding(
                            engine="Engine 3 (Progression)",
                            finding_type="LONGITUDINAL_TRAJECTORY",
                            summary=f"Historical eGFR Slope: {e3_result.historical_egfr_slope:+.2f} mL/min/1.73m²/yr ({e3_result.slope_status})",
                            detail=f"LMM BLUP Random Slope: {e3_result.lmm_annual_slope:+.2f} mL/min/1.73m²/yr" if e3_result.lmm_annual_slope is not None else "OLS trajectory evaluated",
                        ).to_dict()
                    )
                if e3_result.kfre_2year_risk is not None:
                    summary_findings.append(
                        UnifiedFinding(
                            engine="Engine 3 (Progression)",
                            finding_type="KFRE_RISK",
                            summary=f"KFRE Kidney Failure Risk: 2-yr = {e3_result.kfre_2year_risk:.1%}, 5-yr = {e3_result.kfre_5year_risk:.1%}",
                            detail=f"Calibration: {e3_result.kfre_calibration_profile} (Applicable: {e3_result.kfre_is_applicable})",
                        ).to_dict()
                    )
            except Exception as ex:
                logger.error("Engine 3 unexpected execution failure: %s", ex, exc_info=True)
                e3_result = Engine3Result(
                    status=EngineStatus.EXECUTION_ERROR.value,
                    warnings=[str(ex)],
                )
                engines_executed.append("engine3")
                safety_warnings.append(f"Engine 3 execution error: {ex}")
        else:
            engines_skipped["engine3"] = self._explain_skip_reason("engine3", norm_req)

        # 5b. Cross-Engine Analyte Coherence Check (Dipstick al vs Quantitative uACR)
        if e1_result is not None and e2_result is not None and e2_result.uacr is not None and e1_result.sanitized_inputs:
            full_coh = verify_cross_analyte_coherence(e1_result.sanitized_inputs, uacr_mg_g=e2_result.uacr)
            e1_result.coherence_audit = full_coh.to_dict()
            if not full_coh.is_coherent and e1_result.clinical_reliability_index is not None:
                e1_result.clinical_reliability_index = max(
                    0.0, round(e1_result.clinical_reliability_index - full_coh.total_cri_penalty, 2)
                )

        # 6. Evaluate Cross-Engine Consistency & Discrepancies
        discrepancies, disc_warnings = self._evaluate_cross_engine_discrepancies(
            e1_result, e2_result, e3_result, norm_req
        )
        safety_warnings.extend(disc_warnings)

        # 6b. Safety-Max Clinical Arbitration State Machine
        arbitration = arbitrate_clinical_action(e1_result, e2_result, e3_result, discrepancies)

        # 7. Compute Assessment Completeness
        all_possible = ["engine1", "engine2", "engine3"]
        completeness = {
            "requested_engines": norm_req.requested_engines or all_possible,
            "executed_count": len(engines_executed),
            "total_available_engines": len(all_possible),
            "completeness_ratio": round(len(engines_executed) / len(all_possible), 2),
            "has_critical_discrepancies": any(d["severity"] == FindingSeverity.CRITICAL.value for d in discrepancies),
            "status": "COMPLETE" if len(engines_executed) == len(all_possible) else ("PARTIAL" if engines_executed else "INSUFFICIENT"),
            "arbitration_tier": arbitration["tier"],
            "arbitration_detail": arbitration,
        }

        # 8. Record Engine Versions
        pipeline_obj = self.get_pipeline()
        e1_ver = getattr(pipeline_obj, "version", "1.0.0-champion-rf") if pipeline_obj else "UNAVAILABLE"
        engine_versions = {
            "orchestrator": self.orchestrator_version,
            "engine1_screening": e1_ver,
            "engine2_severity": getattr(self.severity_engine, "version", "2.0.0"),
            "engine3_progression": getattr(self.progression_engine, "version", "3.0.0"),
        }

        response = UnifiedAssessmentResponse(
            assessment_id=norm_req.request_id,
            patient_id=norm_req.patient_id,
            assessment_timestamp=norm_req.assessment_timestamp.isoformat(),
            orchestrator_version=self.orchestrator_version,
            engine_versions=engine_versions,
            provenance={
                "source": norm_req.provenance,
                "metadata": dict(norm_req.metadata),
            },
            engines_executed=engines_executed,
            engines_skipped=engines_skipped,
            overall_completeness=completeness,
            engine1_result=e1_result,
            engine2_result=e2_result,
            engine3_result=e3_result,
            summary_findings=summary_findings,
            clinical_discrepancies=discrepancies,
            safety_warnings=safety_warnings,
            disclaimer=self.disclaimer,
        )
        attest = compute_assessment_attestation(response.to_dict())
        response.provenance.update(attest)
        return response

    # -----------------------------------------------------------------------
    # Request Normalization
    # -----------------------------------------------------------------------

    def _normalize_request(
        self,
        request: Union[PatientAssessmentRequest, Dict[str, Any]],
    ) -> PatientAssessmentRequest:
        """Standardize incoming input dictionary or dataclass into a typed request."""
        if isinstance(request, PatientAssessmentRequest):
            return request

        if not isinstance(request, dict):
            raise ValueError(f"Expected PatientAssessmentRequest or dict, got {type(request).__name__}")

        pt_id = str(request.get("patient_id", request.get("SEQN", request.get("id", "ANONYMOUS"))))
        req_id = str(request.get("request_id", f"REQ-{os.urandom(6).hex().upper()}"))
        ts = request.get("assessment_timestamp")
        if isinstance(ts, str):
            try:
                dt_ts = datetime.fromisoformat(ts)
            except Exception:
                dt_ts = datetime.now(timezone.utc)
        elif isinstance(ts, datetime):
            dt_ts = ts
        else:
            dt_ts = datetime.now(timezone.utc)

        # Demographics
        demo = None
        if "demographics" in request and isinstance(request["demographics"], dict):
            demo = Demographics(**request["demographics"])
        elif any(k in request for k in ("age", "sex", "gender", "RIDAGEYR", "RIAGENDR")):
            demo = Demographics(
                age=request.get("age", request.get("RIDAGEYR")),
                sex=request.get("sex", request.get("gender", request.get("RIAGENDR"))),
            )

        # Engine 1 input
        e1_in = None
        if "engine1_input" in request:
            if isinstance(request["engine1_input"], Engine1ScreeningInput):
                e1_in = request["engine1_input"]
            elif isinstance(request["engine1_input"], dict):
                e1_in = Engine1ScreeningInput(**request["engine1_input"])
        else:
            # Check if top-level dictionary has screening biomarkers
            # e.g., 'sc', 'hemo', 'al', 'sg', 'pcv', 'rc', 'bgr', 'bu', etc.
            screening_keys = {
                "sc", "al", "hemo", "sg", "pcv", "rc", "bu", "bgr", "htn", "dm",
                "bp", "sod", "pot", "wc", "su", "age", "cad", "pe", "ane", "appet"
            }
            overlap = set(request.keys()) & screening_keys
            if overlap:
                e1_in = Engine1ScreeningInput(
                    biomarkers={k: request[k] for k in overlap},
                    observation_date=request.get("observation_date", request.get("date")),
                    provenance=request.get("provenance", ProvenanceSource.UNSPECIFIED.value),
                )

        # Engine 2 input
        e2_in = None
        if "engine2_input" in request:
            if isinstance(request["engine2_input"], Engine2SeverityInput):
                e2_in = request["engine2_input"]
            elif isinstance(request["engine2_input"], dict):
                e2_in = Engine2SeverityInput(**request["engine2_input"])
        else:
            # Check for severity parameters at top-level
            scr_val = request.get("serum_creatinine", request.get("sc", request.get("LBXSCR")))
            uacr_val = request.get("uacr", request.get("URDACT", request.get("uacr_mg_g")))
            age_val = request.get("age", request.get("RIDAGEYR", request.get("age_years")))
            sex_val = request.get("sex", request.get("RIAGENDR", request.get("sex_code")))
            if scr_val is not None or uacr_val is not None:
                e2_in = Engine2SeverityInput(
                    serum_creatinine=float(scr_val) if scr_val is not None and str(scr_val).strip() != "" else None,
                    serum_creatinine_unit=request.get("serum_creatinine_unit", "mg/dL"),
                    uacr=float(uacr_val) if uacr_val is not None and str(uacr_val).strip() != "" else None,
                    uacr_unit=request.get("uacr_unit", "mg/g"),
                    age=float(age_val) if age_val is not None else None,
                    sex=sex_val,
                    observation_date_scr=request.get("observation_date_scr", request.get("date_scr", request.get("observation_date"))),
                    observation_date_uacr=request.get("observation_date_uacr", request.get("date_uacr", request.get("observation_date"))),
                    cause=request.get("cause", "UNAVAILABLE_CROSS_SECTIONAL"),
                    provenance=request.get("provenance", ProvenanceSource.UNSPECIFIED.value),
                )

        # Engine 3 input
        e3_in = None
        if "engine3_input" in request:
            if isinstance(request["engine3_input"], Engine3ProgressionInput):
                e3_in = request["engine3_input"]
            elif isinstance(request["engine3_input"], LongitudinalPatientRecord):
                e3_in = Engine3ProgressionInput(longitudinal_record=request["engine3_input"])
            elif isinstance(request["engine3_input"], dict):
                e3_in = Engine3ProgressionInput(**request["engine3_input"])
        elif "longitudinal_record" in request:
            e3_in = Engine3ProgressionInput(
                longitudinal_record=request["longitudinal_record"],
                landmark_time=request.get("landmark_time"),
                kfre_input=request.get("kfre_input"),
                kfre_calibration=request.get("kfre_calibration", KFRECalibrationProfile.NON_NORTH_AMERICA.value),
            )
        elif "visits" in request and isinstance(request["visits"], list):
            # Convert list of visit dicts or ClinicalObservations to LongitudinalPatientRecord
            obs_list = []
            for v in request["visits"]:
                if isinstance(v, ClinicalObservation):
                    obs_list.append(v)
                elif isinstance(v, dict):
                    v_dict = dict(v)
                    if "timestamp" not in v_dict:
                        t_val = v_dict.pop("observation_date", v_dict.pop("date", None))
                        if isinstance(t_val, str):
                            t_val = datetime.fromisoformat(t_val)
                        elif not isinstance(t_val, datetime):
                            t_val = datetime.now(timezone.utc)
                        v_dict["timestamp"] = t_val
                    valid_keys = {
                        "timestamp", "serum_creatinine", "egfr", "uacr",
                        "systolic_bp", "diastolic_bp", "hba1c", "serum_glucose", "notes"
                    }
                    filtered = {k: v_dict[k] for k in v_dict if k in valid_keys}
                    obs_list.append(ClinicalObservation(**filtered))

            age_base = float(request.get("age_baseline", request.get("age", demo.age if demo and demo.age else 60.0)))
            sex_base = str(request.get("sex", demo.sex if demo and demo.sex else "male"))
            e3_in = Engine3ProgressionInput(
                longitudinal_record=LongitudinalPatientRecord(
                    patient_id=pt_id,
                    age_baseline=age_base,
                    sex=sex_base,
                    observations=obs_list,
                    provenance=request.get("provenance", ProvenanceSource.UNSPECIFIED.value),
                ),
                landmark_time=request.get("landmark_time"),
                kfre_input=request.get("kfre_input"),
                kfre_calibration=request.get("kfre_calibration", KFRECalibrationProfile.NON_NORTH_AMERICA.value),
            )
        elif "kfre_input" in request:
            e3_in = Engine3ProgressionInput(
                kfre_input=request["kfre_input"],
                kfre_calibration=request.get("kfre_calibration", KFRECalibrationProfile.NON_NORTH_AMERICA.value),
            )

        return PatientAssessmentRequest(
            patient_id=pt_id,
            request_id=req_id,
            assessment_timestamp=dt_ts,
            demographics=demo,
            engine1_input=e1_in,
            engine2_input=e2_in,
            engine3_input=e3_in,
            requested_engines=request.get("requested_engines"),
            provenance=request.get("provenance", ProvenanceSource.UNSPECIFIED.value),
            metadata=dict(request.get("metadata", {})),
        )

    def _determine_engines_to_execute(self, request: PatientAssessmentRequest) -> List[str]:
        """Determine which engines have sufficient inputs and should be run."""
        if request.requested_engines is not None:
            return list(request.requested_engines)

        # Auto-detect based on input presence
        to_run = []
        if request.engine1_input is not None:
            b = request.engine1_input.biomarkers if hasattr(request.engine1_input, "biomarkers") else (
                request.engine1_input.get("biomarkers", request.engine1_input) if isinstance(request.engine1_input, dict) else {}
            )
            if b:
                to_run.append("engine1")

        if request.engine2_input is not None:
            to_run.append("engine2")

        if request.engine3_input is not None:
            to_run.append("engine3")

        return to_run

    def _explain_skip_reason(self, engine_key: str, request: PatientAssessmentRequest) -> str:
        """Provide a clear clinical reason why an engine was not executed."""
        if request.requested_engines is not None and engine_key not in request.requested_engines:
            return f"Engine '{engine_key}' was omitted from the explicit requested_engines list."

        if engine_key == "engine1":
            return "No screening biomarker inputs provided (requires routine urinalysis and hematology panel)."
        elif engine_key == "engine2":
            return "No severity staging inputs provided (requires serum creatinine, age, and sex for eGFR; uACR for albuminuria)."
        elif engine_key == "engine3":
            return "No longitudinal history or index KFRE input provided (requires repeated observations or KFRE parameters)."
        return "Not requested or insufficient data."

    # -----------------------------------------------------------------------
    # Engine 1 Execution
    # -----------------------------------------------------------------------

    def _execute_engine1(self, request: PatientAssessmentRequest) -> Tuple[Engine1Result, List[str]]:
        """Invoke Engine 1 (Screening Model) with provenance tracking and safe abstention."""
        warnings: List[str] = []
        pipeline_obj = self.get_pipeline()

        if pipeline_obj is None:
            return Engine1Result(
                status=EngineStatus.DEFERRED.value,
                diagnosis="UNAVAILABLE_MODEL_ARTIFACT",
                abstention_reason=f"Pipeline model artifact could not be loaded from: {self.pipeline_path}",
                warnings=["Production model artifact missing or failed to unpickle."],
            ), ["Engine 1 model artifact unavailable."]

        e1_in = request.engine1_input
        if e1_in is None:
            return Engine1Result(
                status=EngineStatus.INSUFFICIENT_DATA.value,
                diagnosis="INSUFFICIENT_INPUTS",
                abstention_reason="No biomarkers provided to Engine 1.",
            ), []

        raw_biomarkers = e1_in.biomarkers if hasattr(e1_in, "biomarkers") else (
            e1_in.get("biomarkers", e1_in) if isinstance(e1_in, dict) else {}
        )

        # Forward demographics if available and not already in biomarkers
        if request.demographics:
            if "age" not in raw_biomarkers and request.demographics.age is not None:
                raw_biomarkers["age"] = request.demographics.age

        # Execute prediction
        pred_dict = pipeline_obj.predict_single(raw_biomarkers, include_attributions=True)

        status_str = pred_dict.get("prediction_status", EngineStatus.AVAILABLE.value)
        diag = pred_dict.get("diagnosis")
        diag_class = pred_dict.get("diagnostic_class")
        risk_prob = pred_dict.get("risk_probability")
        conf = pred_dict.get("confidence_score")
        risk_cat = pred_dict.get("risk_category")
        abstain_rsn = pred_dict.get("abstention_reason")
        data_comp = float(pred_dict.get("data_completeness_ratio", 0.0))
        full_comp = float(pred_dict.get("full_panel_completeness_ratio", 0.0))
        missing_feats = pred_dict.get("missing_features", [])
        imputed_feats = pred_dict.get("imputed_features", [])
        anomalies = pred_dict.get("feature_anomalies", {})
        attributions = pred_dict.get("feature_attributions")
        sanitized = pred_dict.get("sanitized_inputs", {})

        # Generate warnings
        if abstain_rsn:
            warnings.append(f"Engine 1 Abstention: {abstain_rsn}")
        if imputed_feats:
            warnings.append(f"Engine 1 Imputation: Non-critical features {imputed_feats} imputed with training medians.")
        for feat, anom in anomalies.items():
            if anom.get("status") == "OUT_OF_DOMAIN":
                warnings.append(f"Engine 1 Out-of-Domain Feature [{feat}]: {anom.get('reason')}")

        # Execute CD-CIRPVM reliability scoring, MIDR unit audit, and conformal prediction set gate
        rel_info = self._evaluate_engine1_reliability(raw_biomarkers, pred_dict, pipeline_obj)
        if rel_info["conformal_gate_decision"] == "ABSTAIN" and risk_prob is not None:
            warnings.append(
                f"CD-CIRPVM Conformal Gate Abstention ({rel_info['conformal_gate_status']}): "
                f"CRI={rel_info['clinical_reliability_index']:.2f}, "
                f"Conformal Set={rel_info['conformal_set']}, "
                f"q_95={rel_info['conformal_quantile']:.3f}."
            )

        result = Engine1Result(
            status=status_str,
            diagnostic_class=diag_class,
            diagnosis=diag,
            risk_probability=risk_prob,
            confidence_score=conf,
            risk_category=risk_cat,
            abstention_reason=abstain_rsn,
            data_completeness_ratio=data_comp,
            full_panel_completeness_ratio=full_comp,
            missing_features=missing_feats,
            imputed_features=imputed_feats,
            feature_anomalies=anomalies,
            feature_attributions=attributions,
            sanitized_inputs=sanitized,
            model_version=getattr(pipeline_obj, "version", "1.0.0-champion-rf"),
            provenance=getattr(e1_in, "provenance", request.provenance),
            warnings=warnings,
            clinical_reliability_index=rel_info["clinical_reliability_index"],
            conformal_set=rel_info["conformal_set"],
            conformal_gate_decision=rel_info["conformal_gate_decision"],
            conformal_gate_status=rel_info["conformal_gate_status"],
            conformal_quantile=rel_info["conformal_quantile"],
            conformal_coverage_target=rel_info["conformal_coverage_target"],
            conformal_calibration_method=rel_info["conformal_calibration_method"],
            unit_reconciliation_audit=rel_info["unit_reconciliation_audit"],
            bounds_clamping_audit=rel_info["bounds_clamping_audit"],
            live_shap_attributions=rel_info["live_shap_attributions"],
            mondrian_conformal_set=rel_info["mondrian_conformal_set"],
            mondrian_quantiles=rel_info["mondrian_quantiles"],
            stacking_probability=rel_info["stacking_probability"],
            stacking_base_probabilities=rel_info["stacking_base_probabilities"],
            ensemble_disagreement_spread=rel_info["ensemble_disagreement_spread"],
            has_architecture_disagreement=rel_info["has_architecture_disagreement"],
            coherence_audit=rel_info["coherence_audit"],
        )
        return result, warnings

    def _evaluate_engine1_reliability(
        self,
        raw_biomarkers: Dict[str, Any],
        pred_dict: Dict[str, Any],
        pipeline_obj: Any,
    ) -> Dict[str, Any]:
        """Compute CD-CIRPVM CRI, Mondrian set, Stacking disagreement, Coherence & live TreeSHAP."""
        selected_feats = list(getattr(pipeline_obj, "selected_features", [
            "hemo", "sg", "pcv", "rc", "al", "htn", "sc", "bu", "dm", "bgr"
        ]))
        risk_prob = pred_dict.get("risk_probability")
        cal_method = (
            self.conformal_calibration.calibration_method
            if self.conformal_calibration is not None
            else "configured_quantile"
        )

        rel = evaluate_consensus_cirpvm(
            raw_biomarkers=raw_biomarkers,
            reliability_mechanism=self.reliability_mechanism,
            selected_features=selected_feats,
            risk_probability=risk_prob,
            prediction_status=pred_dict.get("prediction_status", "PREDICTION_AVAILABLE"),
            sanitized_from_pipe=pred_dict.get("sanitized_inputs", {}),
            feature_anomalies=pred_dict.get("feature_anomalies", {}),
            calibration_method=cal_method,
        )

        # Cross-analyte physiological coherence verification on sanitized inputs
        sanitized_inputs = pred_dict.get("sanitized_inputs", {})
        coh_res = verify_cross_analyte_coherence(sanitized_inputs if sanitized_inputs else raw_biomarkers)
        rel["coherence_audit"] = coh_res.to_dict()
        if not coh_res.is_coherent:
            rel["clinical_reliability_index"] = max(
                0.0, round(rel["clinical_reliability_index"] - coh_res.total_cri_penalty, 2)
            )

        # Mondrian Class-Conditional Conformal Set
        try:
            mondrian_cal = get_calibrated_mondrian_result()
            rel["mondrian_conformal_set"] = evaluate_mondrian_prediction_set(risk_prob, mondrian_cal)
            rel["mondrian_quantiles"] = {
                "q_healthy": mondrian_cal.q_healthy,
                "q_ckd": mondrian_cal.q_ckd,
            }
        except Exception as ex:
            logger.warning("Mondrian conformal evaluation skipped: %s", ex)
            rel["mondrian_conformal_set"] = None
            rel["mondrian_quantiles"] = None

        # 4-Family Stacking Ensemble Cross-Architecture Disagreement (for real pipeline predictions)
        rel["stacking_probability"] = None
        rel["stacking_base_probabilities"] = None
        rel["ensemble_disagreement_spread"] = None
        rel["has_architecture_disagreement"] = None
        if risk_prob is not None and hasattr(pipeline_obj, "model") and hasattr(pipeline_obj, "preprocessor"):
            try:
                stack_ens = get_stacking_ensemble()
                merged_for_stack = dict(raw_biomarkers)
                merged_for_stack.update(sanitized_inputs)
                stack_out = stack_ens.predict_with_disagreement(merged_for_stack)
                rel["stacking_probability"] = stack_out["stacking_probability"]
                rel["stacking_base_probabilities"] = stack_out["base_probabilities"]
                rel["ensemble_disagreement_spread"] = stack_out["disagreement_spread"]
                rel["has_architecture_disagreement"] = stack_out["has_architecture_disagreement"]
            except Exception as ex:
                logger.warning("Stacking disagreement evaluation skipped: %s", ex)

        # Compute exact game-theoretic TreeSHAP attributions if prediction is available
        live_shap = None
        if risk_prob is not None:
            try:
                shap_res = compute_live_treeshap(pipeline_obj, raw_biomarkers)
                if shap_res is not None:
                    live_shap = shap_res.to_dict()
            except Exception as ex:
                logger.warning("Live TreeSHAP computation skipped: %s", ex)

        rel["live_shap_attributions"] = live_shap
        return rel

    # -----------------------------------------------------------------------
    # Engine 2 Execution
    # -----------------------------------------------------------------------

    def _execute_engine2(self, request: PatientAssessmentRequest) -> Tuple[Engine2Result, List[str]]:
        """Invoke Engine 2 (KDIGO Severity Staging) with unit validation and chronicity disclaimers."""
        warnings: List[str] = []
        e2_in = request.engine2_input

        if e2_in is None:
            return Engine2Result(
                status=EngineStatus.INSUFFICIENT_DATA.value,
                warnings=["No severity staging input payload provided."],
            ), []

        # Prepare record for KidneySeverityEngine
        if hasattr(e2_in, "to_dict"):
            in_dict = e2_in.to_dict()
        elif isinstance(e2_in, dict):
            in_dict = dict(e2_in)
        else:
            in_dict = {}

        # Resolve demographics fallback
        if request.demographics:
            if in_dict.get("age") is None and request.demographics.age is not None:
                in_dict["age"] = request.demographics.age
            if in_dict.get("sex") is None and request.demographics.sex is not None:
                in_dict["sex"] = request.demographics.sex

        # Handle unit conversion if units are explicitly non-standard
        scr_val = in_dict.get("serum_creatinine")
        scr_unit = str(in_dict.get("serum_creatinine_unit", "mg/dL")).lower()
        if scr_val is not None:
            if scr_unit in ["µmol/l", "umol/l", "micromol/l"]:
                # 1 mg/dL = 88.42 µmol/L
                converted_scr = round(float(scr_val) / 88.42, 3)
                warnings.append(f"Engine 2 Unit Conversion: Serum creatinine converted from {scr_val} µmol/L to {converted_scr} mg/dL.")
                in_dict["serum_creatinine"] = converted_scr
            elif scr_unit not in ["mg/dl", "mg/dl.", ""]:
                warnings.append(f"Engine 2 Unit Warning: Unrecognized creatinine unit '{scr_unit}'; proceeding under standard mg/dL assumption.")

        uacr_val = in_dict.get("uacr")
        uacr_unit = str(in_dict.get("uacr_unit", "mg/g")).lower()
        if uacr_val is not None:
            if uacr_unit in ["mg/mmol"]:
                # 1 mg/mmol ≈ 8.84 mg/g
                converted_uacr = round(float(uacr_val) * 8.84, 1)
                warnings.append(f"Engine 2 Unit Conversion: uACR converted from {uacr_val} mg/mmol to {converted_uacr} mg/g.")
                in_dict["uacr"] = converted_uacr

        # Execute Engine 2 assessment
        raw_e2 = self.severity_engine.assess_patient(in_dict)

        filt = raw_e2.get("filtration_assessment", {})
        alb = raw_e2.get("albuminuria_assessment", {})
        cga = raw_e2.get("kdigo_cga_staging", {})
        gov = raw_e2.get("clinical_governance", {})

        # Observation date checking for concurrency
        d_scr = in_dict.get("observation_date_scr")
        d_uacr = in_dict.get("observation_date_uacr")
        same_day: Optional[bool] = None

        if d_scr and d_uacr:
            try:
                dt_scr = datetime.fromisoformat(str(d_scr)) if isinstance(d_scr, str) else d_scr
                dt_uacr = datetime.fromisoformat(str(d_uacr)) if isinstance(d_uacr, str) else d_uacr
                date_scr = dt_scr.date() if hasattr(dt_scr, "date") else dt_scr
                date_uacr = dt_uacr.date() if hasattr(dt_uacr, "date") else dt_uacr
                days_diff = abs((date_scr - date_uacr).days)
                if days_diff == 0:
                    same_day = True
                else:
                    same_day = False
                    if days_diff > 30:
                        warnings.append(
                            f"Engine 2 Temporal Discrepancy: Serum creatinine ({d_scr}) and uACR ({d_uacr}) "
                            f"were observed {days_diff} days apart (>30 days). KDIGO CGA risk assumes concurrent assessment."
                        )
            except Exception:
                same_day = (str(d_scr).split("T")[0] == str(d_uacr).split("T")[0])

        # Missing input warnings
        if filt.get("egfr") is None:
            warnings.append(f"Engine 2 Filtration Warning: {filt.get('message', 'eGFR calculation unavailable')}")
        if alb.get("uacr") is None:
            warnings.append(f"Engine 2 Albuminuria Warning: {alb.get('message', 'uACR measurement unavailable')}")

        status_str = EngineStatus.AVAILABLE.value if gov.get("is_complete_severity_record") else EngineStatus.INCOMPLETE_INPUT_ESTIMATE.value

        result = Engine2Result(
            status=status_str,
            is_adult=bool(raw_e2.get("is_adult", True)),
            age_evaluated_years=raw_e2.get("age_evaluated_years"),
            sex_decoded=raw_e2.get("sex_decoded"),
            egfr=filt.get("egfr"),
            egfr_unit=filt.get("unit", "mL/min/1.73m²"),
            gfr_category=filt.get("gfr_category"),
            gfr_description=filt.get("gfr_description"),
            uacr=alb.get("uacr"),
            uacr_unit=alb.get("unit", "mg/g"),
            albuminuria_category=alb.get("albuminuria_category"),
            albuminuria_description=alb.get("albuminuria_description"),
            cga_string=cga.get("cga_string"),
            composite_risk_level=cga.get("composite_risk_level"),
            risk_tier=cga.get("risk_tier"),
            risk_color=cga.get("risk_color"),
            is_complete_severity_record=bool(gov.get("is_complete_severity_record", False)),
            chronicity_confirmed=bool(gov.get("chronicity_confirmed", False)),
            same_day_measurement=same_day,
            observation_date_scr=str(d_scr) if d_scr else None,
            observation_date_uacr=str(d_uacr) if d_uacr else None,
            disclaimer=gov.get("disclaimer", CHRONICITY_DISCLAIMER),
            warnings=warnings,
            provenance=getattr(e2_in, "provenance", request.provenance),
        )
        return result, warnings

    # -----------------------------------------------------------------------
    # Engine 3 Execution
    # -----------------------------------------------------------------------

    def _execute_engine3(self, request: PatientAssessmentRequest) -> Tuple[Engine3Result, List[str]]:
        """Invoke Engine 3 (Longitudinal Progression & KFRE) with survival gating."""
        warnings: List[str] = []
        e3_in = request.engine3_input

        if e3_in is None:
            return Engine3Result(
                status=EngineStatus.INSUFFICIENT_DATA.value,
                warnings=["No longitudinal progression or KFRE inputs provided."],
            ), []

        rec = e3_in.longitudinal_record if hasattr(e3_in, "longitudinal_record") else None
        l_time = e3_in.landmark_time if hasattr(e3_in, "landmark_time") else None
        k_in = e3_in.kfre_input if hasattr(e3_in, "kfre_input") else None
        k_calib = getattr(e3_in, "kfre_calibration", KFRECalibrationProfile.NON_NORTH_AMERICA.value)

        # Fallback: if KFRE input not explicitly provided, attempt to derive from demographics & Engine 2 input
        if k_in is None and request.engine2_input is not None:
            e2 = request.engine2_input
            scr_val = getattr(e2, "serum_creatinine", None) if hasattr(e2, "serum_creatinine") else e2.get("serum_creatinine")
            uacr_val = getattr(e2, "uacr", None) if hasattr(e2, "uacr") else e2.get("uacr")
            age_val = getattr(e2, "age", None) if hasattr(e2, "age") else e2.get("age")
            sex_val = getattr(e2, "sex", None) if hasattr(e2, "sex") else e2.get("sex")

            if request.demographics:
                age_val = age_val or request.demographics.age
                sex_val = sex_val or request.demographics.sex

            if scr_val is not None and uacr_val is not None and age_val is not None and sex_val is not None:
                # Compute eGFR for KFRE input
                from src.clinical.egfr_calculator import calculate_egfr_ckd_epi_2021
                egfr_res = calculate_egfr_ckd_epi_2021(serum_creatinine=scr_val, age=age_val, sex=sex_val)
                if egfr_res["is_valid"] and egfr_res["egfr"] is not None:
                    k_in = KFREInput(
                        age=float(age_val),
                        sex=str(sex_val),
                        egfr=float(egfr_res["egfr"]),
                        uacr=float(uacr_val),
                        calibration_profile=k_calib,
                    )
                    warnings.append("Engine 3 KFRE Derived: Auto-constructed KFRE input from demographics and Engine 2 laboratory values.")

        # Execute Engine 3 orchestrator
        raw_res: ProgressionEngineResult = self.progression_engine.assess_progression(
            record=rec,
            landmark_time=l_time,
            kfre_input=k_in,
            kfre_calibration=k_calib,
        )

        status_str = EngineStatus.AVAILABLE.value
        if raw_res.should_abstain:
            status_str = EngineStatus.ABSTAINED.value
            for rsn in raw_res.abstention_reasons:
                warnings.append(f"Engine 3 Abstention: {rsn}")

        # Extract KFRE metrics
        k_2y = None
        k_5y = None
        k_profile = None
        k_app = False
        k_exp = None
        if raw_res.kfre_result is not None:
            k_2y = raw_res.kfre_result.risk_2year
            k_5y = raw_res.kfre_result.risk_5year
            k_profile = raw_res.kfre_result.calibration_profile
            k_app = raw_res.kfre_result.is_applicable
            k_exp = raw_res.kfre_applicability_explanation
            if not k_app:
                warnings.append(f"Engine 3 KFRE Applicability Warning: {k_exp}")

        # Extract LMM metrics
        lmm_slope = None
        lmm_ci_l = None
        lmm_ci_u = None
        lmm_stat = "NO_RECORD"
        if raw_res.lmm_trajectory is not None:
            lmm_slope = raw_res.lmm_trajectory.patient_slope
            lmm_ci_l = raw_res.lmm_trajectory.slope_ci_lower
            lmm_ci_u = raw_res.lmm_trajectory.slope_ci_upper
            lmm_stat = raw_res.lmm_trajectory.status
            if not raw_res.lmm_trajectory.is_eligible:
                warnings.append(f"Engine 3 LMM Note: Patient has {raw_res.lmm_trajectory.obs_count} observations; minimum required is 3.")

        # Survival model gating verification:
        # Since CRIC cohort data is unavailable, trained models must be withheld.
        surv_preds = dict(raw_res.survival_predictions)
        surv_stat = surv_preds.get("status", "DEFERRED_PENDING_APPROVED_COHORT")
        if surv_stat == "RESEARCH_SOFTWARE_INTERFACE":
            surv_stat = "DEFERRED_PENDING_APPROVED_COHORT"

        result = Engine3Result(
            status=status_str,
            is_eligible=bool(raw_res.longitudinal_result.is_eligible) if raw_res.longitudinal_result else False,
            should_abstain=raw_res.should_abstain,
            abstention_reasons=list(raw_res.abstention_reasons),
            historical_egfr_slope=raw_res.historical_egfr_slope,
            slope_status=raw_res.slope_status,
            lmm_annual_slope=lmm_slope,
            lmm_slope_ci_lower=lmm_ci_l,
            lmm_slope_ci_upper=lmm_ci_u,
            lmm_status=lmm_stat,
            kfre_2year_risk=k_2y,
            kfre_5year_risk=k_5y,
            kfre_calibration_profile=k_profile,
            kfre_is_applicable=k_app,
            kfre_applicability_explanation=k_exp,
            survival_status=surv_stat,
            survival_predictions=surv_preds,
            competing_risk_profile=dict(raw_res.competing_risk_profile),
            clinical_reliability=dict(raw_res.clinical_reliability),
            warnings=warnings,
            provenance=raw_res.provenance,
            chronicity_aki_assessment=raw_res.progression_explanations.get("chronicity_aki_assessment"),
            trajectory_backtest=raw_res.progression_explanations.get("trajectory_backtest"),
        )
        return result, warnings

    # -----------------------------------------------------------------------
    # Cross-Engine Discrepancy & Consistency Analysis
    # -----------------------------------------------------------------------

    def _evaluate_cross_engine_discrepancies(
        self,
        e1: Optional[Engine1Result],
        e2: Optional[Engine2Result],
        e3: Optional[Engine3Result],
        request: PatientAssessmentRequest,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Identify, categorize, and document clinically critical discrepancies across engines."""
        discrepancies: List[ClinicalDiscrepancy] = []
        warnings: List[str] = []

        # DISCREPANCY 1: Engine 1 Screening Positive, but Engine 2 Severity Unavailable
        if e1 is not None and e1.diagnostic_class == 1:
            if e2 is None or e2.status in [EngineStatus.INSUFFICIENT_DATA.value, EngineStatus.EXECUTION_ERROR.value] or (e2.egfr is None and e2.uacr is None):
                d = ClinicalDiscrepancy(
                    discrepancy_id="DISC-01-SCREENING-POSITIVE-NO-STAGING",
                    title="Screening Positive Without Staging Confirmation",
                    involved_engines=["Engine 1 (Screening)", "Engine 2 (Severity)"],
                    severity=FindingSeverity.WARNING.value,
                    description=(
                        "Engine 1 screening model classified the patient as High-Risk CKD, "
                        "but quantitative KDIGO staging data (eGFR and uACR) is currently unavailable."
                    ),
                    clinical_action="Order serum creatinine, eGFR, and spot urine albumin-to-creatinine ratio (uACR) for formal KDIGO staging.",
                )
                discrepancies.append(d)
                warnings.append(f"Cross-Engine Discrepancy: {d.title} - {d.description}")

        # DISCREPANCY 2: Engine 1 Screening Negative, but Engine 2 Reports Concerning Biomarkers (False Assurance Risk)
        if e1 is not None and e1.diagnostic_class == 0 and e2 is not None:
            egfr_low = e2.egfr is not None and e2.egfr < 60.0
            uacr_high = e2.uacr is not None and e2.uacr >= 30.0
            if egfr_low or uacr_high:
                abnormal_findings = []
                if egfr_low:
                    abnormal_findings.append(f"reduced eGFR ({e2.egfr:.1f} mL/min/1.73m², {e2.gfr_category})")
                if uacr_high:
                    abnormal_findings.append(f"elevated uACR ({e2.uacr:.1f} mg/g, {e2.albuminuria_category})")

                d = ClinicalDiscrepancy(
                    discrepancy_id="DISC-02-FALSE-ASSURANCE-RISK",
                    title="Screening-Staging Discordance (False Assurance Risk)",
                    involved_engines=["Engine 1 (Screening)", "Engine 2 (Severity)"],
                    severity=FindingSeverity.CRITICAL.value,
                    description=(
                        f"Engine 1 binary screening model classified the patient as Healthy (Class 0, risk {e1.risk_probability:.1%}), "
                        f"yet Engine 2 demonstrates clinically significant renal abnormalities: {', '.join(abnormal_findings)}. "
                        "Binary screening relies on routine panel heuristics and may fail to detect isolated renal pathology."
                    ),
                    clinical_action=(
                        "DO NOT rely on the negative binary screening prediction. Defer to laboratory KDIGO CGA "
                        "staging, perform repeat testing, and initiate clinical nephrology evaluation."
                    ),
                )
                discrepancies.append(d)
                warnings.append(f"CRITICAL Cross-Engine Discordance: {d.title} - {d.description}")

        # DISCREPANCY 3: Engine 2 Valid Cross-Sectional Staging, but Engine 3 Insufficient Longitudinal History
        if e2 is not None and e2.is_complete_severity_record:
            if e3 is None or not e3.is_eligible or e3.historical_egfr_slope is None:
                d = ClinicalDiscrepancy(
                    discrepancy_id="DISC-03-CROSS-SECTIONAL-CHRONICITY-UNVERIFIED",
                    title="Single-Timepoint Staging Without Proven Chronicity",
                    involved_engines=["Engine 2 (Severity)", "Engine 3 (Progression)"],
                    severity=FindingSeverity.WARNING.value,
                    description=(
                        "Engine 2 demonstrates abnormal renal biomarkers from a single cross-sectional examination, "
                        "but Engine 3 longitudinal history is insufficient (<2 visits spanning >=90 days) to prove "
                        "chronicity or compute filtration trajectory."
                    ),
                    clinical_action=(
                        "Repeat serum creatinine and uACR in 3 months to distinguish true Chronic Kidney Disease "
                        "from resolving Acute Kidney Injury (AKI) or transient albuminuria."
                    ),
                )
                discrepancies.append(d)
                warnings.append(f"Cross-Engine Caveat: {d.title} - {d.description}")

        # DISCREPANCY 4: Engine 3 Longitudinal Features Available, but Survival Models Blocked
        if e3 is not None and e3.historical_egfr_slope is not None:
            if "DEFERRED" in str(e3.survival_status) or "UNFITTED" in str(e3.survival_status):
                d = ClinicalDiscrepancy(
                    discrepancy_id="DISC-04-SURVIVAL-MODEL-DEFERRED",
                    title="Longitudinal Trajectory Available; Cohort Survival Model Withheld",
                    involved_engines=["Engine 3 (Progression)"],
                    severity=FindingSeverity.INFO.value,
                    description=(
                        f"Individual historical eGFR trajectory ({e3.historical_egfr_slope:+.2f} mL/min/1.73m²/yr) "
                        "was computed, but cohort survival model predictions (Cox PH, Random Survival Forest) are "
                        "withheld because CRIC cohort data has not been ingested under an approved Data Use Agreement."
                    ),
                    clinical_action="Use Tangri KFRE reference equation and LMM trajectory for risk stratification.",
                )
                discrepancies.append(d)

        # DISCREPANCY 5: KFRE Applicability Range Boundary Violation
        if e3 is not None and not e3.kfre_is_applicable and e3.kfre_applicability_explanation:
            d = ClinicalDiscrepancy(
                discrepancy_id="DISC-05-KFRE-OUT-OF-APPLICABILITY",
                title="KFRE Applicability Domain Boundary Warning",
                involved_engines=["Engine 3 (Progression)"],
                severity=FindingSeverity.WARNING.value,
                description=(
                    f"Tangri KFRE was requested or evaluated, but inputs fall outside its validated target domain: "
                    f"{e3.kfre_applicability_explanation}. KFRE is validated exclusively for CKD stages G3-G5 (eGFR < 60 mL/min/1.73m²)."
                ),
                clinical_action="Interpret KFRE applicability status cautiously; risk is withheld for early-stage CKD (G1/G2).",
            )
            discrepancies.append(d)
            warnings.append(f"KFRE Applicability Alert: {d.description}")

        # DISCREPANCY 6: Non-Concurrent Staging Measurements
        if e2 is not None and e2.same_day_measurement is False:
            d = ClinicalDiscrepancy(
                discrepancy_id="DISC-06-NON-CONCURRENT-STAGING",
                title="Non-Concurrent Staging Biomarkers",
                involved_engines=["Engine 2 (Severity)"],
                severity=FindingSeverity.WARNING.value,
                description=(
                    f"Serum creatinine ({e2.observation_date_scr}) and uACR ({e2.observation_date_uacr}) "
                    "were collected on different dates. Staging assumes concurrent measurements."
                ),
                clinical_action="Obtain concurrent repeat measurements to confirm synchronized filtration and albuminuria status.",
            )
            discrepancies.append(d)

        # DISCREPANCY 7: Clinical History Conflict (Hypertension or Diabetes)
        if e1 is not None:
            raw_b = {}
            if request.engine1_input is not None:
                raw_b = request.engine1_input.biomarkers if hasattr(request.engine1_input, "biomarkers") else (
                    request.engine1_input.get("biomarkers", request.engine1_input) if isinstance(request.engine1_input, dict) else {}
                )
            htn_hist = str(e1.sanitized_inputs.get("htn", raw_b.get("htn", ""))).lower()
            bp_val = raw_b.get("bp", e1.sanitized_inputs.get("bp"))
            if htn_hist in ["no", "0", "absent"] and bp_val is not None:
                try:
                    if float(bp_val) >= 140.0:
                        d = ClinicalDiscrepancy(
                            discrepancy_id="DISC-07-HYPERTENSION-HISTORY-CONFLICT",
                            title="Hypertension History vs Measurement Conflict",
                            involved_engines=["Engine 1 (Screening)"],
                            severity=FindingSeverity.WARNING.value,
                            description=(
                                f"Patient history records no hypertension (htn='{htn_hist}'), "
                                f"but measured systolic blood pressure is elevated ({bp_val} mmHg >= 140 mmHg)."
                            ),
                            clinical_action="Verify blood pressure measurement technique and assess for undiagnosed hypertension.",
                        )
                        discrepancies.append(d)
                except (ValueError, TypeError):
                    pass

        # DISCREPANCY 8: CD-CIRPVM Conformal Reliability Gate Abstention
        if e1 is not None and e1.risk_probability is not None and e1.conformal_gate_decision == "ABSTAIN":
            d = ClinicalDiscrepancy(
                discrepancy_id="DISC-08-CONFORMAL-RELIABILITY-GATE",
                title="CD-CIRPVM Conformal Reliability Gate Advises Abstention",
                involved_engines=["Engine 1 (Screening)", "CD-CIRPVM Safety Gate"],
                severity=FindingSeverity.WARNING.value,
                description=(
                    f"Engine 1 produced a point risk estimate ({e1.risk_probability:.1%}), but the CD-CIRPVM "
                    f"verification gate triggered '{e1.conformal_gate_status}' "
                    f"(CRI={e1.clinical_reliability_index:.2f}, Conformal Set C_95={e1.conformal_set})."
                ),
                clinical_action=(
                    "Treat the binary screening point estimate as uncertain/inconclusive. "
                    "Verify missing or boundary laboratory measurements and rely on KDIGO staging and physician review."
                ),
            )
            discrepancies.append(d)
            warnings.append(f"CD-CIRPVM Safety Gate Alert: {d.description}")

        # DISCREPANCY 9: Cross-Analyte Physiological Coherence Alert
        if e1 is not None and e1.coherence_audit and not e1.coherence_audit.get("is_coherent", True):
            coh_findings = e1.coherence_audit.get("findings", [])
            titles = "; ".join(f.get("title", "Coherence anomaly") for f in coh_findings)
            has_crit = any(f.get("severity") == "CRITICAL" for f in coh_findings)
            d = ClinicalDiscrepancy(
                discrepancy_id="DISC-09-CROSS-ANALYTE-COHERENCE-ALERT",
                title="Cross-Analyte Physiological Invariant Contradiction",
                involved_engines=["Engine 1 (Screening)", "Cross-Analyte Coherence Verifier"],
                severity=FindingSeverity.CRITICAL.value if has_crit else FindingSeverity.WARNING.value,
                description=f"Multi-biomarker physiological consistency check flagged anomalies: {titles}",
                clinical_action=(
                    "Verify specimen integrity, rule out hemolysis/clerical transcription error, "
                    "and repeat confirmatory lab draw before clinical action."
                ),
            )
            discrepancies.append(d)
            warnings.append(f"Cross-Analyte Coherence Alert: {titles}")

        # DISCREPANCY 10: Ensemble Architecture Disagreement or Acute Creatinine Velocity Spike
        disagree_reasons = []
        if e1 is not None and e1.has_architecture_disagreement:
            disagree_reasons.append(
                f"Stacking base learners (RF/XGB/SVM/MLP) diverged (spread={e1.ensemble_disagreement_spread:.2f})"
            )
        if e3 is not None and e3.chronicity_aki_assessment and e3.chronicity_aki_assessment.get("acute_spike_detected"):
            disagree_reasons.append(e3.chronicity_aki_assessment.get("summary", "Acute creatinine spike detected"))

        if disagree_reasons:
            d = ClinicalDiscrepancy(
                discrepancy_id="DISC-10-ENSEMBLE-DISAGREEMENT-OR-ACUTE-SPIKE",
                title="Cross-Architecture Disagreement or Acute Velocity Alert",
                involved_engines=["Stacking Ensemble", "Engine 3 (Temporal Velocity)"],
                severity=FindingSeverity.WARNING.value,
                description=" | ".join(disagree_reasons),
                clinical_action="Review individual model probabilities and rule out acute transient kidney injury (AKI).",
            )
            discrepancies.append(d)
            warnings.append(f"DISC-10 Alert: {d.description}")

        return [d.to_dict() for d in discrepancies], warnings
