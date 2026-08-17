from datetime import UTC, datetime
from secrets import randbelow
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import GenerationFeedback, GenerationJob, GenerationOutput, User
from backend.app.prompting import build_generation_plan
from backend.app.schemas import GenerationRequest, GenerationStatus


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, email: str, password_hash: str) -> User:
    user = User(
        id=f"user_{uuid4().hex[:12]}",
        email=email.lower(),
        password_hash=password_hash,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_generation_job(
    db: Session,
    request: GenerationRequest,
    model_version: str,
    user_id: str | None,
    prompt_presets_path: str,
    quality_presets_path: str,
) -> GenerationJob:
    plan = build_generation_plan(request, prompt_presets_path, quality_presets_path)
    job = GenerationJob(
        id=f"gen_{uuid4().hex[:12]}",
        user_id=user_id,
        original_prompt=request.prompt,
        expanded_prompt=plan.expanded_prompt,
        model="flux2",
        model_version=model_version,
        aspect_ratio=request.aspect_ratio,
        quality=request.quality,
        style=request.style,
        width=plan.width,
        height=plan.height,
        steps=plan.steps,
        guidance=plan.guidance,
        seed=request.seed if request.seed is not None else randbelow(2_147_483_647),
        candidate_count=min(request.num_outputs, plan.candidate_count),
        status=GenerationStatus.queued.value,
        status_message="Queued",
        progress=0.05,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_generation_job(db: Session, job_id: str) -> GenerationJob | None:
    statement = (
        select(GenerationJob)
        .where(GenerationJob.id == job_id)
        .options(selectinload(GenerationJob.outputs))
    )
    return db.scalar(statement)


def list_generation_jobs(db: Session, user_id: str, limit: int = 20) -> list[GenerationJob]:
    statement = (
        select(GenerationJob)
        .where(GenerationJob.user_id == user_id)
        .where(GenerationJob.archived_at.is_(None))
        .options(selectinload(GenerationJob.outputs))
        .order_by(GenerationJob.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).unique())


def count_active_generation_jobs(db: Session, user_id: str) -> int:
    statement = select(func.count()).select_from(GenerationJob).where(
        GenerationJob.user_id == user_id,
        GenerationJob.status.in_([GenerationStatus.queued.value, GenerationStatus.generating.value]),
    )
    return int(db.scalar(statement) or 0)


def cancel_generation_job(db: Session, job: GenerationJob) -> GenerationJob:
    if job.status in {
        GenerationStatus.completed.value,
        GenerationStatus.failed.value,
        GenerationStatus.cancelled.value,
    }:
        return job

    job.status = GenerationStatus.cancelled.value
    job.status_message = "Cancelled"
    job.progress = 1.0
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def set_generation_task_id(db: Session, job: GenerationJob, task_id: str) -> GenerationJob:
    job.celery_task_id = task_id
    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def mark_generation_running(db: Session, job: GenerationJob) -> GenerationJob:
    if job.status == GenerationStatus.cancelled.value:
        return job

    job.status = GenerationStatus.generating.value
    job.status_message = "Starting worker"
    job.progress = 0.5
    job.started_at = job.started_at or datetime.now(UTC)

    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def update_generation_progress(
    db: Session,
    job: GenerationJob,
    progress: float,
    status_message: str,
) -> GenerationJob:
    if job.status == GenerationStatus.cancelled.value:
        return job

    job.progress = max(0.0, min(progress, 0.99))
    job.status_message = status_message
    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def complete_generation_with_outputs(
    db: Session,
    job: GenerationJob,
    outputs: list[dict[str, object]],
    generation_time_ms: int | None = None,
    ranking_time_ms: int | None = None,
) -> GenerationJob:
    if job.status == GenerationStatus.cancelled.value:
        return job

    job.status = GenerationStatus.completed.value
    job.status_message = "Completed"
    job.progress = 1.0
    job.completed_at = datetime.now(UTC)
    job.generation_time_ms = generation_time_ms
    job.ranking_time_ms = ranking_time_ms
    if not job.outputs:
        selected_index = max(
            range(len(outputs)),
            key=lambda index: float(outputs[index].get("final_score") or 0),
        )
        suffix = job.id.removeprefix("gen_")
        for index, output_data in enumerate(outputs):
            output = GenerationOutput(
                id=f"img_{suffix}_{index + 1}",
                job_id=job.id,
                storage_path=str(output_data["storage_path"]),
                width=int(output_data["width"]),
                height=int(output_data["height"]),
                seed=int(output_data["seed"]) if output_data.get("seed") is not None else None,
                selected=False,
                model_version=job.model_version,
                prompt_alignment_score=float(output_data["prompt_alignment_score"]),
                aesthetic_score=float(output_data["aesthetic_score"]),
                quality_score=float(output_data["quality_score"]),
                final_score=float(output_data["final_score"]),
            )
            db.add(output)

        selected_output = outputs[selected_index]
        final_output = GenerationOutput(
            id=f"img_{suffix}",
            job_id=job.id,
            storage_path=str(selected_output["final_storage_path"]),
            width=int(selected_output["width"]),
            height=int(selected_output["height"]),
            seed=int(selected_output["seed"]) if selected_output.get("seed") is not None else None,
            selected=True,
            model_version=job.model_version,
            prompt_alignment_score=float(selected_output["prompt_alignment_score"]),
            aesthetic_score=float(selected_output["aesthetic_score"]),
            quality_score=float(selected_output["quality_score"]),
            final_score=float(selected_output["final_score"]),
        )
        db.add(final_output)

    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def complete_generation_with_output(
    db: Session,
    job: GenerationJob,
    storage_path: str,
    width: int,
    height: int,
) -> GenerationJob:
    return complete_generation_with_outputs(
        db,
        job,
        [
            {
                "storage_path": storage_path,
                "final_storage_path": storage_path,
                "width": width,
                "height": height,
                "seed": None,
                "prompt_alignment_score": 1.0,
                "aesthetic_score": 1.0,
                "quality_score": 1.0,
                "final_score": 1.0,
            }
        ],
    )


def mark_generation_failed(
    db: Session,
    job: GenerationJob,
    error_code: str,
    error_message: str,
    generation_time_ms: int | None = None,
) -> GenerationJob:
    job.status = GenerationStatus.failed.value
    job.status_message = "Failed"
    job.progress = 1.0
    job.completed_at = datetime.now(UTC)
    job.error_code = error_code
    job.error_message = error_message
    job.generation_time_ms = generation_time_ms
    db.commit()
    db.refresh(job)
    return job


def select_generation_output(db: Session, job: GenerationJob, output_id: str) -> GenerationJob:
    selected_output = next((output for output in job.outputs if output.id == output_id), None)
    if selected_output is None:
        raise ValueError("Output does not belong to generation job")

    for output in job.outputs:
        output.selected = output.id == output_id

    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def archive_generation_job(db: Session, job: GenerationJob) -> GenerationJob:
    job.archived_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return get_generation_job(db, job.id) or job


def create_generation_feedback(
    db: Session,
    job: GenerationJob,
    output_id: str | None,
    liked: bool | None,
    rating: int | None,
    user_id: str | None,
) -> GenerationFeedback:
    feedback = GenerationFeedback(
        id=f"fb_{uuid4().hex[:12]}",
        user_id=user_id,
        generation_id=job.id,
        output_id=output_id,
        liked=liked,
        rating=rating,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
