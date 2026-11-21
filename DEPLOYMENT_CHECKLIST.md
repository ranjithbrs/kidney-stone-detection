# NEFROAI-X — Cloud Deployment Checklist & Operations Guide

**Target Cloud Platform**: [Render](https://render.com/) (Web Service with Docker runtime)  
**Service URL**: [https://kidney-stone-detection-0x56.onrender.com/](https://kidney-stone-detection-0x56.onrender.com/)  
**Alternative Platforms Supported**: Railway, Google Cloud Run, AWS App Runner, Self-Hosted Docker  

---

## 1. Pre-Deployment Verification Checklist

Before pushing commits to the production branch:

- [x] **Frontend Production Build**: Run `npm --prefix frontend run build` to verify `frontend/dist/` compiles without errors.
- [x] **Lightweight Health Check**: Verify that `GET /api/health` returns in `< 50ms` and does not invoke ML training or cross-validation.
- [x] **Unit & Regression Tests**: Verify that `pytest tests/` and `python src/run_test_suite.py` pass with 100% success rate.
- [x] **Docker Multi-Stage Build**: Ensure Dockerfile builds both frontend assets (Stage 1: `node:20-alpine`) and runtime container (Stage 2: `python:3.10-slim`).
- [x] **Non-Root Execution**: Ensure the container runs as non-privileged user `nefroai` (UID 1001).

---

## 2. Render Web Service Configuration (Dashboard Settings)

Refer to the Render Service Settings pane:

### A. Build & Runtime Settings
| Setting Name | Recommended Production Value | Description |
|:---|:---|:---|
| **Service Type** | Web Service | Standard HTTP web service |
| **Environment** | Docker | Builds image using repo's `Dockerfile` |
| **Region** | Oregon (US West) or nearest region | Data locality |
| **Branch** | `main` | Production release branch |
| **Root Directory** | *(leave blank / root)* | Monorepo root directory |
| **Dockerfile Path** | `./Dockerfile` | Multi-stage production Dockerfile |
| **Docker Build Context Directory** | `.` | Full repository root context |
| **Auto-Deploy** | `On Commit` (Yes) | Automatically deploys on git push |

### B. Health Checks (CRITICAL)
In your Render Service Settings under **Health Checks**:
- **Health Check Path**: Set to `/api/health` (do **not** leave empty).
  - *Why this is essential*: An empty health check path defaults to HTTP GET `/`, which loads the entire React HTML file. Setting `/api/health` ensures Render's monitoring agent receives an instant 200 OK without loading client assets.

---

## 3. Required Environment Variables

Configure these in the Render Dashboard under **Environment**:

| Variable Name | Required? | Example / Recommended Value | Purpose |
|:---|:---:|:---|:---|
| `PORT` | Auto-set by Render | `10000` | Port uvicorn binds to inside the container |
| `SECRET_KEY` | **YES** | *(Click "Generate" in Render)* | Secret for cryptographic signing |
| `NEFROAI_JWT_SECRET` | **YES** | Same value as `SECRET_KEY` | Primary key for signing clinician JWT session tokens |
| `MPLCONFIGDIR` | **YES** | `/tmp/matplotlib` | Writable directory for Matplotlib cache in non-root container |
| `DATABASE_URL` | Optional | `postgresql://user:pass@host:5432/nefroai` | Cloud PostgreSQL database for patient store. If omitted, automatically uses local SQLite |
| `ALLOWED_ORIGINS` | Optional | `https://kidney-stone-detection-0x56.onrender.com` | Allowed CORS origins for browser security |

> [!IMPORTANT]
> If `SECRET_KEY` and `NEFROAI_JWT_SECRET` are not set, the application generates a random ephemeral key at startup. This will log out all signed-in clinicians on every application restart. Always generate a static secret in Render.

---

## 4. Post-Deployment Verification (Smoke Tests)

Immediately after Render finishes deploying (Status: `Live`):

1. **System Health Probe**:
   ```bash
   curl -i https://kidney-stone-detection-0x56.onrender.com/api/health
   ```
   *Expected response*: HTTP 200 OK with JSON:
   ```json
   {
     "status": "ok",
     "service": "nefroai-x-api",
     "pipeline_loaded": true,
     "protected_model_sha256": "f8a8cd7f86cd532e8cb2660c86ca78348fb4430f27bcc8765931a0fcf2f73fe5"
   }
   ```

2. **Web Portal Verification**:
   - Open `https://kidney-stone-detection-0x56.onrender.com/` in your browser.
   - Verify the navigation bar, Patient Profile form, and Presets bar render cleanly.

3. **Clinical Preset Assessment**:
   - Click the **🟢 Healthy Cohort** preset button.
   - Click **Run Multi-Engine CKD Screening**.
   - Verify Engine 1 shows low risk (0.0%), Engine 2 shows KDIGO G1A1, and Engine 3 shows 0.0% KFRE failure risk.
   - Click **Clear Form** to verify form reset behavior.
   - Click the **🔴 High Risk CKD** preset button and verify high-risk escalation.

4. **Authentication Check**:
   - Create an account using the left sidebar "Create Account" modal.
   - Verify signed-in banner displays your username.
   - Reload the browser page to ensure session persistence.

---

## 5. Rollback & Troubleshooting Procedures

### If Deployment Returns HTTP 503
1. Check Render deploy logs for memory limits:
   - Ensure Render Free Tier instance (512MB RAM) has not been exceeded.
   - Confirm `/api/health` does not invoke model retraining.
2. Verify Health Check Path:
   - In Render Settings, confirm **Health Check Path** is set to `/api/health`.

### If Database Fails
- The application automatically falls back to SQLite (`runs/local_cdss.db`). If you intended to use PostgreSQL, check that `DATABASE_URL` uses the correct user, password, and port (e.g. port 6543 for PgBouncer pooler).

### Rollback Command
If an emergency rollback is required:
```bash
git revert HEAD --no-edit
git push origin main
```
Render will automatically detect the commit and re-deploy the previous working build.
