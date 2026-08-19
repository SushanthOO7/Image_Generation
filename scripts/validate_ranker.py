#!/usr/bin/env python3
"""Validate candidate ranking independently from Celery and FLUX generation."""

from __future__ import annotations

import argparse
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from worker.app.generation import GeneratedImage
from worker.app.ranker import build_ranker
from worker.app.settings import load_worker_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["heuristic", "clip"], default="clip")
    parser.add_argument("--prompt", default="a bright white square on a black background")
    parser.add_argument("--model-id", default=None, help="Override CLIP model id.")
    parser.add_argument("--strict", action="store_true", help="Disable heuristic fallback for CLIP validation.")
    return parser.parse_args()


def _solid_webp(color: tuple[int, int, int], size: tuple[int, int] = (224, 224)) -> bytes:
    from PIL import Image

    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="WEBP", quality=92)
    return output.getvalue()


def main() -> int:
    args = parse_args()
    settings = load_worker_settings()
    settings = replace(
        settings,
        ranker_backend=args.backend,
        clip_ranker_model_id=args.model_id or settings.clip_ranker_model_id,
        ranker_fallback_to_heuristic=not args.strict,
    )

    job = SimpleNamespace(id="ranker-validation", original_prompt=args.prompt, expanded_prompt=None)
    try:
        ranker = build_ranker(settings)
        if ranker.__class__.__name__ == "ClipRanker":
            white = GeneratedImage(image_bytes=_solid_webp((245, 245, 245)), width=224, height=224, seed=1)
            black = GeneratedImage(image_bytes=_solid_webp((5, 5, 5)), width=224, height=224, seed=2)
        else:
            white = GeneratedImage(image_bytes=b"", width=224, height=224, seed=1)
            black = GeneratedImage(image_bytes=b"", width=224, height=224, seed=2)
        white_score = ranker.score(job, white, candidate_index=1, candidate_count=2)
        black_score = ranker.score(job, black, candidate_index=2, candidate_count=2)
    except ImportError as exc:
        print(f"ranker_dependency_missing={exc}")
        return 1
    except Exception as exc:
        print(f"ranker_validation_error={exc}")
        return 1

    print(f"ranker_backend={settings.ranker_backend}")
    print(f"ranker_class={ranker.__class__.__name__}")
    print(
        "candidate=white "
        f"prompt_alignment={white_score.prompt_alignment_score:.4f} "
        f"aesthetic={white_score.aesthetic_score:.4f} "
        f"quality={white_score.quality_score:.4f} "
        f"final={white_score.final_score:.4f}"
    )
    print(
        "candidate=black "
        f"prompt_alignment={black_score.prompt_alignment_score:.4f} "
        f"aesthetic={black_score.aesthetic_score:.4f} "
        f"quality={black_score.quality_score:.4f} "
        f"final={black_score.final_score:.4f}"
    )
    print("ranker_validation=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
