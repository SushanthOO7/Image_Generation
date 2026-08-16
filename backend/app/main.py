from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from kombu.exceptions import KombuError
from sqlalchemy.orm import Session

from backend.app.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.app.database import get_db
from backend.app.models import User
from backend.app.queue import enqueue_generation, terminate_generation_task
from backend.app.rate_limits import check_generation_rate_limit
from backend.app.repositories import (
    archive_generation_job,
    count_active_generation_jobs,
    create_generation_job,
    create_user,
    get_generation_job,
    get_user_by_email,
    list_generation_jobs,
    mark_generation_failed,
    select_generation_output,
    set_generation_task_id,
)
from backend.app.repositories import cancel_generation_job, create_generation_feedback
from backend.app.schemas import (
    ArchiveGenerationResponse,
    AuthRequest,
    AuthResponse,
    CancelGenerationResponse,
    FeedbackRequest,
    FeedbackResponse,
    GenerationHistoryItem,
    GenerationHistoryResponse,
    GenerationLimitsResponse,
    GenerationImage,
    GenerationRequest,
    GenerationStatus,
    GenerationStatusResponse,
    GenerationSubmitResponse,
    LoginRequest,
    SelectOutputRequest,
    SelectOutputResponse,
    UserResponse,
)
from backend.app.settings import load_settings

settings = load_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_image_url(storage_path: str) -> str:
    if storage_path.startswith(("http://", "https://")):
        return storage_path
    endpoint = settings.minio_public_endpoint.rstrip("/")
    bucket = settings.minio_bucket.strip("/")
    key = storage_path.lstrip("/")
    return f"{endpoint}/{bucket}/{key}"


@app.get("/internal/health")
def health() -> dict[str, str]:
    return {"status": "up and running", "service": settings.app_name}


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email or "", role=user.role)


def generation_response(job) -> GenerationStatusResponse:
    images: list[GenerationImage] = []
    sorted_outputs = sorted(job.outputs, key=lambda output: (not output.selected, output.id))
    for output in sorted_outputs:
        images.append(
            GenerationImage(
                id=output.id,
                url=public_image_url(output.storage_path),
                selected=output.selected,
                score=output.final_score,
            )
        )

    return GenerationStatusResponse(
        job_id=job.id,
        status=GenerationStatus(job.status),
        progress=job.progress,
        prompt=job.original_prompt,
        expanded_prompt=job.expanded_prompt,
        width=job.width,
        height=job.height,
        candidate_count=job.candidate_count,
        images=images,
        error_code=job.error_code,
        error_message=job.error_message,
    )


@app.post("/v1/auth/register", response_model=AuthResponse)
def register(
    request: AuthRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    existing_user = get_user_by_email(db, request.email)
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = create_user(db, request.email, hash_password(request.password))
    return AuthResponse(access_token=create_access_token(user), user=user_response(user))


@app.post("/v1/auth/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = get_user_by_email(db, request.email)
    if user is None or user.password_hash is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(access_token=create_access_token(user), user=user_response(user))


@app.get("/v1/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_response(current_user)


@app.get("/v1/me/limits", response_model=GenerationLimitsResponse)
def generation_limits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationLimitsResponse:
    active_jobs = count_active_generation_jobs(db, current_user.id)
    return GenerationLimitsResponse(
        rate_limit_per_minute=settings.generation_rate_limit_per_minute,
        rate_limit_remaining=settings.generation_rate_limit_per_minute,
        rate_limit_reset_seconds=0,
        concurrent_limit=settings.concurrent_generation_limit,
        active_jobs=active_jobs,
    )


@app.post(
    "/v1/generations",
    response_model=GenerationSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_generation(
    request: GenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationSubmitResponse:
    active_jobs = count_active_generation_jobs(db, current_user.id)
    if active_jobs >= settings.concurrent_generation_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Concurrent generation limit reached ({settings.concurrent_generation_limit})",
        )

    rate_limit = check_generation_rate_limit(settings, current_user.id)
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Generation rate limit reached. Try again in {rate_limit.reset_seconds}s",
        )

    job = create_generation_job(
        db,
        request,
        settings.default_model_version,
        user_id=current_user.id,
        prompt_presets_path=settings.prompt_presets_path,
        quality_presets_path=settings.quality_presets_path,
    )
    try:
        task_id = enqueue_generation(job.id)
        job = set_generation_task_id(db, job, task_id)
    except KombuError as exc:
        job = mark_generation_failed(db, job, "QUEUE_UNAVAILABLE", str(exc))
    return GenerationSubmitResponse(job_id=job.id, status=GenerationStatus(job.status))


@app.get("/v1/generations", response_model=GenerationHistoryResponse)
def list_generations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationHistoryResponse:
    jobs = list_generation_jobs(db, current_user.id)
    generations: list[GenerationHistoryItem] = []
    for job in jobs:
        response = generation_response(job)
        generations.append(
            GenerationHistoryItem(
                **response.model_dump(),
                created_at=job.created_at,
                completed_at=job.completed_at,
                archived_at=job.archived_at,
            )
        )
    return GenerationHistoryResponse(generations=generations)


@app.get("/v1/generations/{job_id}", response_model=GenerationStatusResponse)
def get_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationStatusResponse:
    job = get_generation_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")

    return generation_response(job)


@app.post("/v1/generations/{job_id}/cancel", response_model=CancelGenerationResponse)
def cancel_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CancelGenerationResponse:
    job = get_generation_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")

    task_id = job.celery_task_id
    job = cancel_generation_job(db, job)
    if task_id:
        terminate_generation_task(task_id)
    return CancelGenerationResponse(job_id=job.id, status=GenerationStatus(job.status))


@app.post("/v1/generations/{job_id}/select-output", response_model=SelectOutputResponse)
def select_generation_candidate(
    job_id: str,
    request: SelectOutputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SelectOutputResponse:
    job = get_generation_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.status != GenerationStatus.completed.value:
        raise HTTPException(status_code=409, detail="Only completed generations can change selected output")

    try:
        job = select_generation_output(db, job, request.output_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SelectOutputResponse(
        job_id=job.id,
        output_id=request.output_id,
        status=GenerationStatus(job.status),
    )


@app.post("/v1/generations/{job_id}/archive", response_model=ArchiveGenerationResponse)
def archive_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArchiveGenerationResponse:
    job = get_generation_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.status in {GenerationStatus.queued.value, GenerationStatus.generating.value}:
        raise HTTPException(status_code=409, detail="Active generations cannot be archived")

    job = archive_generation_job(db, job)
    return ArchiveGenerationResponse(job_id=job.id, archived_at=job.archived_at)


@app.post("/v1/generations/{job_id}/feedback", response_model=FeedbackResponse)
def submit_generation_feedback(
    job_id: str,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    job = get_generation_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if request.output_id is not None and request.output_id not in {output.id for output in job.outputs}:
        raise HTTPException(status_code=400, detail="Output does not belong to generation job")

    feedback = create_generation_feedback(
        db,
        job,
        output_id=request.output_id,
        liked=request.liked,
        rating=request.rating,
        user_id=current_user.id,
    )
    return FeedbackResponse(
        id=feedback.id,
        generation_id=feedback.generation_id,
        output_id=feedback.output_id,
        liked=feedback.liked,
        rating=feedback.rating,
    )
