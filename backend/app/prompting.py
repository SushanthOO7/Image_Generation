from dataclasses import dataclass
from pathlib import Path

from backend.app.schemas import GenerationRequest


ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:3": (1152, 864),
}

DEFAULT_STYLE_PRESETS: dict[str, dict[str, str]] = {
    "none": {},
    "cinematic": {
        "lighting": "cinematic directional lighting",
        "composition": "film still composition",
        "detail": "rich atmosphere and natural depth",
    },
    "product": {
        "lighting": "clean studio lighting",
        "composition": "premium product photography composition",
        "detail": "crisp material detail and controlled reflections",
    },
    "editorial": {
        "lighting": "soft editorial lighting",
        "composition": "magazine cover composition",
        "detail": "tasteful styling and refined color grading",
    },
}

DEFAULT_QUALITY_PRESETS: dict[str, dict[str, float | int]] = {
    "fast": {"steps": 18, "guidance": 3.0, "candidates": 1},
    "standard": {"steps": 28, "guidance": 3.5, "candidates": 2},
    "ultra": {"steps": 40, "guidance": 4.0, "candidates": 4},
}


@dataclass(frozen=True)
class GenerationPlan:
    expanded_prompt: str
    width: int
    height: int
    steps: int
    guidance: float
    candidate_count: int


def load_section_config(path: str, fallback: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    config_path = Path(path)
    if not config_path.exists():
        return fallback

    config: dict[str, dict[str, str]] = {}
    current_section: str | None = None
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        if not raw_line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            config[current_section] = {}
            continue

        if current_section is None or ":" not in line:
            continue

        key, value = line.split(":", 1)
        config[current_section][key.strip()] = value.strip().strip('"')

    return config or fallback


def build_generation_plan(
    request: GenerationRequest,
    prompt_presets_path: str,
    quality_presets_path: str,
) -> GenerationPlan:
    style_presets = load_section_config(prompt_presets_path, DEFAULT_STYLE_PRESETS)
    quality_presets = load_section_config(quality_presets_path, DEFAULT_QUALITY_PRESETS)

    width, height = ASPECT_RATIOS[request.aspect_ratio]
    style_parts = [
        value
        for value in style_presets.get(request.style, {}).values()
        if value
    ]
    expanded_prompt = request.prompt.strip()
    if style_parts:
        expanded_prompt = f"{expanded_prompt}. {', '.join(style_parts)}."

    quality = quality_presets[request.quality]
    return GenerationPlan(
        expanded_prompt=expanded_prompt,
        width=width,
        height=height,
        steps=int(quality["steps"]),
        guidance=float(quality["guidance"]),
        candidate_count=int(quality["candidates"]),
    )
