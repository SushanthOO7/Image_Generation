#!/usr/bin/env python3
"""Validate direct Python GPU worker environment before starting Celery."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from worker.app.preflight import validate_worker_environment
from worker.app.settings import load_worker_settings


def main() -> int:
    settings = load_worker_settings()
    result = validate_worker_environment(settings)
    for line in result.lines:
        print(line)
    print(f"gpu_worker_preflight={'ok' if result.ok else 'failed'}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
