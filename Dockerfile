# =============================================================================
# NEFROAI-X Clinical Decision Support System
# Docker Image — Python 3.10-slim (Debian Bookworm)
#
# Python version rationale:
#   The production model artifact (models/clinical_pipeline.joblib) was
#   serialised with pickle protocol 4 under scikit-learn 1.7.2 / Python 3.10.
#   scikit-learn 1.7.2 supports Python 3.10–3.12, and pickle protocol 4 is
#   readable by any Python ≥ 3.4.  However, numba==0.68.1 (SHAP dependency)
#   supplies pre-built wheels only for Python 3.10, 3.11 and 3.12 on Linux.
#
#   Python 3.12 migration assessment (see docs/ for full report):
#     - scikit-learn 1.7.2  ✅ supports 3.12
#     - numba 0.68.1        ✅ supports 3.12 (Linux wheel available)
#     - lifelines 0.30.0    ✅ supports 3.12
#     - shap 0.49.1         ✅ supports 3.12
#     - reportlab 5.1.0     ✅ supports 3.12
#     - mysql-connector 2.2.9 ❌ no 3.12 wheel (legacy; not critical for CKD UI)
#
#   Decision: python:3.10-slim is preserved as a legacy reproduction environment
#   to maintain exact parity with the serialized model weights and avoid unpickling
#   deviations. Note that Python 3.10 reached official upstream EOL in October 2026;
#   this container is intended exclusively for offline research verification and
#   must never be exposed to public networks. A future migration to Python 3.12+
#   will require retraining the champion model under Python 3.12.
#
# THIS CONTAINER IS A LOCAL RESEARCH-SOFTWARE ENVIRONMENT.
# IT IS NOT A PUBLIC CLINICAL SERVICE OR CERTIFIED MEDICAL DEVICE.
# =============================================================================

FROM python:3.10-slim AS base

LABEL org.opencontainers.image.title="NEFROAI-X CKD Clinical Decision Support System"
LABEL org.opencontainers.image.description="Investigational research software — not a certified medical device"
LABEL org.opencontainers.image.version="1.0.0-rc"
LABEL org.opencontainers.image.authors="NEFROAI-X Research Team"
LABEL nefroai.clinical.designation="INVESTIGATIONAL RESEARCH SOFTWARE — NOT A CERTIFIED MEDICAL DEVICE"

# ---------------------------------------------------------------------------
# System build dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libgomp1 \
        libglib2.0-0 \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Non-root runtime user (security: CWE-250 / OWASP principle of least privilege)
# ---------------------------------------------------------------------------
RUN groupadd --gid 1001 nefroai \
    && useradd --uid 1001 --gid nefroai --shell /bin/bash --create-home nefroai

# ---------------------------------------------------------------------------
# Application directory and writable runtime directories
# ---------------------------------------------------------------------------
WORKDIR /app

# Directories the application writes to at runtime
RUN mkdir -p \
        /app/runs/explainability/plots \
        /app/reports \
        /tmp/matplotlib \
    && chown -R nefroai:nefroai /app /tmp/matplotlib

# ---------------------------------------------------------------------------
# Python dependencies (installed as root, before switching user)
# Cache-friendly: copy manifest first so code changes don't bust this layer
# ---------------------------------------------------------------------------
COPY requirements.docker.txt /tmp/requirements.docker.txt

RUN pip install --no-cache-dir --upgrade pip==24.3.1 \
    && pip install --no-cache-dir -r /tmp/requirements.docker.txt

# ---------------------------------------------------------------------------
# Application source — copy only what the runtime needs
# ---------------------------------------------------------------------------
# Core source package
COPY src/                         /app/src/
# Streamlit launcher
COPY app_streamlit.py             /app/app_streamlit.py
# Legacy auxiliary portal and utility scripts (required for test suite and verification)
COPY App.py                       /app/App.py
COPY scripts/                     /app/scripts/
# Streamlit server configuration
COPY .streamlit/                  /app/.streamlit/
# Serialised model artefacts (protected; never retrain in container)
COPY models/clinical_pipeline.joblib      /app/models/clinical_pipeline.joblib
COPY models/preprocessor_Dataset_A.joblib /app/models/preprocessor_Dataset_A.joblib
# UCI CKD ground-truth dataset (required by test suite and SHAP population plots)
COPY datasets/clinical/dataset_A_uci_ckd.csv /app/datasets/clinical/dataset_A_uci_ckd.csv
# Static and template assets for UI
COPY static/                      /app/static/
COPY templates/                   /app/templates/
# Automated test suite
COPY tests/                       /app/tests/
# Environment template (NOT the real .env — secrets are injected at runtime)
COPY .env.example                 /app/.env.example

# Optional: XAI pre-generated plots (non-critical; missing files handled gracefully)
COPY runs/explainability/         /app/runs/explainability/

# Fix ownership for everything under /app
RUN chown -R nefroai:nefroai /app

# ---------------------------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------------------------
ENV PYTHONPATH="/app/src:/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Point Matplotlib to a writable temp directory (avoids config-dir warnings)
ENV MPLCONFIGDIR=/tmp/matplotlib
# Streamlit server listens on 0.0.0.0 inside container so Docker bridge can forward traffic
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# ---------------------------------------------------------------------------
# Switch to non-root user for all runtime operations
# ---------------------------------------------------------------------------
USER nefroai

EXPOSE 8501

# ---------------------------------------------------------------------------
# Health check — polls the Streamlit health endpoint
# Interval: 30 s   Timeout: 10 s   Start period: 60 s   Retries: 3
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

# ---------------------------------------------------------------------------
# Default command: launch the Streamlit application
# ---------------------------------------------------------------------------
CMD ["python", "-m", "streamlit", "run", "app_streamlit.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
