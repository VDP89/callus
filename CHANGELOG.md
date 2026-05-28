# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-27

Initial alpha. Built in a single session at DG Ingenieria SRL after
benchmarking commercial AI detectors (Humalingo, GPTZero, Originality)
against personal blog posts and confirming the Stanford 2023 non-native EN
bias in practice: same author, two drafts with measurably different tells,
delta of 1 percentage point on a classifier vs 13 on the calibrated judge.

### Added

- `callus.score` — LLM-as-judge multi-axis scorer (voice_distance,
  tells_density, structural_ai_patterns). EN + ES with bias correction
  for non-native EN writers built into the prompt. JSON output with
  verbatim citations and concrete fixes. Retry on parse failure.
- `callus.rewrite` — iterative rewriter targeting a low ai_score. Uses
  hashlib-seeded corpus rotation for reproducibility, early-stops when
  two consecutive iterations degrade the score, preserves claims and
  links while permitting paragraph restructuring. Validated 68 → 22
  (target reached in 2 iterations) on a real submission, 97.5% content
  preserved, ~$0.012 USD/draft on Haiku.
- `callus.build_corpus` — extracts raw user-typed prompts from Claude
  Code session logs and applies 13 filters calibrated against a
  human-labeled sample: codex review heads, dense citations, command
  dumps, log timestamps, Windows shell prompts, dashboard copy,
  markdown-dense pastes, emoji-decorator + arrow-review compact format,
  and operational briefs.
- `callus.approve` — merges approved candidates from a pending review
  file into the per-user voice_corpus.jsonl. Supports `--dry-run` and
  `--yes-all`.
- CLI: `callus score / rewrite / build-corpus / approve` with shared
  `--model` and `--out` options.
- Apache 2.0 license + README + docs (why_not_classifier,
  setup_your_voice) + smoke test suite + GitHub Actions CI workflow
  (Linux/macOS/Windows × Python 3.10–3.12).
- Launch GIF rendered with Pillow (`assets/callus-launch.gif`).

### Notes

- Ships without a corpus on purpose. The architecture only works when
  the corpus is the operator's own raw text; a generic corpus
  reproduces the same failure mode as a classifier-based detector.
- Voice profile in `prompt_template.py` is currently hard-coded to the
  original author's rules as an example. v0.2.0 will read from a
  user-supplied profile file.
- Hooks for closing-session capture exist as a Claude Code skill
  (separate repository) but are not bundled here yet. They will land
  as `callus.hooks` in v0.2.0.

[0.1.0]: https://github.com/VDP89/callus/releases/tag/v0.1.0
