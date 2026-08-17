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

COPY . .

# /var/log/chronolegal: app/core/logging.py creates this and writes a
# rotating file sink to it whenever APP_ENV=production. Confirmed via CI's
# docker-compose-prod-smoke job that without this, the non-root `appuser`
# below hits PermissionError on that mkdir and the backend crashes at
# startup — this bug was latent until this session's build.target fix made
# "production" invocations actually use this stage (and therefore appuser)
# for the first time.
RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /var/log/chronolegal && \
    chown -R appuser:appuser /app /var/log/chronolegal
USER appuser

EXPOSE 8000
# Shell form (not exec-form JSON array) so ${PORT:-8000} is expanded by the
# shell at container startup: PaaS hosts like Render inject PORT and expect
# the process to bind to it, while Docker Compose never sets PORT and must
# keep defaulting to 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4 --loop uvloop
