from dataclasses import dataclass

from worker.app.generation import GeneratedImage


@dataclass(frozen=True)
class CandidateScore:
    prompt_alignment_score: float
    aesthetic_score: float
    quality_score: float
    final_score: float


class HeuristicRanker:
    def score(self, generated: GeneratedImage, candidate_index: int, candidate_count: int) -> CandidateScore:
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
