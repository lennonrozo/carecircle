#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"

if [ -x "$ROOT_DIR/.venv/bin/gunicorn" ]; then
  GUNICORN_BIN="$ROOT_DIR/.venv/bin/gunicorn"
else
  GUNICORN_BIN="gunicorn"
fi

exec "$GUNICORN_BIN" config.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_CONCURRENCY}" \
  --access-logfile - \
  --error-logfile -