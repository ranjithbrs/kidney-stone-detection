# NEFROAI-X: Environment, Dependency & Reproducibility Specification

**Document Version:** 1.0.0  
**Release Target:** NEFROAI-X v1.0 — Research Software Release Candidate  
**Date:** November 2026  
**Clinical Scope:** Chronic Kidney Disease (CKD) Clinical Decision Support System  
**Designation:** `INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE`  
**Deployment Restriction:** `LOCAL RESEARCH SOFTWARE — NO PUBLIC DEPLOYMENT`

---

## 1. Executive Summary

This document establishes the exact runtime configuration, dependency graph, environment reproducibility standards, and migration constraints for NEFROAI-X.

The system requires deterministic reproducibility across all three clinical engines:
1. **Engine 1:** UCI CKD binary risk classification and SHAP/LIME local explainability.
2. **Engine 2:** KDIGO 2024 CGA severity staging using the race-free CKD-EPI 2021 equation.
3. **Engine 3:** Longitudinal eGFR trajectory analysis (OLS / Linear Mixed-Effects Models) and 4-variable Tangri Kidney Failure Risk Equation (KFRE) reference calculator.

To maintain research integrity and prevent silent numerical drift, this document provides complete instructions for recreating the environment, running verification audits, and understanding Python runtime constraints.

---

## 2. Python Runtime Environment

### 2.1 Baseline Development Environment
- **Python Version:** CPython 3.10.0 (Release tag `v3.10.0:b494f59`, compiled Oct 4 2021, MSC v.1929 64-bit AMD64).
- **Virtual Environment Path:** `.venv/` (project-local).
- **Environment Invocation Standard:** Always invoke via `.venv\Scripts\python.exe` (Windows PowerShell / Command Prompt) or `.venv/bin/python` (POSIX).

### 2.2 Python Runtime Lifecycle & Security Status
- **Upstream CPython Status:** Python 3.10 reached official upstream **End-of-Life (EOL) in October 2026**. The Python core development team no longer issues security releases or bugfixes for the 3.10 branch.
- **Operating Classification:** The active Python 3.10 configuration is classified as a **Frozen Legacy Reproduction Environment**.
- **Security Implications:**
  - Because Python 3.10 is past EOL, this environment must **never** be hosted as a publicly accessible web service or bound to non-loopback network interfaces.
  - The software is intended strictly for local, air-gapped, or offline research verification and clinical decision support study.
  - The Docker container runtime enforces an unprivileged non-root user (`nefroai`, `uid=1001`), container-internal listening, and host-side loopback binding strictly to `127.0.0.1:8501`.

---

## 3. Python 3.12 Migration Analysis & Technical Blockers

A rigorous technical feasibility study was conducted to evaluate upgrading NEFROAI-X to Python 3.12 (the current long-term supported CPython release).

### 3.1 Dependency Migration Matrix

| Package / Module | Pinned Version (3.10) | Python 3.12 Support | Migration Assessment & Technical Blocker |
|---|---|---|---|
| `scikit-learn` | 1.7.2 | Compatible | While 1.7.2 has 3.12 wheels, scikit-learn core maintainers explicitly state that unpickling estimators across Python minor versions is not guaranteed for production clinical software due to internal tree indexing optimizations. Unpickling on 3.12 could produce subtle decision-tree leaf mismatches. |
| `numpy` | 2.1.3 | Compatible | C-API ABI changes between Python 3.10 and 3.12 can affect floating-point rounding at the 15th decimal place, altering boundary threshold classifications. |
| `numba` / `llvmlite` | 0.68.1 / 0.50.0 | Compatible | Pre-built Linux wheels exist, but Windows C-extensions require specific MSVC build tools. Tightly coupled to CPython bytecode format. |
| `lifelines` | 0.30.0 | Compatible | Pure Python with autograd-gamma and scipy; functions correctly on 3.12. |
| `reportlab` | 5.1.0 | Compatible | Fully compatible with 3.12. |
| `streamlit` | 1.65.0 | Compatible | Fully compatible with 3.12. |
| `mysql-connector` | 2.2.9 | **INCOMPATIBLE** | **BLOCKER:** Legacy library dating from 2018. Fails build and installation on Python 3.12 due to the removal of `distutils` and deprecated `use_2to3`. Required by auxiliary Flask portal (`App.py`). |
| `Flask` / `Werkzeug` | 2.1.2 | Deprecated | Relies on the standard library `cgi` module, which was deprecated in 3.12 and completely removed in Python 3.13. |

### 3.2 Decision & Future Migration Path
- **Current Decision:** **Retain Python 3.10 as the production reproduction environment.** Upgrading Python without retraining the champion model on training partitions violates clinical ML safety rules (preventing test set contamination and unvalidated weight re-serialization).
- **Future Migration Requirements:**
  1. Replace legacy `mysql-connector` with `mysql-connector-python>=8.3.0` or SQLAlchemy modern engine.
  2. Upgrade Flask/Werkzeug to modern 3.x stack or decouple the legacy Flask portal completely.
  3. Re-execute `src/tune_models.py` on training folds (`X_train`) under Python 3.12 to generate a bit-native Python 3.12 scikit-learn artifact.
  4. Perform non-inferiority testing against `models/clinical_pipeline.joblib` on the held-out test split.

---

## 4. Pinned Dependency Inventory

The application utilizes two distinct dependency manifests:

### 4.1 Full Development Environment (`requirements.txt`)
Contains all packages installed in the local virtual environment, including auxiliary tools, development test runners, and computer-vision libraries.

Key packages:
```text
altair==6.2.2
click==8.1.3
cloudpickle==3.1.2
coverage==7.16.2
Flask==2.1.2
formulaic==1.2.2
imbalanced-learn==0.14.2
joblib==1.6.0
lifelines==0.30.0
lime==0.2.0.1
matplotlib==3.9.2
mysql-connector==2.2.9
numba==0.68.1
numpy==2.1.3
pandas==2.2.3
pytest==8.3.4
pytest-cov==5.0.0
reportlab==5.1.0
scikit-learn==1.7.2
scipy==1.14.1
seaborn==0.13.2
shap==0.49.1
streamlit==1.65.0
```

### 4.2 Production Docker Runtime Manifest (`requirements.docker.txt`)
Contains exactly **93 pinned core dependencies** required for the three clinical engines, XAI suite, and Streamlit user interface.

**Deliberately Excluded from Production Container:**
- `torch==2.5.1` (PyTorch C++ backend — 1.8 GB)
- `torchvision==0.20.1` (Computer vision transforms)
- `ultralytics==8.3.38` & `ultralytics-thop==2.0.12` (YOLO architecture)
- `opencv-python==4.10.0.84` (OpenCV imaging library)

*Rationale:* The YOLO model (`models/best.pt`) is an auxiliary computer-vision kidney-stone detector. It is not part of the multimodal Chronic Kidney Disease (CKD) clinical decision support pipeline. Excluding it reduces the uncompressed container size from **~4.2 GB down to ~650 MB**.

---

## 5. Dependency Conflict & Health Verification

Execution of `pip check` confirms that the dependency graph is entirely clean and free of broken version requirements:

```powershell
.venv\Scripts\pip.exe check
# Output: No broken requirements found.
```

---

## 6. Protected Model Artifacts & Bit-Level Checksums

The following 4 serialized assets represent core scientific deliverables and must never be overwritten, retrained, or altered without formal clinical re-certification:

| Relative Path | Size | Expected SHA-256 Checksum | Verification Status |
|---|---|---|---|
| `models/clinical_pipeline.joblib` | 141,177 bytes | `9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826` | **VERIFIED OK** |
| `datasets/clinical/dataset_A_uci_ckd.csv` | 27,249 bytes | `147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc` | **VERIFIED OK** |
| `models/preprocessor_Dataset_A.joblib` | 26,601 bytes | `fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3` | **VERIFIED OK** |
| `src/clinical_input_reliability_mechanism.py` | 17,678 bytes | `f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0` | **VERIFIED OK** |

### Automated Verification Script
Run the following Python one-liner to verify all checksums on any workstation:

```powershell
& ".venv\Scripts\python.exe" -c "
import hashlib
files = {
    'models/clinical_pipeline.joblib': '9217fbbe3c74207f119fd91528f6c98997bda0220299cb80dcdec0be9dbfc826',
    'datasets/clinical/dataset_A_uci_ckd.csv': '147be021a0a1498db9328ed43d485b0755e80501e7541a37ad9dd889da953cbc',
    'models/preprocessor_Dataset_A.joblib': 'fae81c26a23117d496c69c7c9fb2a3852e2c14ed53b99dde1815dc23af2e39e3',
    'src/clinical_input_reliability_mechanism.py': 'f250cfeb5629c4b30f3beca571f4b9b098fbdd35155a82e9654f865bc5ebcdc0'
}
for f, exp in files.items():
    with open(f, 'rb') as fp:
        h = hashlib.sha256(fp.read()).hexdigest()
    assert h == exp, f'MISMATCH on {f}'
    print(f'OK: {f}')
"
```

---

## 7. Step-by-Step Environment Recreation Guide

### 7.1 Local Native Setup (Windows / macOS / Linux)

1. **Install Python 3.10.x:**
   Ensure Python 3.10 (preferably 3.10.0 to 3.10.14) is installed on the host.

2. **Clone the Repository:**
   ```bash
   git clone https://github.com/ranjithbrs/kidney-stone-detection.git
   cd kidney-stone-detection
   ```

3. **Initialize Isolated Virtual Environment:**
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. **Install Pinned Dependencies:**
   ```bash
   python -m pip install --upgrade pip==24.3.1
   pip install -r requirements.docker.txt
   ```

5. **Verify Environment Integrity:**
   ```bash
   python scripts/verify_container.py
   python -m pytest tests/ -q
   ```

6. **Launch Streamlit Web Application:**
   ```bash
   python -m streamlit run app_streamlit.py
   ```
   Navigate to `http://localhost:8501`.

---

## 8. Docker Packaging & Execution Guide

### 8.1 Docker Host Requirements
- Docker Engine 24.0+ or Docker Desktop 4.25+ with Linux Containers (WSL2 backend on Windows).
- Docker Compose v2.20+.

### 8.2 Build the Docker Image
```bash
docker build -t nefroai-x:latest .
```

### 8.3 Run via Docker Compose
```bash
# Launch the application in detached mode (bound to 127.0.0.1:8501)
docker compose up -d nefroai-x

# Verify health status
docker inspect --format='{{json .State.Health.Status}}' nefroai-x-app
# Output should return: "healthy"

# Execute in-container programmatic verification
docker exec -it nefroai-x-app python scripts/verify_container.py

# Run complete regression test suite inside container
docker compose run --rm nefroai-test

# Gracefully terminate
docker compose down
```

---

## 9. Regulatory & Clinical Disclaimer

> **INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE**  
> This software is an investigational Clinical Decision Support System (CDSS) designed for medical education and research into explainable artificial intelligence. It does not possess CE mark, FDA 510(k), SaMD certification, or clinical approval. It must **never** be used for primary diagnosis, patient prescription, or clinical triaging in human healthcare.
