# NEFROAI-X — Phase 2.6: Post-Deployment Live Verification Report

**Document ID:** NEFROAI-P2.6-LIVE-VERIFY-001  
**Execution Date:** November 21, 2026  
**Auditor:** Senior Full-Stack Developer, Python Backend Engineer & Healthcare Security Reviewer  
**Live Target:** [https://kidney-stone-detection-0x56.onrender.com](https://kidney-stone-detection-0x56.onrender.com)  
**Verification Scope:** Read-Only Post-Deployment Live Telemetry & Security Audit  

---

## 1. Executive Summary & Core Verdict

The live Render deployment was probed following the operator's manual addition of `NEFROAI_JWT_SECRET` to the Render Environment dashboard.

```
+-----------------------------------------------------------------------------------------+
|                                    LIVE STATUS VERDICT                                  |
|                 🟢 LIVE SERVICE ONLINE (RUNNING COMMIT be0a0d9)                         |
|                 🟡 PHASE 2 REMEDIATION CHANGES ARE NOT YET DEPLOYED                     |
+-----------------------------------------------------------------------------------------+
| 1. Live Service Status:            200 OK across /, /api/health, /api/presets           |
| 2. Authentication Integrity:       200 OK (Synthetic user sign-in & JWT verification)   |
| 3. Tamper Resistance:              PASS (Tampered token rejected with HTTP 401)         |
| 4. Deployed Commit SHA:            be0a0d9 (Remote origin/main)                         |
| 5. Local HEAD Commit SHA:          89210b0 (3 commits ahead: 96c572f, eb0824f, 89210b0) |
| 6. Phase 2 Changes Live?:          NO. Phase 2 security changes remain in local git.    |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Live Service Checks

| Endpoint | Method | Live HTTP Status | Response Findings | Security & Safety Findings |
|---|:---:|:---:|---|---|
| `/` | `GET` | **200 OK** | React 18 SPA delivered cleanly; `<title>NEFROAI-X — Renal Clinical Decision Support</title>`. | Zero secrets leaked in HTML source. |
| `/api/health` | `GET` | **200 OK** | `"status": "ok"`, `"service": "nefroai-x-api"`, `"storage_backend": "sqlite"`, `"pipeline_loaded": true`, `"protected_model_sha256": "9217fbbe..."`. | Non-blocking; no expensive training triggered; zero secrets leaked. |
| `/api/presets` | `GET` | **200 OK** | Returns 4 standard clinical presets: `healthy`, `high_risk_ckd`, `discordant_false_assurance`, `si_units_healthy`. | Zero secrets leaked in preset definitions. |

---

## 3. Synthetic Authentication Checks

Testing was conducted strictly using synthetic, non-clinical test credentials (`clinician_qa_2_6`):

1. **User Registration / Sign-In (`POST /api/auth/signup` & `POST /api/auth/signin`):**
   - Status: **200 OK**
   - Result: Authenticated successfully with PBKDF2-HMAC-SHA256 password hashing.
   - Bearer token issued cleanly: `[REDACTED - 187 characters]`.
2. **Protected Route Authorization (`GET /api/auth/me`):**
   - Header: `Authorization: Bearer <valid_token>`
   - Status: **200 OK**
   - Result: Decoded user claims correctly verified (`sub: clinician_qa_2_6`, `role: Nephrologist`).
3. **Cryptographic Tamper Resistance (`GET /api/auth/me` with modified signature):**
   - Header: `Authorization: Bearer <tampered_token>`
   - Status: **401 Unauthorized**
   - Result: `BadTimeSignature` caught; modified token immediately rejected.
4. **Secret Exposure Audit:**
   - Zero tokens or secret keys were printed to terminal logs or included in public test reports.

---

## 4. Deployment Identity & Version Comparison

An exact commit comparison was conducted between the local repository, remote GitHub repository, and live container telemetry:

| Scope | Commit SHA | State Description |
|---|:---:|---|
| **Live Deployed Container** | `be0a0d984d1d13e40d1462bd5b0c3cfdae86eadf` (`be0a0d9`) | Running commit pushed prior to Phase 2 remediation. |
| **Remote GitHub `origin/main`** | `be0a0d984d1d13e40d1462bd5b0c3cfdae86eadf` (`be0a0d9`) | Current GitHub tracking branch. |
| **Local HEAD** | `89210b0dfb4fbc1a3a72f2e741267750f7307b91` (`89210b0`) | Local branch, **3 commits ahead** of remote. |

### Confirmation: Are Phase 2 Changes Live?
**NO.** The live deployment does **not** yet contain the Phase 2 remediation changes:
1. **Health Telemetry:** The live `/api/health` response does not yet contain `"storage_classification": "DEMONSTRATION_EPHEMERAL"` or `"is_ephemeral_demo": true` (introduced in `89210b0`).
2. **UI Warning Banner:** The live React frontend does not yet display the `PUBLIC DEMONSTRATION RUNTIME — STORAGE IS EPHEMERAL` non-dismissible warning banner (introduced in `89210b0`).
3. **Cause:** The local commits (`96c572f`, `eb0824f`, `89210b0`) have **not been pushed to GitHub**. When the operator triggered the deployment on Render, Render pulled the latest commit present on GitHub `origin/main` (`be0a0d9`).

---

## 5. Safety & Demonstration Storage Status

1. **Storage Backend in Live Container:** `sqlite` (`runs/local_cdss.db`).
2. **Ephemerality Reality:** The live database remains on the ephemeral container filesystem. Records saved during this test will be lost if the container sleeps or redeploys.
3. **Data Protection:** Zero real patient information or PHI was submitted during verification. All test records used synthetic prefixes (`clinician_qa_2_6`).

---

## 6. Remaining Issues & Final Recommendation

### Issues Remaining:
- The Phase 2 security remediations (hardcoded secret elimination, production secret enforcement, UI demo warning banner, and storage classification) are completed and tested locally, but are **not yet running on the live website**.

### Final Recommendation:
1. **The environment is fully prepared:** Because the operator has already added `NEFROAI_JWT_SECRET` to the Render Dashboard Environment settings, the cloud environment is **100% ready** to run the production-enforced code without crashing.
2. **Authorized Action to Deploy:**
   To make Phase 2 live, the operator must authorize executing:
   ```bash
   git push origin main
   ```
   Render's `Auto-Deploy: On Commit` will immediately pull commit `89210b0`, build the updated Docker container, and serve the fully remediated application with the non-dismissible warning banner and production secret gating.
