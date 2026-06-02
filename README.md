<!-- markdownlint-disable MD033 -->
<div align="center">
  <img src="assets/callus-launch.gif" alt="callus" width="600" style="max-width: 100%; height: auto;" />
  <p><strong>Per-author voice calibration. Score AI tells and rewrite drafts toward your natural voice.</strong></p>

  <p>
    <a href="https://github.com/VDP89/callus/actions/workflows/ci.yml">
      <img alt="CI" src="https://github.com/VDP89/callus/actions/workflows/ci.yml/badge.svg">
    </a>
    <a href="LICENSE">
      <img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg">
    </a>
    <a href="https://claude.com/claude-code">
      <img alt="Claude Code" src="https://img.shields.io/badge/Claude%20Code-Compatible-6366f1">
    </a>
  </p>
</div>

> Status: **alpha (v0.2.0)**. Score + iterative rewriter + incremental corpus capture are working. Install with `pip install callus`, or use as a Python library / the `callus` CLI.

---

## Why this exists

I write in English as a second language. I tested four commercial AI detectors on my published blog posts. Each of them returned over 90% AI on prose I had written, edited, and corrected myself. A peer-reviewed paper from Stanford in 2023 explained why: detectors based on perplexity flag non-native English writers at 61% false positive, because the same features that mark "AI-like text" — limited vocabulary, common collocations — also describe how most non-native speakers write.

So the score number was useless to me as a metric for iteration. If I rewrote a paragraph to remove the actual AI tells — the aphorisms, the hinge phrases, the triplet negations — the score barely moved. The detector was measuring my passport, not my prose.

`callus` does the other thing. It compares your draft against *your own* raw writing — extracted from your Claude Code sessions or any other source where you typed unedited — and against a small library of AI tells. The score is "how far is this draft from your voice + how dense are the tells", not "what is the probability this came from an LLM". That distinction is the whole point.

---

## What it does

Three operations, all calibrated against you, not against a generic native-English baseline:

- **`callus score <file>`** — Returns a 0-100 score with a per-axis breakdown (voice_distance, tells_density, structural_ai_patterns), the language detected (EN/ES), and concrete tells cited verbatim from the draft with suggested fixes.
- **`callus rewrite <file> --target 25`** — Iteratively rewrites the draft using your voice corpus as few-shot context. Stops when it hits the target or starts degrading (early-stop on degrade). Preserves claims, numbers, and links; allows paragraph restructuring. Typical run: 2-3 iterations, $0.01-0.02 USD on Haiku.
- **`callus build-corpus --source <dir>`** — Extracts your raw user-typed prompts from Claude Code session logs and applies thirteen calibrated filters (drops pastes, command dumps, Codex reviews, dashboard copy, emoji-heavy reviewer output) so what ends up in the corpus is actually your voice, not your assistant's.

A fourth piece, **`callus approve <pending.md>`**, merges new candidates from incremental capture (see hook setup) after you mark each one OK / NO / MEH.

---

## Quick start

```bash
pip install callus
callus --version

# Extract your raw voice from Claude Code sessions
callus build-corpus --source ~/.claude/projects/your-project

# Score a draft
callus score path/to/draft.md

# Rewrite a draft toward your voice
callus rewrite path/to/draft.md --target 25 --out path/to/draft.rewritten.md
```

You need a working `claude` CLI on your PATH (the package shells out to `claude -p --model haiku` for scoring and rewriting).

---

## Why not just use GPTZero / Originality / Humalingo?

I ran the same blog post through Humalingo. It scored 91% AI. I ran the LessWrong submission of the same content, which has measurably more AI tells (hinge phrases, triplet negations, defensive clarifications), through Humalingo as well. It scored 92%.

A one-point delta between a draft with four BLOCK-severity tells and a draft with one. The classifier cannot see the difference between "clean voice" and "voice plus tells" within the cluster of AI-assisted writing. The custom judge in `callus` scored the same two drafts at 20 and 33 — a thirteen-point delta that maps onto what a human moderator would actually read for.

The Stanford 2023 result on non-native English bias ([arXiv:2304.02819](https://arxiv.org/abs/2304.02819)) explains why. Classifier-based detectors lean on perplexity, which is an artifact of vocabulary and collocation distribution. Native English essayists and AI both share a higher-perplexity distribution. Non-native writers and AI both share a lower-perplexity distribution. The detector cannot tell them apart structurally.

`callus` does not try to. It measures something else: distance from a specific writer's voice, defined by that writer's own raw text. There is no claim of universality; there is a claim of usefulness to the operator.

If you want to score against the generic native-English baseline, use Humalingo. If you want to iterate on a draft so it reads more like the way you actually write, use this.

More detail in [docs/why_not_classifier.md](docs/why_not_classifier.md).

---

## Setting up your voice

`callus` ships without a corpus on purpose. The whole architecture only works if the corpus is yours.

1. **Build the corpus** from your Claude Code sessions: `callus build-corpus --source <path>`.
2. **Sample-review** the first 16 entries by hand. The filters drop most contamination but you should know what is in your corpus.
3. **Write a voice profile** by copying `cookbook/profile_template.md` and editing the rules to match how you actually write. The default `tells_ai.md` is generic; the profile is yours.
4. **Score and iterate**.

Full walkthrough: [docs/setup_your_voice.md](docs/setup_your_voice.md).

---

## Incremental capture (optional)

If you want the corpus to grow automatically every time you close a session in Claude Code, wire a hook:

```json
"UserPromptSubmit": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python /path/to/callus/callus/hook_close.py 2>/dev/null || true"
      }
    ]
  }
]
```

The hook watches for closing phrases ("cerramos", "guardar memoria", "listo por hoy", "session close") in your prompts. When it sees one, it extracts the session's user messages, applies the same thirteen filters as `build-corpus`, deduplicates against your existing corpus, and writes a pending review file. Nothing gets merged without you running `callus approve`.

---

## How it is built

```
                ┌──────────────────────────────────────┐
                │              callus.score             │
                │   LLM-as-judge, multi-axis, EN+ES     │
                └───────────────┬──────────────────────┘
                                │
        ┌───────────────────────┴─────────────────────────┐
        │                                                  │
┌───────▼────────┐                              ┌─────────▼──────────┐
│  callus.rewrite │  ←── few-shot voice ──→     │  callus.build_corpus│
│   iterative     │       voice_corpus.jsonl     │   F1-F13 filters    │
│   loop          │                              │   (calibrated)       │
└────────────────┘                              └─────────────────────┘
```

The judge prompt sees four things on every call: your voice profile, a generic tells_ai library, six rotating raw-voice samples from your corpus, and the draft. It returns strict JSON with axis scores and verbatim citations. The rewriter feeds those citations back into a follow-up call that asks the LLM to produce a voice-translated draft while preserving every quantitative claim and link.

The bias correction for non-native EN is built into the prompt instructions, not as a post-hoc adjustment.

---

## When NOT to use callus

- You do not have a corpus of your own writing. The skill is calibration against you; without a corpus, you are scoring against nothing.
- You want a generic "is this AI" detector for a third party's writing. Use a commercial classifier; that is what they are calibrated for.
- The draft is shorter than a hundred words. The signal-to-noise ratio is too low; iterate by hand.

---

## Roadmap

- Hooks for closing-session detection across editors beyond Claude Code
- Embeddings-based similarity layer as an optional add-on for stronger personal calibration
- Multilingual corpus mixing rules (current default is single-language per corpus)

---

## Related projects

Part of a small cluster for operating LLM coding agents in production:

- **[lucy-syndrome](https://github.com/VDP89/lucy-syndrome)** — research on cross-session correction persistence (five invariants).
- **[fscars](https://github.com/VDP89/fscars)** — deterministic correction hooks (functional scars) for AI coding agents.

---

## Contributing

Issues and pull requests welcome. The interesting work right now is on calibrating the F-filters for other languages and on writing more eval sets so the rewriter's convergence behavior can be measured across more domains.

```bash
git clone https://github.com/VDP89/callus
cd callus
pip install -e ".[dev]"
pytest -q
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
