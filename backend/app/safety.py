from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class SafetyResult:
    allowed: bool
    reason: str | None = None


DEFAULT_BLOCKED_TERMS = (
    "child sexual",
    "csam",
    "sexual minor",
    "minor nude",
    "self harm",
    "suicide",
)


def check_prompt_safety(prompt: str, config_path: str) -> SafetyResult:
    normalized_prompt = _normalize(prompt)
    for term in _load_blocked_terms(config_path):
        if _normalize(term) in normalized_prompt:
            return SafetyResult(allowed=False, reason=f"Prompt blocked by safety term: {term}")
    return SafetyResult(allowed=True)


def _load_blocked_terms(config_path: str) -> tuple[str, ...]:
    path = Path(config_path)
    if not path.exists():
        return DEFAULT_BLOCKED_TERMS

    terms: list[str] = []
    in_blocked_terms = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "blocked_terms:":
            in_blocked_terms = True
            continue
        if in_blocked_terms and line.startswith("- "):
            terms.append(line[2:].strip().strip('"'))
    return tuple(terms) or DEFAULT_BLOCKED_TERMS


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
