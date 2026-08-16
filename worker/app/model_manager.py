from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from worker.app.model_config import load_simple_yaml
from worker.app.settings import WorkerSettings


@dataclass
class ModelHealth:
    model_loaded: bool
    model_id: str
    model_version: str
    backend: str


class FluxModelManager:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.config = load_simple_yaml(settings.flux_config_path)
        self.pipeline: Any | None = None

    def load(self) -> Any:
        if self.pipeline is not None:
            return self.pipeline

        if bool(self.config.get("enable_parallel_loading", False)):
            os.environ["HF_ENABLE_PARALLEL_LOADING"] = "true"
            os.environ["HF_PARALLEL_LOADING_WORKERS"] = str(self.config.get("parallel_loading_workers", 8))

        import torch
        from diffusers import DiffusionPipeline

        try:
            from diffusers import Flux2Pipeline
        except ImportError:
            Flux2Pipeline = DiffusionPipeline

        dtype_name = str(self.config.get("precision", "bfloat16"))
        torch_dtype = torch.bfloat16 if dtype_name == "bfloat16" else torch.float16
        model_id = str(self.config["model_id"])
        local_model_path = Path(self.settings.model_root) / model_id.replace("/", "--")
        model_path = str(local_model_path) if local_model_path.exists() else model_id
        device_map = self.config.get("device_map")
        max_memory = self._max_memory_config()

        load_kwargs: dict[str, Any] = {
            "dtype": torch_dtype,
            "local_files_only": bool(self.config.get("local_files_only", True)),
            "low_cpu_mem_usage": bool(self.config.get("low_cpu_mem_usage", True)),
        }
        if "use_safetensors" in self.config:
            load_kwargs["use_safetensors"] = bool(self.config["use_safetensors"])
        if "disable_mmap" in self.config:
            load_kwargs["disable_mmap"] = bool(self.config["disable_mmap"])
        if device_map:
            load_kwargs["device_map"] = str(device_map)
        if max_memory:
            load_kwargs["max_memory"] = max_memory

        self.pipeline = Flux2Pipeline.from_pretrained(model_path, **load_kwargs)
        if device_map:
            return self.pipeline
        if bool(self.config.get("enable_cpu_offload", False)):
            self.pipeline.enable_model_cpu_offload()
        else:
            self.pipeline.to(str(self.config.get("device", "cuda")))
        return self.pipeline

    def _max_memory_config(self) -> dict[int, str]:
        max_memory: dict[int, str] = {}
        for index in range(8):
            value = self.config.get(f"max_memory_gpu_{index}")
            if value:
                max_memory[index] = str(value)
        return max_memory

    def unload(self) -> None:
        self.pipeline = None

    def reload(self) -> Any:
        self.unload()
        return self.load()

    def get_pipeline(self) -> Any:
        return self.load()

    def get_model_version(self) -> str:
        return str(self.config.get("model_version", self.settings.default_model_version))

    def health_check(self) -> ModelHealth:
        return ModelHealth(
            model_loaded=self.pipeline is not None,
            model_id=str(self.config.get("model_id", "unknown")),
            model_version=self.get_model_version(),
            backend=self.settings.generation_backend,
        )
