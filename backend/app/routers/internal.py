from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.monitoring import collect_system_snapshot, prometheus_metrics
from backend.app.queue import get_worker_health
from backend.app.settings import load_settings

router = APIRouter(tags=["internal"])
settings = load_settings()


@router.get("/internal/health")
def health() -> dict[str, str]:
    return {"status": "up and running", "service": settings.app_name}


@router.get("/internal/system")
def system_status(db: Session = Depends(get_db)) -> dict[str, object]:
    worker_health = get_worker_health(settings.worker_health_timeout_seconds)
    return collect_system_snapshot(db, worker_health=worker_health).__dict__


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> Response:
    worker_health = get_worker_health(settings.worker_health_timeout_seconds)
    return Response(
        content=prometheus_metrics(collect_system_snapshot(db, worker_health=worker_health)),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
