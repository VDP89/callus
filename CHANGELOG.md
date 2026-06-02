# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] — 2026-06-02

### Added

- **`callus similarity <file>`** and the `callus.similarity` module — a
  lexical voice-similarity layer: character n-gram cosine between a draft and
  the most similar samples in your corpus. Free, offline, deterministic, no
  LLM call; a cheap complement to `callus score`. The backend is pluggable
  (`SimilarityBackend` protocol); set `CALLUS_SIMILARITY_BACKEND=module:Attr`
  to swap in a semantic-embeddings backend (planned as the optional
  `callus[embeddings]` extra). Lexical similarity is a coarse proxy: high
  similarity does not prove voice, but low similarity is a cheap red flag
  worth an LLM look.

## [0.3.0] — 2026-06-02

### Added

- **Dynamic voice profile.** The judge profile is no longer hardcoded to one
  author. Resolve order: `--profile FILE` > `CALLUS_PROFILE` env > a generic
  default that carries no author-specific rules. `callus` is no longer
  pre-calibrated to anyone — point it at your own profile for real per-author
  calibration. Worked example in `examples/voz_victor.md`, blank starter in
  `examples/profile_template.md`. Optional `CALLUS_AUTHOR` labels the judge.
- **`callus.hooks.voice_corpus_close`** — the incremental-capture hook now
  ships in the package. Wire `python -m callus.hooks.voice_corpus_close` as a
  Claude Code UserPromptSubmit hook; on a session-close phrase it captures
  your raw prompts, filters them through the corpus pipeline, dedups against
  your corpus, and writes a pending review for `callus approve`. Never blocks.
  Config: `CALLUS_PENDING_DIR`, `CALLUS_CLOSE_KEYWORDS`.
- `score` / `rewrite` print a one-line note when no profile or no corpus is
  configured, so a fresh install explains how to calibrate instead of
  silently scoring against the default.

### Changed

- Launch GIF now animates a Bender-style robot mouth morphing into line-art
  human lips, centered. Reproducible via `scripts/render_launch_gif.py`.

### Fixed

- A fresh `pip install callus` is now functional and scalable for any author,
  not only the author whose voice rules were previously baked into the wheel.

## [0.2.0] — 2026-05-28

### Added

- `callus.runlog` — per-call JSONL log for `score_draft` and
  `rewrite_draft`. Records draft hash (not body), score axes, rewrite
  trajectory, latency, estimated cost, and tell categories. Silent on
  failure so a logging hiccup never breaks a user's call.
- `callus stats [--period 7d|30d|90d|all]` — aggregates the log into a
  markdown summary: total operations, score distribution by band,
  rewriter convergence (target-reached rate, average score drop,
  average iterations), most-cited tell categories, p50/p99 latency,
  cumulative cost estimate.
- Default log path: `~/.callus/runs.jsonl`. Override with the
  `CALLUS_LOG_PATH` environment variable.

### Notes

- The log is per-user. If you operate multiple voices on the same
  machine, point `CALLUS_LOG_PATH` at distinct files per project.
- Cost estimates use Haiku ballparks (`$0.002` per score, `$0.004` per
  rewrite iteration). Edit the `cost_usd_estimated` field if you run a
  different model.
- Logging is enabled by default. To disable, point `CALLUS_LOG_PATH`
  at `/dev/null` (POSIX) or `NUL` (Windows).

[0.2.0]: https://github.com/VDP89/callus/releases/tag/v0.2.0

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
