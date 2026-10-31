#!/usr/bin/env bash
# Start the API on :8000. Loads .env if present (ANTHROPIC_API_KEY optional).
cd "$(dirname "$0")/.." || exit 1
[ -f .env ] && set -a && . ./.env && set +a
exec .venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port "${PORT:-8000}" "$@"
