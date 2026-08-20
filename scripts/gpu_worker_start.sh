#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.gpu-worker}"
SESSION_NAME="${FLUX_WORKER_SESSION:-flux-worker}"
QUEUE_NAMES="${FLUX_WORKER_QUEUES:-generation:high,generation:normal,generation:low}"
CONCURRENCY="${FLUX_WORKER_CONCURRENCY:-1}"
VALIDATE_RUNTIME="${FLUX_VALIDATE_RUNTIME_ON_START:-false}"
VALIDATION_WIDTH="${FLUX_VALIDATION_WIDTH:-512}"
VALIDATION_HEIGHT="${FLUX_VALIDATION_HEIGHT:-512}"
VALIDATION_STEPS="${FLUX_VALIDATION_STEPS:-4}"
CELERY_POOL="${FLUX_WORKER_POOL:-solo}"

if [[ ! -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  echo "Missing virtualenv: $ROOT_DIR/.venv" >&2
  echo "Create it first, then install worker/requirements-ml.txt." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required for background worker management on this server." >&2
  exit 1
fi

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "GPU worker tmux session already exists: $SESSION_NAME"
  echo "Attach with: tmux attach -t $SESSION_NAME"
  exit 0
fi

cd "$ROOT_DIR"
source .venv/bin/activate
set -a
source "$ENV_FILE"
set +a
python scripts/gpu_worker_preflight.py
if [[ "${GENERATION_BACKEND:-mock}" == "flux" && "$VALIDATE_RUNTIME" == "true" ]]; then
  python scripts/validate_flux_runtime.py --width "$VALIDATION_WIDTH" --height "$VALIDATION_HEIGHT" --steps "$VALIDATION_STEPS"
fi

tmux new-session -d -s "$SESSION_NAME" \
  "cd '$ROOT_DIR' && source .venv/bin/activate && set -a && source '$ENV_FILE' && set +a && echo 'Starting Celery GPU worker with pool=$CELERY_POOL concurrency=$CONCURRENCY queues=$QUEUE_NAMES' && exec python -m celery -A worker.app.celery_app worker --loglevel=info --pool='$CELERY_POOL' -Q '$QUEUE_NAMES' -c '$CONCURRENCY'"

echo "Started GPU worker in tmux session: $SESSION_NAME"
echo "Celery pool: $CELERY_POOL"
echo "Attach with: tmux attach -t $SESSION_NAME"
