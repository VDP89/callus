"""approve.VOICE_CORPUS debe honrar la env CALLUS_CORPUS.

Regresion del split-brain: `approve` escribia en el corpus del paquete
(`SCORE_DIR/voice_corpus.jsonl`) mientras build/scorer/dedup leian el corpus
por-usuario apuntado por CALLUS_CORPUS. Con la env seteada, ambos deben
resolver al mismo archivo.
"""

from __future__ import annotations

import importlib
from pathlib import Path


def _reload_approve():
    import callus.approve as approve

    return importlib.reload(approve)


def test_voice_corpus_honors_env(monkeypatch, tmp_path):
    target = tmp_path / "mi_corpus.jsonl"
    monkeypatch.setenv("CALLUS_CORPUS", str(target))
    approve = _reload_approve()
    assert target == approve.VOICE_CORPUS


def test_voice_corpus_default_without_env(monkeypatch):
    monkeypatch.delenv("CALLUS_CORPUS", raising=False)
    approve = _reload_approve()
    # Fallback al default del paquete (SCORE_DIR/voice_corpus.jsonl).
    assert approve.VOICE_CORPUS.name == "voice_corpus.jsonl"
    assert approve.VOICE_CORPUS == approve.SCORE_DIR / "voice_corpus.jsonl"


def test_voice_corpus_blank_env_falls_back(monkeypatch):
    # Env vacia (string "") no debe ganarle al default.
    monkeypatch.setenv("CALLUS_CORPUS", "")
    approve = _reload_approve()
    assert approve.VOICE_CORPUS == approve.SCORE_DIR / "voice_corpus.jsonl"


def test_reload_restores_env_state(monkeypatch):
    # Higiene: dejar el modulo recargado con el estado real del entorno.
    approve = _reload_approve()
    assert isinstance(approve.VOICE_CORPUS, Path)
