# NEFROAI-X: Docker & Reproducible Packaging Specification

**Document Version:** 1.0.0  
**Release Target:** NEFROAI-X Research Software Prototype (Phase 10 Deliverable)  
**Clinical Scope:** Chronic Kidney Disease (CKD) Clinical Decision Support System  
**Designation:** `INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE`  
**Deployment Restriction:** Local research-software environment only (`127.0.0.1` binding). Must never be exposed to public networks.

---

## 1. Executive Summary

This specification defines the containerization architecture, runtime dependency manifest, Dockerfile, Docker Compose orchestrator, and automated container verification procedure for NEFROAI-X.

The packaging strategy enforces:
1. **Mathematical Reproducibility:** Exact preservation of serialized scikit-learn model artifacts (`models/clinical_pipeline.joblib`), ensuring identical risk probabilities and KDIGO classification thresholds across environments.
2. **Clinical Safety by Design:** Hard isolation of the research engine, strict `127.0.0.1` loopback binding, explicit demonstration provenance tags, and absence of external telemetry or unauthenticated cloud endpoints.
3. **Least Privilege Runtime:** Execution under an unprivileged `nefroai` user (`uid=1001, gid=1001`) with read-only root system files and isolated temporary scratch directories.
4. **Data Hygiene & Secret Exclusion:** Automated prevention of secrets (`.env`, certificates, tokens) and restricted or unapproved cohorts (`datasets/external/`, raw images, non-renal clinical records) from entering the build context via a strict `.dockerignore` policy.

---

## 2. Environment & Serialized Model Dependency Audit

### 2.1 Host & Development Baseline
- **Python Version:** 3.10.0 (`v3.10.0:b494f59`, 64-bit AMD64)
- **Primary Model Serializer:** `joblib 1.6.0` wrapping `pickle` protocol 4
- **Serialized Production Pipeline:** `models/clinical_pipeline.joblib` (141 KB, SHA-256: `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826`)
- **Key Scientific Libraries:**
  - `scikit-learn`: 1.7.2
  - `numpy`: 2.1.3
  - `pandas`: 2.2.3
  - `shap`: 0.49.1
  - `numba`: 0.68.1 / `llvmlite`: 0.50.0
  - `lifelines`: 0.30.0
  - `reportlab`: 5.1.0
  - `streamlit`: 1.65.0

### 2.2 Serialized Pipeline Integrity Analysis
Inspection of `models/clinical_pipeline.joblib` using python `pickletools` confirms:
- **Pickle Protocol:** Protocol 4 (supported by Python 3.4 through Python 3.13+).
- **Embedded Architecture:** `pipeline.KidneyDiagnosticPipeline`, containing:
  - `ClinicalDataPreprocessor`: fitted median/mode imputers and `StandardScaler` fitted strictly on UCI CKD training split.
  - Tuned Champion Estimator: `RandomForestClassifier(n_estimators=50, random_state=42)`.
  - Feature Selector: Top-10 consensus biomarkers `['hemo', 'sg', 'pcv', 'rc', 'al', 'htn', 'sc', 'bu', 'dm', 'bgr']`.

---

## 3. Python 3.12 Migration Feasibility Assessment

A formal audit was conducted to evaluate migrating the production runtime from Python 3.10 to Python 3.12 (the current long-term supported CPython release).

### 3.1 Dependency Migration Matrix

| Component / Package | Baseline (3.10) | Python 3.12 Compatibility Status | Assessment & Technical Risk |
|---|---|---|---|
| `scikit-learn` | 1.7.2 | Compatible (Python 3.10–3.12 wheels available) | Model loads, but scikit-learn documentation explicitly cautions against cross-minor-version unpickling in high-stakes clinical domains due to internal tree indexing optimizations. |
| `numpy` | 2.1.3 | Compatible (Python 3.10–3.12 wheels available) | C-API ABI changes between Python 3.10 and 3.12 require identical minor versions for bit-for-bit floating-point reproducible predictions. |
| `numba` / `llvmlite` | 0.68.1 / 0.50.0 | Compatible on Linux | Required by SHAP TreeExplainer. Linux wheels exist for 3.12. |
| `lifelines` | 0.30.0 | Compatible | Pure Python / autograd-gamma / scipy based; compatible with 3.12. |
| `reportlab` | 5.1.0 | Compatible | Pre-built wheels exist for 3.12. |
| `streamlit` | 1.65.0 | Compatible | Supports 3.12. |
| `mysql-connector` | 2.2.9 | **INCOMPATIBLE** | Legacy pure-Python / C extension dated 2018. Fails installation on Python 3.12 due to removal of `distutils` and deprecated `use_2to3`. Used only by legacy auxiliary Flask portal (`App.py`). |
| `Flask` / `Werkzeug` | 2.1.2 | Deprecated on 3.12 | Uses `cgi` module removed in Python 3.13 and deprecated in 3.12. |

### 3.2 Migration Conclusion & Risk Recommendation
- **Decision:** **Retain Python 3.10-slim as the Primary Production Reproduction Container.**
- **Rationale:** 
  1. **Clinical Prediction Determinism:** Upgrading Python or scikit-learn without re-training and re-validating the champion model on held-out test splits violates clinical AI governance rules (AGENTS.md Rule 3: *The final held-out test set must never influence hyperparameter tuning or champion-model selection*, and Rule 1: *Preserve existing model artifacts unchanged*).
  2. **Pickle Deserialization Safety:** Retaining Python 3.10 ensures bit-level parity between the environment that generated the champion weights and the inference runtime.
  3. **Security Assessment of Python 3.10 (Legacy EOL Status):** Python 3.10 reached official upstream End-of-Life (EOL) in October 2026 and no longer receives official security patches from the Python core team. The Debian Bookworm base (`python:3.10-slim`) continues to receive Debian OS package updates, but CPython itself is frozen. Consequently, this container environment is designated strictly as a **legacy reproduction container**. For research reproducibility and local offline verification, running Python 3.10-slim as an unprivileged user (`nefroai`) strictly bound to `127.0.0.1` prevents remote exploitation, but it is **not security-current and must never be exposed to public or multi-tenant networks**.

---

## 4. Container Architecture & Security Hardening

### 4.1 Image Specifications
- **Base Image:** `python:3.10-slim` (Debian Bookworm)
- **Container User:** `nefroai` (`uid=1001, gid=1001`) — strictly non-root.
- **Root Filesystem:** Read-only except `/tmp` and dedicated named volumes.
- **Port Exposure:** `8501/tcp` bound exclusively to host loopback `127.0.0.1`.

### 4.2 Resource Boundaries
- **CPU Quota:** 2.0 Cores (configured in `compose.yaml`).
- **Memory Ceiling:** 2.0 GB (sufficient for Streamlit + SHAP TreeExplainer; measured host RSS: ~209 MB).

### 4.3 Pruned Dependencies for Compact Image Size
The development environment contained computer-vision packages (`torch 2.5.1`, `torchvision 0.20.1`, `ultralytics 8.3.38`, `opencv-python 4.10.0.84`) used for exploratory kidney-stone YOLO detection. These packages are **not** part of the CKD clinical decision support system (Engines 1, 2, and 3).
- **Pruning Action:** All PyTorch, YOLO, and OpenCV dependencies were excluded from `requirements.docker.txt`.
- **Image Size Reduction:**
  - With PyTorch + YOLO: ~4.2 GB uncompressed.
  - With Pruned Manifest (`requirements.docker.txt`): **~650 MB uncompressed**.

---

## 5. Artifact Manifest & Verification

### 5.1 Dockerfile Structure
The `Dockerfile` employs multi-stage layer caching:
1. **Base OS Layer:** Installs minimal runtime libraries (`libgomp1`, `curl`, `gcc`).
2. **User Creation:** Adds `nefroai:nefroai` system user.
3. **Dependency Layer:** Copies `requirements.docker.txt` and runs `pip install --no-cache-dir`.
4. **Application Payload Layer:** Copies only verified application code (`src/`, `models/clinical_pipeline.joblib`, `models/preprocessor_Dataset_A.joblib`, `datasets/clinical/dataset_A_uci_ckd.csv`, `templates/`, `static/`, `tests/`, `app_streamlit.py`).
5. **Security & Healthcheck Layer:** Configures non-root user, `MPLCONFIGDIR=/tmp/matplotlib`, `0.0.0.0` container listener with strict `127.0.0.1` host-only port mapping, and `/_stcore/health` healthcheck probe.

### 5.2 Build Exclusion (`.dockerignore`)
The `.dockerignore` file prevents the following assets from ever entering the image:
- Real credentials (`.env`, `*.pem`, `*.key`, `secrets.json`).
- Python virtual environments (`.venv/`, `venv/`).
- YOLO/PyTorch large weight binaries (`models/best.pt`, `models/yolo11n.pt`).
- Restricted / raw cohort data (`datasets/external/nhanes_2017_2018/raw/*.xpt`).
- Contaminant non-renal datasets (`datasets/clinical/dataset_B_kidney_stone.csv`, `dataset_C_simpson_kidney.csv`).
- Computer-vision image archives (`datasets/train/`, `datasets/valid/`, `datasets/test/`).
- Git history and IDE caches (`.git/`, `.idea/`, `.vscode/`).

---

## 6. Container Automated Verification Suite (`verify_container.py`)

To verify the container environment programmatically without relying on an interactive browser, the project provides `scripts/verify_container.py`.

### 6.1 Executed Checks & Results

The verification script was executed against the exact runtime dependencies:

```text
================================================================
NEFROAI-X Container Verification: 11/11 passed, 0 failed
================================================================
  [PASS] Python 3.10 runtime — Python 3.10.0
  [PASS] Protected asset SHA-256 hashes — verified 4 assets:
         clinical_pipeline.joblib, dataset_A_uci_ckd.csv,
         preprocessor_Dataset_A.joblib, clinical_input_reliability_mechanism.py
  [PASS] Core clinical library imports — numpy=2.1.3 sklearn=1.7.2 shap=0.49.1 lifelines=0.30.0 reportlab=5.1.0
  [PASS] Engine 1 — model load and predict_single — diagnosis='Chronic Kidney Disease (At Risk)' risk_probability=0.740
  [PASS] Engine 2 — eGFR + KDIGO staging — eGFR=71.4 mL/min/1.73m² GFR-cat=G2 Albumin-cat=A2
  [PASS] Engine 3 — KFRE calculator — KFRE 2yr=0.145 5yr=0.482 applicable=True
  [PASS] CD-CIRPVM — reliability mechanism — CRI score=0.28, missing=6, sanitized_keys=24
  [PASS] Report export — text report generation — text report generated: 2647 chars
  [PASS] Report export — PDF generation (reportlab) — PDF 168,436 bytes — magic bytes %PDF OK
  [PASS] Security — CSV formula injection sanitisation (CWE-1236) — CSV formula injection guard active — 6 assertions passed
  [PASS] Test suite — all test modules importable — 19 test modules importable
```

### 6.2 Full Test Suite Execution
In addition to the container verification script, the entire 19-module automated test suite was executed:
- **Result:** **349 passed, 0 failed** in 22.90 s.

---

## 7. Operator Instructions & Runbook

### 7.1 Prerequisites
- Docker Engine 24.0+ or Docker Desktop 4.25+ with Linux Containers enabled.
- Docker Compose v2.20+.

### 7.2 Build Command
To build the production container image locally:

```bash
docker build -t nefroai-x:latest -f Dockerfile .
```

To build without using cache:
```bash
docker build --no-cache -t nefroai-x:latest -f Dockerfile .
```

### 7.3 Run Command (Docker Compose — Recommended)
Launch the primary clinical application:

```bash
docker compose up -d nefroai-x
```

To run the automated test suite inside the container:
```bash
docker compose run --rm nefroai-test
```

To view logs:
```bash
docker compose logs -f nefroai-x
```

To gracefully stop the container:
```bash
docker compose down
```

### 7.4 Run Command (Docker CLI Direct)
If running without Docker Compose:

```bash
docker run -d \
  --name nefroai-x-app \
  -p 127.0.0.1:8501:8501 \
  --memory="2g" \
  --cpus="2.0" \
  --restart=no \
  nefroai-x:latest
```

### 7.5 Health Verification
Verify that the container is healthy and responding to probes:

```bash
curl -f http://127.0.0.1:8501/_stcore/health
```

Expected response:
```text
ok
```

Inspect Docker health status:
```bash
docker inspect --format='{{json .State.Health.Status}}' nefroai-x-app
```

Expected output:
```json
"healthy"
```

### 7.6 In-Container Diagnostic Verification
Run the 11-point clinical diagnostic script inside a running container:

```bash
docker exec -it nefroai-x-app python scripts/verify_container.py
```

---

## 8. Summary Table of Deliverables

| Deliverable Artifact | Path | Purpose / Description | Status |
|---|---|---|---|
| **Production Dockerfile** | [`Dockerfile`](file:///c:/Users/B%20Ranjith/Downloads/project/Dockerfile) | Hardened Python 3.10-slim container, non-root user, health check | **VERIFIED** |
| **Docker Ignore Rulebook** | [`.dockerignore`](file:///c:/Users/B%20Ranjith/Downloads/project/.dockerignore) | Excludes secrets, .venv, large weights, raw external datasets | **VERIFIED** |
| **Compose Orchestrator** | [`compose.yaml`](file:///c:/Users/B%20Ranjith/Downloads/project/compose.yaml) | Local-only port binding, resource limits, test runner profile | **VERIFIED** |
| **Pinned Manifest** | [`requirements.docker.txt`](file:///c:/Users/B%20Ranjith/Downloads/project/requirements.docker.txt) | Exact 93 core dependencies excluding heavy YOLO/PyTorch stack | **VERIFIED** |
| **Container Verifier** | [`scripts/verify_container.py`](file:///c:/Users/B%20Ranjith/Downloads/project/scripts/verify_container.py) | 11-point programmatic health check of E1, E2, E3, reports, hashes | **11/11 PASS** |
| **Full Test Suite** | `tests/test_*.py` | Complete 19-module regression and validation test suite | **349/349 PASS** |
| **Technical Documentation** | [`docs/NEFROAI_X_DOCKER_AND_REPRODUCIBLE_PACKAGING.md`](file:///c:/Users/B%20Ranjith/Downloads/project/docs/NEFROAI_X_DOCKER_AND_REPRODUCIBLE_PACKAGING.md) | Comprehensive engineering, security, and migration report | **DELIVERED** |

---

## 9. Regulatory & Diagnostic Disclaimer

> **INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE**  
> NEFROAI-X is an investigational Clinical Decision Support System (CDSS) developed for research and educational purposes. It does not provide definitive medical diagnoses, treatment prescriptions, or clinical management protocols. All calculations (including eGFR 2021, KDIGO CGA staging, and KFRE risk estimations) must be verified by a board-certified physician or nephrologist before any clinical application.
