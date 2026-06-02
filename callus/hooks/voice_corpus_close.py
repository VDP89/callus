"""callus incremental-capture hook for Claude Code.

Wire this as a UserPromptSubmit hook. When you signal session close in a
prompt (e.g. "wrap up", "save memory", "cerramos"), it captures the raw
user-typed prompts from the current session, filters them through the same
pipeline as ``callus build-corpus``, dedups them against your existing
corpus, and writes a pending review file you approve later with
``callus approve``.

It NEVER blocks and exits silently on any error — a capture hiccup must not
break your session.

Wiring (Claude Code ``settings.json``)::

    {"hooks": {"UserPromptSubmit": [
      {"hooks": [{"type": "command",
                  "command": "python -m callus.hooks.voice_corpus_close"}]}
    ]}}

Config (environment variables)::

    CALLUS_CORPUS         existing corpus to dedup against (default in-package)
    CALLUS_PENDING_DIR    where pending files are written (default ~/.callus/pending)
    CALLUS_CLOSE_KEYWORDS  comma-separated extra trigger phrases
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from callus.build_corpus import filter_reason, is_opsec, is_system, wc
from callus.prompt_template import _resolve_corpus_path

_DEFAULT_TRIGGERS = (
    "cerramos", "cerrar sesion", "cerrar sesión", "listo por hoy",
    "guardar memoria", "guardemos memoria", "wrap up", "wrap-up",
    "save memory", "end session", "that's all for today", "thats all for today",
)


def _triggers() -> tuple[str, ...]:
    extra = os.environ.get("CALLUS_CLOSE_KEYWORDS", "")
    extra_list = tuple(s.strip().lower() for s in extra.split(",") if s.strip())
    return _DEFAULT_TRIGGERS + extra_list


def is_close_signal(prompt: str) -> bool:
    """True when the prompt contains a session-close trigger phrase."""
    p = (prompt or "").lower()
    return any(t in p for t in _triggers())


def _pending_dir() -> Path:
    env = os.environ.get("CALLUS_PENDING_DIR")
    return Path(env) if env else Path.home() / ".callus" / "pending"


def read_user_messages(transcript: Path) -> list[dict]:
    """Extract user-typed messages from a Claude Code session ``.jsonl``."""
    out: list[dict] = []
    try:
        with transcript.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "user":
                    continue
                content = obj.get("message", {}).get("content", "")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "\n".join(
                        c.get("text", "")
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                else:
                    text = ""
                text = text.strip()
                if text:
                    out.append({"text": text, "ts": obj.get("timestamp", "")})
    except OSError:
        return []
    return out


def clean_candidates(rows: list[dict]) -> list[dict]:
    """Dedup and filter raw messages through the corpus pipeline."""
    seen: set[str] = set()
    clean: list[dict] = []
    for m in rows:
        text = m["text"]
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        if is_opsec(text) or is_system(text) or wc(text) < 30:
            continue
        if filter_reason(text):
            continue
        clean.append({"text": text, "ts": m.get("ts", ""), "words": wc(text)})
    return clean


def _corpus_hashes() -> set[str]:
    path = _resolve_corpus_path()
    hashes: set[str] = set()
    if not path.exists():
        return hashes
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = obj.get("text", "")
                if t:
                    hashes.add(hashlib.md5(t.encode("utf-8")).hexdigest())
    except OSError:
        pass
    return hashes


def _sid(session_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", session_id or "")[:16] or "session"


def write_pending(candidates: list[dict], session_id: str, ts: str) -> Path:
    """Write the pending review ``.md`` + sibling ``.jsonl``. Returns the .md path."""
    pdir = _pending_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    sid = _sid(session_id)[:8]
    stem = f"pending_{ts}_{sid}"
    (pdir / f"{stem}.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in candidates) + "\n",
        encoding="utf-8",
    )
    lines = [
        f"# Voice corpus — pending review ({ts})",
        "",
        f"_{len(candidates)} new candidates from session `{sid}`._",
        "",
        "Mark each: `[OK]` voice match · `[NO]` paste/contamination · `[MEH]` mixed.",
        "Run `callus approve` on this file to merge OKs into the corpus.",
        "",
        "---",
        "",
    ]
    for i, c in enumerate(candidates, 1):
        preview = c["text"].replace("\n", " / ")[:240]
        lines += [
            f"## [{i:2d}] {c['words']}w · {c.get('ts', '')}",
            "",
            f"> {preview}",
            "",
            "**Veredicto:** [   ]",
            "",
        ]
    md = pdir / f"{stem}.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError, ValueError):
        return 0
    if not isinstance(payload, dict) or not is_close_signal(payload.get("prompt", "")):
        return 0

    session_id = payload.get("session_id") or ""
    marker = _pending_dir() / ".session_markers" / _sid(session_id)
    if marker.exists():            # cooldown: one capture per session
        return 0

    transcript = payload.get("transcript_path") or ""
    if not transcript:
        return 0

    fresh_seen = _corpus_hashes()
    candidates = [
        c
        for c in clean_candidates(read_user_messages(Path(transcript)))
        if hashlib.md5(c["text"].encode("utf-8")).hexdigest() not in fresh_seen
    ]
    if not candidates:
        return 0

    try:
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        md = write_pending(candidates, session_id, ts)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("done", encoding="utf-8")
    except OSError:
        return 0

    print(
        json.dumps(
            {
                "systemMessage": (
                    f"callus: captured {len(candidates)} voice candidate(s) this "
                    f"session. Review at {md} then run `callus approve {md}`."
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
