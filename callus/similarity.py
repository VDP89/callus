"""Voice-similarity layer — a cheap, local, deterministic complement to the
LLM-as-judge.

The judge (``callus.score``) measures voice distance with an LLM. This module
adds a second, free, offline signal: how lexically close a draft is to the
author's own corpus, via character n-gram cosine similarity against the most
similar samples the author actually wrote. No model, no network, no API cost.

The backend is pluggable. The default is :class:`LexicalSimilarity` (pure
Python, zero dependencies). A semantic-embeddings backend can replace it
without touching callers: set ``CALLUS_SIMILARITY_BACKEND=module:Attr`` to a
class implementing :class:`SimilarityBackend` (shipped later as the optional
``callus[embeddings]`` extra). Lexical similarity is a coarse proxy — high
similarity does not prove voice, but low similarity is a cheap red flag worth
an LLM look.
"""
from __future__ import annotations

import importlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Protocol, runtime_checkable

from callus.prompt_template import _resolve_corpus_path


@runtime_checkable
class SimilarityBackend(Protocol):
    """A fitted draft-vs-corpus similarity scorer returning 0..1."""

    name: str

    def fit(self, corpus_texts: list[str]) -> SimilarityBackend: ...

    def score(self, draft: str) -> float: ...


def _char_ngrams(text: str, n: int) -> Counter:
    t = re.sub(r"\s+", " ", text.lower()).strip()
    if len(t) < n:
        return Counter()
    return Counter(t[i : i + n] for i in range(len(t) - n + 1))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class LexicalSimilarity:
    """Character n-gram cosine against the author's corpus (pure Python).

    The score is the mean of the top-``top_k`` per-sample cosine similarities,
    so it measures "does this resemble the kind of thing the author writes"
    rather than washing the whole corpus into one average.
    """

    name = "lexical-charngram"

    def __init__(self, n: int = 4, top_k: int = 5) -> None:
        self.n = n
        self.top_k = top_k
        self._samples: list[Counter] = []

    def fit(self, corpus_texts: list[str]) -> LexicalSimilarity:
        self._samples = [g for t in corpus_texts if (g := _char_ngrams(t, self.n))]
        return self

    def score(self, draft: str) -> float:
        d = _char_ngrams(draft, self.n)
        if not d or not self._samples:
            return 0.0
        sims = sorted((_cosine(d, s) for s in self._samples), reverse=True)
        k = min(self.top_k, len(sims))
        return sum(sims[:k]) / k


def resolve_backend() -> SimilarityBackend:
    """Return the active backend. ``CALLUS_SIMILARITY_BACKEND=module:Attr`` swaps it."""
    spec = os.environ.get("CALLUS_SIMILARITY_BACKEND")
    if not spec:
        return LexicalSimilarity()
    mod_name, _, attr = spec.partition(":")
    if not mod_name or not attr:
        raise ValueError(
            f"CALLUS_SIMILARITY_BACKEND must be 'module:Attr', got {spec!r}"
        )
    obj = getattr(importlib.import_module(mod_name), attr)
    return obj() if isinstance(obj, type) else obj


def _load_corpus_texts(corpus_path: str | Path | None = None) -> list[str]:
    path = Path(corpus_path) if corpus_path else _resolve_corpus_path()
    if not path.exists():
        return []
    texts: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("text")
            if t:
                texts.append(t)
    return texts


def voice_similarity(
    draft: str,
    *,
    corpus_path: str | Path | None = None,
    backend: SimilarityBackend | None = None,
) -> dict:
    """How lexically close ``draft`` is to the author's corpus.

    Returns ``{"similarity": 0-100, "backend": name, "corpus_size": N}``.
    Higher means closer to the author's voice. ``similarity`` is 0 when no
    corpus is available (point ``CALLUS_CORPUS`` at one, or pass ``corpus_path``).
    """
    be = backend or resolve_backend()
    texts = _load_corpus_texts(corpus_path)
    if not texts:
        return {"similarity": 0, "backend": be.name, "corpus_size": 0, "note": "no corpus"}
    be.fit(texts)
    return {
        "similarity": round(be.score(draft) * 100),
        "backend": be.name,
        "corpus_size": len(texts),
    }


def similarity_file(
    path: str | Path,
    *,
    corpus_path: str | Path | None = None,
    backend: SimilarityBackend | None = None,
) -> dict:
    """:func:`voice_similarity` on a file's contents."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return voice_similarity(text, corpus_path=corpus_path, backend=backend)


__all__ = [
    "LexicalSimilarity",
    "SimilarityBackend",
    "resolve_backend",
    "similarity_file",
    "voice_similarity",
]
