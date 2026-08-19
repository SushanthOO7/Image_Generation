from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models import GenerationJob, User
from backend.app.repositories import get_generation_job


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def get_owned_generation_or_404(db: Session, job_id: str, user: User) -> GenerationJob:
    job = get_generation_job(db, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return job
