#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.gpu-worker}"

cd "$ROOT_DIR"
source .venv/bin/activate
set -a
source "$ENV_FILE"
set +a

python - <<'PY'
from worker.app.celery_app import celery_app

result = celery_app.send_task("worker.health", queue="generation:normal")
print(result.get(timeout=30))
PY
