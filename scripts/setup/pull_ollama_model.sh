#!/bin/bash
# Pull the LLM model into Ollama
# Usage: ./scripts/setup/pull_ollama_model.sh

MODEL=${LLM_MODEL:-"llama3.1:8b"}
OLLAMA_URL=${OLLAMA_BASE_URL:-"http://localhost:11434"}

echo "Pulling model: $MODEL from $OLLAMA_URL"

curl -X POST "$OLLAMA_URL/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$MODEL\"}" \
  --no-buffer

echo ""
echo "Model pull complete: $MODEL"
