import time
from typing import Any

from backend.app.database import SessionLocal
from backend.app.repositories import (
    complete_generation_with_outputs,
    get_generation_job,
    mark_generation_failed,
    mark_generation_running,
)
from backend.app.schemas import GenerationStatus
from worker.app.celery_app import celery_app
from worker.app.generation import build_image_generator
from worker.app.image_renderer import render_thumbnail
from worker.app.settings import load_worker_settings
from worker.app.storage import ObjectStorage, generation_object_key

_GENERATOR_CACHE: dict[tuple[str, str, str], Any] = {}


def get_cached_generator(settings):
    cache_key = (settings.generation_backend, settings.model_root, settings.flux_config_path)
    generator = _GENERATOR_CACHE.get(cache_key)
    if generator is None:
        generator = build_image_generator(settings)
        _GENERATOR_CACHE[cache_key] = generator
    return generator


@celery_app.task(name="worker.generate_image")
def generate_image(job_id: str) -> dict[str, str]:
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
        generator = get_cached_generator(settings)
        candidate_outputs: list[dict[str, object]] = []
        candidate_count = max(1, min(job.candidate_count, 4))
        for candidate_index in range(1, candidate_count + 1):
            generated = generator.generate(job, candidate_index=candidate_index)
            job = get_generation_job(db, job_id)
            if job is None:
                return {"job_id": job_id, "status": "NOT_FOUND"}
            if job.status == GenerationStatus.cancelled.value:
                return {"job_id": job_id, "status": job.status}

            candidate_key = generation_object_key(job.id, f"candidate-{candidate_index}.webp")
            storage.upload_webp(candidate_key, generated.image_bytes)

            prompt_alignment_score = 0.78 + candidate_index * 0.03
            aesthetic_score = 0.8 + (candidate_count - candidate_index) * 0.02
            quality_score = 0.82 + candidate_index * 0.015
            final_score = round(
                prompt_alignment_score * 0.4 + aesthetic_score * 0.3 + quality_score * 0.3,
                4,
            )
            candidate_outputs.append(
                {
                    "storage_path": candidate_key,
                    "width": generated.width,
                    "height": generated.height,
                    "seed": generated.seed,
                    "prompt_alignment_score": prompt_alignment_score,
                    "aesthetic_score": aesthetic_score,
                    "quality_score": quality_score,
                    "final_score": final_score,
                    "image_bytes": generated.image_bytes,
                }
            )

        selected_candidate = max(candidate_outputs, key=lambda output: float(output["final_score"]))
        thumbnail_bytes = render_thumbnail(bytes(selected_candidate["image_bytes"]))
        final_key = generation_object_key(job.id, "final.webp")
        thumbnail_key = generation_object_key(job.id, "thumbnail.webp")

        storage.upload_webp(final_key, bytes(selected_candidate["image_bytes"]))
        storage.upload_webp(thumbnail_key, thumbnail_bytes)
        for output in candidate_outputs:
            output["final_storage_path"] = final_key
            output.pop("image_bytes")

        completed = complete_generation_with_outputs(
            db,
            job,
            candidate_outputs,
        )
        return {"job_id": job_id, "status": completed.status}
    except Exception as exc:
        db.rollback()
        job = get_generation_job(db, job_id)
        if job is not None:
            mark_generation_failed(db, job, "WORKER_ERROR", str(exc))
        raise
    finally:
        db.close()
