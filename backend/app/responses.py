from backend.app.models import ApiKey, GenerationJob, User
from backend.app.schemas import ApiKeyResponse, GenerationImage, GenerationStatus, GenerationStatusResponse, UserResponse
from backend.app.settings import Settings


def public_image_url(settings: Settings, storage_path: str) -> str:
    if storage_path.startswith(("http://", "https://")):
        return storage_path
    endpoint = settings.minio_public_endpoint.rstrip("/")
    bucket = settings.minio_bucket.strip("/")
    key = storage_path.lstrip("/")
    return f"{endpoint}/{bucket}/{key}"


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email or "", role=user.role, plan=user.plan)


def api_key_response(api_key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
    )


def generation_response(settings: Settings, job: GenerationJob) -> GenerationStatusResponse:
    images: list[GenerationImage] = []
    sorted_outputs = sorted(job.outputs, key=lambda output: (not output.selected, output.id))
    for output in sorted_outputs:
        images.append(
            GenerationImage(
                id=output.id,
                url=public_image_url(settings, output.storage_path),
                selected=output.selected,
                score=output.final_score,
                seed=output.seed,
            )
        )

    return GenerationStatusResponse(
        job_id=job.id,
        status=GenerationStatus(job.status),
        status_message=job.status_message,
        progress=job.progress,
        prompt=job.original_prompt,
        expanded_prompt=job.expanded_prompt,
        width=job.width,
        height=job.height,
        candidate_count=job.candidate_count,
        seed=job.seed,
        images=images,
        generation_time_ms=job.generation_time_ms,
        ranking_time_ms=job.ranking_time_ms,
        upscale_time_ms=job.upscale_time_ms,
        error_code=job.error_code,
        error_message=job.error_message,
    )
