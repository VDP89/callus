"""Iterative draft rewriter that targets a low AI-feel score.

Workflow (single function ``rewrite_draft``):

1. Score the input draft with the LLM-as-judge in :mod:`scorer`.
2. If the score is already at or below ``target_score``, return as-is.
3. Otherwise call the LLM (Claude Haiku via subprocess) with:
     - the current draft;
     - the tells the judge cited verbatim;
     - 6-8 rotating raw-Victor samples from the corpus (few-shot voice);
     - a rubric that allows paragraph restructuring but forbids content
       changes (claims, numbers, decisions, links).
4. Re-score the rewritten draft. Keep the lowest-scoring version seen.
5. Stop when the score hits the target or ``max_iterations`` is reached.
6. Return ``RewriteResult`` with best version, score trajectory, and
   final residual tells.

The rewriter does NOT optimise for classifier-based detectors like Humalingo
or GPTZero — those penalise non-native EN and clean essay syntax
structurally (Stanford 2023, arXiv:2304.02819). It optimises for the LLM
judge, which measures distance from the operator's calibrated voice. That
is also what a human moderator (LessWrong-style) actually reads for.
"""
from __future__ import annotations

import hashlib
import subprocess
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from callus.runlog import log_rewrite

try:
    from callus.prompt_template import load_corpus_samples, resolve_profile
    from callus.score import ScoreResult, _resolve_claude_cli, score_draft
except ImportError:
    from prompt_template import load_corpus_samples, resolve_profile

    from callus.score import ScoreResult, _resolve_claude_cli, score_draft


DEFAULT_TARGET = 25
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MODEL = "haiku"
DEFAULT_TIMEOUT_SEC = 180  # rewriting takes longer than scoring


@dataclass
class RewriteIteration:
    iteration: int
    score: int
    draft: str
    rewrite_raw_response: str = ""
    error: str | None = None


@dataclass
class RewriteResult:
    original_draft: str
    best_draft: str
    initial_score: int
    final_score: int
    target_score: int
    iterations: list[RewriteIteration] = field(default_factory=list)
    stopped_reason: str = ""
    final_tells: list[dict[str, str]] = field(default_factory=list)


REWRITE_INSTRUCTIONS = """\
You are a voice translator. Your job is to rewrite a draft so it matches the
operator's natural voice (shown via raw samples) while preserving every
factual claim, number, link, and decision.

# What you MUST preserve

- All numeric claims (counts, percentages, dates, identifiers like PR #5).
- All proper nouns (people, products, repos, papers).
- All hyperlinks (markdown links, bare URLs).
- The core arguments and their conclusions.
- The intended audience and register of the original (informal-tech if
  the draft is informal-tech).

# What you SHOULD change to lower AI tells

Re-read the cited tells. Each is verbatim from the draft. For each tell:

- **Hinge phrases / aphorisms**: replace with situational past observation
  or concrete dated example.
- **Triplet negations ("not X, not Y, is Z")**: collapse into a single
  affirmative sentence describing what the thing IS.
- **Negation_identity ("This is not X")**: reformulate affirmatively. State
  the boundary as a positive scope statement.
- **Em-dashes used rhetorically**: replace with commas, parentheses, or
  period split. Keep em-dashes only when they introduce a verbatim quote
  or a strict appositive.
- **Filler ("worth noting", "in essence", "let's dive in")**: delete the
  filler; jump to the concrete observation it introduces.
- **Revelation punchlines ("And that's when I realized...", "Turns
  out...")**: cut. State the observation directly without the reveal.
- **Missing contractions in EN informal**: use "don't / can't / it's /
  I'm / won't" when register is conversational.

# What you MAY change

- Paragraph order and grouping (restructure when it tightens the flow).
- Sentence length variation (break long uniform sentences; merge short
  staccato ones when they read as a triplet).
- Headings (rewrite to match operator's voice from samples). **A heading
  shaped as a hinge phrase like "Why I don't think this is just memory"
  must be replaced** — pick a noun-phrase heading instead, e.g. "Where
  the memory framing falls short" or "The case against the memory framing".
- Opening hook (replace atemporal/abstract openings with situational past
  if a concrete past frame fits the content).

# What you MUST NOT do

- Insert new facts, examples, numbers, or claims not present in the draft.
- Remove any quantitative claim, link, or specific reference.
- **Drop more than ~20% of the draft length.** The output should be a
  voice-translated version of the SAME piece, not a tighter summary. If
  every sentence ended up shorter, the rewrite went too far; keep the
  scope but vary the rhythm.
- Add hashtags, emojis, marketing language, or call-to-action.
- Translate to another language.
- Change the title.

# Output format

Return ONLY the rewritten draft, no preamble, no commentary, no markdown
code fences around the whole document. If the original draft has markdown
formatting (headings, lists, links), keep equivalent formatting in the
output.
"""


def _call_claude_rewrite(
    prompt: str,
    *,
    model: str,
    claude_cli: str,
    timeout_sec: int,
) -> str:
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


def _strip_code_fence_wrapping(text: str) -> str:
    """Drop a single outer ```...``` wrapping if the LLM ignored the format rule."""
    stripped = text.strip()
    if not (stripped.startswith("```") and stripped.endswith("```")):
        return stripped
    body = stripped[3:-3]
    # Drop the optional language tag on the first line (e.g. ```markdown\n...)
    first_newline = body.find("\n")
    if first_newline != -1:
        tag = body[:first_newline].strip()
        if tag and " " not in tag and tag.replace("-", "").isalpha():
            body = body[first_newline + 1 :]
    return body.strip()


def _build_rewrite_prompt(
    draft: str, tells: list[dict[str, str]], profile: str | None = None
) -> str:
    if profile is None:
        profile = resolve_profile()
    samples = load_corpus_samples(n=6)
    samples_block = "\n\n---\n\n".join(
        f"[VOICE SAMPLE {i + 1}]\n{s[:1000]}{'...' if len(s) > 1000 else ''}"
        for i, s in enumerate(samples)
    ) if samples else "[no corpus available]"

    tells_block = "\n".join(
        f"- [{t.get('severity', 'unknown')}] {t.get('category', '?')}: "
        f"\"{t.get('quote', '')[:160]}\""
        for t in tells[:8]
    ) if tells else "- (no specific tells cited; rewrite for general voice match)"

    return f"""\
{REWRITE_INSTRUCTIONS}

# Author voice rules

{profile}

# Operator voice samples (raw, unedited)

{samples_block}

# Tells the judge cited in the current draft

{tells_block}

# Current draft to rewrite

<draft>
{draft}
</draft>

Now output the rewritten draft. Output the draft text only.
"""


def rewrite_draft(
    draft: str,
    *,
    target_score: int = DEFAULT_TARGET,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    model: str = DEFAULT_MODEL,
    claude_cli: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    initial_score_result: ScoreResult | None = None,
    profile_path: str | None = None,
    author: str | None = None,
) -> RewriteResult:
    """Iteratively rewrite ``draft`` until score <= ``target_score``.

    Args:
        draft: Text to rewrite.
        target_score: Stop when an iteration's score is <= this value.
        max_iterations: Hard cap on rewrite calls.
        model: Forwarded to ``claude -p --model``.
        claude_cli: Override the CLI binary.
        timeout_sec: Subprocess timeout per call.
        initial_score_result: Pass a pre-computed score to skip the first
            scoring call (useful when the caller already scored the draft).

    Returns:
        :class:`RewriteResult` with trajectory, best draft, and residual tells.
    """
    _rewrite_start = _time.time()
    cli = _resolve_claude_cli(claude_cli)
    profile_text = resolve_profile(profile_path)

    # Deterministic seed per draft for reproducibility across iterations AND
    # across processes. Python's built-in hash() is randomized per process
    # (PYTHONHASHSEED) so we use hashlib instead to get the same seed for
    # the same draft text every time.
    draft_seed = int(hashlib.md5(draft.encode("utf-8")).hexdigest()[:8], 16) % 100_000

    if initial_score_result is None:
        initial = score_draft(
            draft,
            model=model,
            claude_cli=cli,
            timeout_sec=90,
            corpus_seed=draft_seed,
            profile_path=profile_path,
            author=author,
        )
    else:
        initial = initial_score_result

    result = RewriteResult(
        original_draft=draft,
        best_draft=draft,
        initial_score=initial.ai_score,
        final_score=initial.ai_score,
        target_score=target_score,
        final_tells=list(initial.top_tells),
    )
    result.iterations.append(
        RewriteIteration(iteration=0, score=initial.ai_score, draft=draft)
    )

    if initial.ai_score <= target_score:
        result.stopped_reason = "already_at_target"
        return result

    current_draft = draft
    current_tells = list(initial.top_tells)
    best_score = initial.ai_score
    best_draft = draft
    best_tells = list(initial.top_tells)
    iters_since_improvement = 0

    for i in range(1, max_iterations + 1):
        prompt = _build_rewrite_prompt(current_draft, current_tells, profile=profile_text)
        raw = _call_claude_rewrite(
            prompt, model=model, claude_cli=cli, timeout_sec=timeout_sec
        )

        if raw.startswith("__ERROR__"):
            result.iterations.append(
                RewriteIteration(
                    iteration=i,
                    score=best_score,
                    draft=current_draft,
                    rewrite_raw_response=raw,
                    error=raw,
                )
            )
            result.stopped_reason = f"rewrite_error: {raw}"
            break

        new_draft = _strip_code_fence_wrapping(raw)
        # Refuse a rewrite that dropped >40% of the content (60% min preservation)
        if not new_draft or len(new_draft) < len(draft) * 0.6:
            result.iterations.append(
                RewriteIteration(
                    iteration=i,
                    score=best_score,
                    draft=current_draft,
                    rewrite_raw_response=raw[:500],
                    error=(
                        f"rewrite_too_short ({len(new_draft)}/{len(draft)} chars "
                        f"= {100 * len(new_draft) / max(len(draft), 1):.0f}%)"
                    ),
                )
            )
            result.stopped_reason = "rewrite_dropped_content"
            break

        rescore = score_draft(
            new_draft,
            model=model,
            claude_cli=cli,
            timeout_sec=90,
            corpus_seed=draft_seed,
            profile_path=profile_path,
            author=author,
        )
        result.iterations.append(
            RewriteIteration(
                iteration=i,
                score=rescore.ai_score,
                draft=new_draft,
                rewrite_raw_response=raw[:500],
            )
        )

        # Always refresh tells from the current draft for the next iteration
        current_tells = list(rescore.top_tells)
        current_draft = new_draft

        if rescore.ai_score < best_score:
            best_score = rescore.ai_score
            best_draft = new_draft
            best_tells = list(rescore.top_tells)
            iters_since_improvement = 0
        else:
            iters_since_improvement = iters_since_improvement + 1

        if rescore.ai_score <= target_score:
            result.stopped_reason = "target_reached"
            break

        # Early-stop if the rewriter is degrading: 2 consecutive iterations
        # without improvement over the running best.
        if iters_since_improvement >= 2:
            result.stopped_reason = "early_stop_degrading"
            break

    result.best_draft = best_draft
    result.final_score = best_score
    result.final_tells = best_tells
    if not result.stopped_reason:
        result.stopped_reason = "max_iterations"

    log_rewrite(
        original_draft=draft,
        initial_score=result.initial_score,
        final_score=result.final_score,
        target_score=target_score,
        iterations=[
            {"iteration": it.iteration, "score": it.score} for it in result.iterations
        ],
        stopped_reason=result.stopped_reason,
        final_tells=result.final_tells,
        latency_sec=_time.time() - _rewrite_start,
        model=model,
    )
    return result


def rewrite_file(path: str, **kwargs: Any) -> RewriteResult:
    """Rewrite a file's contents and return the trajectory."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return rewrite_draft(text, **kwargs)


__all__ = ["RewriteIteration", "RewriteResult", "rewrite_draft", "rewrite_file"]
