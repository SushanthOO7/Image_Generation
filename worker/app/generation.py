from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from backend.app.models import GenerationJob
from worker.app.image_renderer import render_placeholder_image
from worker.app.settings import WorkerSettings


@dataclass(frozen=True)
class GeneratedImage:
    image_bytes: bytes
    width: int
    height: int
    seed: int | None = None


def derive_candidate_seed(job: GenerationJob, candidate_index: int = 1) -> int:
    if job.seed is not None:
        return (job.seed + candidate_index - 1) % 2_147_483_647
    return int(sha256(f"{job.id}:{candidate_index}".encode()).hexdigest()[:8], 16) % 2_147_483_647


class ImageGenerator(Protocol):
    def generate(self, job: GenerationJob, candidate_index: int = 1) -> GeneratedImage:
        pass


class MockImageGenerator:
    def generate(self, job: GenerationJob, candidate_index: int = 1) -> GeneratedImage:
        width = job.width or 1024
        height = job.height or 1024
        seed = derive_candidate_seed(job, candidate_index)
        prompt = job.expanded_prompt or job.original_prompt
        return GeneratedImage(
            image_bytes=render_placeholder_image(
                f"{prompt}\n\nCandidate {candidate_index} seed {seed}",
                size=(width, height),
            ),
            width=width,
            height=height,
            seed=seed,
        )


def build_image_generator(settings: WorkerSettings) -> ImageGenerator:
    if settings.generation_backend == "flux":
        from worker.app.flux_generator import FluxImageGenerator

        return FluxImageGenerator(settings)
    return MockImageGenerator()
