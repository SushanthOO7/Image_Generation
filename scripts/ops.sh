#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/ops.sh <command>

Commands:
  check             Compile backend/worker/scripts and verify frontend lint/build
  migrate           Run Alembic migrations in the api container
  compose-config    Validate docker compose configuration
  gpu-preflight     Validate direct Python GPU worker environment
  gpu-validate      Run one real FLUX generation outside Celery
  worker-start      Start direct Python GPU worker in tmux
EOF
}

command="${1:-}"
case "$command" in
  check)
    cd "$ROOT_DIR"
    python -m compileall backend/app worker/app scripts
    npm --prefix frontend run lint
    npm --prefix frontend run build
    ;;
  migrate)
    cd "$ROOT_DIR"
    docker compose exec api alembic -c backend/alembic.ini upgrade head
    ;;
  compose-config)
    cd "$ROOT_DIR"
    docker compose config --quiet
    ;;
  gpu-preflight)
    cd "$ROOT_DIR"
    python scripts/gpu_worker_preflight.py
    ;;
  gpu-validate)
    cd "$ROOT_DIR"
    python scripts/validate_flux_runtime.py "${@:2}"
    ;;
  worker-start)
    cd "$ROOT_DIR"
    scripts/gpu_worker_start.sh "${@:2}"
    ;;
  "" | -h | --help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
