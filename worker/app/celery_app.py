from celery import Celery

from worker.app.settings import load_worker_settings

settings = load_worker_settings()

celery_app = Celery(
    settings.worker_name,
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.app.lifecycle", "worker.app.tasks"],
)

celery_app.conf.task_default_queue = "generation:normal"
celery_app.conf.worker_pool = "solo"
celery_app.conf.task_routes = {
    "worker.generate_image": {"queue": "generation:normal"},
}
