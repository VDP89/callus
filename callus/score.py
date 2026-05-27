"""Score a draft using the LLM-as-judge prompt against Victor's voice.

Wraps ``judge.prompt_template.build_prompt`` + a subprocess call to the
``claude`` CLI (Haiku by default) and returns a parsed dataclass.

Mirrors the architectural pattern of ``fscars.validation.llm`` (Windows-safe
shim resolution via ``shutil.which``, UTF-8 + errors=replace decode, JSON
extraction tolerant of leading/trailing prose).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from callus.prompt_template import build_prompt  # imported as package
except ImportError:
    from callus.prompt_template import build_prompt  # imported as flat module


DEFAULT_MODEL = "haiku"
DEFAULT_TIMEOUT_SEC = 90


@dataclass
class ScoreResult:
    ai_score: int
    voice_distance: int
    tells_density: int
    structural_ai_patterns: int
    language_detected: str
    top_tells: list[dict[str, str]] = field(default_factory=list)
    top_fixes: list[dict[str, str]] = field(default_factory=list)
    verdict: str = "unknown"
    raw_response: str = ""
    parse_ok: bool = True
    error: str | None = None


def _resolve_claude_cli(override: str | None = None) -> str:
    if override:
        return override
    return shutil.which("claude") or "claude"


def _call_claude(prompt: str, *, model: str, claude_cli: str, timeout_sec: int) -> str:
    """Subprocess call to ``claude -p --model <model>`` with the prompt on stdin.

    Returns stdout (stripped) or ``"__ERROR__: <reason>"``.
    """
    try:
        result = subprocess.run(
            [claude_cli, "-p", "--model", model],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "__ERROR__: timeout"
    except (FileNotFoundError, OSError) as exc:
        return f"__ERROR__: {exc}"


def _extract_json(text: str) -> dict[str, Any] | None:
    """Tolerantly extract a JSON object from a possibly-prose response."""
    if not text or text.startswith("__ERROR__"):
        return None
    # Strip code fences if the model wrapped its output despite instructions.
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = fence.group(1) if fence else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return default


def score_draft(
    draft: str,
    *,
    model: str = DEFAULT_MODEL,
    claude_cli: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    corpus_seed: int | None = None,
) -> ScoreResult:
    """Score ``draft`` against Victor's voice. Single LLM call.

    Args:
        draft: Text to evaluate.
        model: Model name forwarded to ``claude -p --model``.
        claude_cli: Override the CLI binary path. None resolves via
            ``shutil.which("claude")``.
        timeout_sec: Subprocess timeout.
        corpus_seed: Forwarded to the corpus sampler for reproducibility
            during evaluation. None = rotates per call.

    Returns:
        A :class:`ScoreResult`. On error, ``parse_ok=False`` and ``error``
        describes the failure mode; numeric axes default to 0.
    """
    cli = _resolve_claude_cli(claude_cli)
    prompt = build_prompt(draft, corpus_seed=corpus_seed)

    # One retry on parse failure (covers the occasional malformed-JSON case)
    raw = ""
    parsed: dict[str, Any] | None = None
    for attempt in range(2):
        raw = _call_claude(prompt, model=model, claude_cli=cli, timeout_sec=timeout_sec)
        if raw.startswith("__ERROR__"):
            if attempt == 0:
                continue
            return ScoreResult(
                ai_score=0,
                voice_distance=0,
                tells_density=0,
                structural_ai_patterns=0,
                language_detected="unknown",
                raw_response=raw[:500],
                parse_ok=False,
                error=raw,
            )
        parsed = _extract_json(raw)
        if parsed is not None:
            break

    if parsed is None:
        return ScoreResult(
            ai_score=0,
            voice_distance=0,
            tells_density=0,
            structural_ai_patterns=0,
            language_detected="unknown",
            raw_response=raw[:500],
            parse_ok=False,
            error="json_parse_failed_after_retry",
        )

    axes = parsed.get("axes", {})
    return ScoreResult(
        ai_score=_coerce_int(parsed.get("ai_score")),
        voice_distance=_coerce_int(axes.get("voice_distance")),
        tells_density=_coerce_int(axes.get("tells_density")),
        structural_ai_patterns=_coerce_int(axes.get("structural_ai_patterns")),
        language_detected=str(parsed.get("language_detected", "unknown"))[:10],
        top_tells=parsed.get("top_tells", []) or [],
        top_fixes=parsed.get("top_fixes", []) or [],
        verdict=str(parsed.get("verdict", "unknown")),
        raw_response=raw[:500],
        parse_ok=True,
    )


def score_file(path: str | Path, **kwargs: Any) -> ScoreResult:
    """Score the contents of a file. Markdown frontmatter is preserved as-is."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return score_draft(text, **kwargs)


__all__ = ["ScoreResult", "score_draft", "score_file"]
