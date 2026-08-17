#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.gpu-worker}"
SESSION_NAME="${FLUX_WORKER_SESSION:-flux-worker}"
QUEUE_NAMES="${FLUX_WORKER_QUEUES:-generation:high,generation:normal,generation:low}"
CONCURRENCY="${FLUX_WORKER_CONCURRENCY:-1}"

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

tmux new-session -d -s "$SESSION_NAME" \
  "cd '$ROOT_DIR' && source .venv/bin/activate && set -a && source '$ENV_FILE' && set +a && exec python -m celery -A worker.app.celery_app worker --loglevel=info -Q '$QUEUE_NAMES' -c '$CONCURRENCY'"

echo "Started GPU worker in tmux session: $SESSION_NAME"
echo "Attach with: tmux attach -t $SESSION_NAME"
