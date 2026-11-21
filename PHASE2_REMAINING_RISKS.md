# NEFROAI-X — Phase 2 Remaining Risks & Clinical Limitations Report

**Document ID:** NEFROAI-P2-RISKS-001  
**Execution Date:** November 21, 2026  
**Auditor:** Healthcare Information Security & Clinical AI Safety Reviewer  
**Context:** Formal Risk & Limitation Disclosure Following Phase 2 Remediation

---

## 1. Executive Statement on Risk Transparency

Healthcare software systems requiring clinical decision support capabilities must operate under absolute transparency regarding technical, statistical, and operational boundaries. 

The remediation in Phase 2 has eliminated critical code-level vulnerabilities (hardcoded secrets, missing demo banners, silent SQLite persistence assumptions). However, five fundamental technical and clinical risks remain inherent to the current prototype architecture.

---

## 2. Inventory of Remaining Risks

### 2.1 Risk 1: Ephemeral Data Loss in Containerized Demonstration Deployments
- **Severity:** Medium (Operational) / High (if real data is entered)
- **Description:** On cloud platforms utilizing container-as-a-service (e.g. Render Free Plan, Google Cloud Run without persistent NFS/volume mounts), the local filesystem is ephemeral.
- **Consequence:** If an evaluator registers accounts and saves patient evaluations without attaching a cloud PostgreSQL database, all records in `runs/local_cdss.db` are permanently destroyed whenever the container restarts, sleeps, or is updated.
- **Mitigation Implemented:** Added a persistent, non-dismissible amber warning banner in the React UI prohibiting entry of real Protected Health Information (PHI) and alerting users to container ephemerality.
- **Unresolved Prerequisite for True Production:** An enterprise managed PostgreSQL database instance (`DATABASE_URL`) with point-in-time recovery (PITR) must be provisioned before saving real-world patient records.

---

### 2.2 Risk 2: Spectrum Bias & Generalization Limits in the Benchmark Dataset
- **Severity:** High (Clinical / Generalization)
- **Description:** The machine learning champion model and stacking ensemble achieved an empirical ROC-AUC of $1.0000$ and PR-AUC of $1.0000$ on the held-out test partition ($N=80$). A rigorous audit confirmed this is **not** due to synthetic data leakage, but rather to **Spectrum Bias (Case-Control Selection Bias)** in the source dataset (`dataset_A_uci_ckd.csv`, $N=400$):
  - **Cases:** Severely compromised hospitalized CKD patients (median creatinine $2.2\text{ mg/dL}$, 100% proteinuria, renal anemia).
  - **Controls:** Completely healthy screening donors (serum creatinine $\le 1.2\text{ mg/dL}$, zero proteinuria, normal hemoglobin, zero hypertension).
- **Consequence:** In real-world primary care and ambulatory clinics, patients frequently present with subtle Stage 1–2 CKD, fluctuating borderline creatinine, dehydration, or confounding non-renal comorbidities (e.g. congestive heart failure, liver cirrhosis). The model's 100% sensitivity on this benchmark **will not** replicate at 100% in unstructured outpatient clinical practice.
- **Mitigation Implemented:** Labeled all evaluation metrics as internal benchmark validation on a single historic dataset. Added the Conformal Prediction epistemic uncertainty gate ($C_\alpha = \{0, 1\}$) and Clinical Reliability Index (CRI) to withhold automated outputs when inputs exhibit noise or discordance.
- **Unresolved Prerequisite for True Production:** Prospective external clinical validation on multi-institutional, racially and geographically diverse EHR cohorts.

---

### 2.3 Risk 3: Regulatory & Diagnostic Device Boundary
- **Severity:** Critical (Legal & Regulatory Compliance)
- **Description:** NEFROAI-X is an investigational software prototype. It has **not** received:
  - US FDA 510(k) clearance or De Novo classification for Software as a Medical Device (SaMD).
  - EU Medical Device Regulation (MDR 2017/745) CE mark.
  - Formal HIPAA Business Associate Agreement (BAA) coverage in the public cloud host.
- **Consequence:** Deploying this system to provide definitive automated diagnoses, prescribe nephroprotective medications, or override board-certified physician judgment violates medical regulatory standards.
- **Mitigation Implemented:** Formally reinforced the disclaimer in UI headers, medical report exports, and attestation certificates:  
  *Investigational Clinical Decision Support Prototype — Not clinically validated for standalone medical diagnosis. All recommendations require board-certified nephrologist clinical adjudication.*

---

### 2.4 Risk 4: Operational Environment Variable Enforcement
- **Severity:** Medium (Operational Configuration)
- **Description:** Phase 2 removed the hardcoded fallback secret in production mode. If an administrator launches a new production container without configuring `NEFROAI_JWT_SECRET` in their hosting platform's environment variables, the service will refuse to start and crash immediately on startup with a `RuntimeError`.
- **Consequence:** A deployment could experience a temporary HTTP 503 until the platform administrator configures the required secret in the dashboard.
- **Mitigation Implemented:** Added clear startup error logs explaining the missing secret and documented the requirement in `.env.example`, `render.yaml`, and `run_app.py`.

---

### 2.5 Risk 5: Duplicate Dataset Mirror in Repository
- **Severity:** Low (Documentation & Scientific Rigor)
- **Description:** The repository contains both `datasets/clinical/dataset_A_uci_ckd.csv` and `datasets/clinical/dataset_C_kaggle_ckd.csv`.
- **Consequence:** Researchers or junior developers might mistakenly assume Dataset C represents an independent external validation cohort, leading to false claims of cross-dataset generalization.
- **Mitigation Implemented:** Documented in [AGENTS.md](file:///c:/Users/B%20Ranjith/Downloads/project/AGENTS.md) and [INDEPENDENT_VERIFICATION_REPORT.md](file:///c:/Users/B%20Ranjith/Downloads/project/INDEPENDENT_VERIFICATION_REPORT.md) that Dataset C is a byte-level duplicate mirror of Dataset A. Models are trained and tested strictly on isolated partitions of Dataset A.

---

## 3. Summary Risk Matrix

| Risk Factor | Current Mitigation Status | Path to Full Remediation |
|---|:---:|---|
| **Ephemeral SQLite Storage** | High-contrast UI warning banner active | Provision persistent PostgreSQL (`DATABASE_URL`) |
| **Dataset Spectrum Bias** | Conformal prediction gate & CRI abstention | Multi-site prospective clinical trials |
| **Regulatory SaMD Status** | Prominent investigational CDSS disclaimer | Formal FDA 510(k) / CE mark clinical trial submission |
| **JWT Platform Secret Requirement** | Clear startup error & `.env.example` docs | Configure `NEFROAI_JWT_SECRET` in cloud dashboard |
| **Duplicate Dataset Confusion** | Explicitly audited in documentation | Retain Dataset A as sole ground truth; archive mirror |
