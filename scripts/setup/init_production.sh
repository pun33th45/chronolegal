#!/usr/bin/env bash
# Production init script — run once after docker compose up
set -euo pipefail

echo "🔷 ChronoLegal Production Init"

# Wait for services
echo "⏳ Waiting for PostgreSQL..."
until docker compose exec -T postgres pg_isready -U chronolegal > /dev/null 2>&1; do
  sleep 2
done

echo "⏳ Waiting for backend..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  sleep 3
done

# Run Alembic migrations
echo "📦 Running database migrations..."
docker compose exec -T backend alembic upgrade head

# Seed landmark cases
echo "🌱 Seeding sample cases..."
docker compose exec -T backend python -m scripts.setup.seed_db

# Create admin user
echo "👤 Creating admin user..."
docker compose exec -T backend python -m scripts.setup.create_admin

# Pull Ollama model (if Ollama is the provider)
if [ "${LLM_PROVIDER:-ollama}" = "ollama" ]; then
  echo "🤖 Pulling LLaMA 3.1 8B model..."
  docker compose exec -T ollama ollama pull llama3.1:8b || true
fi

echo "✅ Production init complete."
echo ""
echo "  Platform: http://localhost"
echo "  Admin:    http://localhost/admin"
echo "  (API docs are disabled under APP_ENV=production — see backend/app/main.py)"
