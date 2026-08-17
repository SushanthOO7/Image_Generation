#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="${FLUX_WORKER_SESSION:-flux-worker}"

echo "== tmux =="
if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux ls | grep "$SESSION_NAME" || true
  else
    echo "No tmux session named $SESSION_NAME"
  fi
else
  echo "tmux not installed"
fi

echo
echo "== celery processes =="
pgrep -af "celery -A worker.app.celery_app" || echo "No Celery worker process found"

echo
echo "== gpu =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "nvidia-smi not found"
fi
