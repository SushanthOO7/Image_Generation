from celery import Celery

from backend.app.settings import load_settings

settings = load_settings()

celery_app = Celery(
    "flux-platform-api",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


def enqueue_generation(job_id: str) -> str:
    task = celery_app.send_task("worker.generate_image", args=[job_id], queue="generation:normal")
    return task.id


def terminate_generation_task(task_id: str) -> None:
    celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
