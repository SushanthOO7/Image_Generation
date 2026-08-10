"""Worker settings shared by the Stage 1 skeleton."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class WorkerSettings:
    worker_name: str = "flux-platform-worker"
    redis_url: str = "redis://redis:6380/0"
    model_root: str = "/models"


def load_worker_settings() -> WorkerSettings:
    return WorkerSettings(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6380/0"),
        model_root=os.getenv("MODEL_ROOT", "/models"),
    )
