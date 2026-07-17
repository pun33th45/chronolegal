# =============================================================================
# ChronoLegal - Makefile
# =============================================================================

.PHONY: help setup dev prod down logs test lint clean data-pipeline test-e2e test-perf

help:
	@echo "ChronoLegal Make targets:"
	@echo "  make setup         - First-time setup: copy .env and build containers"
	@echo "  make dev           - Start development stack"
	@echo "  make prod          - Start production stack"
	@echo "  make down          - Stop all containers"
	@echo "  make logs          - Follow container logs"
	@echo "  make test          - Run backend tests"
	@echo "  make lint          - Run linters"
	@echo "  make clean         - Remove containers and volumes"
	@echo "  make data-pipeline - Download, preprocess and embed dataset"
	@echo "  make pull-model    - Pull Ollama LLM model"
	@echo "  make create-admin  - Create admin user"
	@echo "  make test-e2e      - Run Playwright end-to-end tests"
	@echo "  make test-perf     - Run Locust load tests (headless, 60s)"

setup:
	@cp -n .env.example .env || true
	@echo "→ Edit .env before continuing"

dev:
	docker compose up --build -d
	@echo "→ Frontend: http://localhost:5173"
	@echo "→ Backend:  http://localhost:8000"
	@echo "→ API Docs: http://localhost:8000/api/docs"

prod:
	docker compose --profile production up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest --cov=app --cov-report=term-missing

lint:
	docker compose exec backend black . && isort . && flake8 .

clean:
	docker compose down -v --remove-orphans
	docker system prune -f

pull-model:
	docker compose exec ollama ollama pull $(MODEL)

create-admin:
	docker compose exec backend python /app/../scripts/setup/create_admin.py

test-e2e:
	cd tests/e2e && npm install && npx playwright install chromium && npm test

test-perf:
	cd tests/performance && locust -f locustfile.py --host http://localhost:8000 \
		--users 50 --spawn-rate 5 --run-time 60s --headless \
		--html reports/load_report.html --csv reports/load_stats

data-pipeline:
	docker compose exec backend python /app/../scripts/data/01_download_dataset.py
	docker compose exec backend python /app/../scripts/data/02_preprocess.py
	docker compose exec backend python /app/../scripts/data/03_ingest_to_db.py
	docker compose exec backend python /app/../scripts/data/04_generate_embeddings.py
