from fastapi import HTTPException, status
from kombu.exceptions import KombuError
from sqlalchemy.orm import Session

from backend.app.models import User
from backend.app.queue import enqueue_generation
from backend.app.rate_limits import check_generation_rate_limit
from backend.app.repositories import (
    count_active_generation_jobs,
    create_generation_job,
    get_monthly_generation_usage,
    mark_generation_failed,
    release_monthly_generation_quota,
    reserve_monthly_generation_quota,
    set_generation_task_id,
)
from backend.app.safety import check_prompt_safety
from backend.app.schemas import GenerationRequest, GenerationStatus, GenerationSubmitResponse
from backend.app.settings import Settings, limits_for_plan


def submit_generation_job(
    db: Session,
    settings: Settings,
    request: GenerationRequest,
    user: User,
) -> GenerationSubmitResponse:
    safety_result = check_prompt_safety(request.prompt, settings.safety_config_path)
    if not safety_result.allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=safety_result.reason or "Prompt blocked")

    plan_limits = limits_for_plan(settings, user.plan)
    active_jobs = count_active_generation_jobs(db, user.id)
    if active_jobs >= plan_limits.concurrent_generation_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Concurrent generation limit reached ({plan_limits.concurrent_generation_limit})",
        )

    monthly_used = get_monthly_generation_usage(db, user.id)
    if plan_limits.monthly_generation_quota >= 0 and monthly_used >= plan_limits.monthly_generation_quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly generation quota reached ({monthly_used}/{plan_limits.monthly_generation_quota})",
        )

    rate_limit = check_generation_rate_limit(settings, user.id, plan_limits.rate_limit_per_minute)
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Generation rate limit reached. Try again in {rate_limit.reset_seconds}s",
        )

    quota_allowed, monthly_used = reserve_monthly_generation_quota(
        db,
        user.id,
        plan_limits.monthly_generation_quota,
    )
    if not quota_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly generation quota reached ({monthly_used}/{plan_limits.monthly_generation_quota})",
        )

    job = create_generation_job(
        db,
        request,
        settings.default_model_version,
        user_id=user.id,
        prompt_presets_path=settings.prompt_presets_path,
        quality_presets_path=settings.quality_presets_path,
    )
    try:
        task_id = enqueue_generation(job.id)
        job = set_generation_task_id(db, job, task_id)
    except KombuError as exc:
        release_monthly_generation_quota(db, user.id, plan_limits.monthly_generation_quota)
        job = mark_generation_failed(db, job, "QUEUE_UNAVAILABLE", str(exc))

    return GenerationSubmitResponse(job_id=job.id, status=GenerationStatus(job.status))
