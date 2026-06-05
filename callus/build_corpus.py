"""Build a voice corpus from your Claude Code session logs.

Iterates over every ``.jsonl`` under the Claude Code project directory you
point at, extracts the raw user-typed messages, and applies a 13-filter
pipeline calibrated against a human-labeled sample to drop pasted outputs,
shell dumps, Codex reviews, and other non-voice noise. Output is a single
JSONL with one cleaned prompt per line, ready to use as few-shot context
for the LLM-as-judge scorer.

Filters dropped:
- opsec        — paths you mark as sensitive (default: empty; pass
                 ``--opsec-paths`` to add your own e.g. financial dirs)
- system       — system reminders, command tags, hook injections
- short_lt30w  — under 30 words (operational commands, not voice)
- F1  — Codex/reviewer headers (Veredicto:/Verdict:/Approved/...)
- F2  — review dense (>=2 markers: P0/P1/Severity/file.py:N)
- F4  — code-heavy (>50% inside triple-backtick blocks)
- F6  — command dump (shell, log timestamps, Windows prompts)
- F7  — pasted output with short intro + dense markdown body
- F8  — Skill execution headers (Base directory for this skill:)
- F9  — operational briefs you might recycle (Sesion previa, Trabajo:, ...)
- F10 — markdown-dense doc (>=5 headers + 40% structured lines)
- F11 — naked paste (markdown header at start + dense body)
- F12 — dashboard/marketing copy fragments
- F13 — emoji decorators heavy + arrow-review compact format

After running this script:
1. Inspect a 16-prompt sample (this script also writes
   ``voice_corpus_sample_review.md``).
2. Mark each as OK / NO / MEH. Target pass rate >=80%.
3. If pass rate is low, calibrate filters or your ``--opsec-paths``.

Usage:
    # Default: reads from your Claude Code project, writes voice_corpus.jsonl
    python build_corpus.py

    # Custom source dir + extra opsec paths
    python build_corpus.py --source "C:/path/to/.claude/projects/your-proj" \\
                           --opsec-paths "secrets/" "private_data/" \\
                           --out voice_corpus.jsonl

The DEFAULT_SOURCE constant points at the original author's directory and is
only useful for reference / re-running the calibration sample. Any other
operator should pass ``--source``.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
from collections import Counter

from callus.prompt_template import _resolve_corpus_path

# Reference path (original calibration). Other operators MUST pass --source.
DEFAULT_SOURCE = (
    r"C:\Users\DG INGENIERIA SRL\.claude\projects\D--DG-2026-OFFICE"
)


def default_out() -> str:
    """Default corpus output path: honors CALLUS_CORPUS (shared resolver),
    else the package corpus. Avoids the split-brain where build-corpus wrote a
    divergent file from what score/approve/hook read. Resolved at call time
    (not import) so a sentinel `--out None` picks up the current env."""
    return str(_resolve_corpus_path())
DEFAULT_OPSEC_PATHS: tuple[str, ...] = ()


# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #

F1_HEAD = re.compile(
    r"^\s*\*?\*?\s*(Veredicto:|Verdict:|VERDICT:|"
    r"APPROVED[- _]with[- _]observations|APPROVED|CHANGES[- _]REQUESTED|CHANGES[- _]REQUIRED|"
    r"Approved with observations|LGTM|Changes requested|"
    r"Audit verdict:|My (read|take|reading):|"
    r"Revis[eé]|Revalid[eé]|"
    r"Re-review|Re-revis[eé]|Dictamen|Aprobado conceptualmente|Verificaci[oó]n:)",
    re.IGNORECASE,
)

F2_DENSE = re.compile(
    r"(\bP0\b|\bP1\b|\bP2\b|Severity:|Files affected:|Audit verdict:|"
    r"round-?\d+ findings?|round \d+|"
    r"\[[\w/.]+\.py:\d+\]|\(servidor_local\.py:\d+\))",
    re.IGNORECASE,
)

F8_SKILL = re.compile(
    r"^Base directory for this skill:|^# \w+ Skill\s*\n## Quick Reference|"
    r"^Skill loaded\.|^Launching skill:",
    re.IGNORECASE | re.MULTILINE,
)

F9_BRIEF = re.compile(
    r"^Sesion previa \d{4}-\d{2}-\d{2}|^Sesion N\+\d+|"
    r"^Sprint N\+\d+|"
    r"^Estado actual prod\s*\n=+|"
    r"^[A-Z][\w ]+\n=+\s*$|"
    r"^Trabajo:\s|"
    r"^Path local:|^Repo:\s+[\w/-]+|^main HEAD:|^Brief sealed:",
    re.MULTILINE,
)

F12_MARKETING = re.compile(
    r"\b(Ready to bring|Have an idea|Protect your (site|account)|"
    r"Detect and block|WHOIS information|Domain Registration|"
    r"Cloudflare to launch|optimal security and speed|"
    r"Sign (up|in) (now|today)|Get started (today|free))",
    re.IGNORECASE,
)

# F13 — decorative emoji + arrow-review patterns (Codex/Claude output pegado)
F13_EMOJI_DECORATIVO = re.compile(
    "["
    "\U0001f4cc"  # 📌
    "\U0001f9e0"  # 🧠
    "❗"      # ❗
    "\U0001f525"  # 🔥
    "\U0001f449"  # 👉
    "\U0001f50d"  # 🔍
    "⚠"      # ⚠
    "✅"      # ✅
    "❌"      # ❌
    "\U0001f4ca"  # 📊
    "\U0001f3af"  # 🎯
    "\U0001f4a1"  # 💡
    "⭐"      # ⭐
    "\U0001f4dd"  # 📝
    "\U0001f6e0"  # 🛠
    "\U0001f680"  # 🚀
    "\U0001f527"  # 🔧
    "⚙"      # ⚙
    "\U0001f4c8"  # 📈
    "\U0001f4c9"  # 📉
    "✨"      # ✨
    "]"
)
F13_ARROW_REVIEW = re.compile(r"^\s*\w[\w\s]{1,30}\s*→\s*\w", re.MULTILINE)  # "Idea → correcta"

PASTED_INTRO = re.compile(
    r"^\s*(justo (esto |me )?lei|te paso|miralo|mira esto|leete esto|"
    r"esto recibi|esto llego|me llego|esto me mandaron|"
    r"esto dice|lo que dice|aca tenes|ahi va|pegandote esto|copio aca|"
    r"recibi este|llego este|aca esta el)",
    re.IGNORECASE,
)

# Module-level default — overridden by --opsec-paths on the CLI.
OPSEC_PATHS: tuple[str, ...] = DEFAULT_OPSEC_PATHS


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def wc(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def code_fraction(text: str) -> float:
    blocks = re.findall(r"```[\s\S]*?```", text)
    code_chars = sum(len(b) for b in blocks)
    return code_chars / max(len(text), 1)


def is_opsec(text: str) -> bool:
    return any(p in text for p in OPSEC_PATHS)


def is_system(text: str) -> bool:
    if text.startswith("<") and ">" in text[:200]:
        return True
    if "Caveat: The messages below were generated" in text:
        return True
    if text.startswith("<command-message>") or text.startswith("<command-name>"):
        return True
    if "system-reminder" in text[:200].lower():
        return True
    return bool(text.startswith("[Request interrupted"))


def is_command_dump(text: str) -> bool:
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) < 4:
        return False
    cmd_re = re.compile(
        r"^\s*(\$\s*)?(cd|git|gh|python|npm|pip|curl|cat|ls|grep|find|"
        r"echo|mkdir|rm|cp|mv|chmod|ssh|scp|wget|tar|unzip|"
        r"docker|kubectl|wrangler|astro|node|yarn|pnpm|claude|fscar)\s+\S+"
    )
    win_prompt_re = re.compile(r"^[A-Z]:\\[^>\n]+>")
    log_ts_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    cmd_lines = sum(1 for ln in lines if cmd_re.match(ln))
    win_prompt_lines = sum(1 for ln in lines if win_prompt_re.match(ln))
    log_ts_lines = sum(1 for ln in lines if log_ts_re.match(ln))
    shell_comment = sum(1 for ln in lines if re.match(r"^\s*[>#]\s", ln))
    if log_ts_lines >= 5 and log_ts_lines / len(lines) > 0.4:
        return True
    if win_prompt_lines >= 3:
        return True
    score = (
        cmd_lines + win_prompt_lines + log_ts_lines + 0.5 * shell_comment
    ) / len(lines)
    return score > 0.6


def is_markdown_dense(text: str) -> bool:
    if wc(text) < 300:
        return False
    lines = text.split("\n")
    if len(lines) < 10:
        return False
    headers = sum(1 for ln in lines if re.match(r"^#{1,6}\s+", ln))
    list_items = sum(1 for ln in lines if re.match(r"^\s*[-*]\s+", ln))
    table_rows = sum(1 for ln in lines if re.match(r"^\s*\|", ln))
    structured = headers + list_items + table_rows
    return headers >= 5 and structured / len(lines) > 0.4


def is_naked_paste(text: str) -> bool:
    if not re.match(r"^(#{1,6}\s+|[A-Z][\w ]+:\s*\n|>\s+)", text[:200]):
        return False
    return is_markdown_dense(text)


def is_pasted_output(text: str) -> bool:
    if not PASTED_INTRO.search(text[:200]):
        return False
    body = text[200:]
    if wc(body) < 100:
        return False
    headers = len(re.findall(r"^#{1,6}\s+", body, re.MULTILINE))
    return headers >= 2


def is_brief_sesion_previa(text: str) -> bool:
    return bool(F9_BRIEF.search(text[:500]))


def is_marketing_copy(text: str) -> bool:
    return len(F12_MARKETING.findall(text)) >= 2


def is_emoji_heavy_review(text: str) -> bool:
    """Codex/Claude output pegado: emojis decorativos o arrows review compact."""
    if len(F13_EMOJI_DECORATIVO.findall(text)) >= 4:
        return True
    return len(F13_ARROW_REVIEW.findall(text)) >= 3


def filter_reason(text: str) -> str | None:
    if F1_HEAD.search(text):
        return "F1_codex_review_head"
    if len(F2_DENSE.findall(text)) >= 2:
        return "F2_codex_review_dense"
    if is_command_dump(text):
        return "F6_command_dump"
    if F8_SKILL.search(text):
        return "F8_skill_injection"
    if is_brief_sesion_previa(text):
        return "F9_brief_sesion_previa"
    if is_marketing_copy(text):
        return "F12_marketing_copy"
    if is_emoji_heavy_review(text):
        return "F13_emoji_arrow_review"
    if is_pasted_output(text):
        return "F7_pasted_with_intro"
    if is_naked_paste(text):
        return "F11_naked_paste"
    if is_markdown_dense(text):
        return "F10_markdown_dense"
    if code_fraction(text) > 0.5:
        return "F4_mostly_code"
    return None


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #


def extract_user_messages(source_dir: str) -> list[dict]:
    """Walk every ``*.jsonl`` under ``source_dir`` and return user-text messages."""
    out: list[dict] = []
    for fp in sorted(glob.glob(os.path.join(source_dir, "*.jsonl"))):
        try:
            with open(fp, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") != "user":
                        continue
                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        parts = [
                            c.get("text", "")
                            for c in content
                            if isinstance(c, dict) and c.get("type") == "text"
                        ]
                        text = "\n".join(parts)
                    else:
                        text = ""
                    text = text.strip()
                    if not text:
                        continue
                    out.append(
                        {
                            "text": text,
                            "ts": obj.get("timestamp", ""),
                            "source_file": os.path.basename(fp),
                        }
                    )
        except OSError:
            continue
    return out


def build(source_dir: str, out_path: str) -> dict:
    """Run the full pipeline and write the cleaned corpus. Return stats."""
    raw = extract_user_messages(source_dir)

    seen: set[str] = set()
    deduped: list[dict] = []
    for m in raw:
        h = hashlib.md5(m["text"].encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        deduped.append(m)

    stats: Counter = Counter()
    clean: list[dict] = []
    for m in deduped:
        text = m["text"]
        if is_opsec(text):
            stats["opsec"] += 1
            continue
        if is_system(text):
            stats["system"] += 1
            continue
        if wc(text) < 30:
            stats["short_lt30w"] += 1
            continue
        reason = filter_reason(text)
        if reason:
            stats[reason] += 1
            continue
        clean.append(m)
        stats["passed"] += 1

    with open(out_path, "w", encoding="utf-8") as fh:
        for m in clean:
            fh.write(
                json.dumps(
                    {
                        "text": m["text"],
                        "ts": m["ts"],
                        "words": wc(m["text"]),
                        "source_file": m["source_file"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {
        "input_lines": len(raw),
        "deduped": len(deduped),
        "clean": len(clean),
        "stats": dict(stats),
        "total_words": sum(wc(m["text"]) for m in clean),
    }


def main() -> None:
    global OPSEC_PATHS
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=(
            "Claude Code project dir to scan for *.jsonl session logs. "
            "Default points at the original author's directory; for other "
            "operators pass your own path "
            "(e.g. ~/.claude/projects/your-project)."
        ),
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output JSONL path (default: CALLUS_CORPUS env, else package corpus)",
    )
    p.add_argument(
        "--opsec-paths",
        nargs="*",
        default=[],
        help=(
            "Path substrings to exclude from the corpus for privacy. "
            "Any prompt containing one of these strings is dropped. "
            "Example: --opsec-paths secrets/ private/ /04_BANCOS/"
        ),
    )
    args = p.parse_args()

    if args.opsec_paths:
        OPSEC_PATHS = tuple(args.opsec_paths)

    out = args.out or default_out()
    result = build(args.source, out)
    print(f"Input rows: {result['input_lines']}")
    print(f"Deduped: {result['deduped']}")
    print(f"Clean corpus: {result['clean']} prompts, {result['total_words']:,} words")
    print("Breakdown:")
    for k in sorted(result["stats"]):
        print(f"  {k:<28} {result['stats'][k]:>5}")
    print(f"\nWrote: {out}")
    print("\nNext steps:")
    print("  1. Sample-review the corpus manually (target >=80% true-voice).")
    print("  2. Drop the corpus into score/voice_corpus.jsonl on the skill.")
    print("  3. Run `voice-calibration --score <draft>` to validate.")


if __name__ == "__main__":
    main()
