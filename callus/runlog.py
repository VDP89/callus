"""Per-call JSONL log for score / rewrite operations.

Every ``score_draft`` and ``rewrite_draft`` call appends one row to a JSONL
file. The ``callus stats`` command reads back these rows and aggregates
them into a usage report.

Failure is silent on purpose: a logging hiccup must never break a user's
score or rewrite call. Same principle as ``fscars.core.log``.

Resolution order for the log path:

1. ``CALLUS_LOG_PATH`` environment variable (full file path).
2. ``~/.callus/runs.jsonl`` (created on first write).

The log is per-user, not per-project. If you operate multiple voices on
the same machine, point ``CALLUS_LOG_PATH`` at distinct files.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Approximate per-call cost (Haiku, ~2.5k input + ~500 output tokens).
# Override per-row if you call with a different model.
DEFAULT_COST_USD_SCORE = 0.002
DEFAULT_COST_USD_REWRITE_PER_ITER = 0.004


def _resolve_log_path() -> Path:
    env = os.environ.get("CALLUS_LOG_PATH")
    if env:
        return Path(env)
    return Path.home() / ".callus" / "runs.jsonl"


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def log_run(record: dict[str, Any]) -> bool:
    """Append a single record. Returns True on success, False on any failure."""
    try:
        path = _resolve_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def log_score(
    *,
    draft: str,
    ai_score: int,
    voice_distance: int,
    tells_density: int,
    structural_ai_patterns: int,
    language_detected: str,
    verdict: str,
    parse_ok: bool,
    top_tells: list[dict[str, str]],
    latency_sec: float,
    model: str,
) -> bool:
    """Convenience wrapper. Drops the draft body but keeps a hash."""
    record = {
        "op": "score",
        "draft_hash": _hash(draft),
        "draft_words": len(draft.split()),
        "ai_score": ai_score,
        "voice_distance": voice_distance,
        "tells_density": tells_density,
        "structural_ai_patterns": structural_ai_patterns,
        "language": language_detected,
        "verdict": verdict,
        "parse_ok": parse_ok,
        "tell_categories": [
            (t.get("category") or "?") for t in top_tells[:5]
        ],
        "tell_severities": [
            (t.get("severity") or "?") for t in top_tells[:5]
        ],
        "latency_sec": round(latency_sec, 2),
        "model": model,
        "cost_usd_estimated": DEFAULT_COST_USD_SCORE,
    }
    return log_run(record)


def log_rewrite(
    *,
    original_draft: str,
    initial_score: int,
    final_score: int,
    target_score: int,
    iterations: list[dict[str, Any]],
    stopped_reason: str,
    final_tells: list[dict[str, str]],
    latency_sec: float,
    model: str,
) -> bool:
    """Append a rewrite run with the score trajectory."""
    trajectory = [
        {"iter": it.get("iteration", i), "score": it.get("score")}
        for i, it in enumerate(iterations)
    ]
    n_calls = max(len(iterations) - 1, 0)  # iter 0 is the initial score
    cost = DEFAULT_COST_USD_SCORE + n_calls * DEFAULT_COST_USD_REWRITE_PER_ITER
    record = {
        "op": "rewrite",
        "draft_hash": _hash(original_draft),
        "draft_words": len(original_draft.split()),
        "initial_score": initial_score,
        "final_score": final_score,
        "target_score": target_score,
        "score_drop": initial_score - final_score,
        "target_reached": final_score <= target_score,
        "iterations": len(iterations),
        "trajectory": trajectory,
        "stopped_reason": stopped_reason,
        "final_tell_categories": [
            (t.get("category") or "?") for t in final_tells[:5]
        ],
        "latency_sec": round(latency_sec, 2),
        "model": model,
        "cost_usd_estimated": round(cost, 4),
    }
    return log_run(record)


def read_runs(*, log_path: Path | None = None) -> list[dict]:
    """Read every row. Used by ``callus stats``. Skips malformed lines."""
    path = log_path or _resolve_log_path()
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


__all__ = [
    "DEFAULT_COST_USD_REWRITE_PER_ITER",
    "DEFAULT_COST_USD_SCORE",
    "log_rewrite",
    "log_run",
    "log_score",
    "read_runs",
]
