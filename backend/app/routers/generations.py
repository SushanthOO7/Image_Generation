from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.dependencies import get_owned_generation_or_404
from backend.app.models import User
from backend.app.queue import terminate_generation_task
from backend.app.repositories import (
    archive_generation_job,
    cancel_generation_job,
    create_generation_feedback,
    list_generation_jobs,
    select_generation_output,
)
from backend.app.responses import generation_response
from backend.app.schemas import (
    ArchiveGenerationResponse,
    CancelGenerationResponse,
    FeedbackRequest,
    FeedbackResponse,
    GenerationHistoryItem,
    GenerationHistoryResponse,
    GenerationRequest,
    GenerationStatus,
    GenerationStatusResponse,
    GenerationSubmitResponse,
    SelectOutputRequest,
    SelectOutputResponse,
)
from backend.app.services.generations import submit_generation_job
from backend.app.settings import load_settings

router = APIRouter(prefix="/v1/generations", tags=["generations"])
settings = load_settings()


@router.post("", response_model=GenerationSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_generation(
    request: GenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationSubmitResponse:
    return submit_generation_job(db, settings, request, current_user)


@router.get("", response_model=GenerationHistoryResponse)
def list_generations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationHistoryResponse:
    jobs = list_generation_jobs(db, current_user.id)
    generations: list[GenerationHistoryItem] = []
    for job in jobs:
        response = generation_response(settings, job)
        generations.append(
            GenerationHistoryItem(
                **response.model_dump(),
                created_at=job.created_at,
                completed_at=job.completed_at,
                archived_at=job.archived_at,
            )
        )
    return GenerationHistoryResponse(generations=generations)


@router.get("/{job_id}", response_model=GenerationStatusResponse)
def get_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationStatusResponse:
    job = get_owned_generation_or_404(db, job_id, current_user)
    return generation_response(settings, job)


@router.post("/{job_id}/cancel", response_model=CancelGenerationResponse)
def cancel_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CancelGenerationResponse:
    job = get_owned_generation_or_404(db, job_id, current_user)
    task_id = job.celery_task_id
    job = cancel_generation_job(db, job)
    if task_id:
        terminate_generation_task(task_id)
    return CancelGenerationResponse(job_id=job.id, status=GenerationStatus(job.status))


@router.post("/{job_id}/select-output", response_model=SelectOutputResponse)
def select_generation_candidate(
    job_id: str,
    request: SelectOutputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SelectOutputResponse:
    job = get_owned_generation_or_404(db, job_id, current_user)
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


@router.post("/{job_id}/archive", response_model=ArchiveGenerationResponse)
def archive_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArchiveGenerationResponse:
    job = get_owned_generation_or_404(db, job_id, current_user)
    if job.status in {GenerationStatus.queued.value, GenerationStatus.generating.value}:
        raise HTTPException(status_code=409, detail="Active generations cannot be archived")

    job = archive_generation_job(db, job)
    return ArchiveGenerationResponse(job_id=job.id, archived_at=job.archived_at)


@router.post("/{job_id}/feedback", response_model=FeedbackResponse)
def submit_generation_feedback(
    job_id: str,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    job = get_owned_generation_or_404(db, job_id, current_user)
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
