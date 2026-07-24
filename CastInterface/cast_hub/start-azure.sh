#!/usr/bin/env bash
set -euo pipefail

# Azure App Service injects PORT for Linux containers.
PORT="${PORT:-8000}"
HOST="0.0.0.0"

# Zip deploy may skip Oryx pip install (no antenv). Docker images already have deps.
if ! python -c "import aiohttp" >/dev/null 2>&1; then
  if [[ -f requirements.txt ]]; then
    echo "Installing Python dependencies from requirements.txt..."
    python -m pip install --no-cache-dir -r requirements.txt
  else
    echo "WARNING: requirements.txt not found; hub may fail on missing imports." >&2
  fi
fi

# Optional hub settings (override from App Settings as needed).
export CAST_HUB_WS_KEEPALIVE="${CAST_HUB_WS_KEEPALIVE:-true}"
export CAST_HUB_WS_KEEPALIVE_INTERVAL_SECONDS="${CAST_HUB_WS_KEEPALIVE_INTERVAL_SECONDS:-30}"
export CAST_HUB_UVICORN_WS_PING_INTERVAL_SECONDS="${CAST_HUB_UVICORN_WS_PING_INTERVAL_SECONDS:-20}"
export CAST_HUB_UVICORN_WS_PING_TIMEOUT_SECONDS="${CAST_HUB_UVICORN_WS_PING_TIMEOUT_SECONDS:-20}"
export CAST_HUB_HTTP_PAYLOAD_TTL_SECONDS="${CAST_HUB_HTTP_PAYLOAD_TTL_SECONDS:-300}"
export CAST_HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES="${CAST_HUB_HTTP_PAYLOAD_MAX_TOTAL_BYTES:-2147483648}"
export CAST_HUB_FILENAME_POLICY="${CAST_HUB_FILENAME_POLICY:-on}"

echo "Starting Cast Hub on ${HOST}:${PORT}"
exec python cast_hub.py --host "${HOST}" --port "${PORT}"
