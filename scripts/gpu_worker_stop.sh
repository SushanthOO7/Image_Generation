#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="${FLUX_WORKER_SESSION:-flux-worker}"

if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux send-keys -t "$SESSION_NAME" C-c
  sleep 5
  if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
  fi
fi

pkill -TERM -u "$USER" -f "celery -A worker.app.celery_app" 2>/dev/null || true
sleep 5
pkill -KILL -u "$USER" -f "celery -A worker.app.celery_app" 2>/dev/null || true

echo "Stopped GPU worker processes for user $USER"
