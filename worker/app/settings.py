"""Worker settings."""

from dataclasses import dataclass
import os
from pathlib import Path


def _default_flux_config_path() -> str:
    docker_path = Path("/app/model_configs/flux2.yaml")
    if docker_path.exists():
        return str(docker_path)
    repo_path = Path(__file__).resolve().parents[2] / "model_configs" / "flux2.yaml"
    return str(repo_path)


@dataclass(frozen=True)
class WorkerSettings:
    worker_name: str = "flux-platform-worker"
    redis_url: str = "redis://redis:6379/0"
    model_root: str = "/models"
    generation_backend: str = "mock"
    default_model_version: str = "flux2-dev-bf16-v1"
    flux_config_path: str = _default_flux_config_path()
    preload_model_on_startup: bool = False
    ranker_backend: str = "heuristic"
    clip_ranker_model_id: str = "openai/clip-vit-base-patch32"
    ranker_fallback_to_heuristic: bool = True
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
        flux_config_path=os.getenv("FLUX_CONFIG_PATH", _default_flux_config_path()),
        preload_model_on_startup=os.getenv("PRELOAD_MODEL_ON_STARTUP", "false").lower() == "true",
        ranker_backend=os.getenv("RANKER_BACKEND", "heuristic"),
        clip_ranker_model_id=os.getenv("CLIP_RANKER_MODEL_ID", "openai/clip-vit-base-patch32"),
        ranker_fallback_to_heuristic=os.getenv("RANKER_FALLBACK_TO_HEURISTIC", "true").lower() == "true",
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        minio_public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000"),
        minio_root_user=os.getenv("MINIO_ROOT_USER", "flux_minio"),
        minio_root_password=os.getenv("MINIO_ROOT_PASSWORD", "flux_minio_password"),
        minio_bucket=os.getenv("MINIO_BUCKET", "generations"),
    )
