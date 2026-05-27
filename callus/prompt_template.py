"""Build the LLM-as-judge prompt that scores a draft against Victor's voice.

Conceptual framing (critical):
- This is NOT a classifier of P(LLM-generated).
- It scores 'distance from Victor's natural voice' + 'density of AI tells'.
- The two are reported separately so a draft that scores high on tells but
  low on voice-distance can be diagnosed as 'AI-edited Victor', and vice
  versa.

The judge sees three pieces of context plus the draft:
  1. A short profile string declaring Victor's voice rules (from voz_victor.md)
  2. A short list of AI tells with severity (from tells_ai.md)
  3. A small rotating sample of raw Victor prompts (from the corpus)

Then the judge returns a strict JSON with axis scores and concrete fixes.

The corpus sample is rotated per-call so the judge does not memorize a fixed
set; each call exposes a different slice of Victor's writing.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent / "voice_corpus.jsonl"


def _resolve_corpus_path() -> Path:
    """Locate the per-user voice corpus.

    Honors the ``CALLUS_CORPUS`` environment variable when set. callus
    ships without a bundled corpus on purpose — calibration only works
    against the author's own raw text.
    """
    import os

    env = os.environ.get("CALLUS_CORPUS")
    if env:
        return Path(env)
    return CORPUS_PATH


VOICE_PROFILE = """\
Victor Del Puerto — voice rules (compressed from voz_victor.md):

- First person experiential: writes 'me toco decidir', 'lo que me llevo',
  'habia que elegir'. Past situational hooks beat present-atemporal.
- Positive framing strict: no 'no es X', no 'no hacemos Y', no 'a diferencia
  de'. Describe what the system IS, not what it is not.
- Concrete numbers only. No vague magnitudes ('miles de millones perdidos').
  Small verifiable numbers OK ('$100 arithmetic bug').
- No comparisons against competitors. No defensive clarifications ('no con
  promesas', 'no con palabras').
- No 'Ing. Victor' (degree not awarded).
- Verb precision: 'rediseñar' only when prior design exists, 'optimizar'
  only with a measured metric.
- Preserved personal tells (NOT AI tells, do NOT penalize):
  - 'habian' instead of 'habia' in colloquial past
  - closing with 'Resultado:' + concrete pragmatic impact
  - occasional organic typo on non-technical words
- 'I/my' for personal introspection; 'we/our/team' for executive capacity.
- Hooks approved: 'Ante un dato tecnico que no cerraba, habian dos
  caminos...' (situational past).
- Hooks forbidden: 'Cuando un dato tecnico no cierra, hay dos caminos...'
  (present atemporal), 'Antes de disenar, verificar la base.' (aphoristic
  imperative), 'La ingenieria no empieza cuando...' (hinge phrase).
"""


AI_TELLS = """\
AI tells, with severity (compressed from tells_ai.md):

BLOCK level (high signal of LLM output):
- 'X is not Y, it's Z' / 'No es A, es B' — opposing-and-revealing slogan
- Aphoristic closing sentence ('It always has', 'Engineering is about
  decisions', 'Verify before you trust')
- Parallel triplets >=2 in same paragraph ('Fast. Reliable. Predictable.')
- Corporate signature line at the end ('Asi trabaja DG.')
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
You score the draft on a 0-100 scale, where 0 = pure Victor voice and 100 =
maximally AI-generic. You report THREE axes plus an aggregate:

1. voice_distance (0-100): how far the draft is from Victor's natural voice
   (the corpus samples and the profile rules). Reward situational hooks,
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

Bias correction: Victor is a non-native English writer. Do NOT penalize
non-native EN constructions, vocabulary repetition, or limited
collocations. The Stanford 2023 study found classifier-based detectors
flag non-native EN at 61% FP. Counteract that here.

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

    Reads from ``score/voice_corpus.jsonl`` if present (per-user corpus),
    otherwise falls back to the bundled ``examples/victor_corpus.jsonl``.
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


def build_prompt(draft: str, *, corpus_seed: int | None = None) -> str:
    """Assemble the full LLM-as-judge prompt for ``draft``.

    ``corpus_seed`` is forwarded to the corpus sampler so callers can fix the
    seed during evaluation but leave it None in production (rotates per call).
    """
    samples = load_corpus_samples(n=6, seed=corpus_seed)
    samples_block = "\n\n---\n\n".join(
        f"[SAMPLE {i + 1}]\n{s[:1200]}{'...' if len(s) > 1200 else ''}"
        for i, s in enumerate(samples)
    ) if samples else "[no corpus available]"

    return f"""\
You are a writing voice judge for one specific writer: Victor Del Puerto.
Your job is to score a draft against his natural voice and against a list
of AI-generic tells. You return strict JSON. No prose outside the JSON.

# Victor's voice rules

{VOICE_PROFILE}

# AI tells reference

{AI_TELLS}

# Raw Victor samples (cold, unedited prompts he typed)

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


__all__ = ["build_prompt", "load_corpus_samples"]
