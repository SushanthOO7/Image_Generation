from backend.app.models import GenerationJob
from worker.app.generation import GeneratedImage, derive_candidate_seed
from worker.app.model_manager import FluxModelManager
from worker.app.settings import WorkerSettings


class FluxImageGenerator:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.model_manager = FluxModelManager(settings)

    def generate(self, job: GenerationJob, candidate_index: int = 1) -> GeneratedImage:
        import torch

        config = self.model_manager.config
        pipeline = self.model_manager.get_pipeline()

        width = job.width or int(config.get("default_width", 1024))
        height = job.height or int(config.get("default_height", 1024))
        steps = job.steps or int(config.get("default_num_inference_steps", 28))
        guidance = job.guidance or float(config.get("default_guidance_scale", 3.5))
        seed = derive_candidate_seed(job, candidate_index)
        generator = torch.Generator(device="cpu").manual_seed(seed)

        image = pipeline(
            prompt=job.expanded_prompt or job.original_prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=generator,
        ).images[0]

        from io import BytesIO

        output = BytesIO()
        image.save(output, format="WEBP", quality=92)
        return GeneratedImage(image_bytes=output.getvalue(), width=width, height=height, seed=seed)
