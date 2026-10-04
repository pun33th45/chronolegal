# =============================================================================
# ChronoLegal Backend - Multi-stage Dockerfile
# =============================================================================

# --- Base stage ---
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# --- Development stage ---
FROM base AS development

COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- Production stage ---
FROM base AS production

# Bake the embedding model and reranker into the image so a cold container
# never downloads ~530MB from HuggingFace before it can bind its port.
# HF_HOME lives outside /app so `COPY . .` below can't shadow it. The
# LegalBERT id is byte-identical (pytorch_model.bin SHA-256) to the local
# backend/.model_cache/legalbert copy used to build the existing vectors.
ARG LEGALBERT_MODEL=nlpaueb/legal-bert-base-uncased
ARG RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV HF_HOME=/opt/hf-cache
RUN python -c "\
from transformers import AutoModel, AutoTokenizer; \
from sentence_transformers import CrossEncoder; \
AutoTokenizer.from_pretrained('${LEGALBERT_MODEL}'); \
AutoModel.from_pretrained('${LEGALBERT_MODEL}'); \
CrossEncoder('${RERANKER_MODEL}')"

COPY . .

# /var/log/chronolegal: app/core/logging.py creates this and writes a
# rotating file sink to it whenever APP_ENV=production. Confirmed via CI's
# docker-compose-prod-smoke job that without this, the non-root `appuser`
# hits PermissionError on that mkdir and the backend crashes at startup.
# The entrypoint (run as root) fixes ownership of the runtime-mounted Chroma
# disk, then drops to appuser before starting the app.
RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /var/log/chronolegal && \
    sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appuser /app /var/log/chronolegal /opt/hf-cache
ENTRYPOINT ["/app/docker-entrypoint.sh"]

EXPOSE 8000
# Shell form (not exec-form JSON array) so ${PORT:-8000} is expanded by the
# shell at container startup: PaaS hosts like Render inject PORT and expect
# the process to bind to it, while Docker Compose never sets PORT and must
# keep defaulting to 8000.
#
# --workers 1 is required, not a tuning choice: CHROMA_MODE=embedded opens
# Chroma's PersistentClient in-process, which must not be shared by several
# processes, and upload progress, the cache fallback and the rate limiter
# are all per-process memory too.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --loop uvloop
