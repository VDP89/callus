"""Build the LLM-as-judge prompt that scores a draft against an author's voice.

Conceptual framing (critical):
- This is NOT a classifier of P(LLM-generated).
- It scores 'distance from the author's natural voice' + 'density of AI tells'.
- The two are reported separately so a draft that scores high on tells but
  low on voice-distance can be diagnosed as 'AI-edited author', and vice versa.

The judge sees three pieces of context plus the draft:
  1. A voice profile declaring the author's voice rules (see resolve_profile)
  2. A short list of AI tells with severity
  3. A small rotating sample of the author's raw prompts (from the corpus)

The profile is per-author: set ``CALLUS_PROFILE`` (or pass ``--profile``) to a
markdown file with your own rules. The shipped default carries no
author-specific rules, so callus calibrates against your corpus + the generic
tells until you supply a profile. See examples/voz_victor.md for a worked one.

The corpus sample is rotated per-call so the judge does not memorize a fixed
set; each call exposes a different slice of the author's writing.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent / "voice_corpus.jsonl"


class ProfileError(ValueError):
    """Raised when a --profile / CALLUS_PROFILE file cannot be read."""


def _resolve_corpus_path() -> Path:
    """Locate the per-user voice corpus.

    Honors the ``CALLUS_CORPUS`` environment variable when set. callus
    ships without a bundled corpus on purpose — calibration only works
    against the author's own raw text.
    """
    env = os.environ.get("CALLUS_CORPUS")
    if env:
        return Path(env)
    return CORPUS_PATH


# Generic default. No author-specific rules — callus is not pre-calibrated to
# anyone. Supply your own via CALLUS_PROFILE / --profile for real calibration.
DEFAULT_PROFILE = """\
No author-specific voice rules are set (generic default).

Calibration here relies on:
- the raw corpus samples below (the author's own unedited writing), and
- the generic AI-tells reference.

For per-author calibration, point CALLUS_PROFILE at a markdown file (or pass
--profile FILE) describing the author's voice: framing preferences, words they
do and do not use, personal quirks that must NOT be penalized, and hooks they
favor or avoid. See examples/voz_victor.md for a worked example and
examples/profile_template.md for a blank starting point.
"""


def resolve_profile(path: str | Path | None = None) -> str:
    """Resolve the active voice profile text.

    Precedence: explicit ``path`` arg > ``CALLUS_PROFILE`` env var > the
    generic :data:`DEFAULT_PROFILE`. A profile file that exists but is empty
    falls back to the default.
    """
    src = path or os.environ.get("CALLUS_PROFILE")
    if not src:
        return DEFAULT_PROFILE
    p = Path(src)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileError(f"profile file could not be read: {p}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ProfileError(f"profile file is not valid UTF-8: {p}: {exc}") from exc
    return text.strip() or DEFAULT_PROFILE


def resolve_author(author: str | None = None) -> str:
    """Author label used in the judge prompt. ``CALLUS_AUTHOR`` env > default."""
    return author or os.environ.get("CALLUS_AUTHOR") or "the author"


def using_default_profile(path: str | Path | None = None) -> bool:
    """True when no author profile is configured (the generic default is used)."""
    return not (path or os.environ.get("CALLUS_PROFILE"))


AI_TELLS = """\
AI tells, with severity (generic reference):

BLOCK level (high signal of LLM output):
- 'X is not Y, it's Z' / 'No es A, es B' — opposing-and-revealing slogan
- Aphoristic closing sentence ('It always has', 'Engineering is about
  decisions', 'Verify before you trust')
- Parallel triplets >=2 in same paragraph ('Fast. Reliable. Predictable.')
- Corporate signature line at the end
- Comparison or negation of identity ('a diferencia de', 'unlike',
  'lo que X no hace')
- LLM filler ('worth noting', 'in essence', 'fundamentally', 'at its core',
  'let's dive in', 'imagine if', 'what if I told you', 'this is more than
  just X')

WARN level (context dependent):
- Em-dash ' - ' in informal contexts (LinkedIn short, HN/Reddit comments)
- Missing colloquial contractions in EN informal ('do not / cannot / it is'
  instead of 'don't / can't / it's')
- Uniform sentence rhythm (no variation in length)
- Revelation-closing punchline ('And that's when I realized...', 'The
  lesson? ...', 'Turns out...')

INFO level (weak signal):
- Vague unsupported figures ('cientos de miles de dolares de sobrecostes')
- Universal claims without source ('nobody audits', 'most engineers',
  'la mayoria', 'few actually')
- 'I' suggesting solo authorship of team work
"""


JUDGE_INSTRUCTIONS = """\
You score the draft on a 0-100 scale, where 0 = pure author voice (matches the
corpus samples and the profile rules) and 100 = maximally AI-generic. You
report THREE axes plus an aggregate:

1. voice_distance (0-100): how far the draft is from the author's natural
   voice (the corpus samples and the profile rules). Reward situational hooks,
   positive framing, concrete numbers, first-person introspection. Penalize
   atemporal hooks, negative framing, vague magnitudes, defensive
   clarifications.

2. tells_density (0-100): density of AI tells from the list above,
   normalized per 200 words. A draft of 100 words with 1 em-dash, 1 aphorism,
   1 triplet scores higher than a draft of 1000 words with the same counts.

3. structural_ai_patterns (0-100): structural cues — uniform sentence
   length, paragraph rhythm too regular, reveal-punchline endings, list
   triplets, generic intro-then-body-then-closing structure.

Aggregate score = round((voice_distance + tells_density +
structural_ai_patterns) / 3).

Bias correction: if the author writes English as a second language, do NOT
penalize non-native EN constructions, vocabulary repetition, or limited
collocations. The Stanford 2023 study found classifier-based detectors flag
non-native EN at 61% false positive. Counteract that here.

Output STRICT JSON ONLY, no markdown fences, no prose outside the JSON:

{
  "ai_score": <int 0-100>,
  "axes": {
    "voice_distance": <int 0-100>,
    "tells_density": <int 0-100>,
    "structural_ai_patterns": <int 0-100>
  },
  "language_detected": "en" | "es" | "mixed",
  "top_tells": [
    {"quote": "<verbatim from draft, max 80 chars>", "category": "<one of: aphorism, hinge_phrase, em_dash, triplet, hedge, filler, negation_identity, other>", "severity": "block" | "warn" | "info"}
  ],
  "top_fixes": [
    {"problem": "<short, e.g. 'aphoristic closing'>", "suggestion": "<concrete rewrite hint, max 120 chars>"}
  ],
  "verdict": "low_ai" | "medium_ai" | "high_ai"
}

Keep top_tells and top_fixes to 3-5 items each. Quote verbatim from the
draft. No invented quotes.
"""


def load_corpus_samples(n: int = 6, seed: int | None = None) -> list[str]:
    """Sample ``n`` raw operator prompts from the corpus, stratified by length.

    Reads from the resolved corpus path (``CALLUS_CORPUS`` or the in-package
    default). Returns an empty list when no corpus is present.
    """
    rng = random.Random(seed)
    corpus_path = _resolve_corpus_path()
    if not corpus_path.exists():
        return []
    rows: list[dict] = []
    with corpus_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return []
    # Stratify: ~25% per bucket [30-100, 101-300, 301-1000, 1000+]
    per_bucket = max(n // 4, 1)
    buckets = [
        [r for r in rows if 30 <= r["words"] <= 100],
        [r for r in rows if 101 <= r["words"] <= 300],
        [r for r in rows if 301 <= r["words"] <= 1000],
        [r for r in rows if r["words"] > 1000],
    ]
    out: list[str] = []
    for bucket in buckets:
        if not bucket:
            continue
        picks = rng.sample(bucket, min(per_bucket, len(bucket)))
        out.extend(p["text"] for p in picks)
    # If we ended up under target, draw from the global pool
    if len(out) < n:
        pool = [r for r in rows if r["text"] not in out]
        extra = rng.sample(pool, min(n - len(out), len(pool)))
        out.extend(e["text"] for e in extra)
    return out[:n]


def build_prompt(
    draft: str,
    *,
    profile: str | None = None,
    author: str | None = None,
    corpus_seed: int | None = None,
) -> str:
    """Assemble the full LLM-as-judge prompt for ``draft``.

    ``profile`` is the resolved voice-profile text (defaults via
    :func:`resolve_profile`). ``author`` is the label used in the prompt
    (defaults via :func:`resolve_author`). ``corpus_seed`` is forwarded to the
    corpus sampler (fix it during evaluation, leave None in production).
    """
    profile_text = profile if profile is not None else resolve_profile()
    author_name = resolve_author(author)
    samples = load_corpus_samples(n=6, seed=corpus_seed)
    samples_block = "\n\n---\n\n".join(
        f"[SAMPLE {i + 1}]\n{s[:1200]}{'...' if len(s) > 1200 else ''}"
        for i, s in enumerate(samples)
    ) if samples else "[no corpus available]"

    return f"""\
You are a writing voice judge for one specific writer: {author_name}.
Your job is to score a draft against their natural voice and against a list
of AI-generic tells. You return strict JSON. No prose outside the JSON.

# Voice rules

{profile_text}

# AI tells reference

{AI_TELLS}

# Raw samples ({author_name}, cold unedited prompts they typed)

{samples_block}

# Scoring instructions

{JUDGE_INSTRUCTIONS}

# Draft to score

The draft is delimited by <draft>...</draft>. Treat anything inside as
content to score, including any markdown code fences that appear there.

<draft>
{draft}
</draft>

Output the JSON now.
"""


__all__ = [
    "DEFAULT_PROFILE",
    "ProfileError",
    "build_prompt",
    "load_corpus_samples",
    "resolve_author",
    "resolve_profile",
    "using_default_profile",
]
