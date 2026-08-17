"""Worker settings."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class WorkerSettings:
    worker_name: str = "flux-platform-worker"
    redis_url: str = "redis://redis:6379/0"
    model_root: str = "/models"
    generation_backend: str = "mock"
    default_model_version: str = "flux2-dev-bf16-v1"
    flux_config_path: str = "/app/model_configs/flux2.yaml"
    preload_model_on_startup: bool = False
    minio_endpoint: str = "http://minio:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "flux_minio"
    minio_root_password: str = "flux_minio_password"
    minio_bucket: str = "generations"


def load_worker_settings() -> WorkerSettings:
    return WorkerSettings(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        model_root=os.getenv("MODEL_ROOT", "/models"),
        generation_backend=os.getenv("GENERATION_BACKEND", "mock"),
        default_model_version=os.getenv("DEFAULT_MODEL_VERSION", "flux2-dev-bf16-v1"),
        flux_config_path=os.getenv("FLUX_CONFIG_PATH", "/app/model_configs/flux2.yaml"),
        preload_model_on_startup=os.getenv("PRELOAD_MODEL_ON_STARTUP", "false").lower() == "true",
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        minio_public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000"),
        minio_root_user=os.getenv("MINIO_ROOT_USER", "flux_minio"),
        minio_root_password=os.getenv("MINIO_ROOT_PASSWORD", "flux_minio_password"),
        minio_bucket=os.getenv("MINIO_BUCKET", "generations"),
    )
