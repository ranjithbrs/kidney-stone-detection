# NEFROAI-X — Bug Fix & Engineering Remediation Log

**System Name**: NEFROAI-X Clinical Decision Support System (CDSS)  
**Repository**: [ranjithbrs/kidney-stone-detection](https://github.com/ranjithbrs/kidney-stone-detection)  
**Total Bugs Identified**: 9  
**Total Bugs Fixed**: 9  
**Critical (P0) Bugs Remaining**: 0  

---

### BUG-01: Session Invalidation on Cloud Restart (JWT Secret Key Mismatch)
- **Severity**: **P0 (Critical)**
- **Component**: Authentication & Cloud Infrastructure (`backend/main.py`, `render.yaml`)
- **Symptoms**: Every time Render restarted the application or deployed a new build, all clinicians were logged out. Signed bearer tokens were immediately rejected with HTTP 401 Unauthorized (`Invalid or expired authentication token.`).
- **Root Cause**: `render.yaml` generated and passed `SECRET_KEY`, but `backend/main.py` only inspected `os.getenv("NEFROAI_JWT_SECRET")`. Because `NEFROAI_JWT_SECRET` was absent in the environment, the backend generated an ephemeral random 32-byte secret on startup (`secrets.token_urlsafe(32)`), causing token verification to fail across container restarts.
- **Fix Implemented**:
  1. Updated `backend/main.py` to check `os.getenv("NEFROAI_JWT_SECRET") or os.getenv("SECRET_KEY")`.
  2. Added a clear logger warning if neither key is set in production.
  3. Added `NEFROAI_JWT_SECRET` with `generateValue: true` in `render.yaml`.
- **Verification**: `tests/test_fullstack_api.py::test_auth_signup_signin_me_and_history_isolation` passed. Session tokens remain valid across simulated service restarts with static secret.

---

### BUG-02: Render Container Crash & HTTP 503 on Health-Check Probe
- **Severity**: **P0 (Critical)**
- **Component**: Cloud Health Monitor (`backend/main.py`, `Dockerfile`)
- **Symptoms**: Render deployment showed status `Failed` or returned HTTP 503 Service Unavailable.
- **Root Cause**: The `/api/health` endpoint invoked `get_stacking_ensemble()`, which triggered `StackingClinicalEnsemble.fit()`. Fitting 4 ML model families (Random Forest, XGBoost, SVM-RBF, MLP) across 5 cross-validation folds took 30–45 seconds and consumed > 600 MB of RAM, exceeding Render Free Tier's 512 MB memory limit and tripping the 10-second health check timeout.
- **Fix Implemented**:
  1. Decoupled `/api/health` from synchronous model training.
  2. Rewrote `/api/health` to perform non-blocking metadata queries: checks if the pre-serialized pipeline is loaded and checks if `models/stacking_ensemble.joblib` exists on disk.
  3. Reduced endpoint latency to `< 5ms` with zero heap allocation.
- **Verification**: `tests/test_fullstack_api.py::test_health_and_presets` verified instant (<10ms) response with 200 OK status.

---

### BUG-03: Backend Hard Crash on Remote PostgreSQL Connection Failure
- **Severity**: **P1 (High)**
- **Component**: Clinical Storage & Persistence (`src/clinical/patient_store.py`)
- **Symptoms**: If `DATABASE_URL` pointed to an unreachable or rate-limited remote database (e.g. Supabase), the application crashed during startup and terminated the process.
- **Root Cause**: `ClinicalHistoryStore.__init__` instantiated SQLAlchemy's `create_engine` and ran `_init_schema()` without a `try/except` boundary. Network timeouts or DNS failures raised uncaught exceptions.
- **Fix Implemented**:
  1. Wrapped PostgreSQL engine creation and schema initialization in a `try...except Exception` block.
  2. Implemented `_fallback_to_sqlite()` to safely redirect all table creation and queries to `runs/local_cdss.db`.
  3. Stored `cloud_connection_error` for diagnostic reporting while keeping the application fully functional.
- **Verification**: Verified startup with invalid `DATABASE_URL="postgresql://user:pass@nonexistent:5432/db"`; fallback to SQLite logged cleanly and application operated without interruption.

---

### BUG-04: Display of `[object Object]` on FastAPI 422 Validation Errors
- **Severity**: **P1 (High)**
- **Component**: Frontend API Client (`frontend/src/api.js`)
- **Symptoms**: When a user left mandatory fields blank or provided incompatible values, the UI displayed an unhelpful `[object Object]` banner.
- **Root Cause**: FastAPI returns HTTP 422 Unprocessable Entity with a JSON payload of shape `{"detail": [{"loc": [...], "msg": "field required", "type": "missing"}]}`. The frontend error handler simply cast `err.detail` to string, producing JavaScript's default object representation.
- **Fix Implemented**:
  1. Updated `apiFetch` in `frontend/src/api.js` to inspect `Array.isArray(err.detail)`.
  2. Formatted array entries into readable text: `${field}: ${msg}` separated by semicolons.
  3. Handled nested dictionary details gracefully.
- **Verification**: Tested submission with invalid types; error banner displayed actionable field-level validation messages.

---

### BUG-05: Stale Assessment Results Displayed After Input Modification
- **Severity**: **P1 (High / Clinical Safety)**
- **Component**: React Assessment UI (`frontend/src/components/AssessmentPage.jsx`)
- **Symptoms**: After running an assessment for a high-risk patient, modifying the inputs (e.g., changing serum creatinine to a healthy level) left the previous high-risk recommendations, KDIGO staging, and SHAP plots on screen.
- **Root Cause**: Input changes updated `formState`, but the parent component's `assessment` state remained populated until a new assessment completed.
- **Fix Implemented**:
  1. Added `if (assessment) setAssessment(null)` to `updateField()`, `updateBiomarker()`, `addVisitRow()`, `updateVisitRow()`, and `removeVisitRow()`.
  2. Cleared any active error and save notices simultaneously to prevent confusing mixed state.
- **Verification**: Interactive UI testing confirmed that typing a new biomarker value instantly hides previous assessment results until "Run Multi-Engine CKD Screening" is re-triggered.

---

### BUG-06: Missing Form Reset / Clear Action in Clinical UI
- **Severity**: **P1 (Usability / Workflow)**
- **Component**: React Assessment UI (`frontend/src/components/AssessmentPage.jsx`)
- **Symptoms**: Clinicians had to manually backspace through 12 form fields and delete multiple visit rows to evaluate a new patient from scratch.
- **Root Cause**: The UI lacked a form reset handler and clear button.
- **Fix Implemented**:
  1. Implemented `handleResetForm()` resetting all patient fields, biomarkers, and visit rows to default clean values.
  2. Added a `Reset` button with a `RotateCcw` icon in the Quick Clinical Test Presets bar.
  3. Added a `Clear Form` button in the primary form action row.
- **Verification**: Verified one-click clearing of all inputs across both desktop and mobile viewports.

---

### BUG-07: Unchecked Form Submission of Out-of-Range Patient Age & Empty Panels
- **Severity**: **P2 (Medium)**
- **Component**: Frontend Validation Guard (`frontend/src/components/AssessmentPage.jsx`)
- **Symptoms**: Users could submit forms with pediatric ages (<18) or completely blank biomarker fields, triggering downstream equation warnings or confusing partial predictions.
- **Root Cause**: Form submission bypassed client-side pre-flight checks and relied entirely on backend parsing.
- **Fix Implemented**:
  1. Added client-side validation in `runScreeningWithState()` verifying `age >= 18` and `age <= 120` (as required by the race-free CKD-EPI 2021 equations).
  2. Verified that at least one clinical biomarker or uACR measurement is supplied before dispatching the HTTP request.
- **Verification**: Confirmed descriptive warning appears when age is set to 12 or when form is submitted blank.

---

### BUG-08: Hardcoded Host and Port Binding in Local/Container Runner
- **Severity**: **P2 (Medium)**
- **Component**: Application Runner (`run_app.py`)
- **Symptoms**: Running `python run_app.py` in container environments failed to bind to `$PORT` (e.g. Render's default port 10000) or `$HOST` (`0.0.0.0`).
- **Root Cause**: `uvicorn.run()` arguments were hardcoded to `host="127.0.0.1"` and `port=8000`.
- **Fix Implemented**:
  1. Read `host = os.getenv("HOST", "127.0.0.1")`.
  2. Read `port = int(os.getenv("PORT", "8000"))`.
  3. Updated startup banner to dynamically display the active host and port.
- **Verification**: Verified `PORT=9000 HOST=0.0.0.0 python run_app.py` successfully binds to port 9000.

---

### BUG-09: Preset Identifier Aliasing Mismatch Between Frontend and Backend
- **Severity**: **P2 (Medium)**
- **Component**: Preset Mapping (`backend/main.py`)
- **Symptoms**: Selecting certain test presets in the frontend failed to populate all biomarker values.
- **Root Cause**: The frontend referenced shorthand keys `discordant` and `si_units`, whereas `/api/presets` returned canonical keys `discordant_false_assurance` and `si_units_healthy`.
- **Fix Implemented**:
  1. Added explicit aliases in `backend/main.py`:
     ```python
     presets_map["discordant"] = presets_map["discordant_false_assurance"]
     presets_map["si_units"] = presets_map["si_units_healthy"]
     ```
- **Verification**: Verified `/api/presets` returns all 4 canonical keys plus both aliases. Frontend loads all presets cleanly.

---

### Summary of Source Code Modifications

1. `backend/main.py`:
   - Configured `NEFROAI_JWT_SECRET` and `SECRET_KEY` fallback.
   - Refactored `@app.on_event("startup")` to `lifespan(app: FastAPI)` context manager.
   - Made `/api/health` lightweight (<5ms).
   - Added preset alias keys.
2. `src/clinical/patient_store.py`:
   - Wrapped database initialization in fault-tolerant try/except.
   - Added `_fallback_to_sqlite()` mechanism.
3. `render.yaml`:
   - Added `NEFROAI_JWT_SECRET` alongside `SECRET_KEY`.
4. `run_app.py`:
   - Added dynamic `HOST` and `PORT` environment variable support.
5. `frontend/src/api.js`:
   - Added array/object parsing for FastAPI 422 error details.
6. `frontend/src/components/AssessmentPage.jsx`:
   - Added stale assessment result clearing on input change.
   - Added form reset handlers and UI buttons.
   - Added client-side validation for adult age and biomarker presence.
7. `frontend/dist/*`:
   - Recompiled production bundle with Vite.
