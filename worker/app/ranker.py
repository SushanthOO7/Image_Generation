from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from PIL import Image

from backend.app.models import GenerationJob
from worker.app.generation import GeneratedImage
from worker.app.settings import WorkerSettings


@dataclass(frozen=True)
class CandidateScore:
    prompt_alignment_score: float
    aesthetic_score: float
    quality_score: float
    final_score: float


class CandidateRanker(Protocol):
    def score(
        self,
        job: GenerationJob,
        generated: GeneratedImage,
        candidate_index: int,
        candidate_count: int,
    ) -> CandidateScore:
        pass


class HeuristicRanker:
    def score(
        self,
        job: GenerationJob,
        generated: GeneratedImage,
        candidate_index: int,
        candidate_count: int,
    ) -> CandidateScore:
        aspect_balance = min(generated.width, generated.height) / max(generated.width, generated.height)
        prompt_alignment_score = min(0.72 + candidate_index * 0.04, 0.98)
        aesthetic_score = min(0.78 + aspect_balance * 0.12 + (candidate_count - candidate_index) * 0.015, 0.98)
        quality_score = min(0.8 + candidate_index * 0.012, 0.98)
        final_score = round(
            prompt_alignment_score * 0.4 + aesthetic_score * 0.3 + quality_score * 0.3,
            4,
        )
        return CandidateScore(
            prompt_alignment_score=round(prompt_alignment_score, 4),
            aesthetic_score=round(aesthetic_score, 4),
            quality_score=round(quality_score, 4),
            final_score=final_score,
        )


class ClipRanker:
    def __init__(self, model_id: str) -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = CLIPProcessor.from_pretrained(model_id)
        self.model = CLIPModel.from_pretrained(model_id).to(self.device)
        self.model.eval()

    def score(
        self,
        job: GenerationJob,
        generated: GeneratedImage,
        candidate_index: int,
        candidate_count: int,
    ) -> CandidateScore:
        prompt = job.expanded_prompt or job.original_prompt
        with Image.open(BytesIO(generated.image_bytes)) as image:
            image = image.convert("RGB")
            inputs = self.processor(text=[prompt], images=[image], return_tensors="pt", padding=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.no_grad():
            outputs = self.model(**inputs)
            similarity = outputs.logits_per_image.softmax(dim=1)[0, 0].item()

        aspect_balance = min(generated.width, generated.height) / max(generated.width, generated.height)
        prompt_alignment_score = max(0.0, min(similarity, 1.0))
        aesthetic_score = min(0.78 + aspect_balance * 0.12 + (candidate_count - candidate_index) * 0.01, 0.98)
        quality_score = min(0.82 + candidate_index * 0.01, 0.98)
        final_score = round(
            prompt_alignment_score * 0.5 + aesthetic_score * 0.25 + quality_score * 0.25,
            4,
        )
        return CandidateScore(
            prompt_alignment_score=round(prompt_alignment_score, 4),
            aesthetic_score=round(aesthetic_score, 4),
            quality_score=round(quality_score, 4),
            final_score=final_score,
        )


def build_ranker(settings: WorkerSettings) -> CandidateRanker:
    if settings.ranker_backend == "clip":
        return ClipRanker(settings.clip_ranker_model_id)
    return HeuristicRanker()
