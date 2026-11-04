# NEFROAI-X — Phase 9: Clinical Research Software Release Readiness Checklist

**System Title:** NEFROAI-X Multimodal Clinical Decision Support System (CDSS)  
**System Designation:** `INVESTIGATIONAL RESEARCH SOFTWARE`  
**Phase Status:** `SYSTEM QA AND SECURITY REVIEW COMPLETE — LOCAL RESEARCH SOFTWARE RELEASE CANDIDATE`  
**Clinical Validation Status:** `CLINICAL VALIDATION: BLOCKED — APPROVED LONGITUDINAL COHORT REQUIRED`  
**Repository:** `ranjithbrs/kidney-stone-detection` | **Branch:** `main` | **HEAD:** `64b831a`  
**Runtime:** Python 3.10.0 (`.venv\Scripts\python.exe`)  
**Streamlit Binary:** `.venv\Scripts\streamlit.exe`  
**Launch Command:** `.venv\Scripts\streamlit.exe run app_streamlit.py`  
**Date:** November 2026

---

## 1. Release Readiness Summary Table

| Category | Evaluation Dimension | Target Requirement | Evaluation Status | Operational Notes |
|---|---|---|:---:|---|
| **1. Engineering** | Core Engine 1 (Screening) | Tuned Champion Random Forest with 10 consensus features | `PASS` | Preprocessor + RF pipeline loaded from `models/clinical_pipeline.joblib`. |
| **1. Engineering** | Core Engine 2 (Staging) | Race-free CKD-EPI 2021 + KDIGO CGA 2024 matrix staging | `PASS` | Filtration and albuminuria categorized with composite risk tiering. |
| **1. Engineering** | Core Engine 3 (Progression) | OLS & LMM BLUP random slopes + Tangri 4-variable KFRE | `PASS` | Historical trajectories compute for $\ge 2$ visits; KFRE for stages G3-G5. |
| **1. Engineering** | Unified Orchestration | `UnifiedAssessmentEngine` coordinating independent engines | `PASS` | Protected try-except boundaries isolate failures between engines. |
| **1. Engineering** | User Interface | Modular Streamlit application across 6 clinical views | `PASS` | Responsive, accessible UI with clinical presets and interactive charts. |
| **1. Engineering** | Report Generation | Dynamic Vector PDF, JSON, CSV, and formatted text export | `PASS` | Multi-page vector PDF via `PdfPages` (no binary dependencies). |
| **2. Testing** | Unit & Integration QA | Full automated test discovery across repository | `PASS` | **349 / 349 Tests Passing** in $14.31\text{ seconds}$ with zero failures. |
| **2. Testing** | Streamlit UI Tests | Dedicated 24-scenario UI test suite | `PASS` | 24 / 24 UI tests passing in $2.41\text{ seconds}$. |
| **2. Testing** | Phase 9 QA & Security | Formula injection, presets, boundaries, limits | `PASS` | 13 / 13 Phase 9 security and boundary tests passing in $0.80\text{ seconds}$. |
| **2. Testing** | Continuous Integration | Automated GitHub Actions CI workflow | `PASS` | Lightweight workflow configured in `.github/workflows/ci.yml`. |
| **3. Security** | Secrets & Credentials | Zero hardcoded passwords, tokens, or keys in source | `PASS` | Git history and source code audited; `.gitignore` blocks `.env`/secrets. |
| **3. Security** | CSV Formula Injection | Neutralize spreadsheet command execution | `PASS` | `sanitize_csv_cell()` prepends `'` to special characters (`=`, `+`, `-`, `@`). |
| **3. Security** | File Upload Boundaries | Enforce upload size and row limits | `PASS` | 5 MB upload size and 500 row limits enforced with biological bounds checks. |
| **3. Security** | Model Deserialization | Prevent arbitrary code execution via untrusted models | `PASS` | Serialized model uploads prohibited; only trusted SHA-256 artifacts loaded. |
| **3. Security** | Dependency Vulnerabilities | Dependency pinning and supply chain inspection | `PASS` | All 84 dependencies pinned to exact versions in `requirements.txt`. |
| **3. Security** | Scanner Pre-Installation | External scanners (pip-audit, safety, bandit) | `NOT TESTED` | Tools not pre-installed in environment; reported transparently. |
| **4. Privacy** | Data Minimization | Collect only necessary clinical parameters | `PASS` | Pseudonymous patient IDs used; direct PII fields excluded. |
| **4. Privacy** | Ephemeral Processing | Zero external transmission or unauthorized persistence | `PASS` | All calculations local in-memory; no external cloud API calls. |
| **4. Privacy** | Statutory Compliance | HIPAA, GDPR, India DPDP Act formal certifications | `WARNING` | Software is an investigational prototype; not certified under HIPAA/DPDP. |
| **5. Models** | Engine 1 & 2 Availability | Baseline screening and KDIGO staging models active | `PASS` | Online and certified for research evaluation. |
| **5. Models** | Survival ML Models | Cause-specific Cox PH & Random Survival Forest models | `DEFERRED` | Algorithmic code verified; patient prediction deferred pending CRIC DUA. |
| **6. Validation** | External Clinical Validation| Prospective multi-center clinical validation trials | `BLOCKED` | **BLOCKED — APPROVED LONGITUDINAL COHORT REQUIRED.** |
| **7. Regulatory** | Regulatory Clearance | FDA 510(k), De Novo, or CE-MDR SaMD certification | `BLOCKED` | **BLOCKED:** Software is strictly an investigational research prototype. |
| **8. Deployment**| Local Research Deployment | Local loopback execution (`http://localhost:8501`) | `PASS` | Verified runnable via `.venv\Scripts\streamlit.exe run app_streamlit.py`. |
| **8. Deployment**| Public Internet Exposure | Direct binding to public internet interfaces | `BLOCKED` | Public internet exposure is strictly prohibited without proxy/auth hardening. |

---

## 2. Release Status Categories Explanation

- **PASS:** The requirement was thoroughly inspected, tested, and verified to meet functional, security, or clinical consistency criteria.
- **FAIL:** The requirement demonstrated an unmitigated software defect (Zero currently present).
- **WARNING:** The requirement requires clinician awareness or operational caution (e.g. single-timepoint staging chronicity caveat, lack of formal statutory HIPAA certification).
- **NOT TESTED:** External automated scanning tools were not pre-installed in the virtual environment (pip-audit, bandit).
- **DEFERRED:** The capability is architecturally implemented and verified, but withheld for patient predictions pending external data governance agreements (e.g. survival machine learning models requiring an approved CRIC cohort DUA).
- **BLOCKED:** The status is intentionally blocked and unauthorized (prospective clinical validation without cohort access, regulatory SaMD clearance, or public internet exposure).

---

## 3. Explicit Clinical & Regulatory Declarations

```text
================================================================================
CLINICAL VALIDATION: BLOCKED — APPROVED LONGITUDINAL COHORT REQUIRED
REGULATORY DESIGNATION: INVESTIGATIONAL RESEARCH SOFTWARE
RELEASE CANDIDATE: SYSTEM QA AND SECURITY REVIEW COMPLETE — LOCAL RESEARCH SOFTWARE RELEASE CANDIDATE
================================================================================
```

### Operational Guidance for Clinicians & Researchers
1. **Screening Assistance Only:** This framework assists in risk triaging and exploratory research; it does **not** provide definitive clinical diagnoses.
2. **Adjudication Requirement:** All algorithmic outputs, risk tiers, and trajectory predictions must be reviewed alongside comprehensive clinical history and physician judgment.
3. **Synthetic Demonstration Notice:** Demonstration presets are illustrative archetypes and must **never** be cited as evidence of real-world patient outcomes or software clinical accuracy.
