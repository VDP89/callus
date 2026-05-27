"""Merge approved pending candidates into voice_corpus.jsonl.

Reads a ``pending_<ts>_<sid>.md`` review file (written by the
``hook_voice_corpus_close.py`` hook) plus its sibling ``.jsonl``, parses
the operator's verdicts, and appends [OK]-marked entries to the corpus.

[MEH] entries are kept aside in a separate ``review_again.jsonl`` so the
operator can revisit them later without losing them.

Workflow:

1. Hook captures candidates → writes ``pending_*.md`` and ``pending_*.jsonl``.
2. Operator opens the ``.md`` file and marks each item:
       **Veredicto:** [OK ]    voice match, merge into corpus
       **Veredicto:** [NO ]    paste/contamination, drop
       **Veredicto:** [MEH]    mixed, keep for later review
3. Operator runs ``python approve_corpus.py path/to/pending_*.md``.
4. Script merges OKs to ``voice_corpus.jsonl``, archives the pending file.

Pass ``--dry-run`` to preview the merge without writing.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCORE_DIR = Path(__file__).resolve().parent
VOICE_CORPUS = SCORE_DIR / "voice_corpus.jsonl"

VERDICT_RE = re.compile(
    r"^\*\*Veredicto:\*\*\s*\[\s*(OK|NO|MEH)\s*\]",
    re.MULTILINE | re.IGNORECASE,
)
ITEM_HEADER_RE = re.compile(r"^##\s+\[\s*(\d+)\s*\]", re.MULTILINE)


def parse_verdicts(md_text: str) -> dict[int, str]:
    """Parse `## [N]` headings + `**Veredicto:** [X]` into ``{N: verdict}``."""
    out: dict[int, str] = {}
    headers = list(ITEM_HEADER_RE.finditer(md_text))
    for i, header in enumerate(headers):
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(md_text)
        body = md_text[start:end]
        verdict_match = VERDICT_RE.search(body)
        if not verdict_match:
            continue
        item_num = int(header.group(1))
        verdict = verdict_match.group(1).upper()
        out[item_num] = verdict
    return out


def load_pending_jsonl(jsonl_path: Path) -> list[dict]:
    rows: list[dict] = []
    with jsonl_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_to_corpus(approved: list[dict], corpus_path: Path) -> int:
    """Append approved candidates to corpus. Returns count written."""
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with corpus_path.open("a", encoding="utf-8") as fh:
        for entry in approved:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(approved)


def write_review_again(meh: list[dict], pending_dir: Path) -> Path | None:
    if not meh:
        return None
    out = pending_dir / "review_again.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        for entry in meh:
            entry_with_meta = {**entry, "deferred_at": datetime.now().isoformat()}
            fh.write(json.dumps(entry_with_meta, ensure_ascii=False) + "\n")
    return out


def archive_pending(md_path: Path, jsonl_path: Path) -> Path:
    archive_dir = md_path.parent / "_archived"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    moved_md = archive_dir / f"{md_path.stem}_processed_{ts}{md_path.suffix}"
    moved_jsonl = archive_dir / f"{jsonl_path.stem}_processed_{ts}{jsonl_path.suffix}"
    shutil.move(str(md_path), moved_md)
    shutil.move(str(jsonl_path), moved_jsonl)
    return moved_md


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "pending_md",
        help="Path to the pending_<ts>_<sid>.md review file",
    )
    p.add_argument(
        "--yes-all",
        action="store_true",
        help="Auto-approve every candidate without reading verdicts (NOT recommended).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without writing.",
    )
    p.add_argument(
        "--corpus",
        default=str(VOICE_CORPUS),
        help=f"Voice corpus to append to (default: {VOICE_CORPUS}).",
    )
    args = p.parse_args()

    md_path = Path(args.pending_md).resolve()
    if not md_path.exists():
        print(f"ERROR: pending file not found: {md_path}", file=sys.stderr)
        return 1

    jsonl_path = md_path.with_suffix(".jsonl")
    if not jsonl_path.exists():
        print(f"ERROR: matching .jsonl not found: {jsonl_path}", file=sys.stderr)
        return 1

    candidates = load_pending_jsonl(jsonl_path)
    if not candidates:
        print("Pending file has zero candidates. Nothing to do.")
        return 0

    if args.yes_all:
        verdicts = {i + 1: "OK" for i in range(len(candidates))}
        print(f"--yes-all: auto-approving {len(candidates)} candidates")
    else:
        md_text = md_path.read_text(encoding="utf-8")
        verdicts = parse_verdicts(md_text)
        if not verdicts:
            print(
                "No verdicts found in the .md file. Mark each item with "
                "`**Veredicto:** [OK]` (or [NO] / [MEH]) and re-run.",
                file=sys.stderr,
            )
            return 1

    approved: list[dict] = []
    rejected: list[dict] = []
    meh: list[dict] = []
    skipped: list[int] = []

    for i, entry in enumerate(candidates, 1):
        verdict = verdicts.get(i)
        if verdict is None:
            skipped.append(i)
            continue
        if verdict == "OK":
            approved.append(entry)
        elif verdict == "MEH":
            meh.append(entry)
        else:
            rejected.append(entry)

    print(f"Pending: {len(candidates)} candidates")
    print(f"  OK   approved: {len(approved)}")
    print(f"  NO   rejected: {len(rejected)}")
    print(f"  MEH  deferred: {len(meh)}")
    if skipped:
        print(f"  ??   unmarked: {len(skipped)} (items {skipped})")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return 0

    corpus_path = Path(args.corpus).resolve()
    n_merged = append_to_corpus(approved, corpus_path) if approved else 0
    review_again_path = write_review_again(meh, md_path.parent)
    archived_path = archive_pending(md_path, jsonl_path)

    print(f"\nMerged {n_merged} entries into {corpus_path}")
    if review_again_path:
        print(f"Deferred {len(meh)} for later review: {review_again_path}")
    print(f"Archived pending file: {archived_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
