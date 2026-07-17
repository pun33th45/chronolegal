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
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

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

### Option A — Let's Encrypt (recommended for public servers)

```bash
# Install certbot
sudo apt install certbot -y

# Stop nginx temporarily
docker compose stop nginx

# Issue certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certs to nginx volume
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/ssl/key.pem

# Restart nginx
docker compose start nginx

# Auto-renewal (add to cron)
echo "0 3 * * * certbot renew --quiet && docker compose restart nginx" | sudo crontab -
```

### Option B — Self-signed (internal/staging only)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/key.pem \
  -out docker/ssl/cert.pem \
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
docker compose --profile production up -d
```

---

## 7. Verify Deployment

```bash
# All services healthy?
docker compose ps

# Backend health endpoint
curl https://yourdomain.com/api/health

# Expected
# {"status":"healthy","version":"1.0.0","db":"connected","chroma":"connected","redis":"connected"}
```

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

## Backup Strategy

### Database Backup
```bash
# Full backup
docker compose exec postgres pg_dump -U chronolegal chronolegal_prod \
  > backups/chronolegal_$(date +%Y%m%d_%H%M%S).sql

# Automated daily backup (add to cron)
0 2 * * * docker compose -f /path/to/chronolegal/docker-compose.yml \
  exec -T postgres pg_dump -U chronolegal chronolegal_prod \
  > /backups/chronolegal_$(date +\%Y\%m\%d).sql
```

### ChromaDB Backup
ChromaDB persists data to `chroma_data` Docker volume:
```bash
docker run --rm -v chronolegal_chroma_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/chroma_$(date +%Y%m%d).tar.gz /data
```

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
