#!/usr/bin/env python3
"""
NEFROAI-X Container Health & Engine Verification Script
========================================================
Purpose: Verify that all three clinical engines, model loading, and report
         export are functional inside the Docker container.

Run inside the container:
    python scripts/verify_container.py

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.

This script does NOT start a Streamlit server. It tests the backend
programmatically. The Streamlit health endpoint is verified separately
by the Docker HEALTHCHECK directive (curl to /_stcore/health).
"""

from __future__ import annotations

import sys
import os
import hashlib
import traceback
import datetime

# Ensure src/ and project root are importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "src")
for p in (SRC, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

PASS_SYM = "  [PASS]"
FAIL_SYM = "  [FAIL]"
results: list[tuple[bool, str, str]] = []


def check(name: str, fn) -> None:
    try:
        msg = fn()
        results.append((True, name, msg or ""))
        print(f"{PASS_SYM} {name}" + (f" — {msg}" if msg else ""))
    except Exception as exc:
        results.append((False, name, str(exc)))
        print(f"{FAIL_SYM} {name} — {exc}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# 1. Python runtime version
# ---------------------------------------------------------------------------
def chk_python() -> str:
    v = sys.version_info
    assert v.major == 3 and v.minor == 10, \
        f"Expected Python 3.10, got {v.major}.{v.minor}.{v.micro}"
    return f"Python {v.major}.{v.minor}.{v.micro}"

check("Python 3.10 runtime", chk_python)


# ---------------------------------------------------------------------------
# 2. Protected asset SHA-256 hashes
# ---------------------------------------------------------------------------
PROTECTED_HASHES = {
    "models/clinical_pipeline.joblib":
        "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826",
    "datasets/clinical/dataset_A_uci_ckd.csv":
        "147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc",
    "models/preprocessor_Dataset_A.joblib":
        "fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3",
    "src/clinical_input_reliability_mechanism.py":
        "f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0",
}

def chk_hashes() -> str:
    ok = []
    for rel, expected in PROTECTED_HASHES.items():
        path = os.path.join(ROOT, rel)
        with open(path, "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()
        assert got == expected, f"Hash mismatch on {rel}:\n  got:      {got}\n  expected: {expected}"
        ok.append(os.path.basename(rel))
    return f"verified {len(ok)} assets: {', '.join(ok)}"

check("Protected asset SHA-256 hashes", chk_hashes)


# ---------------------------------------------------------------------------
# 3. Core clinical library imports
# ---------------------------------------------------------------------------
def chk_imports() -> str:
    import numpy
    import pandas
    import sklearn
    import shap
    import lifelines
    import reportlab
    return (
        f"numpy={numpy.__version__} sklearn={sklearn.__version__} "
        f"shap={shap.__version__} lifelines={lifelines.__version__} "
        f"reportlab={reportlab.Version}"
    )

check("Core clinical library imports", chk_imports)


# ---------------------------------------------------------------------------
# 4. Engine 1 — CKD Screening: model load and predict_single
# ---------------------------------------------------------------------------
def chk_engine1() -> str:
    import joblib
    # Register legacy module alias required by the pickle-serialised artifact
    import pipeline as _pipe_mod
    sys.modules.setdefault("pipeline", _pipe_mod)

    pipe = joblib.load(os.path.join(ROOT, "models/clinical_pipeline.joblib"))
    assert pipe is not None, "Pipeline is None after load"

    # Minimal valid 10-feature consensus sample
    sample = {
        "hemo": 13.0,   # Haemoglobin g/dL
        "sg":   1.020,  # Specific Gravity
        "pcv":  40.0,   # Packed Cell Volume %
        "rc":   4.5,    # Red Blood Cell count M/mcL
        "al":   1,      # Albumin dipstick grade
        "htn":  "no",   # Hypertension
        "sc":   1.2,    # Serum Creatinine mg/dL
        "bu":   35.0,   # Blood Urea mg/dL
        "dm":   "no",   # Diabetes Mellitus
        "bgr":  110.0,  # Blood Glucose Random mg/dL
    }
    result = pipe.predict_single(sample)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "diagnosis" in result, f"Missing 'diagnosis' key; keys: {list(result)}"
    assert "risk_probability" in result, "Missing 'risk_probability' key"

    prob = result["risk_probability"]
    diag = result["diagnosis"]
    return f"diagnosis='{diag}' risk_probability={prob:.3f}"

check("Engine 1 — model load and predict_single", chk_engine1)


# ---------------------------------------------------------------------------
# 5. Engine 2 — eGFR calculator and KDIGO staging
# ---------------------------------------------------------------------------
def chk_engine2() -> str:
    from clinical.egfr_calculator import calculate_egfr_ckd_epi_2021
    from clinical.kdigo_staging import classify_gfr_category, classify_albuminuria_category

    egfr_res = calculate_egfr_ckd_epi_2021(
        serum_creatinine=1.2, age=55, sex="male"
    )
    assert isinstance(egfr_res, dict)
    egfr = egfr_res.get("egfr")
    assert egfr is not None and egfr > 0, f"eGFR must be positive, got {egfr}"

    gfr_cat = classify_gfr_category(egfr)
    assert isinstance(gfr_cat, dict)
    assert "category" in gfr_cat, f"Expected 'category' in gfr result, got {list(gfr_cat)}"

    alb_cat = classify_albuminuria_category(uacr=30.0)
    assert isinstance(alb_cat, dict)

    return (
        f"eGFR={egfr:.1f} mL/min/1.73m² "
        f"GFR-cat={gfr_cat.get('category', '?')} "
        f"Albumin-cat={alb_cat.get('category', '?')}"
    )

check("Engine 2 — eGFR + KDIGO staging", chk_engine2)


# ---------------------------------------------------------------------------
# 6. Engine 3 — KFRE calculator
# ---------------------------------------------------------------------------
def chk_engine3() -> str:
    from clinical.kfre_calculator import calculate_kfre

    result = calculate_kfre(
        egfr=25.0,
        uacr=300.0,
        age=60,
        sex="male",
        calibration_profile="north_america",
    )
    assert result is not None, "calculate_kfre returned None"
    assert result.is_applicable, \
        f"KFRE should be applicable for eGFR=25; got is_applicable={result.is_applicable}"
    assert 0.0 < result.risk_2year < 1.0, \
        f"KFRE 2yr risk out of range: {result.risk_2year}"

    return (
        f"KFRE 2yr={result.risk_2year:.3f} "
        f"5yr={result.risk_5year:.3f} "
        f"applicable={result.is_applicable}"
    )

check("Engine 3 — KFRE calculator", chk_engine3)


# ---------------------------------------------------------------------------
# 7. CD-CIRPVM — Clinical Input Reliability Mechanism
# ---------------------------------------------------------------------------
def chk_cirpvm() -> str:
    from clinical_input_reliability_mechanism import ClinicalInputReliabilityMechanism

    cirpvm = ClinicalInputReliabilityMechanism()
    public_methods = [m for m in dir(cirpvm) if not m.startswith("_")]
    assert len(public_methods) > 0, "CIRPVM has no public methods"

    # Verify core public method exists
    assert hasattr(cirpvm, "sanitize_and_score_reliability"), \
        f"Expected 'sanitize_and_score_reliability'; available: {public_methods}"

    sample = {
        "hemo": 13.0, "sg": 1.020, "pcv": 40.0, "rc": 4.5,
        "al": 1, "htn": "no", "sc": 1.2, "bu": 35.0,
        "dm": "no", "bgr": 110.0,
    }
    sanitized, cri_score, anomalies, missing_cnt = cirpvm.sanitize_and_score_reliability(sample)
    assert isinstance(cri_score, float), f"Expected float CRI, got {type(cri_score)}"
    assert 0.0 <= cri_score <= 1.0, f"CRI out of bounds: {cri_score}"

    return f"CRI score={cri_score:.2f}, missing={missing_cnt}, sanitized_keys={len(sanitized)}"

check("CD-CIRPVM — reliability mechanism", chk_cirpvm)


# ---------------------------------------------------------------------------
# 8. Report export — text report using proper assessment contracts
# ---------------------------------------------------------------------------
def chk_report_text() -> str:
    from ui.components.report_export import generate_text_report
    from clinical.assessment_contracts import (
        UnifiedAssessmentResponse, Engine1Result, Engine2Result, Engine3Result,
    )

    e1 = Engine1Result(
        status="PREDICTION_COMPLETE",
        diagnostic_class=1,
        diagnosis="Chronic Kidney Disease (At Risk)",
        risk_probability=0.72,
        confidence_score=0.88,
        risk_category="High",
        abstention_reason=None,
        data_completeness_ratio=1.0,
        full_panel_completeness_ratio=1.0,
        missing_features=[],
        imputed_features=[],
        feature_anomalies={},
        feature_attributions=None,
        sanitized_inputs={},
        model_version="RF-v1",
        provenance="CONTAINER_VERIFICATION",
        warnings=[],
    )
    e2 = Engine2Result(
        status="STAGING_COMPLETE",
        is_adult=True,
        age_evaluated_years=55.0,
        sex_decoded="male",
        egfr=28.5,
        egfr_unit="mL/min/1.73m²",
        gfr_category="G4",
        gfr_description="Severely decreased",
        uacr=300.0,
        uacr_unit="mg/g",
        albuminuria_category="A3",
        albuminuria_description="Severely increased",
        cga_string="G4A3",
        composite_risk_level="Very High",
        risk_tier="Very High",
        risk_color="red",
        is_complete_severity_record=True,
        chronicity_confirmed=False,
        same_day_measurement=None,
        observation_date_scr=None,
        observation_date_uacr=None,
        disclaimer="Research software only.",
        warnings=[],
        provenance="CONTAINER_VERIFICATION",
    )
    e3 = Engine3Result(
        status="KFRE_ONLY",
        is_eligible=True,
        should_abstain=False,
        abstention_reasons=[],
        historical_egfr_slope=-3.2,
        slope_status="DECLINING",
        lmm_annual_slope=None,
        lmm_slope_ci_lower=None,
        lmm_slope_ci_upper=None,
        lmm_status="NOT_FITTED",
        kfre_2year_risk=0.18,
        kfre_5year_risk=0.41,
        kfre_calibration_profile="NORTH_AMERICAN",
        kfre_is_applicable=True,
        kfre_applicability_explanation=None,
        survival_status="DEFERRED_PENDING_APPROVED_COHORT",
        survival_predictions={},
        competing_risk_profile={},
        clinical_reliability={},
        warnings=[],
        provenance="CONTAINER_VERIFICATION",
    )
    response = UnifiedAssessmentResponse(
        assessment_id="CONTAINER-TEST-001",
        patient_id="TEST-PATIENT-CONTAINER",
        assessment_timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        orchestrator_version="1.0.0-rc",
        engine_versions={"engine1": "RF-v1", "engine2": "eGFR-2021", "engine3": "KFRE-Tangri"},
        provenance={"source": "CONTAINER_VERIFICATION", "is_synthetic": False},
        engines_executed=["engine1", "engine2", "engine3"],
        engines_skipped={},
        overall_completeness={"ratio": 1.0},
        engine1_result=e1,
        engine2_result=e2,
        engine3_result=e3,
        summary_findings=[],
        clinical_discrepancies=[],
        safety_warnings=[],
        disclaimer=(
            "INVESTIGATIONAL RESEARCH SOFTWARE. "
            "DOES NOT PROVIDE DEFINITIVE MEDICAL DIAGNOSES. "
            "NOT A CERTIFIED MEDICAL DEVICE."
        ),
    )

    report = generate_text_report(response)
    assert isinstance(report, str) and len(report) > 300, \
        f"Report too short ({len(report)} chars) or wrong type"
    # Verify critical sections are present
    assert "NEFROAI-X" in report
    assert "Engine 1" in report or "ENGINE 1" in report
    return f"text report generated: {len(report)} chars"

check("Report export — text report generation", chk_report_text)


# ---------------------------------------------------------------------------
# 9. Report export — PDF report (reportlab)
# ---------------------------------------------------------------------------
def chk_report_pdf() -> str:
    from ui.components.report_export import generate_pdf_report
    from clinical.assessment_contracts import (
        UnifiedAssessmentResponse, Engine1Result, Engine2Result, Engine3Result,
    )

    # Reuse same minimal valid response
    e1 = Engine1Result(
        status="PREDICTION_COMPLETE",
        diagnostic_class=1,
        diagnosis="Chronic Kidney Disease (At Risk)",
        risk_probability=0.72,
        confidence_score=0.88,
        risk_category="High",
        abstention_reason=None,
        data_completeness_ratio=1.0,
        full_panel_completeness_ratio=1.0,
        missing_features=[],
        imputed_features=[],
        feature_anomalies={},
        feature_attributions=None,
        sanitized_inputs={},
        model_version="RF-v1",
        provenance="CONTAINER_VERIFICATION",
        warnings=[],
    )
    e2 = Engine2Result(
        status="STAGING_COMPLETE",
        is_adult=True,
        age_evaluated_years=55.0,
        sex_decoded="male",
        egfr=28.5,
        egfr_unit="mL/min/1.73m²",
        gfr_category="G4",
        gfr_description="Severely decreased",
        uacr=300.0,
        uacr_unit="mg/g",
        albuminuria_category="A3",
        albuminuria_description="Severely increased",
        cga_string="G4A3",
        composite_risk_level="Very High",
        risk_tier="Very High",
        risk_color="red",
        is_complete_severity_record=True,
        chronicity_confirmed=False,
        same_day_measurement=None,
        observation_date_scr=None,
        observation_date_uacr=None,
        disclaimer="Research software only.",
        warnings=[],
        provenance="CONTAINER_VERIFICATION",
    )
    e3 = Engine3Result(
        status="KFRE_ONLY",
        is_eligible=True,
        should_abstain=False,
        abstention_reasons=[],
        historical_egfr_slope=-3.2,
        slope_status="DECLINING",
        lmm_annual_slope=None,
        lmm_slope_ci_lower=None,
        lmm_slope_ci_upper=None,
        lmm_status="NOT_FITTED",
        kfre_2year_risk=0.18,
        kfre_5year_risk=0.41,
        kfre_calibration_profile="NORTH_AMERICAN",
        kfre_is_applicable=True,
        kfre_applicability_explanation=None,
        survival_status="DEFERRED_PENDING_APPROVED_COHORT",
        survival_predictions={},
        competing_risk_profile={},
        clinical_reliability={},
        warnings=[],
        provenance="CONTAINER_VERIFICATION",
    )
    response = UnifiedAssessmentResponse(
        assessment_id="CONTAINER-TEST-001",
        patient_id="TEST-PATIENT-CONTAINER",
        assessment_timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        orchestrator_version="1.0.0-rc",
        engine_versions={"engine1": "RF-v1", "engine2": "eGFR-2021", "engine3": "KFRE-Tangri"},
        provenance={"source": "CONTAINER_VERIFICATION", "is_synthetic": False},
        engines_executed=["engine1", "engine2", "engine3"],
        engines_skipped={},
        overall_completeness={"ratio": 1.0},
        engine1_result=e1,
        engine2_result=e2,
        engine3_result=e3,
        summary_findings=[],
        clinical_discrepancies=[],
        safety_warnings=[],
        disclaimer=(
            "INVESTIGATIONAL RESEARCH SOFTWARE. "
            "DOES NOT PROVIDE DEFINITIVE MEDICAL DIAGNOSES. "
            "NOT A CERTIFIED MEDICAL DEVICE."
        ),
    )

    pdf_bytes = generate_pdf_report(response)
    assert isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 0, "PDF is empty"
    assert pdf_bytes[:4] == b"%PDF", \
        f"PDF magic bytes missing; got {pdf_bytes[:4]!r}"
    return f"PDF {len(pdf_bytes):,} bytes — magic bytes %PDF OK"

check("Report export — PDF generation (reportlab)", chk_report_pdf)


# ---------------------------------------------------------------------------
# 10. Report export — CSV sanitisation security
# ---------------------------------------------------------------------------
def chk_csv_sanitize() -> str:
    from ui.components.report_export import sanitize_csv_cell

    # Formula-injection characters must be prefixed with '
    assert sanitize_csv_cell("=CMD|' /C calc'!A0") == "'=CMD|' /C calc'!A0", \
        "= prefix not neutralised"
    assert sanitize_csv_cell("+1234") == "'+1234", "+ prefix not neutralised"
    assert sanitize_csv_cell("-100") == "'-100", "- prefix not neutralised"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)", "@ prefix not neutralised"
    # Normal values must pass through unchanged
    assert sanitize_csv_cell("normal text") == "normal text"
    assert sanitize_csv_cell(42) == 42, "Numeric must pass unchanged"
    return "CSV formula injection guard active — 6 assertions passed"

check("Security — CSV formula injection sanitisation (CWE-1236)", chk_csv_sanitize)


# ---------------------------------------------------------------------------
# 11. Test suite smoke — import all test modules without collection errors
# ---------------------------------------------------------------------------
def chk_test_imports() -> str:
    import importlib
    test_dir = os.path.join(ROOT, "tests")
    test_files = [
        f[:-3] for f in os.listdir(test_dir)
        if f.startswith("test_") and f.endswith(".py")
    ]
    failed = []
    for mod_name in test_files:
        try:
            importlib.import_module(f"tests.{mod_name}")
        except Exception as e:
            failed.append(f"{mod_name}: {e}")
    assert not failed, "Test import failures:\n" + "\n".join(failed)
    return f"{len(test_files)} test modules importable"

check("Test suite — all test modules importable", chk_test_imports)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 64)
passed = sum(1 for ok, *_ in results if ok)
failed = sum(1 for ok, *_ in results if not ok)
total  = len(results)
print(f"NEFROAI-X Container Verification: {passed}/{total} passed, {failed} failed")
print("=" * 64)

if failed > 0:
    print("\nFailed checks:")
    for ok, name, msg in results:
        if not ok:
            print(f"  FAIL: {name}")
            print(f"        {msg}")
    print()
    sys.exit(1)
else:
    print()
    print("All container checks passed.")
    print()
    print("Clinical designation : INVESTIGATIONAL RESEARCH SOFTWARE")
    print("                       NOT A CERTIFIED MEDICAL DEVICE")
    print("Survival models      : DEFERRED — approved longitudinal cohort required")
    sys.exit(0)
