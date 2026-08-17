# ChronoLegal — Production Deployment Guide

---

## Overview

ChronoLegal ships as a fully Dockerised stack. Production deployment is a three-step process:

1. Provision a Linux server
2. Run `init_production.sh`
3. Configure domain + SSL

---

## Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| vCPUs | 4 | 8 |
| RAM | 16 GB | 32 GB |
| Disk | 100 GB SSD | 200 GB NVMe |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| GPU | None (slower LLM) | NVIDIA A10 / T4 |

**Recommended providers**: AWS EC2 (g4dn.xlarge), GCP (n2-standard-8), Hetzner (AX52).

---

## 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install make and other tools
sudo apt install make git curl unzip -y

# Clone the repository
git clone https://github.com/your-org/chronolegal.git
cd chronolegal
```

---

## 2. Production Environment Configuration

```bash
cp .env.example .env
nano .env
```

Required production values:

```dotenv
# === SECURITY (MUST change) ===
SECRET_KEY=<64-char random hex — python3 -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<another 64-char random hex>

# === Database ===
POSTGRES_DB=chronolegal_prod
POSTGRES_USER=chronolegal
POSTGRES_PASSWORD=<very-strong-password>

# === Redis ===
REDIS_PASSWORD=<strong-redis-password>

# === Domain ===
DOMAIN=yourdomain.com
CORS_ORIGINS=https://yourdomain.com

# === LLM (choose one) ===
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b

# OR cloud LLM for faster responses:
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o-mini
# OPENAI_API_KEY=sk-...

# === Environment ===
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
```

`APP_ENV` (not `ENVIRONMENT`) is the setting the backend actually reads
(`backend/app/core/config.py`). It gates two things: the insecure-default-secret
validator that refuses to boot with placeholder `SECRET_KEY`/`JWT_SECRET_KEY`/
`POSTGRES_PASSWORD`/`REDIS_PASSWORD` values, and whether `/api/docs`,
`/api/redoc`, `/api/openapi.json` are exposed at all (only in non-production).
Getting the variable name wrong means both silently do nothing (the config
model ignores unknown keys) — the container boots with `APP_ENV=development`
regardless of what you set `ENVIRONMENT` to, insecure defaults are accepted,
and the API docs stay exposed.

---

## 3. One-Command Production Init

```bash
chmod +x scripts/setup/init_production.sh
sudo scripts/setup/init_production.sh
```

This script:
1. Creates the Docker network
2. Starts all services in production mode
3. Runs Alembic migrations
4. Creates the admin user (prompts for email/password)
5. Pulls the Ollama model
6. Runs the data pipeline
7. Validates all services are healthy

---

## 4. SSL Certificate Setup

`nginx/default.conf` expects real certs at `/etc/nginx/ssl/fullchain.pem` and
`/etc/nginx/ssl/privkey.pem` inside the container, mounted read-only from
`./nginx/ssl` on the host (see the `nginx` service's volumes in
`docker-compose.yml`). `nginx/Dockerfile` bakes in a self-signed placeholder
at that same path purely so the image works out of the box in local dev —
the volume mount below shadows it, so **populate `nginx/ssl/` before
starting the `nginx` service**, or it will boot with the placeholder (or,
once the mount is in place, fail to start if `nginx/ssl/` is empty).

### Option A — Let's Encrypt (recommended for public servers)

```bash
# Install certbot
sudo apt install certbot -y

# Stop nginx temporarily (no-op if it isn't running yet)
docker compose stop nginx

# Issue certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certs into the volume nginx actually mounts
mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/fullchain.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/privkey.pem

# Start/restart nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile production up -d nginx

# Auto-renewal (add to cron)
echo "0 3 * * * certbot renew --quiet && docker compose restart nginx" | sudo crontab -
```

### Option B — Self-signed (internal/staging only)

```bash
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=yourdomain.com"
```

---

## 5. Nginx Configuration

Update `nginx/default.conf` — replace `server_name _` with your domain:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

Then reload:
```bash
docker compose exec nginx nginx -s reload
```

---

## 6. Start Production Stack

```bash
make prod
# OR
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile production up -d
```

---

## 7. Verify Deployment

```bash
# All services healthy?
docker compose ps

# Backend health endpoint (proxied by nginx at /health, not /api/health)
curl https://yourdomain.com/health

# Expected
# {"status":"healthy","app":"ChronoLegal","version":"1.0.0","environment":"production"}
```

Note: `/health` is a liveness check only — it confirms the backend process is
up and responding, not that Postgres/Redis/ChromaDB are reachable. A "healthy"
response does not by itself prove the database or cache are connected; check
`docker compose ps` (service healthchecks) and `docker compose logs backend`
for that.

Open in browser: `https://yourdomain.com`

---

## 8. GitHub Actions CI/CD

The `.github/workflows/cd.yml` pipeline automates deployment on every push to `main`.

### Setup

1. Add repository secrets in GitHub Settings → Secrets:

| Secret | Value |
|--------|-------|
| `GHCR_TOKEN` | GitHub Personal Access Token (write:packages) |
| `SSH_HOST` | Your server IP / hostname |
| `SSH_USER` | SSH username |
| `SSH_KEY` | Private SSH key (no passphrase) |
| `SSH_PORT` | SSH port (usually 22) |

2. The pipeline runs:
   - **CI** (`ci.yml`): lint → test → build (every push)
   - **CD** (`cd.yml`): build Docker images → push to GHCR → SSH into server → `docker compose pull && docker compose up -d` (on merge to `main`)

### SSH Key Setup
```bash
# Generate deployment key (on your local machine)
ssh-keygen -t ed25519 -f deploy_key -N ""

# Add public key to server
ssh-copy-id -i deploy_key.pub user@your-server

# Add private key to GitHub Secrets as SSH_KEY
cat deploy_key
```

---

## Monitoring

### Application Logs
```bash
# Live logs from all services
docker compose logs -f

# Backend only
docker compose logs -f backend

# Search for errors
docker compose logs backend | grep ERROR
```

### Container Resource Usage
```bash
docker stats
```

### Database Size
```bash
docker compose exec postgres psql -U chronolegal -d chronolegal_prod \
  -c "SELECT pg_size_pretty(pg_database_size('chronolegal_prod'));"
```

### ChromaDB Embedding Count
```bash
curl http://localhost:8001/api/v1/collections/legal_cases | python3 -m json.tool
```

---

## Backup & Restore

`scripts/backup/backup_db.sh` and `scripts/backup/restore_db.sh` wrap
PostgreSQL's own `pg_dump`/`pg_restore` (custom format, `-Fc` — compressed,
supports selective/parallel restore) via `docker compose exec postgres`, so
no extra tooling is required on the host or in any application image; the
`postgres:16-alpine` image already ships both binaries. This is a genuine,
tested capability — see `backend/tests/integration/test_backup_restore.py`
(full pg_dump → pg_restore round trip against disposable databases, verifying
both schema and data survive) and `backend/tests/unit/test_backup_retention.py`
(retention edge cases: zero/one/multiple backups, and the guarantee that the
newest backup is never deleted).

### Creating a backup
```bash
make backup
# or directly:
set -a; source .env; set +a
bash scripts/backup/backup_db.sh
```
Writes a timestamped `.dump` file to `./backups` (override with
`BACKUP_DIR=/path make backup`), refusing to leave a partial file behind if
`pg_dump` fails or produces empty output. Retention defaults to 14 days
(`BACKUP_RETENTION_DAYS=0` disables pruning); the single most recent backup
is never deleted, even if every backup is older than the retention window.

### Listing backups
```bash
ls -lh backups/
```

### Restoring a backup
**Never restore over the live production database to "test" a backup.**
Always verify a backup by restoring into a fresh, disposable database name
first:
```bash
make restore BACKUP=backups/chronolegal_20260101T020000Z.dump DB=chronolegal_restore_check
```
`restore_db.sh` refuses to run if the target database already exists,
unless `FORCE=--force` is explicitly passed — that flag exists only for the
genuine disaster-recovery case (the real database is gone or corrupted and
must be rebuilt in place), not for routine verification.

### Verifying a restore
After restoring into a disposable database, confirm it's actually usable —
don't trust a `pg_restore` exit code alone:
```bash
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d chronolegal_restore_check -c "\dt"
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d chronolegal_restore_check \
  -c "SELECT version_num FROM alembic_version;"   # must show the current head
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d chronolegal_restore_check \
  -c "SELECT COUNT(*) FROM legal_cases;"
```
Then drop the disposable database once satisfied:
```bash
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE chronolegal_restore_check;"
```

### Recovering from a failed deployment or real data loss
1. Stop the backend so nothing writes to the database mid-restore:
   `docker compose stop backend`.
2. Restore the most recent good backup with `FORCE=--force` **into the real
   database name** (only once you've already verified that exact backup file
   restores cleanly into a disposable database, per above).
3. Run `docker compose exec backend alembic current` to confirm the restored
   database is still at the expected head revision before restarting traffic.
4. `docker compose start backend`.

### ChromaDB
ChromaDB persists to the `chromadb_data` Docker volume. It rebuilds from
`legal_cases`/`case_chunks` via the data pipeline (`make data-pipeline`), so
it is not part of the PostgreSQL backup above; a raw volume snapshot remains
an option if re-embedding from scratch is too slow to be an acceptable
recovery path:
```bash
docker run --rm -v chronolegal_chromadb_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/chromadb_$(date +%Y%m%d).tar.gz /data
```

### Automating backups (cron)
No automated schedule is installed by anything in this repository — the
script above must be wired into cron (or a systemd timer) yourself:
```cron
0 2 * * * cd /path/to/chronolegal && set -a && . ./.env && set +a && bash scripts/backup/backup_db.sh >> /var/log/chronolegal-backup.log 2>&1
```

### Backup security
Treat backup files as sensitive production data — they contain full
database contents (including hashed passwords and any stored personal
data), not sanitized exports:
- `backups/` is gitignored (`.gitignore`); never commit a `.dump` file.
- Nothing in `docker-compose.yml`/nginx mounts or serves `backups/` — it is
  not reachable over HTTP by nginx, the frontend, or any other container.
- `backup_db.sh` writes backups `chmod 600` and the directory `chmod 700`.
- Database credentials are read from the environment (`.env`) at run time
  and are never written into a script, a backup filename, or a log line.

### Off-host replication (`sync_offhost.sh`)
**A backup living only in `./backups` on the same host as the database is
not disaster-recovery coverage** — it protects against database/container
corruption or an operator mistake, but not against loss of the host itself
(disk failure, accidental deletion, host compromise, the VM/server being
destroyed).

`scripts/backup/sync_offhost.sh` closes this gap without committing to any
specific cloud provider: it's plain `rsync` over SSH to any remote host you
already control (a second server, a NAS, a storage-only VPS, etc.) — no new
SDK or cloud subscription required. It is **disabled by default** (a no-op,
exit 0) unless you set:
```bash
OFFHOST_BACKUP_HOST=backup-user@backup-host.example.com
OFFHOST_BACKUP_PATH=/remote/path/to/store/backups
# optional:
OFFHOST_SSH_KEY=/path/to/private_key
```
Chain it after a backup in cron:
```cron
0 2 * * * cd /path/to/chronolegal && set -a && . ./.env && set +a && bash scripts/backup/backup_db.sh && bash scripts/backup/sync_offhost.sh >> /var/log/chronolegal-backup.log 2>&1
```
It never deletes a local backup — it only ever adds a remote copy — so a
failed sync (network issue, remote host down, wrong path) leaves local
backups completely intact; it just means off-host coverage is stale until
the next successful run. `rsync --checksum` verifies each transferred file
by content hash, not just size/timestamp, so a corrupted transfer gets
re-copied rather than silently accepted.

**As shipped, no off-host destination is configured** — this script is the
mechanism, not a working destination. You must point `OFFHOST_BACKUP_HOST`/
`OFFHOST_BACKUP_PATH` at real infrastructure you control before off-host
replication is actually happening.

---

## Scaling

### Multiple Backend Workers
```yaml
# docker-compose.override.yml
services:
  backend:
    deploy:
      replicas: 4
```

Update Nginx upstream to round-robin across replicas.

### External LLM (recommended for production)
Switch from local Ollama to OpenAI/Anthropic for:
- Faster responses (no local GPU required)
- Better answer quality
- No model management overhead

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

Cost estimate at gpt-4o-mini: ~$0.002 per query.

### Managed Databases
For production at scale, replace Docker-hosted databases:
- PostgreSQL → AWS RDS / Supabase / Neon
- Redis → AWS ElastiCache / Upstash
- ChromaDB → Qdrant Cloud / Weaviate Cloud

Update connection strings in `.env`.

---

## Updating ChronoLegal

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose up --build -d

# Run any new migrations
docker compose exec backend alembic upgrade head
```

---

## Rollback

```bash
# Roll back to previous image (if using GHCR tags)
docker compose pull backend:v1.2.0
docker compose up -d

# Roll back database migration
docker compose exec backend alembic downgrade -1
```

---

## College Demo Deployment (Free-Tier: Vercel + Koyeb + Supabase + Groq)

This is a separate, additive deployment path for a low-traffic college
demonstration — it does not replace anything above. The self-hosted Docker
Compose stack documented in the rest of this file remains the primary,
fully-featured deployment; nothing in this section changes it.

```
Vercel (React/Vite frontend)
        |
        v
Koyeb (FastAPI backend, existing Dockerfile)
   |              |
   |              +--> Groq API (LLM_PROVIDER=groq)
   |
   +--> Embedded Chroma (CHROMA_MODE=embedded, in-process, no separate service)
   |
   +--> HuggingFace embeddings (EMBEDDING_PROVIDER=huggingface, unchanged default)
   |
   +--> Supabase PostgreSQL (via the same POSTGRES_*/DATABASE_URL settings)
```

No Redis, no Ollama, no nginx, no separate Chroma service. Nothing here makes
OpenAI mandatory — Groq is the LLM provider for this path, and the existing
OpenAI/Anthropic/Ollama providers remain fully intact and selectable via
`LLM_PROVIDER` for anyone self-hosting instead.

### Required environment variables

Set these on the Koyeb backend service (never commit real values — the
repo's `.env.example` documents the same variables with placeholder values):

```
APP_ENV=production
DEBUG=false
SECRET_KEY=<generate a real random value>
JWT_SECRET_KEY=<generate a real random value>

POSTGRES_HOST=<from Supabase>
POSTGRES_PORT=<from Supabase>
POSTGRES_DB=<from Supabase>
POSTGRES_USER=<from Supabase>
POSTGRES_PASSWORD=<from Supabase>

CHROMA_MODE=embedded
CHROMA_PERSIST_DIRECTORY=/tmp/chronolegal-chroma

EMBEDDING_PROVIDER=huggingface

LLM_PROVIDER=groq
GROQ_API_KEY=<from Groq console — never commit this>
GROQ_MODEL=llama-3.1-8b-instant

CORS_ORIGINS=<the actual Vercel frontend URL, once known>
CORS_ALLOW_CREDENTIALS=true
```

On Vercel (frontend), set as a build-time environment variable:

```
VITE_API_BASE_URL=<the actual Koyeb backend URL>/api/v1
```

`VITE_WS_BASE_URL` is intentionally not introduced — the frontend has no
WebSocket client code; chat streaming uses Server-Sent Events over a plain
`fetch()` call, not a WebSocket.

### Where secrets are entered

Never in this repo. `GROQ_API_KEY`, `SECRET_KEY`, `JWT_SECRET_KEY`, and the
Supabase `POSTGRES_PASSWORD` are entered directly into the Koyeb service's
environment-variable dashboard (or via the Koyeb CLI's `--env` flags), and
`VITE_API_BASE_URL` into Vercel's Project Settings → Environment Variables.

### Deploying the backend (Koyeb)

The existing `backend/Dockerfile` is reused as-is — it already binds to
`${PORT:-8000}` (shell-form `CMD`), which is what Koyeb (and any similar
PaaS) injects at runtime.

1. In the Koyeb dashboard (or CLI), create a new Web Service from this
   GitHub repo, Docker deployment method, build context `backend/`,
   Dockerfile `backend/Dockerfile`.
2. Set the health check path to `/health`.
3. Set the environment variables listed above.
4. Deploy, then confirm `GET https://<your-koyeb-url>/health` returns
   `{"status": "healthy", ...}`.

No `koyeb.yaml`/declarative app-spec file is included here — Koyeb's exact
current declarative schema wasn't verified against live documentation as
part of this change, and inventing one risks shipping unsupported syntax.
Use the dashboard/CLI flow above, or check Koyeb's own current docs if a
declarative file is preferred later.

### Deploying the frontend (Vercel)

`frontend/vercel.json` sets the build command, output directory (`dist`,
matching the existing Vite config), and the SPA rewrite rule Vercel needs
for client-side routing.

1. Import this repo into Vercel.
2. Since the frontend lives in a subdirectory, set **Root Directory:
   `frontend`** in the Vercel project settings (this is a dashboard setting,
   not expressible inside `vercel.json` itself).
3. Set `VITE_API_BASE_URL` as an environment variable (build-time).
4. Deploy. Vercel's generated HTTPS URL is sufficient for a college demo —
   no custom domain is required.

### Connecting Supabase PostgreSQL

The application already expects generic `POSTGRES_HOST` / `POSTGRES_PORT` /
`POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` (see
`backend/app/core/config.py`'s `Settings.build_database_url`), which already
assembles the correct `postgresql+asyncpg://...` URL SQLAlchemy's async
engine and Alembic both need — no database-layer code change was required
or made for this.

Two ways to point it at Supabase, both already supported without any code
change:

- **Individual parts** (`POSTGRES_HOST`/`PORT`/`DB`/`USER`/`PASSWORD`): copy
  these directly from Supabase's connection-info page.
- **Full override**: set `DATABASE_URL` directly instead (the existing
  validator only builds one from the individual parts when `DATABASE_URL`
  itself is left empty), e.g. including an explicit
  `?ssl=require` suffix if your Supabase project's connection string
  requires it.

**SSL is not guessed here.** Supabase's dashboard shows both a "Direct
connection" and a "Connection pooler" string for each project, and whether
an explicit SSL parameter is required depends on which one you use and
Supabase's current settings for your project — copy the exact string
Supabase gives you (as `DATABASE_URL`) rather than assuming the individual-
parts form will work unmodified.

Standard Postgres extensions this app's own init script normally creates
(`uuid-ossp`, `pg_trgm`, `btree_gin` — see
`database/migrations/001_initial_schema.sql`) do not run automatically
against a managed database like Supabase. Create them once, manually,
before running migrations:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

Then let the backend's own startup (`run_migrations()` in
`backend/app/core/database.py`) apply Alembic migrations as it already does
on every boot.

### Configuring CORS

Set `CORS_ORIGINS` on the backend to the exact Vercel URL once it's known
(not `*` — `Settings._validate_production_secrets` already blocks
`CORS_ORIGINS=*` combined with `CORS_ALLOW_CREDENTIALS=true` in production).

### Limitations of this free/low-cost hosted architecture

- **Cold starts**: free/low-cost tiers on most PaaS providers (Koyeb
  included) can sleep an idle service and take a few seconds to cold-start
  on the next request. Acceptable for a demo; not something this
  architecture tries to eliminate.
- **Embedded Chroma is ephemeral**: `CHROMA_MODE=embedded` persists to local
  disk (`CHROMA_PERSIST_DIRECTORY`), which most free-tier compute is not
  guaranteed to retain across restarts/redeploys. The existing demo
  bootstrap (`_ensure_demo_data_ready()` in `backend/app/main.py`, added for
  the free-tier deployment work) already handles this: on startup, if
  `legal_cases` is empty it reseeds the small sample dataset, and if the
  Chroma collection is empty it re-embeds everything — using the existing
  seed file and embedding pipeline, nothing new invented for this.
- **HuggingFace embeddings and free-tier RAM**: `EMBEDDING_PROVIDER=huggingface`
  (the default, kept as-is per this deployment's requirements) loads
  `BAAI/bge-large-en-v1.5` (~1.3GB of weights) into the backend process.
  Whether this fits comfortably within Koyeb's current free-tier RAM
  allocation was not verified against live Koyeb specs as part of this
  change — check Koyeb's current published limits before relying on it. If
  it doesn't fit in practice, the codebase already supports
  `EMBEDDING_PROVIDER=openai` as a fallback (see `backend/app/services/ai/
  embedding_service.py`) without further code changes — not used by default
  here because the task for this deployment explicitly asked to keep
  HuggingFace unless proven impossible.
- **Redis is intentionally not provisioned**: rate limiting is already
  in-memory (no Redis dependency), and every caching call site already
  degrades gracefully without it. The one real, disclosed trade-off: the
  refresh-token revocation denylist (`backend/app/core/security.py`) fails
  closed by design — without Redis, `/auth/refresh` always fails, so demo
  users stay logged in for the access token's natural lifetime
  (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, 60 minutes by default) and then need
  to log in again. This is not a weakened security behavior; it's the
  existing fail-closed design doing exactly what it's supposed to when
  Redis isn't there.
- **Demo dataset**: the seeded dataset is the existing small set of landmark
  cases in `database/seeds/01_sample_cases.sql` (six cases) — enough to
  demonstrate search/RAG/chat, not a production-scale corpus.
