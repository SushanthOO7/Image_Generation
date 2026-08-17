import logging
import time

from celery.signals import worker_process_init

from worker.app.generation import build_image_generator
from worker.app.settings import load_worker_settings

_PRELOADED_GENERATOR = None
logger = logging.getLogger(__name__)


def get_preloaded_generator():
    return _PRELOADED_GENERATOR


@worker_process_init.connect
def preload_model(**_kwargs) -> None:
    global _PRELOADED_GENERATOR

    settings = load_worker_settings()
    if not settings.preload_model_on_startup:
        return

    started_at = time.perf_counter()
    logger.info("Preloading generation backend '%s'", settings.generation_backend)
    _PRELOADED_GENERATOR = build_image_generator(settings)
    if hasattr(_PRELOADED_GENERATOR, "model_manager"):
        _PRELOADED_GENERATOR.model_manager.get_pipeline()
    logger.info("Generation backend preload completed in %.2fs", time.perf_counter() - started_at)
