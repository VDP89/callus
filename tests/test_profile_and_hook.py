"""Tests for the dynamic voice profile and the packaged capture hook.

None of these require a live ``claude`` CLI.
"""

from __future__ import annotations

import json

import pytest

from callus.hooks import voice_corpus_close as hook
from callus.prompt_template import (
    DEFAULT_PROFILE,
    ProfileError,
    build_prompt,
    resolve_author,
    resolve_profile,
    using_default_profile,
)


def test_default_profile_is_not_author_specific(monkeypatch):
    monkeypatch.delenv("CALLUS_PROFILE", raising=False)
    prof = resolve_profile()
    assert prof == DEFAULT_PROFILE
    assert "Victor" not in prof
    assert using_default_profile() is True


def test_profile_precedence_arg_over_env(tmp_path, monkeypatch):
    env_file = tmp_path / "env.md"
    env_file.write_text("ENV PROFILE RULES", encoding="utf-8")
    arg_file = tmp_path / "arg.md"
    arg_file.write_text("ARG PROFILE RULES", encoding="utf-8")
    monkeypatch.setenv("CALLUS_PROFILE", str(env_file))
    assert resolve_profile().strip() == "ENV PROFILE RULES"
    assert resolve_profile(str(arg_file)).strip() == "ARG PROFILE RULES"
    assert using_default_profile(str(arg_file)) is False


def test_empty_profile_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.delenv("CALLUS_PROFILE", raising=False)
    empty = tmp_path / "empty.md"
    empty.write_text("   \n", encoding="utf-8")
    assert resolve_profile(str(empty)) == DEFAULT_PROFILE


def test_profile_error_on_unreadable(tmp_path, monkeypatch):
    monkeypatch.delenv("CALLUS_PROFILE", raising=False)
    with pytest.raises(ProfileError):
        resolve_profile(str(tmp_path / "does_not_exist.md"))


def test_resolve_author(monkeypatch):
    monkeypatch.delenv("CALLUS_AUTHOR", raising=False)
    assert resolve_author() == "the author"
    assert resolve_author("Jane") == "Jane"
    monkeypatch.setenv("CALLUS_AUTHOR", "Sam")
    assert resolve_author() == "Sam"


def test_build_prompt_uses_given_profile_and_author(monkeypatch):
    monkeypatch.delenv("CALLUS_CORPUS", raising=False)
    prompt = build_prompt("draft body", profile="BE TERSE AND CONCRETE", author="Jane Roe")
    assert "BE TERSE AND CONCRETE" in prompt
    assert "Jane Roe" in prompt
    assert "Victor" not in prompt
    assert "draft body" in prompt


def test_hook_close_signal():
    assert hook.is_close_signal("ok, cerramos aca") is True
    assert hook.is_close_signal("let's wrap up for today") is True
    assert hook.is_close_signal("keep going on the feature") is False


def test_hook_close_signal_custom_keyword(monkeypatch):
    monkeypatch.setenv("CALLUS_CLOSE_KEYWORDS", "fin del dia, signing off")
    assert hook.is_close_signal("signing off now") is True


def test_hook_clean_candidates_filters_short_and_dupes():
    rows = [
        {"text": "hi", "ts": ""},  # < 30 words -> dropped
        {"text": "word " * 40, "ts": "t1"},  # passes
        {"text": "word " * 40, "ts": "t2"},  # duplicate -> dropped
    ]
    clean = hook.clean_candidates(rows)
    assert len(clean) == 1
    assert clean[0]["words"] >= 30


def test_hook_write_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("CALLUS_PENDING_DIR", str(tmp_path))
    cands = [{"text": "a real prompt " * 10, "ts": "2026-06-02", "words": 30}]
    md = hook.write_pending(cands, session_id="abc123def", ts="20260602T120000")
    assert md.exists()
    jsonl = md.with_suffix(".jsonl")
    assert jsonl.exists()
    body = md.read_text(encoding="utf-8")
    assert "**Veredicto:** [   ]" in body
    assert len(jsonl.read_text(encoding="utf-8").strip().splitlines()) == 1
    json.loads(jsonl.read_text(encoding="utf-8").strip())  # valid jsonl
