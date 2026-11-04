# NEFROAI-X — Phase 7: Three-Engine Clinical Assessment Integration Report

**System:** NefroAI-X Clinical Decision Support System (CDSS)  
**Document Version:** 1.0.0  
**Phase:** Phase 7 (Unified Multi-Engine Orchestration & Architecture)  
**Status:** `THREE-ENGINE INTEGRATION COMPLETE — RESEARCH SOFTWARE`  
**Clinical Validation Status:** `BLOCKED — APPROVED LONGITUDINAL COHORT REQUIRED`  
**Baseline Git Commit:** `64b831a`  
**Python Runtime:** 3.10.0 (`.venv\Scripts\python.exe`)  
**Designation:** Investigational Research Software Prototype (Not for Autonomous Medical Diagnosis)

---

## 1. Executive Summary & Clinical Scope

Phase 7 delivers the unified orchestration layer coordinating all three independently engineered clinical engines within the NefroAI-X Clinical Decision Support System:

1. **Engine 1 (Screening & Binary Classification):** Replicates and enhances the *IEEE Access* (Huda et al.) champion Random Forest pipeline on the 10-consensus routine urinalysis and hematological biomarker panel.
2. **Engine 2 (KDIGO CGA Severity Staging):** Implements the KDIGO 2024 Clinical Practice Guideline framework combining race-free CKD-EPI 2021 eGFR estimation, continuous uACR staging (A1–A3), and composite prognosis risk matrix evaluation.
3. **Engine 3 (Longitudinal Progression & KFRE Risk):** Implements multi-visit landmarking, individual descriptive and Linear Mixed-Effects (LMM) Empirical Bayes eGFR decline trajectories, Tangri 4-variable Kidney Failure Risk Equation (KFRE) reference evaluation, and competing-risk data representation.

The orchestration layer is encapsulated in [`UnifiedAssessmentEngine`](file:///c:/Users/B%20Ranjith/Downloads/project/src/engines/unified_assessment_engine.py#L46-L950) with shared data contracts defined in [`src/clinical/assessment_contracts.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py). The system guarantees independent engine execution, safe abstention, zero silent imputation, and transparent cross-engine discrepancy reporting.

---

## 2. Unified Assessment Architecture & Data Flow

```
                                  Patient Assessment Request
                        (Demographics, Engine 1, Engine 2, Engine 3)
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │      UnifiedAssessmentEngine (Orchestrator)   │
                    │   • Normalizes input format & provenance      │
                    │   • Detects available & requested engines     │
                    │   • Isolates failures (independent execution) │
                    └───────┬───────────────────┬───────────────────┘
                            │                   │
         ┌──────────────────┼───────────────────┼──────────────────┐
         │                  │                   │                  │
         ▼                  ▼                   ▼                  ▼
┌─────────────────┐┌─────────────────┐┌──────────────────┐┌────────────────┐
│    Engine 1     ││    Engine 2     ││     Engine 3     ││   Provenance   │
│   (Screening)   ││   (Severity)    ││  (Progression)   ││   & Tracking   │
├─────────────────┤├─────────────────┤├──────────────────┤├────────────────┤
│ • Strict schema ││ • CKD-EPI 2021   ││ • Landmarking    ││ • Timestamps   │
│   validation    ││   eGFR race-free││ • OLS/LMM slope  ││ • Lab origins  │
│ • Critical gate ││ • uACR staging  ││ • Tangri 4-v KFRE││ • Conversions  │
│ • Random Forest ││ • CGA composite ││ • Gated survival ││ • Imputation   │
│ • Attributions  ││ • Chronicity    ││ • Competing CIF  ││   indicators   │
│ • Safe abstain  ││   disclaimer    ││ • Selective CRI  ││ • Audit trails │
└────────┬────────┘└────────┬────────┘└─────────┬────────┘└───────┬────────┘
         │                  │                   │                 │
         └──────────────────┼───────────────────┴─────────────────┘
                            │
                            ▼
                    ┌───────────────────────────────────────────────┐
                    │    Cross-Engine Discrepancy & Safety Gates    │
                    │   • DISC-01: Screening Positive, No Staging   │
                    │   • DISC-02: False Assurance Risk (CRITICAL)  │
                    │   • DISC-03: Single Staging, Unproven Chron.  │
                    │   • DISC-04: Trajectory OK, Survival Deferred │
                    │   • DISC-05: KFRE Boundary Violation Warning  │
                    │   • DISC-06: Non-Concurrent Biomarkers (>30d) │
                    │   • DISC-07: Clinical History Conflict (HTN)  │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                               UnifiedAssessmentResponse
                        (JSON-Serializable Structured Clinical Output)
```

---

## 3. Shared Data Contracts

The orchestration architecture defines typed dataclasses in [`src/clinical/assessment_contracts.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py):

### 3.1 Input Contracts
- [`PatientAssessmentRequest`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L125-L160): Top-level request encapsulating `patient_id`, `request_id`, `assessment_timestamp`, `demographics`, engine-specific payloads, `requested_engines`, and provenance.
- [`Demographics`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L55-L67): `age`, `sex` (decoded or numeric), `race_ethnicity` (noting CKD-EPI 2021 is race-free), height, weight.
- [`Engine1ScreeningInput`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L70-L86): Key-value clinical biomarkers (canonical 24-feature schema), observation date, provenance.
- [`Engine2SeverityInput`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L89-L115): Serum creatinine, uACR, observation dates for each marker, units, clinical cause.
- [`Engine3ProgressionInput`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L118-L138): Longitudinal history (`LongitudinalPatientRecord`), landmark time, explicit KFRE inputs, regional calibration.

### 3.2 Output Contracts
- [`Engine1Result`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L165-L210): Screening status, diagnostic class (0/1), diagnosis, calibrated probability, confidence score, triage tier, missingness tracking, and feature attributions.
- [`Engine2Result`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L215-L265): eGFR, G-category (G1–G5), uACR, A-category (A1–A3), CGA classification, composite KDIGO risk tier, chronicity disclaimer, same-day measurement indicator.
- [`Engine3Result`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L270-L320): Longitudinal eligibility, descriptive OLS slope, LMM BLUP random slope and 95% CI, KFRE 2-year/5-year risk, survival model status (`DEFERRED_PENDING_APPROVED_COHORT`), competing-risk profile, and Clinical Reliability Index (CRI).
- [`UnifiedAssessmentResponse`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical/assessment_contracts.py#L345-L390): Integrated master response containing assessment metadata, individual engine results, summary findings, cross-engine clinical discrepancies, safety warnings, and full JSON serialization (`to_dict()`, `to_json()`).

---

## 4. Engine Invocation & Responsibilities

| Engine | Primary Clinical Role | Implementation & Model Artifact | Independence Guarantee |
|---|---|---|---|
| **Engine 1** | Routine hematological and urinalysis screening; binary risk classification | `KidneyDiagnosticPipeline` loaded from [`models/clinical_pipeline.joblib`](file:///c:/Users/B%20Ranjith/Downloads/project/models/clinical_pipeline.joblib) | Operates strictly independently. Fails gracefully or abstains when critical features (`sc`, `al`, `hemo`) are missing. Never suppresses Engine 2 or 3. |
| **Engine 2** | KDIGO CGA severity staging; quantitative filtration & albuminuria risk | [`KidneySeverityEngine`](file:///c:/Users/B%20Ranjith/Downloads/project/src/engines/kidney_severity_engine.py#L42-L180) | Operates on single cross-sectional measurements. Never requires Engine 1 to be positive. Always attaches chronicity disclaimer. |
| **Engine 3** | Longitudinal eGFR decline trajectory, KFRE risk, and competing-risk analysis | [`KidneyProgressionEngine`](file:///c:/Users/B%20Ranjith/Downloads/project/src/engines/kidney_progression_engine.py#L173-L530) | Operates independently when multi-visit or KFRE inputs exist. Unfitted survival models are strictly withheld with explicit deferred status. |

---

## 5. Cross-Engine Safety & Discrepancy Rules

The orchestrator actively compares results across engines to detect clinically important discordance. Rather than forcing artificial agreement, the orchestrator reports discrepancies transparently:

1. **DISC-01 (Screening Positive, No Staging):** Engine 1 predicts CKD ($prob \ge 0.50$), but quantitative eGFR or uACR data are missing.  
   *Action:* Recommends immediate quantitative laboratory workup to confirm staging and rule out acute impairment.
2. **DISC-02 (False Assurance Risk — CRITICAL):** Engine 1 classifies patient as Healthy (Class 0, $prob < 0.50$), but Engine 2 reports reduced filtration ($\text{eGFR} < 60\text{ mL/min/1.73m}^2$) or pathological albuminuria ($\text{uACR} \ge 30\text{ mg/g}$).  
   *Action:* Disables reliance on binary screening output; alerts clinician to defer to laboratory KDIGO staging and initiate clinical evaluation.
3. **DISC-03 (Single Staging Without Proven Chronicity):** Engine 2 identifies abnormal biomarkers, but Engine 3 has $<2$ visits spanning $\ge 90$ days.  
   *Action:* Advises repeat testing in 3 months per KDIGO guidelines to distinguish true CKD from resolving AKI or transient proteinuria.
4. **DISC-04 (Trajectory Available, Survival Model Withheld):** Engine 3 calculates empirical/LMM slope, but ML survival models (Cox PH, RSF) are unfitted.  
   *Action:* Documents that cohort survival inference is deferred pending approved longitudinal cohort ingestion (CRIC DUA).
5. **DISC-05 (KFRE Out-of-Scope Warning):** Tangri KFRE is evaluated for patients with $\text{eGFR} \ge 60\text{ mL/min/1.73m}^2$ (Stages G1/G2) or $\text{eGFR} < 10\text{ mL/min/1.73m}^2$.  
   *Action:* Withholds risk probabilities to prevent misleading prognostications, flagging applicability boundaries.
6. **DISC-06 (Non-Concurrent Staging Measurements):** Serum creatinine and uACR were collected $>30$ days apart.  
   *Action:* Advises concurrent repeat measurements to establish synchronized filtration and albuminuria status.
7. **DISC-07 (Clinical History vs Measurement Conflict):** Patient history states no hypertension, but recorded systolic blood pressure is $\ge 140\text{ mmHg}$.  
   *Action:* Flags discrepancy to prompt clinician verification of blood pressure measurement technique and rule out undiagnosed hypertension.

---

## 6. Input Reliability & Anti-Leakage Safeguards

- **Zero Silent Imputation:** Missing measurements are explicitly recorded in `missing_features` and penalized in data completeness metrics. Coercive substitution with healthy defaults (`sc=1.0`, `al=0`, `hemo=13.5`) is strictly prohibited.
- **Unit Reconciliation (MIDR):** Automatic recognition of SI units (e.g. $\mu\text{mol/L}$ for creatinine converted via factor $88.42$, $\text{mg/mmol}$ for uACR converted via factor $8.84$) with explicit provenance warnings logged.
- **Temporal Anti-Leakage:** Engine 3 strictly discards observations recorded after `landmark_time`, ensuring prospective validity.
- **Model Loading Efficiency:** The production Random Forest pipeline is cached in memory (`_cached_pipeline`), avoiding repetitive disk I/O and unpickling overhead during batch processing.

---

## 7. Implementation Status vs. Deferred Scope

| Component / Functionality | Implementation Status | Clinical / Regulatory Scope |
|---|:---:|---|
| Unified Assessment Orchestrator | **IMPLEMENTED** | Operational in `src/engines/unified_assessment_engine.py` |
| Shared Data Contracts | **IMPLEMENTED** | Defined in `src/clinical/assessment_contracts.py` |
| Engine 1 Pipeline Integration | **IMPLEMENTED** | Reuses `models/clinical_pipeline.joblib` |
| Engine 2 KDIGO Integration | **IMPLEMENTED** | Reuses `src/engines/kidney_severity_engine.py` |
| Engine 3 Progression Integration | **IMPLEMENTED** | Reuses `src/engines/kidney_progression_engine.py` |
| Cross-Engine Discrepancy Detector | **IMPLEMENTED** | 7 automated clinical discordance checks |
| Model Caching & Error Isolation | **IMPLEMENTED** | Exception isolation; memory-cached pipeline |
| Full JSON Serialization | **IMPLEMENTED** | `to_dict()`, `to_json()` methods certified |
| Survival Model Clinical Training | **DEFERRED** | Blocked pending approved CRIC longitudinal cohort DUA |
| India-Specific KFRE Recalibration | **DEFERRED** | Non-North American default used; empirical calibration withheld |
| Streamlit Web UI Integration | **PLANNED** | Reserved for Phase 8 frontend implementation |

---

## 8. Verification & Test Results

### 8.1 Dedicated Phase 7 Integration Test Suite
The dedicated integration test suite [`tests/test_unified_assessment_engine.py`](file:///c:/Users/B%20Ranjith/Downloads/project/tests/test_unified_assessment_engine.py) covers 23 comprehensive scenarios:

```
tests/test_unified_assessment_engine.py
├── test_01_all_three_engines_available .................... [ PASSED ]
├── test_02_engine1_only ................................... [ PASSED ]
├── test_03_engine2_only ................................... [ PASSED ]
├── test_04_engine3_only ................................... [ PASSED ]
├── test_05_partial_input_combinations ..................... [ PASSED ]
├── test_06_independent_engine_failure_handling ............ [ PASSED ]
├── test_07_engine_specific_abstention ..................... [ PASSED ]
├── test_08_missing_critical_measurements_gate ............. [ PASSED ]
├── test_09_non_standard_units_handling .................... [ PASSED ]
├── test_10_no_silent_imputation_preserves_missing_status .. [ PASSED ]
├── test_11_conflicting_engine_outputs_false_assurance_risk  [ PASSED ]
├── test_12_cross_sectional_vs_longitudinal_separation ..... [ PASSED ]
├── test_13_kfre_applicability_range_warning ............... [ PASSED ]
├── test_14_untrained_survival_model_blocking .............. [ PASSED ]
├── test_15_provenance_and_id_preservation ................. [ PASSED ]
├── test_16_no_temporal_leakage_landmark_filtering ......... [ PASSED ]
├── test_17_same_day_measurement_consistency ............... [ PASSED ]
├── test_18_reproducibility_of_response .................... [ PASSED ]
├── test_19_engine_independence_no_forced_positivity ....... [ PASSED ]
├── test_20_complete_assessment_serialization_and_json ..... [ PASSED ]
├── test_21_flat_dictionary_input_normalization ............ [ PASSED ]
├── test_22_explicit_requested_engines_filtering ........... [ PASSED ]
└── test_23_clinical_history_conflict_detection ............ [ PASSED ]
-----------------------------------------------------------------------
Integration Suite Subtotal: 23 passed in 1.43s (0 failures, 0 errors)
```

### 8.2 Full Repository Regression Test Suite
```
Command: .venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
Ran: 312 tests in 18.168s
Result: OK (312 passed, 0 failures, 0 errors, 0 regressions)
```

Test count reconciliation:
- Phase 6 regression total: 289 tests.
- Phase 7 new integration tests: 23 tests.
- Combined repository total: **312 tests passed**.

---

## 9. Protected Baseline Asset Integrity Verification

| File Path | Baseline SHA-256 | Current SHA-256 | Status |
|---|---|---|:---:|
| [`models/clinical_pipeline.joblib`](file:///c:/Users/B%20Ranjith/Downloads/project/models/clinical_pipeline.joblib) | `9217fbbe3c74207f...` | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | **VERIFIED UNCHANGED** |
| [`datasets/clinical/dataset_A_uci_ckd.csv`](file:///c:/Users/B%20Ranjith/Downloads/project/datasets/clinical/dataset_A_uci_ckd.csv) | `147be021a0a1498d...` | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | **VERIFIED UNCHANGED** |
| [`models/preprocessor_Dataset_A.joblib`](file:///c:/Users/B%20Ranjith/Downloads/project/models/preprocessor_Dataset_A.joblib) | `fae81c26a23117d4...` | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | **VERIFIED UNCHANGED** |
| [`src/clinical_input_reliability_mechanism.py`](file:///c:/Users/B%20Ranjith/Downloads/project/src/clinical_input_reliability_mechanism.py) | `f250cfeb5629c4b3...` | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | **VERIFIED UNCHANGED** |

---

## 10. Phase 8 Frontend Integration Specifications

For the upcoming Streamlit user interface (Phase 8):
1. **Primary Entry Point:** Use [`UnifiedAssessmentEngine`](file:///c:/Users/B%20Ranjith/Downloads/project/src/engines/unified_assessment_engine.py#L46-L950) as the central backend service for clinical inferences.
2. **Preset Profiles:** Provide quick clinical test presets (Healthy Screening, Mild Impairment G2/A1, Discordant False Assurance Case G3a/A3, Advanced Diabetic Nephropathy G4/A3 with rapid trajectory).
3. **Multi-Tab Architecture:** Render separate views for Engine 1 Screening, Engine 2 KDIGO Staging Matrix (6x3 color grid), Engine 3 Trajectory/KFRE Curves, and an Integrated Summary with Discordance Banners.
4. **Safety Disclaimers:** Display the investigational CDSS disclaimer prominently on all evaluation screens and reports.
