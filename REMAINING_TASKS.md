# NEFROAI-X — Roadmap, Incomplete Tasks & Governance Log

**System Name**: NEFROAI-X Clinical Decision Support System (CDSS)  
**Status**: Core Engines 1–3 Production Ready. Survival ML Deferred by Design.

---

## 1. Deferred Tasks Requiring External Data Access & Approvals

### A. Longitudinal Survival ML (DeepSurv / Cox Proportional Hazards)
- **Current Status**: **DEFERRED BY DESIGN** (`SURVIVAL_ML_STATUS = "DEFERRED_PENDING_APPROVED_COHORT"`).
- **Clinical Rationale**:
  - The primary benchmark dataset (UCI CKD Dataset A, $N=400$) is a **cross-sectional** cohort containing baseline lab values without time-to-event longitudinal survival outcomes.
  - Training survival models (e.g. Kaplan-Meier, Cox Proportional Hazards, DeepSurv) on synthetic follow-up times or cross-sectional proxies violates fundamental epidemiological integrity and clinical AI safety standards.
- **Required Next Steps**:
  1. Secure formal Institutional Data Use Agreement (DUA) for an approved prospective longitudinal cohort (e.g., the NIH/NIDDK Chronic Renal Insufficiency Cohort [CRIC] or UK Biobank renal follow-up).
  2. Implement time-to-event pipeline only when validated right-censored event records ($\text{time-to-ESRD}$, $\text{all-cause mortality}$) are legitimately available.

---

## 2. Clinical Trial & Regulatory Governance

### A. Prospective Multi-Center Clinical Validation
- **Current Status**: Investigational Decision Support Prototype.
- **Requirement**: Before any deployment in patient-facing clinical workflows, the system requires:
  1. IRB / Institutional Ethics Committee (IEC) clinical trial protocol approval.
  2. Multi-center prospective diagnostic accuracy study comparing NefroAI-X risk stratification against board-certified nephrologist clinical judgment.
  3. Formal FDA 510(k) or SaMD (Software as a Medical Device) pre-market review if commercial diagnostic claims are pursued.

---

## 3. Infrastructure & Repository Maintenance

### A. Dedicated Managed PostgreSQL Instance
- **Current Status**: Dual-backend support active (PostgreSQL with SQLite fallback).
- **Task**: For permanent patient audit persistence on Render Free Tier (where container local filesystems are ephemeral), set `DATABASE_URL` to a free managed PostgreSQL database (e.g. Supabase, Neon, or Render PostgreSQL).

### B. Legacy Dataset Archival
- **Current Status**: Legacy kidney-stone datasets (`datasets/clinical/dataset_B_kidney_stone.csv`, `datasets/clinical/dataset_C_simpson_kidney.csv`, `datasets/test/images/`) remain in the repository for historical reasons.
- **Task**: Archive non-renal image and stone datasets to a separate legacy branch to reduce repository clone footprint.
