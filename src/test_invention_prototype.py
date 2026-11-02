"""
Phase 17 Verification Test Suite:
Validation of Candidate Invention: Cross-Dataset Clinical Input Reliability and Prediction Validation Mechanism (CD-CIRPVM) / NephroGuard-AI

Tests:
1. Compatible inputs (Healthy & CKD standard presentations)
2. Incompatible inputs (Sensor outliers, extreme out-of-bounds, NaN/Inf)
3. Missing measurements (Empty and sparse records)
4. Inconsistent units and feature definitions (SI µmol/L, g/L, mmol/L, categorical synonyms)
5. Unreliable predictions (Borderline/epistemic uncertainty triggering selective abstention)
"""

import sys
import os
import pprint
import numpy as np
import pandas as pd

# Add src to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from pipeline import KidneyDiagnosticPipeline
from clinical_input_reliability_mechanism import ClinicalInputReliabilityMechanism


def run_invention_tests():
    print("=" * 80)
    print("PHASE 17: CANDIDATE INVENTION PROTOTYPE VERIFICATION SUITE")
    print("Mechanism: Cross-Dataset Clinical Input Reliability and Prediction Validation")
    print("=" * 80)

    # 1. Load trained Champion CKD Pipeline
    model_path = os.path.join("models", "clinical_pipeline.joblib")
    if not os.path.exists(model_path):
        print(f"Error: Model file {model_path} not found.")
        sys.exit(1)

    pipeline = KidneyDiagnosticPipeline.load(model_path)
    print(f"Loaded trained pipeline from {model_path}")
    print(f"Selected consensus biomarkers ({len(pipeline.selected_features)}): {pipeline.selected_features}\n")

    # 2. Instantiate Candidate Invention Mechanism
    guard = ClinicalInputReliabilityMechanism(conformal_quantile=0.261, alpha=0.05, reliability_threshold=0.60)
    print("Initialized NephroGuard-AI (CD-CIRPVM):")
    print(f"  - Conformal Quantile (q_95): {guard.conformal_quantile}")
    print(f"  - Coverage Guarantee (1 - alpha): {(1 - guard.alpha)*100:.0f}%")
    print(f"  - CRI Minimum Reliability Threshold: {guard.reliability_threshold}\n")

    test_results = {}

    # =========================================================================
    # TEST 1: COMPATIBLE INPUTS (Standard Healthy & Standard CKD)
    # =========================================================================
    print("-" * 80)
    print("TEST 1: COMPATIBLE INPUTS (Standard Clinical Presentations)")
    print("-" * 80)

    healthy_record = {
        "age": 40, "bp": 70, "sg": 1.025, "al": 0, "su": 0, "rbc": "normal", "pc": "normal",
        "pcc": "notpresent", "ba": "notpresent", "bgr": 90, "bu": 25, "sc": 0.8, "sod": 140,
        "pot": 4.5, "hemo": 15.5, "pcv": 48, "wc": 7500, "rc": 5.2, "htn": "no", "dm": "no",
        "cad": "no", "appet": "good", "pe": "no", "ane": "no"
    }

    ckd_record = {
        "age": 62, "bp": 90, "sg": 1.010, "al": 3, "su": 1, "rbc": "abnormal", "pc": "abnormal",
        "pcc": "present", "ba": "notpresent", "bgr": 210, "bu": 120, "sc": 5.2, "sod": 130,
        "pot": 5.8, "hemo": 7.8, "pcv": 24, "wc": 11500, "rc": 2.7, "htn": "yes", "dm": "yes",
        "cad": "yes", "appet": "poor", "pe": "yes", "ane": "yes"
    }

    dossier_healthy = guard.validate_and_predict(healthy_record, pipeline)
    print(f"1A. Healthy Patient:")
    print(f"    CRI: {dossier_healthy['clinical_reliability_index']}")
    print(f"    Gate Decision: {dossier_healthy['gate_decision']} ({dossier_healthy['gate_status']})")
    print(f"    Conformal Set: {dossier_healthy['conformal_set']}")
    print(f"    Diagnosis: {dossier_healthy['diagnosis']}")
    print(f"    Risk Probability: {dossier_healthy['calibrated_risk_probability']}")
    print(f"    Triage Tier: {dossier_healthy['triage_tier']}")

    assert dossier_healthy['gate_decision'] == "PROCEED", "Healthy patient should PROCEED"
    assert dossier_healthy['clinical_reliability_index'] == 1.00, "Healthy patient CRI should be 1.0"
    assert dossier_healthy['diagnostic_class'] == 0, "Healthy patient should be classified as Normal (0)"

    dossier_ckd = guard.validate_and_predict(ckd_record, pipeline)
    print(f"\n1B. CKD Patient:")
    print(f"    CRI: {dossier_ckd['clinical_reliability_index']}")
    print(f"    Gate Decision: {dossier_ckd['gate_decision']} ({dossier_ckd['gate_status']})")
    print(f"    Conformal Set: {dossier_ckd['conformal_set']}")
    print(f"    Diagnosis: {dossier_ckd['diagnosis']}")
    print(f"    Risk Probability: {dossier_ckd['calibrated_risk_probability']}")
    print(f"    Triage Tier: {dossier_ckd['triage_tier']}")

    assert dossier_ckd['gate_decision'] == "PROCEED", "CKD patient should PROCEED"
    assert dossier_ckd['clinical_reliability_index'] == 1.00, "CKD patient CRI should be 1.0"
    assert dossier_ckd['diagnostic_class'] == 1, "CKD patient should be classified as CKD (1)"

    test_results["Test 1 (Compatible Inputs)"] = "PASSED"
    print(">>> TEST 1 RESULT: SUCCESS (Decisive Conformal Pass for Standard Inputs)\n")

    # =========================================================================
    # TEST 2: INCOMPATIBLE INPUTS (Sensor Glitches, Out-of-Bounds, NaN/Inf)
    # =========================================================================
    print("-" * 80)
    print("TEST 2: INCOMPATIBLE INPUTS (Sensor Glitches, Out-of-Bounds & NaN/Inf)")
    print("-" * 80)

    incompatible_record = {
        "age": -15,               # Impossible negative age
        "bp": 380,                # Fatal extreme BP
        "sg": 1.999,              # Physically impossible specific gravity
        "sc": 95.0,               # Impossible creatinine (dialysis needed at 15-20)
        "bgr": 4500.0,            # Extreme laboratory glitch
        "hemo": float('nan'),     # Corrupted sensor NaN
        "pot": float('inf'),      # Corrupted sensor Inf
        "htn": "yes", "dm": "yes"
    }

    dossier_incomp = guard.validate_and_predict(incompatible_record, pipeline)
    print(f"2. Incompatible Outlier Record:")
    print(f"    CRI: {dossier_incomp['clinical_reliability_index']}")
    print(f"    Gate Decision: {dossier_incomp['gate_decision']} ({dossier_incomp['gate_status']})")
    print(f"    Clamped / Intercepted Bounds Audit:")
    for k, v in dossier_incomp['bounds_clamping_audit'].items():
        print(f"      - {k}: {v}")

    assert dossier_incomp['clinical_reliability_index'] < guard.reliability_threshold, "CRI must fall below threshold"
    assert dossier_incomp['gate_decision'] == "ABSTAIN", "Incompatible inputs must ABSTAIN"
    assert dossier_incomp['human_action_required'] is True, "Human action must be required"
    assert "AUTOMATED DIAGNOSIS WITHHELD" in dossier_incomp['clinical_alert']

    test_results["Test 2 (Incompatible Inputs)"] = "PASSED"
    print(">>> TEST 2 RESULT: SUCCESS (Physiological Clamping & Selective Abstention Triggered)\n")

    # =========================================================================
    # TEST 3: MISSING MEASUREMENTS (Empty and Sparse Records)
    # =========================================================================
    print("-" * 80)
    print("TEST 3: MISSING MEASUREMENTS (Empty & Ultra-Sparse Records)")
    print("-" * 80)

    empty_record = {}
    dossier_empty = guard.validate_and_predict(empty_record, pipeline)
    print(f"3A. Empty Patient Record ({{}}):")
    print(f"    CRI: {dossier_empty['clinical_reliability_index']}")
    print(f"    Gate Decision: {dossier_empty['gate_decision']} ({dossier_empty['gate_status']})")
    print(f"    Missing Features Count: {dossier_empty['missing_features_count']}")
    print(f"    Clinical Alert: {dossier_empty['clinical_alert']}")

    assert dossier_empty['gate_decision'] == "ABSTAIN", "Empty record must ABSTAIN"
    assert dossier_empty['clinical_reliability_index'] == 0.0, "Empty record CRI must be 0.0"

    sparse_record = {"age": 55, "bp": 80}
    dossier_sparse = guard.validate_and_predict(sparse_record, pipeline)
    print(f"\n3B. Ultra-Sparse Patient Record (age=55, bp=80 only):")
    print(f"    CRI: {dossier_sparse['clinical_reliability_index']}")
    print(f"    Gate Decision: {dossier_sparse['gate_decision']} ({dossier_sparse['gate_status']})")
    assert dossier_sparse['gate_decision'] == "ABSTAIN", "Sparse record must ABSTAIN"

    test_results["Test 3 (Missing Measurements)"] = "PASSED"
    print(">>> TEST 3 RESULT: SUCCESS (Low-CRI Incompleteness Rejection Verified)\n")

    # =========================================================================
    # TEST 4: INCONSISTENT UNITS & FEATURE DEFINITIONS (MIDR & Synonyms)
    # =========================================================================
    print("-" * 80)
    print("TEST 4: INCONSISTENT UNITS & FEATURE DEFINITIONS (MIDR & Dialects)")
    print("-" * 80)

    # UK / International Hospital Record:
    # sc in µmol/L (88.42 µmol/L = 1.0 mg/dL)
    # hemo in g/L (145.0 g/L = 14.5 g/dL)
    # bgr in mmol/L (5.5 mmol/L = 99.1 mg/dL)
    # Categoricals with boolean/numeric variants ("1", "true")
    international_uk_record = {
        "age": 45,
        "bp": 75,
        "sg": 1.025,
        "al": 0,
        "su": 0,
        "sc": 88.42,      # µmol/L (SI) -> should convert to ~1.0 mg/dL
        "hemo": 150.0,    # g/L (SI) -> should convert to 15.0 g/dL
        "bgr": 5.2,       # mmol/L (SI) -> should convert to ~93.7 mg/dL
        "bu": 28,
        "pcv": 45,
        "rc": 5.0,
        "wc": 7200,
        "sod": 142,
        "pot": 4.2,
        "htn": "0",       # Numeric variant -> "no"
        "dm": "FALSE",    # Boolean string variant -> "no"
        "cad": "negative",
        "pe": "absent"
    }

    dossier_intl = guard.validate_and_predict(international_uk_record, pipeline)
    print(f"4A. International SI Record (UK / NHS Format):")
    print(f"    Reconciled Unit Audit:")
    for k, v in dossier_intl['unit_reconciliation_audit'].items():
        if v.get("status") != "native_standard":
            print(f"      - {k}: {v['original_value']} -> {v['reconciled_value']} ({v['detected_unit']} -> {v['standard_unit']})")

    print(f"    Sanitized Model Inputs: {dossier_intl['sanitized_inputs']}")
    print(f"    CRI: {dossier_intl['clinical_reliability_index']}")
    print(f"    Gate Decision: {dossier_intl['gate_decision']}")
    print(f"    Diagnosis: {dossier_intl['diagnosis']}")
    print(f"    Calibrated Risk Probability: {dossier_intl['calibrated_risk_probability']}")

    assert dossier_intl['sanitized_inputs']['sc'] == 1.0, f"sc should be reconciled to 1.0 mg/dL, got {dossier_intl['sanitized_inputs']['sc']}"
    assert dossier_intl['sanitized_inputs']['hemo'] == 15.0, f"hemo should be reconciled to 15.0 g/dL, got {dossier_intl['sanitized_inputs']['hemo']}"
    assert dossier_intl['gate_decision'] == "PROCEED", "Reconciled SI record should PROCEED"
    assert dossier_intl['diagnostic_class'] == 0, "Healthy SI patient should be correctly diagnosed as Normal (0)"

    # UK CKD Patient with high µmol/L:
    international_ckd_record = {
        "age": 68, "bp": 95, "sg": 1.010, "al": 3, "su": 1,
        "sc": 442.1,     # µmol/L -> 5.0 mg/dL
        "hemo": 80.0,     # g/L -> 8.0 g/dL
        "bgr": 12.5,     # mmol/L -> 225.2 mg/dL
        "bu": 115, "pcv": 25, "rc": 2.9, "wc": 11000,
        "htn": "1",      # Numeric affirmative -> "yes"
        "dm": "TRUE",    # Boolean affirmative -> "yes"
        "cad": "positive"
    }
    dossier_intl_ckd = guard.validate_and_predict(international_ckd_record, pipeline)
    print(f"\n4B. International SI CKD Patient:")
    print(f"    Reconciled sc: {dossier_intl_ckd['sanitized_inputs']['sc']} mg/dL (from 442.1 µmol/L)")
    print(f"    Reconciled hemo: {dossier_intl_ckd['sanitized_inputs']['hemo']} g/dL (from 80.0 g/L)")
    print(f"    Gate Decision: {dossier_intl_ckd['gate_decision']}")
    print(f"    Diagnosis: {dossier_intl_ckd['diagnosis']}")
    assert dossier_intl_ckd['sanitized_inputs']['sc'] == 5.0, "sc 442.1 µmol/L should reconcile to 5.0 mg/dL"
    assert dossier_intl_ckd['diagnostic_class'] == 1, "CKD SI patient should be diagnosed as CKD (1)"

    test_results["Test 4 (Inconsistent Units & Synonyms)"] = "PASSED"
    print(">>> TEST 4 RESULT: SUCCESS (MIDR Seamless Cross-Dataset Unit Translation Verified)\n")

    # =========================================================================
    # TEST 5: UNRELIABLE PREDICTIONS (Epistemic Boundary Ambiguity Abstention)
    # =========================================================================
    print("-" * 80)
    print("TEST 5: UNRELIABLE PREDICTIONS (Borderline Presentation & Conformal Abstention)")
    print("-" * 80)

    # Borderline presentation engineered near decision threshold:
    # Equivocal presentation where base model probability falls near 0.50 (e.g. 0.58)
    borderline_record = {
        "age": 50,
        "bp": 75,
        "sg": 1.020,
        "al": 0,
        "su": 0,
        "sc": 1.2,
        "bu": 35,
        "bgr": 110,
        "hemo": 13.0,
        "pcv": 40,
        "rc": 4.5,
        "wc": 7500,
        "sod": 138,
        "pot": 4.3,
        "htn": "no",
        "dm": "no",
        "cad": "no",
        "pe": "no",
        "ane": "no",
        "appet": "good"
    }

    dossier_borderline = guard.validate_and_predict(borderline_record, pipeline)
    print(f"5. Borderline Equivocal Patient Record:")
    print(f"    CRI: {dossier_borderline['clinical_reliability_index']}")
    print(f"    Calibrated Risk Probability: {dossier_borderline['calibrated_risk_probability']}")
    print(f"    Conformal Set: {dossier_borderline['conformal_set']}")
    print(f"    Gate Decision: {dossier_borderline['gate_decision']} ({dossier_borderline['gate_status']})")
    print(f"    Human Action Required: {dossier_borderline['human_action_required']}")
    print(f"    Diagnosis: {dossier_borderline['diagnosis']}")
    if dossier_borderline['human_action_required']:
        print(f"    Clinical Alert: {dossier_borderline['clinical_alert']}")

    # Check that abstention gate behaves safely
    assert dossier_borderline['gate_decision'] == "ABSTAIN", "Borderline case must trigger selective ABSTAIN"
    assert dossier_borderline['gate_status'] == "REJECTED_EPISTEMIC_UNCERTAINTY", "Status must be epistemic uncertainty"
    assert dossier_borderline['human_action_required'] is True, "Human action must be required"
    assert dossier_borderline['conformal_set'] == [0, 1], "Conformal set must contain both {0, 1}"
    test_results["Test 5 (Unreliable Predictions Handling)"] = "PASSED"
    print(">>> TEST 5 RESULT: SUCCESS (Selective Abstention Gate Operational for Ambiguous Cases)\n")

    # =========================================================================
    # SUMMARY OF VERIFICATION
    # =========================================================================
    print("=" * 80)
    print("PHASE 17 INVENTION PROTOTYPE VERIFICATION SUMMARY")
    print("=" * 80)
    for t_name, status in test_results.items():
        print(f"  [PASS] {t_name:50s} : {status}")
    print("\nAll 5 prototype validation criteria successfully satisfied!")
    print("Candidate Invention (NephroGuard-AI / CD-CIRPVM) working prototype is verified.")
    return True


if __name__ == "__main__":
    run_invention_tests()
