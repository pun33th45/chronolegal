# ChronoLegal — Installation Guide

Complete step-by-step guide for setting up ChronoLegal locally for development.

---

## System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| RAM | 16 GB | 32 GB |
| Disk | 50 GB free | 100 GB |
| CPU | 4 cores | 8+ cores |
| GPU | Optional | NVIDIA GPU (for faster LLM) |
| OS | Linux / macOS / Windows (WSL2) | Ubuntu 22.04 |

> **Note on GPU**: Ollama automatically uses CUDA if available. On CPU-only machines, LLM responses take ~30–60 seconds per query.

---

## Prerequisites

### 1. Docker & Docker Compose

**Ubuntu/Debian**
```bash
# Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose v2
sudo apt install docker-compose-plugin
docker compose version  # should be v2.x
```

**macOS**
```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop/
# Docker Compose is bundled with Docker Desktop
```

**Windows**
```powershell
# Install Docker Desktop with WSL2 backend
# https://docs.docker.com/desktop/install/windows/
# Run all subsequent commands inside WSL2
```

### 2. Git
```bash
git --version  # should be 2.x+
```

### 3. Make (optional but recommended)
```bash
# Ubuntu
sudo apt install make

# macOS (included with Xcode Command Line Tools)
xcode-select --install
```

---

## Installation Steps

### Step 1 — Clone the Repository
```bash
git clone https://github.com/your-org/chronolegal.git
cd chronolegal
```

### Step 2 — Configure Environment
```bash
cp .env.example .env
```

Open `.env` and update the following values:

```dotenv
# REQUIRED — change these before running
SECRET_KEY=your-32-char-random-secret-here
JWT_SECRET_KEY=your-jwt-secret-here

# Database (defaults work for local Docker)
POSTGRES_DB=chronolegal
POSTGRES_USER=chronolegal
POSTGRES_PASSWORD=choose-a-strong-password

# LLM Provider (ollama is default — runs locally)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b

# Optional — only needed if using OpenAI/Anthropic
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

Generate secure keys:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 3 — Build and Start Services
```bash
make dev
# OR
docker compose up --build -d
```

This starts 7 services:
- `backend` — FastAPI on port 8000
- `frontend` — React dev server on port 5173
- `postgres` — PostgreSQL on port 5432
- `chroma` — ChromaDB on port 8001
- `redis` — Redis on port 6379
- `ollama` — Ollama LLM server on port 11434
- `nginx` — Reverse proxy on port 80/443

Check all services are healthy:
```bash
docker compose ps
```

### Step 4 — Run Database Migrations
```bash
docker compose exec backend alembic upgrade head
```

### Step 5 — Pull the LLM Model

This downloads ~4.7GB (LLaMA 3.1 8B quantised):
```bash
docker compose exec ollama ollama pull llama3.1:8b
```

Alternative models:
```bash
# Faster, slightly less accurate
docker compose exec ollama ollama pull qwen3:8b

# Good balance of speed and quality
docker compose exec ollama ollama pull mistral:7b

# Smaller for low-RAM machines
docker compose exec ollama ollama pull llama3.2:3b
```

### Step 6 — Create Admin User
```bash
docker compose exec backend python scripts/setup/create_admin.py
```

Follow the prompt to set admin email and password.

### Step 7 — Load the Legal Dataset

**Option A** — Download from HuggingFace (recommended, ~2–3 hours for full dataset):
```bash
make data-pipeline
# OR run each step individually:
docker compose exec backend python scripts/data/01_download_dataset.py
docker compose exec backend python scripts/data/02_preprocess.py
docker compose exec backend python scripts/data/03_ingest_to_db.py
docker compose exec backend python scripts/data/04_generate_embeddings.py
```

**Option B** — Load sample data only (fast, for testing):
```bash
docker compose exec backend psql -U chronolegal -d chronolegal -f database/seeds/01_sample_cases.sql
```

This loads 6 landmark Supreme Court cases for immediate testing.

### Step 8 — Verify Installation

```bash
# Backend health
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","version":"1.0.0","db":"connected","chroma":"connected","redis":"connected"}
```

Open your browser:
- **Frontend**: http://localhost:5173
- **API Docs**: http://localhost:8000/api/docs
- **ChromaDB UI**: http://localhost:8001

---

## Development Workflow

### Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
```

### Hot Reload

The frontend Vite dev server and FastAPI backend both support hot reload automatically when Docker volumes are mounted.

### Backend Shell
```bash
docker compose exec backend bash
```

### Database Shell
```bash
docker compose exec postgres psql -U chronolegal -d chronolegal
```

### Running Backend Tests
```bash
# Full test suite with coverage
make test

# Specific test file
docker compose exec backend pytest tests/api/test_auth.py -v

# Unit tests only
docker compose exec backend pytest tests/unit/ -v
```

### Linting
```bash
make lint
```

---

## Switching the LLM

Edit `.env` — no code changes needed:

```dotenv
# Use OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Use Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...

# Back to local Ollama
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
```

Then restart the backend:
```bash
docker compose restart backend
```

---

## Stopping the Stack
```bash
make down
# OR
docker compose down
```

To also remove volumes (WARNING: deletes all data):
```bash
make clean
```

---

## Troubleshooting

### Port already in use
```bash
# Find which process uses port 8000
lsof -i :8000
# Kill it
kill -9 <PID>
```

### Ollama model download fails
```bash
# Check Ollama service is running
docker compose logs ollama

# Retry pull
docker compose exec ollama ollama pull llama3.1:8b
```

### Database connection refused
```bash
# Check PostgreSQL is healthy
docker compose ps postgres

# View logs
docker compose logs postgres

# Reset database
docker compose down postgres
docker volume rm chronolegal_postgres_data
docker compose up postgres -d
```

### ChromaDB out of memory
ChromaDB can use significant RAM. If it crashes:
```bash
# Add memory limit to docker-compose.override.yml
services:
  chroma:
    mem_limit: 4g
```

### Frontend can't connect to backend
Check CORS settings in `.env`:
```dotenv
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Embedding generation is slow
- Embedding on CPU is ~200 cases/hour. For faster indexing, use a machine with CUDA GPU.
- To check if CUDA is available inside the container:
```bash
docker compose exec backend python -c "import torch; print(torch.cuda.is_available())"
```
