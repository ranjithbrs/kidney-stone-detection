# =============================================================================
# NEFROAI-X Production Full-Stack Container (React 18 SPA + FastAPI)
# Targets Render / Railway / Cloud Run / Docker with non-root security.
# =============================================================================

# --- Stage 1: Build React + Vite Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build

# --- Stage 2: FastAPI Clinical Backend + SPA Host ---
FROM python:3.10-slim AS runtime

LABEL org.opencontainers.image.title="NEFROAI-X Full-Stack CDSS"
LABEL org.opencontainers.image.description="Investigational CKD screening & XAI prototype — not a standalone medical diagnosis device"

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
        libglib2.0-0 \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 nefroai \
    && useradd --uid 1001 --gid nefroai --shell /bin/bash --create-home nefroai

WORKDIR /app
RUN mkdir -p /app/runs /app/reports /tmp/matplotlib \
    && chown -R nefroai:nefroai /app /tmp/matplotlib

COPY requirements.docker.txt /tmp/requirements.docker.txt
RUN grep -vi '^mysql-connector' /tmp/requirements.docker.txt > /tmp/req-fullstack.txt \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/req-fullstack.txt \
    && rm -f /tmp/requirements.docker.txt /tmp/req-fullstack.txt

# Copy backend API, clinical engines, protected models & reference datasets
COPY backend/ /app/backend/
COPY src/ /app/src/
COPY models/clinical_pipeline.joblib /app/models/clinical_pipeline.joblib
COPY models/preprocessor_Dataset_A.joblib /app/models/preprocessor_Dataset_A.joblib
COPY models/stacking_ensemble.joblib /app/models/stacking_ensemble.joblib
COPY datasets/clinical/dataset_A_uci_ckd.csv /app/datasets/clinical/dataset_A_uci_ckd.csv
COPY supabase/ /app/supabase/
COPY .env.example /app/.env.example

# Copy compiled React production SPA bundle from Stage 1
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

RUN chown -R nefroai:nefroai /app

ENV PYTHONPATH="/app/src:/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PORT=8000
ENV NEFROAI_JWT_SECRET="nefroai-x-prod-cloud-secret-d8b3f2c9e7a4b1c8e6d5a2f0"
ENV NEFROAI_TOKEN_TTL_SECONDS=86400

USER nefroai
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
