"""Minimal smoke tests that do not require a live `claude` CLI."""

from __future__ import annotations

import json

from callus import __version__
from callus.prompt_template import build_prompt, load_corpus_samples
from callus.rewrite import RewriteResult
from callus.score import ScoreResult


def test_version_string():
    assert __version__ == "0.1.0"


def test_score_result_defaults():
    r = ScoreResult(
        ai_score=42,
        voice_distance=40,
        tells_density=45,
        structural_ai_patterns=41,
        language_detected="en",
    )
    assert r.ai_score == 42
    assert r.parse_ok is True
    assert r.top_tells == []
    assert r.top_fixes == []


def test_rewrite_result_initial_state():
    r = RewriteResult(
        original_draft="x",
        best_draft="x",
        initial_score=50,
        final_score=50,
        target_score=25,
    )
    assert r.stopped_reason == ""
    assert r.iterations == []


def test_load_corpus_empty_when_missing(tmp_path, monkeypatch):
    # Point CORPUS_PATH at a non-existent file
    from callus import prompt_template as pt

    fake = tmp_path / "nonexistent.jsonl"
    monkeypatch.setattr(pt, "CORPUS_PATH", fake)
    monkeypatch.delenv("CALLUS_CORPUS", raising=False)
    samples = load_corpus_samples(n=6)
    assert samples == []


def test_load_corpus_reads_jsonl(tmp_path, monkeypatch):
    from callus import prompt_template as pt

    corpus = tmp_path / "corpus.jsonl"
    rows = [
        {"text": "short voice sample one", "ts": "2026-01-01", "words": 4},
        {"text": "another bit of voice writing here that is longer", "ts": "2026-01-02", "words": 9},
    ]
    with corpus.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    monkeypatch.setattr(pt, "CORPUS_PATH", corpus)
    monkeypatch.delenv("CALLUS_CORPUS", raising=False)
    samples = load_corpus_samples(n=6, seed=0)
    assert len(samples) == 2
    assert "voice" in samples[0] or "voice" in samples[1]


def test_build_prompt_includes_draft():
    prompt = build_prompt("here is the draft text to score", corpus_seed=0)
    assert "here is the draft text to score" in prompt
    assert "Victor's voice rules" in prompt or "voice rules" in prompt
    assert "<draft>" in prompt
    assert "</draft>" in prompt


def test_build_prompt_handles_code_fences_in_draft():
    # The draft is wrapped in <draft>...</draft>, not in triple backticks,
    # so a draft containing ``` should not collapse the template. The tag
    # may also appear in instructions; we just require both markers exist.
    draft = "this is a draft\n\n```python\nprint('hi')\n```\n\nend"
    prompt = build_prompt(draft, corpus_seed=0)
    assert "<draft>" in prompt
    assert "</draft>" in prompt
    assert "print('hi')" in prompt


def test_callus_corpus_env_var_resolves(tmp_path, monkeypatch):
    """CALLUS_CORPUS env var is honored by the path resolver."""
    from callus import prompt_template as pt

    corpus = tmp_path / "override.jsonl"
    corpus.touch()
    monkeypatch.setenv("CALLUS_CORPUS", str(corpus))
    assert pt._resolve_corpus_path() == corpus
