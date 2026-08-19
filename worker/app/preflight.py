from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from worker.app.model_config import load_simple_yaml
from worker.app.settings import WorkerSettings


@dataclass(frozen=True)
class WorkerPreflightResult:
    ok: bool
    lines: tuple[str, ...]


def _bool_config(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _configured_gpu_indexes(config: dict[str, object]) -> list[int]:
    indexes: list[int] = []
    for key, value in config.items():
        if not key.startswith("max_memory_gpu_") or not value:
            continue
        try:
            indexes.append(int(key.removeprefix("max_memory_gpu_")))
        except ValueError:
            continue
    return sorted(indexes)


def _model_root_has_files(model_root: Path) -> bool:
    if not model_root.exists() or not model_root.is_dir():
        return False
    return any(path.is_file() for path in model_root.rglob("*"))


def validate_worker_environment(settings: WorkerSettings, require_flux: bool | None = None) -> WorkerPreflightResult:
    lines: list[str] = [
        f"generation_backend={settings.generation_backend}",
        f"model_root={settings.model_root}",
        f"flux_config_path={settings.flux_config_path}",
        f"CUDA_VISIBLE_DEVICES={os.getenv('CUDA_VISIBLE_DEVICES', '<unset>')}",
    ]
    errors: list[str] = []

    if settings.generation_backend not in {"mock", "flux"}:
        errors.append("GENERATION_BACKEND must be either 'mock' or 'flux'.")

    flux_required = settings.generation_backend == "flux" if require_flux is None else require_flux
    config_path = Path(settings.flux_config_path)
    config: dict[str, object] = {}
    if flux_required or settings.generation_backend == "flux":
        if not config_path.exists():
            errors.append(f"FLUX_CONFIG_PATH does not exist: {config_path}")
        else:
            config = load_simple_yaml(str(config_path))
            lines.append(f"model_id={config.get('model_id', '<unset>')}")
            lines.append(f"device={config.get('device', 'cuda')}")
            lines.append(f"device_map={config.get('device_map', '<unset>')}")

    try:
        import torch
    except ImportError:
        lines.append("torch=not installed")
        if flux_required:
            errors.append("Install worker/requirements-ml.txt before running GENERATION_BACKEND=flux.")
        return WorkerPreflightResult(ok=not errors, lines=tuple([*lines, *errors]))

    cuda_available = torch.cuda.is_available()
    cuda_count = torch.cuda.device_count()
    lines.append(f"torch_cuda_available={cuda_available}")
    lines.append(f"torch_cuda_device_count={cuda_count}")
    for index in range(cuda_count):
        lines.append(f"cuda:{index}={torch.cuda.get_device_name(index)}")

    if flux_required and not cuda_available:
        errors.append("GENERATION_BACKEND=flux requires CUDA, but PyTorch cannot see a CUDA device.")

    invalid_indexes = [index for index in _configured_gpu_indexes(config) if index >= cuda_count]
    if invalid_indexes:
        errors.append(
            f"Invalid max_memory_gpu_N entries for invisible devices: {invalid_indexes}. "
            "Remove those entries or expose enough GPUs."
        )

    if flux_required:
        model_root = Path(settings.model_root)
        local_files_only = _bool_config(config.get("local_files_only", True))
        if not model_root.exists():
            errors.append(f"MODEL_ROOT does not exist: {model_root}")
        elif local_files_only and not _model_root_has_files(model_root):
            errors.append(
                f"MODEL_ROOT has no model files: {model_root}. "
                "Download FLUX.2 weights first or set local_files_only=false in the config."
            )

    return WorkerPreflightResult(ok=not errors, lines=tuple([*lines, *errors]))
