from worker.app.model_config import load_simple_yaml
from worker.app.settings import WorkerSettings


def worker_health(settings: WorkerSettings) -> dict[str, str | bool]:
    config = load_simple_yaml(settings.flux_config_path)
    return {
        "worker": settings.worker_name,
        "backend": settings.generation_backend,
        "model_id": str(config.get("model_id", "unknown")),
        "model_version": str(config.get("model_version", settings.default_model_version)),
        "flux_config_found": True,
    }
