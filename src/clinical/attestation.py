"""Safety-Max Clinical Arbitration State Machine & SHA-256 Inference Attestation.

1. `arbitrate_clinical_action(...)`: Non-compensatory clinical escalation graph
   synthesizing Engine 1 (Conformal / Mondrian / Stacking Disagreement), Engine 2
   (KDIGO CGA staging), Engine 3 (AKI-vs-CKD persistence, slope, KFRE), and
   Cross-Analyte Coherence into an actionable escalation tier.
2. `compute_assessment_attestation(...)` & `verify_assessment_attestation(...)`:
   Deterministic SHA-256 cryptographic manifest binding sanitized inputs, model
   artifact hash, calibrated conformal parameters, and multi-engine outputs for
   tamper-evident auditability (without storing PII).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

PROTECTED_MODEL_SHA256 = "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826"


def arbitrate_clinical_action(
    e1: Optional[Any],
    e2: Optional[Any],
    e3: Optional[Any],
    discrepancies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Non-compensatory Safety-Max escalation state machine across all clinical engines."""
    triggers: List[str] = []

    def _get(obj: Any, attr: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    # 1. Pre-inference specimen / coherence failure check
    coh = _get(e1, "coherence_audit") or {}
    if coh.get("specimen_verification_recommended"):
        triggers.append("Cross-analyte physiological contradiction detected (COH check)")
        return {
            "tier": "SPECIMEN_VERIFICATION_REDRAW",
            "urgency_rank": 3,
            "trigger_reasons": triggers,
            "recommended_action": (
                "Verify laboratory transcription and specimen integrity; repeat blood/urine panel before "
                "relying on automated risk screening."
            ),
            "safety_rule_applied": "PRE_INFERENCE_COHERENCE_PRIORITY",
        }

    # 2. High-priority Nephrology Referral triggers (non-compensatory max-risk)
    disc_ids = {d.get("discrepancy_id", "") for d in discrepancies}
    if "DISC-02-FALSE-ASSURANCE-RISK" in disc_ids:
        triggers.append("DISC-02 False Assurance Discordance (Engine 1 Negative vs. Engine 2 Abnormal)")

    gfr_cat = _get(e2, "gfr_category")
    comp_risk = str(_get(e2, "composite_risk_level") or "")
    if gfr_cat in ("G4", "G5") or "Very High" in comp_risk:
        triggers.append(f"KDIGO Advanced/Very High Risk ({_get(e2, 'cga_string') or comp_risk})")

    kfre_2y = _get(e3, "kfre_2year_risk")
    if kfre_2y is not None and float(kfre_2y) >= 0.20:
        triggers.append(f"Elevated 2-year KFRE risk ({float(kfre_2y):.1%} >= 20%)")

    slope = _get(e3, "historical_egfr_slope")
    if slope is not None and float(slope) <= -5.0:
        triggers.append(f"Rapid annualized eGFR decline ({float(slope):+.2f} mL/min/yr)")

    e1_prob = _get(e1, "risk_probability")
    e1_cset = _get(e1, "conformal_set")
    if e1_prob is not None and float(e1_prob) >= 0.80 and e1_cset == [1]:
        triggers.append(f"Decisive Critical CKD Screening Risk ({float(e1_prob):.1%}, C_alpha={{1}})")

    if triggers:
        return {
            "tier": "NEPHROLOGY_REFERRAL_PRIORITY",
            "urgency_rank": 4,
            "trigger_reasons": triggers,
            "recommended_action": (
                "Prioritize specialist nephrology evaluation, repeat confirmatory renal panel, and review "
                "guideline-directed nephroprotective management."
            ),
            "safety_rule_applied": "SAFETY_MAX_CRITICAL_ESCALATION",
        }

    # 3. Clinical Review / Repeat 3-Month Confirmation triggers
    review_triggers: List[str] = []
    aki_info = _get(e3, "chronicity_aki_assessment") or {}
    if aki_info.get("acute_spike_detected"):
        review_triggers.append(f"Acute creatinine velocity spike ({aki_info.get('status')})")

    if _get(e1, "conformal_gate_decision") == "ABSTAIN" or _get(e1, "has_architecture_disagreement"):
        review_triggers.append("Epistemic ambiguity / cross-architecture disagreement or low CRI")

    if "High" in comp_risk or "Moderate" in comp_risk:
        review_triggers.append(f"KDIGO Risk Elevation ({_get(e2, 'cga_string') or comp_risk})")

    if "DISC-03-CROSS-SECTIONAL-CHRONICITY-UNVERIFIED" in disc_ids:
        e2_egfr = _get(e2, "egfr")
        e2_uacr = _get(e2, "uacr")
        has_abn_marker = (
            "Moderate" in comp_risk
            or "High" in comp_risk
            or (e2_egfr is not None and float(e2_egfr) < 60.0)
            or (e2_uacr is not None and float(e2_uacr) >= 30.0)
        )
        if has_abn_marker:
            review_triggers.append("Single-timepoint abnormal renal marker without proven >=90-day chronicity")

    if e1_prob is not None and float(e1_prob) >= 0.50:
        review_triggers.append(f"Elevated screening risk ({float(e1_prob):.1%})")

    if review_triggers:
        return {
            "tier": "REPEAT_CONFIRM_3MO" if not aki_info.get("acute_spike_detected") else "URGENT_ACUTE_EVALUATION",
            "urgency_rank": 2,
            "trigger_reasons": review_triggers,
            "recommended_action": (
                "Order repeat serum creatinine / uACR within 3 months (or urgently if acute creatinine rise) "
                "and obtain physician review."
            ),
            "safety_rule_applied": "UNCERTAINTY_OR_CHRONICITY_CONFIRMATION",
        }

    return {
        "tier": "ROUTINE_MONITORING",
        "urgency_rank": 1,
        "trigger_reasons": ["Concordant low-risk findings across executed engines"],
        "recommended_action": "Continue routine annual wellness and blood pressure/glycemic monitoring.",
        "safety_rule_applied": "CONCORDANT_LOW_RISK",
    }


def _canonical_attestation_payload(response_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Extract deterministic, PII-free payload subset for cryptographic attestation."""
    e1 = response_dict.get("engine1_result") or {}
    e2 = response_dict.get("engine2_result") or {}
    e3 = response_dict.get("engine3_result") or {}
    comp = response_dict.get("overall_completeness") or {}

    return {
        "schema_version": "NEFROAI-X-ATTEST-1.0",
        "assessment_id": response_dict.get("assessment_id"),
        "patient_id": response_dict.get("patient_id"),
        "assessment_timestamp": response_dict.get("assessment_timestamp"),
        "orchestrator_version": response_dict.get("orchestrator_version"),
        "protected_model_sha256": PROTECTED_MODEL_SHA256,
        "engine1": {
            "status": e1.get("status"),
            "diagnostic_class": e1.get("diagnostic_class"),
            "risk_probability": e1.get("risk_probability"),
            "stacking_probability": e1.get("stacking_probability"),
            "clinical_reliability_index": e1.get("clinical_reliability_index"),
            "conformal_set": e1.get("conformal_set"),
            "mondrian_conformal_set": e1.get("mondrian_conformal_set"),
            "conformal_quantile": e1.get("conformal_quantile"),
            "sanitized_inputs": e1.get("sanitized_inputs"),
            "unit_reconciliation_audit": e1.get("unit_reconciliation_audit"),
        },
        "engine2": {
            "status": e2.get("status"),
            "egfr": e2.get("egfr"),
            "uacr": e2.get("uacr"),
            "cga_string": e2.get("cga_string"),
            "composite_risk_level": e2.get("composite_risk_level"),
        },
        "engine3": {
            "status": e3.get("status"),
            "historical_egfr_slope": e3.get("historical_egfr_slope"),
            "kfre_2year_risk": e3.get("kfre_2year_risk"),
            "kfre_5year_risk": e3.get("kfre_5year_risk"),
            "survival_status": e3.get("survival_status"),
        },
        "arbitration_tier": comp.get("arbitration_tier"),
        "discrepancy_ids": [d.get("discrepancy_id") for d in response_dict.get("clinical_discrepancies", [])],
    }


def compute_assessment_attestation(response_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Compute SHA-256 provenance attestation digest for a UnifiedAssessmentResponse dict."""
    canonical = _canonical_attestation_payload(response_dict)
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    return {
        "attestation_sha256": digest,
        "attestation_schema": canonical["schema_version"],
        "protected_model_sha256": PROTECTED_MODEL_SHA256,
    }


def verify_assessment_attestation(response_dict: Dict[str, Any]) -> Tuple[bool, Optional[str], str]:
    """Verify whether an exported JSON assessment matches its embedded SHA-256 attestation."""
    prov = response_dict.get("provenance") or {}
    expected = prov.get("attestation_sha256")
    recomputed = compute_assessment_attestation(response_dict)["attestation_sha256"]
    if not expected:
        return False, None, recomputed
    return (expected == recomputed), expected, recomputed

