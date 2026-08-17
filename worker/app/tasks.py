import time
import os
import shutil
import subprocess
from typing import Any

from backend.app.database import SessionLocal
from backend.app.repositories import (
    complete_generation_with_outputs,
    get_generation_job,
    mark_generation_failed,
    mark_generation_running,
    update_generation_progress,
)
from backend.app.schemas import GenerationStatus
from worker.app.celery_app import celery_app
from worker.app.generation import build_image_generator
from worker.app.image_renderer import render_thumbnail
from worker.app.lifecycle import get_preloaded_generator
from worker.app.ranker import build_ranker
from worker.app.settings import load_worker_settings
from worker.app.storage import ObjectStorage, generation_object_key

_GENERATOR_CACHE: dict[tuple[str, str, str], Any] = {}


def get_cached_generator(settings):
    cache_key = (settings.generation_backend, settings.model_root, settings.flux_config_path)
    generator = _GENERATOR_CACHE.get(cache_key)
    if generator is None:
        generator = get_preloaded_generator() or build_image_generator(settings)
        _GENERATOR_CACHE[cache_key] = generator
    return generator


@celery_app.task(name="worker.generate_image")
def generate_image(job_id: str) -> dict[str, str]:
    started_at = time.perf_counter()
    db = SessionLocal()
    try:
        job = get_generation_job(db, job_id)
        if job is None:
            return {"job_id": job_id, "status": "NOT_FOUND"}

        if job.status in {
            GenerationStatus.completed.value,
            GenerationStatus.failed.value,
            GenerationStatus.cancelled.value,
        }:
            return {"job_id": job_id, "status": job.status}

        mark_generation_running(db, job)
        time.sleep(1)
        job = get_generation_job(db, job_id)
        if job is None:
            return {"job_id": job_id, "status": "NOT_FOUND"}
        if job.status == GenerationStatus.cancelled.value:
            return {"job_id": job_id, "status": job.status}

        settings = load_worker_settings()
        storage = ObjectStorage(settings)
        storage.ensure_bucket()
        ranker = build_ranker(settings)
        job = update_generation_progress(db, job, 0.15, "Loading model")
        generator = get_cached_generator(settings)
        job = get_generation_job(db, job_id)
        if job is None:
            return {"job_id": job_id, "status": "NOT_FOUND"}
        if job.status == GenerationStatus.cancelled.value:
            return {"job_id": job_id, "status": job.status}

        job = update_generation_progress(db, job, 0.3, "Model ready")
        candidate_outputs: list[dict[str, object]] = []
        candidate_count = max(1, min(job.candidate_count, 4))
        generation_started_at = time.perf_counter()
        for candidate_index in range(1, candidate_count + 1):
            generation_progress = 0.3 + ((candidate_index - 1) / candidate_count) * 0.55
            job = update_generation_progress(
                db,
                job,
                generation_progress,
                f"Generating candidate {candidate_index} of {candidate_count}",
            )
            generated = generator.generate(job, candidate_index=candidate_index)
            score = ranker.score(job, generated, candidate_index, candidate_count)
            job = get_generation_job(db, job_id)
            if job is None:
                return {"job_id": job_id, "status": "NOT_FOUND"}
            if job.status == GenerationStatus.cancelled.value:
                return {"job_id": job_id, "status": job.status}

            upload_progress = 0.3 + (candidate_index / candidate_count) * 0.55
            job = update_generation_progress(
                db,
                job,
                upload_progress,
                f"Uploading candidate {candidate_index} of {candidate_count}",
            )
            candidate_key = generation_object_key(job.id, f"candidate-{candidate_index}.webp")
            storage.upload_webp(candidate_key, generated.image_bytes)

            candidate_outputs.append(
                {
                    "storage_path": candidate_key,
                    "width": generated.width,
                    "height": generated.height,
                    "seed": generated.seed,
                    "prompt_alignment_score": score.prompt_alignment_score,
                    "aesthetic_score": score.aesthetic_score,
                    "quality_score": score.quality_score,
                    "final_score": score.final_score,
                    "image_bytes": generated.image_bytes,
                }
            )

        generation_time_ms = int((time.perf_counter() - generation_started_at) * 1000)
        ranking_started_at = time.perf_counter()
        job = update_generation_progress(db, job, 0.9, "Ranking candidates")
        selected_candidate = max(candidate_outputs, key=lambda output: float(output["final_score"]))
        ranking_time_ms = int((time.perf_counter() - ranking_started_at) * 1000)
        thumbnail_bytes = render_thumbnail(bytes(selected_candidate["image_bytes"]))
        final_key = generation_object_key(job.id, "final.webp")
        thumbnail_key = generation_object_key(job.id, "thumbnail.webp")

        job = update_generation_progress(db, job, 0.95, "Uploading final image")
        storage.upload_webp(final_key, bytes(selected_candidate["image_bytes"]))
        storage.upload_webp(thumbnail_key, thumbnail_bytes)
        for output in candidate_outputs:
            output["final_storage_path"] = final_key
            output.pop("image_bytes")

        completed = complete_generation_with_outputs(
            db,
            job,
            candidate_outputs,
            generation_time_ms=generation_time_ms,
            ranking_time_ms=ranking_time_ms,
        )
        return {"job_id": job_id, "status": completed.status}
    except Exception as exc:
        db.rollback()
        job = get_generation_job(db, job_id)
        if job is not None:
            mark_generation_failed(
                db,
                job,
                "WORKER_ERROR",
                str(exc),
                generation_time_ms=int((time.perf_counter() - started_at) * 1000),
            )
        raise
    finally:
        db.close()


@celery_app.task(name="worker.health")
def worker_health() -> dict[str, object]:
    settings = load_worker_settings()
    generator = _GENERATOR_CACHE.get((settings.generation_backend, settings.model_root, settings.flux_config_path))
    generator = generator or get_preloaded_generator()
    model_health = None
    if generator is not None and hasattr(generator, "model_manager"):
        model_health = generator.model_manager.health_check().__dict__

    return {
        "status": "ok",
        "backend": settings.generation_backend,
        "model_root": settings.model_root,
        "flux_config_path": settings.flux_config_path,
        "preloaded": get_preloaded_generator() is not None,
        "model": model_health,
        "system": _worker_system_snapshot(),
        "gpus": _gpu_snapshot(),
    }


def _worker_system_snapshot() -> dict[str, object]:
    load_1m, load_5m, load_15m = os.getloadavg()
    disk = shutil.disk_usage("/")
    return {
        "load_1m": round(load_1m, 3),
        "load_5m": round(load_5m, 3),
        "load_15m": round(load_15m, 3),
        "cpu_count": os.cpu_count() or 1,
        "disk_used_percent": round((1 - disk.free / disk.total) * 100, 2),
    }


def _gpu_snapshot() -> list[dict[str, object]]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    gpus: list[dict[str, object]] = []
    for line in output.strip().splitlines():
        index, name, util, mem_used, mem_total, temp, power = [part.strip() for part in line.split(",")]
        gpus.append(
            {
                "index": int(index),
                "name": name,
                "utilization_gpu_percent": float(util),
                "memory_used_mib": float(mem_used),
                "memory_total_mib": float(mem_total),
                "temperature_c": float(temp),
                "power_draw_w": float(power) if power != "[Not Supported]" else None,
            }
        )
    return gpus
