# NEFROAI-X — Final Deployment Status & Live Verification

**Deployment Target:** Render Web Service (`kidney-stone-detection`)  
**Public Live URL:** [https://kidney-stone-detection-0x56.onrender.com](https://kidney-stone-detection-0x56.onrender.com)  
**Verification Date:** November 21, 2026  
**Status:** 🟢 **OPERATIONAL (HTTP 200)**  

---

## 1. Live Deployment Health Matrix

Live verification was performed against the live container endpoint `https://kidney-stone-detection-0x56.onrender.com`:

| Endpoint | Method | Live HTTP Status | Verification Finding |
|---|:---:|:---:|---|
| `/` | `GET` | **200 OK** | React 18 SPA served with title `NEFROAI-X — Renal Clinical Decision Support` |
| `/api/health` | `GET` | **200 OK** | Health check non-blocking; pipeline loaded; model SHA-256 confirmed |
| `/api/presets` | `GET` | **200 OK** | 4 clinical reference presets loaded (`healthy`, `high_risk_ckd`, `discordant`, `si_units`) |
| `/api/auth/signup` | `POST` | **200 OK** | User registration functional with PBKDF2 password hashing |
| `/api/auth/signin` | `POST` | **200 OK** | Cryptographic bearer token issued (TTL: 86,400s) |
| `/api/assess` | `POST` | **200 OK** | Full 3-engine assessment executed, KDIGO staged, Safety-Max tier computed |
| `/api/explain` | `POST` | **200 OK** | Live TreeSHAP values, LIME decision rules, and XAI concordance computed |
| `/api/history` | `GET` | **200 OK** | User-scoped patient history query functional and isolated |

---

## 2. Live Health Payload

Querying `GET https://kidney-stone-detection-0x56.onrender.com/api/health` returns:

```json
{
  "status": "ok",
  "service": "nefroai-x-api",
  "storage_backend": "sqlite",
  "cloud_postgres_connected": false,
  "pipeline_loaded": true,
  "protected_model_sha256": "9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826",
  "xgboost_active": false,
  "survival_ml_status": "DEFERRED_PENDING_APPROVED_COHORT"
}
```

---

## 3. UI Fidelity & Clinical Layout Verification

The live deployment matches the clinician-focused UI specifications:

1. **Patient Inputs Panel (Panel 01):**
   - Demographics (Age, Sex, KFRE Region)
   - 10 Consensus Biomarkers (`hemo`, `sg`, `pcv`, `rc`, `al`, `htn`, `sc`, `bu`, `dm`, `bgr`)
   - Longitudinal Visit History table with date pickers, serum creatinine, uACR, and blood pressure.
   - Quick presets: 🟢 Healthy Cohort, 🔴 High-Risk CKD, ⚠️ Discordant, 🌍 EU/UK SI Units.
2. **Multi-Engine Clinical Results (Panel 02):**
   - **Safety-Max Arbitration Banner:** Displays high-priority clinical action tiers (`NEPHROLOGY_REFERRAL_PRIORITY`) and guideline-directed recommendations.
   - **Engine 1 (ML Screening):** Displays Champion RF probability, 4-Family Stacking probability, CRI quality score, and Conformal prediction set ($C_\alpha = \{1\}$).
   - **Engine 2 (KDIGO CGA Staging):** Highlights the interactive 2D KDIGO heat matrix cell (e.g. G4-A3 Very High Risk) and reports race-free CKD-EPI 2021 eGFR.
   - **Engine 3 (Trajectory & KFRE):** Reports Tangri 2-Year and 5-Year kidney failure probabilities and verifies $\ge 90\text{d}$ chronicity vs AKI.
   - **Attestation & Export:** Emits cryptographic SHA-256 seal and allows report exports in PDF, CSV (CWE-1236 sanitized), JSON, and TXT formats.

---

## 4. Operational Instructions for Render

### Environment Variables
In the Render Web Service settings, the application operates seamlessly with zero required configuration due to built-in fallbacks. For enhanced enterprise persistence:

| Variable | Recommended Value | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | Persistent PostgreSQL connection (overrides ephemeral SQLite) |
| `NEFROAI_JWT_SECRET` | 64-char hex string | Production authentication signing key |
| `ALLOWED_ORIGINS` | `https://kidney-stone-detection-0x56.onrender.com` | Additional explicit CORS origins |

### Health Check Configuration
- In Render Dashboard > **Settings** > **Health Checks**:
  - Set **Health Check Path** to: `/api/health`
  - This ensures Render's load balancer monitors application readiness without triggering ML retraining.
