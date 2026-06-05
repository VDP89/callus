"""Single corpus-path resolver: approve AND build-corpus must honor CALLUS_CORPUS.

Regression del split-brain: `approve` escribia en el corpus del paquete y
`build-corpus` tambien (DEFAULT_OUT hardcodeado), mientras score/scorer/hook
leian el corpus por-usuario (CALLUS_CORPUS). Ahora todos resuelven por el unico
`prompt_template._resolve_corpus_path()`, que lee el env en cada llamada.
"""

from __future__ import annotations

import importlib


def _reload(mod_name: str):
    return importlib.reload(importlib.import_module(mod_name))


# --- el resolver canonico (fuente unica) ------------------------------------

def test_resolver_honors_env(monkeypatch, tmp_path):
    target = tmp_path / "mi_corpus.jsonl"
    monkeypatch.setenv("CALLUS_CORPUS", str(target))
    import callus.prompt_template as pt

    assert pt._resolve_corpus_path() == target


def test_resolver_default_without_env(monkeypatch):
    monkeypatch.delenv("CALLUS_CORPUS", raising=False)
    import callus.prompt_template as pt

    assert pt._resolve_corpus_path() == pt.CORPUS_PATH
    assert pt._resolve_corpus_path().name == "voice_corpus.jsonl"


def test_resolver_blank_env_falls_back(monkeypatch):
    # "" no debe ganarle al default (Path("") seria el cwd, no un corpus util).
    monkeypatch.setenv("CALLUS_CORPUS", "")
    import callus.prompt_template as pt

    assert pt._resolve_corpus_path() == pt.CORPUS_PATH


# --- los dos write-paths que causaban el split-brain ------------------------

def test_approve_wires_to_resolver(monkeypatch, tmp_path):
    # approve.VOICE_CORPUS se fija al importar -> reload tras setear el env.
    target = tmp_path / "approve_corpus.jsonl"
    monkeypatch.setenv("CALLUS_CORPUS", str(target))
    approve = _reload("callus.approve")
    assert target == approve.VOICE_CORPUS


def test_build_corpus_default_out_honors_env(monkeypatch, tmp_path):
    # default_out() resuelve en cada llamada -> sin reload.
    target = tmp_path / "build_corpus.jsonl"
    monkeypatch.setenv("CALLUS_CORPUS", str(target))
    import callus.build_corpus as bc

    assert bc.default_out() == str(target)
