#!/usr/bin/env python3
"""Run one real FLUX generation outside Celery to validate the GPU worker path."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from worker.app.flux_generator import FluxImageGenerator
from worker.app.preflight import validate_worker_environment
from worker.app.settings import load_worker_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default="A small plush snow figure photographed in a cool-toned studio, glossy icy highlights, soft shadows",
        help="Prompt to generate.",
    )
    parser.add_argument("--width", type=int, default=512, help="Validation image width.")
    parser.add_argument("--height", type=int, default=512, help="Validation image height.")
    parser.add_argument("--steps", type=int, default=4, help="Inference steps for a quick smoke test.")
    parser.add_argument("--guidance", type=float, default=3.5, help="Guidance scale.")
    parser.add_argument("--seed", type=int, default=12345, help="Deterministic validation seed.")
    parser.add_argument("--output", default="generated/flux-runtime-validation.webp", help="Local output file path.")
    parser.add_argument("--upload", action="store_true", help="Also upload the validation image to configured MinIO.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_worker_settings()
    if settings.generation_backend != "flux":
        settings = replace(settings, generation_backend="flux")

    preflight = validate_worker_environment(settings, require_flux=True)
    for line in preflight.lines:
        print(line)
    if not preflight.ok:
        print("flux_runtime_validation=preflight_failed")
        return 1

    job_id = f"runtime-validation-{uuid4().hex[:12]}"
    job = SimpleNamespace(
        id=job_id,
        original_prompt=args.prompt,
        expanded_prompt=None,
        width=args.width,
        height=args.height,
        steps=args.steps,
        guidance=args.guidance,
        seed=args.seed,
    )

    started_at = time.perf_counter()
    try:
        generated = FluxImageGenerator(settings).generate(job, candidate_index=1)  # type: ignore[arg-type]
    except RuntimeError as exc:
        print(f"flux_runtime_error={exc}")
        if "invalid device ordinal" in str(exc).lower():
            print("Check CUDA_VISIBLE_DEVICES and remove max_memory_gpu_N entries for invisible GPUs.")
        return 1

    elapsed = time.perf_counter() - started_at
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(generated.image_bytes)
    print(f"validation_output={output_path}")
    print(f"validation_size={generated.width}x{generated.height}")
    print(f"validation_seed={generated.seed}")
    print(f"validation_seconds={elapsed:.2f}")

    if args.upload:
        from worker.app.storage import ObjectStorage, generation_object_key

        storage = ObjectStorage(settings)
        storage.ensure_bucket()
        key = generation_object_key(job_id, "validation.webp")
        storage.upload_webp(key, generated.image_bytes)
        print(f"minio_key={key}")

    print("flux_runtime_validation=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
