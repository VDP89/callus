"""Tests for the lexical voice-similarity layer (no LLM needed)."""

from __future__ import annotations

import json

import pytest

from callus.similarity import (
    LexicalSimilarity,
    SimilarityBackend,
    resolve_backend,
    similarity_file,
    voice_similarity,
)


def _corpus(tmp_path, texts):
    p = tmp_path / "corpus.jsonl"
    p.write_text(
        "\n".join(json.dumps({"text": t, "words": len(t.split())}) for t in texts) + "\n",
        encoding="utf-8",
    )
    return p


def test_lexical_backend_satisfies_protocol():
    assert isinstance(LexicalSimilarity(), SimilarityBackend)


def test_similar_text_scores_higher_than_unrelated(tmp_path, monkeypatch):
    monkeypatch.delenv("CALLUS_CORPUS", raising=False)
    corpus = _corpus(
        tmp_path,
        [
            "ante un dato tecnico que no cerraba habian dos caminos y elegi el costoso",
            "me toco decidir entre dos opciones y fui por la que tenia respaldo en numeros",
        ],
    )
    same = voice_similarity(
        "ante un dato tecnico que no cerraba habian dos caminos", corpus_path=corpus
    )["similarity"]
    diff = voice_similarity(
        "quarterly synergies leverage a paradigm shift across deliverables",
        corpus_path=corpus,
    )["similarity"]
    assert same > diff


def test_no_corpus_returns_zero(tmp_path):
    r = voice_similarity("whatever text", corpus_path=tmp_path / "nope.jsonl")
    assert r["similarity"] == 0
    assert r["corpus_size"] == 0


def test_voice_similarity_shape(tmp_path):
    corpus = _corpus(tmp_path, ["one sample of writing here", "another sample of text here"])
    r = voice_similarity("a sample of writing here", corpus_path=corpus)
    assert {"similarity", "backend", "corpus_size"} <= set(r)
    assert 0 <= r["similarity"] <= 100
    assert r["backend"] == "lexical-charngram"
    assert r["corpus_size"] == 2


def test_similarity_file(tmp_path):
    corpus = _corpus(tmp_path, ["sample writing one here", "sample writing two here"])
    draft = tmp_path / "d.md"
    draft.write_text("sample writing here too", encoding="utf-8")
    r = similarity_file(str(draft), corpus_path=corpus)
    assert 0 <= r["similarity"] <= 100


def test_resolve_backend_default_and_env(monkeypatch):
    monkeypatch.delenv("CALLUS_SIMILARITY_BACKEND", raising=False)
    assert resolve_backend().name == "lexical-charngram"
    monkeypatch.setenv("CALLUS_SIMILARITY_BACKEND", "callus.similarity:LexicalSimilarity")
    assert isinstance(resolve_backend(), LexicalSimilarity)


def test_resolve_backend_bad_spec(monkeypatch):
    monkeypatch.setenv("CALLUS_SIMILARITY_BACKEND", "notavalidspec")
    with pytest.raises(ValueError):
        resolve_backend()
