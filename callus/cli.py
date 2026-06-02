"""`callus` CLI — score, rewrite, build_corpus, approve."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from callus import __version__
from callus.prompt_template import (
    ProfileError,
    _resolve_corpus_path,
    using_default_profile,
)
from callus.rewrite import rewrite_file
from callus.score import score_file

app = typer.Typer(
    name="callus",
    help="Per-author voice calibration: score AI tells and rewrite to your voice.",
    add_completion=False,
    no_args_is_help=True,
)


def _preflight_notes(profile: Path | None) -> None:
    """Warn (to stderr) when calibration is not set up for this author yet."""
    if using_default_profile(str(profile) if profile else None):
        typer.secho(
            "note: no author profile set — using the generic default. Set "
            "CALLUS_PROFILE or pass --profile FILE for per-author calibration.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    if not _resolve_corpus_path().exists():
        typer.secho(
            "note: no voice corpus found — scoring leans on the AI-tells "
            "reference only. Run `callus build-corpus --source <sessions dir>` "
            "to calibrate to your own writing.",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.command()
def score(
    path: Path = typer.Argument(..., help="Draft file to score (markdown or txt)."),
    model: str = typer.Option("haiku", help="Claude model passed to `claude -p`."),
    profile: Path = typer.Option(
        None, "--profile", help="Voice profile .md (overrides CALLUS_PROFILE)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of formatted."),
) -> None:
    """Score a draft 0-100 against your calibrated voice."""
    _preflight_notes(profile)
    try:
        r = score_file(
            str(path), model=model, profile_path=str(profile) if profile else None
        )
    except ProfileError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "ai_score": r.ai_score,
                    "voice_distance": r.voice_distance,
                    "tells_density": r.tells_density,
                    "structural_ai_patterns": r.structural_ai_patterns,
                    "language": r.language_detected,
                    "verdict": r.verdict,
                    "top_tells": r.top_tells,
                    "top_fixes": r.top_fixes,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    typer.echo(f"ai_score: {r.ai_score}  ({r.verdict})")
    typer.echo(f"  voice_distance:         {r.voice_distance}")
    typer.echo(f"  tells_density:          {r.tells_density}")
    typer.echo(f"  structural_ai_patterns: {r.structural_ai_patterns}")
    typer.echo(f"  language:               {r.language_detected}")
    typer.echo("")
    if r.top_tells:
        typer.echo("Tells:")
        for t in r.top_tells[:5]:
            typer.echo(
                f"  [{t.get('severity','?')}] {t.get('category','?')}: "
                f"{t.get('quote', '')[:120]}"
            )
        typer.echo("")
    if r.top_fixes:
        typer.echo("Fixes:")
        for f in r.top_fixes[:5]:
            typer.echo(f"  - {f.get('problem','')}: {f.get('suggestion', '')[:160]}")


@app.command()
def rewrite(
    path: Path = typer.Argument(..., help="Draft file to rewrite."),
    target: int = typer.Option(25, help="Target ai_score; loop stops when reached."),
    max_iter: int = typer.Option(5, "--max-iter", help="Hard cap on rewrite iterations."),
    out: Path = typer.Option(None, "--out", help="Write the rewritten draft to this path."),
    profile: Path = typer.Option(
        None, "--profile", help="Voice profile .md (overrides CALLUS_PROFILE)."
    ),
    model: str = typer.Option("haiku"),
) -> None:
    """Iteratively rewrite a draft toward your voice."""
    _preflight_notes(profile)
    try:
        r = rewrite_file(
            str(path),
            target_score=target,
            max_iterations=max_iter,
            model=model,
            profile_path=str(profile) if profile else None,
        )
    except ProfileError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Initial:  {r.initial_score}")
    typer.echo(f"Final:    {r.final_score}")
    typer.echo(f"Stopped:  {r.stopped_reason}")
    typer.echo(f"Iterations: {len(r.iterations)}")
    for it in r.iterations:
        err = f" ERR={it.error}" if it.error else ""
        typer.echo(f"  iter {it.iteration}: score={it.score}{err}")
    if out:
        out.write_text(r.best_draft, encoding="utf-8")
        typer.echo(f"\nWrote: {out}")
    else:
        typer.echo("\n--- best draft ---")
        typer.echo(r.best_draft)


@app.command(name="build-corpus")
def build_corpus_cmd(
    source: str = typer.Argument(..., help="Path to your Claude Code sessions dir."),
    out: Path = typer.Option(None, "--out", help="Output JSONL (default: callus/voice_corpus.jsonl)."),
    opsec: list[str] = typer.Option([], "--opsec", help="Path substrings to exclude."),
) -> None:
    """Extract your raw voice corpus from Claude Code session logs."""
    from callus import build_corpus as bc

    if opsec:
        bc.OPSEC_PATHS = tuple(opsec)
    out_path = str(out) if out else bc.DEFAULT_OUT
    result = bc.build(source, out_path)
    typer.echo(f"Input rows:  {result['input_lines']}")
    typer.echo(f"Deduped:     {result['deduped']}")
    typer.echo(f"Clean:       {result['clean']} prompts, {result['total_words']:,} words")
    for k in sorted(result["stats"]):
        typer.echo(f"  {k:<28} {result['stats'][k]:>5}")
    typer.echo(f"\nWrote: {out_path}")


@app.command()
def stats(
    period: str = typer.Option("30d", help="Time window: 7d, 30d, 90d, all."),
    out: Path = typer.Option(None, "--out", "-o", help="Write markdown to file."),
    log_path: Path = typer.Option(None, "--log", help="Override CALLUS_LOG_PATH."),
) -> None:
    """Render a usage summary from runs.jsonl."""
    from callus.stats import build_stats

    md = build_stats(period=period, log_path=log_path)
    if out:
        out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote: {out}")
    else:
        typer.echo(md)


@app.command()
def approve(
    pending_md: Path = typer.Argument(..., help="Pending review .md file."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes_all: bool = typer.Option(False, "--yes-all"),
) -> None:
    """Merge approved candidates into voice_corpus.jsonl."""
    from callus.approve import main as approve_main

    sys.argv = [
        "approve",
        str(pending_md),
        *(["--dry-run"] if dry_run else []),
        *(["--yes-all"] if yes_all else []),
    ]
    sys.exit(approve_main())


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", is_eager=True),
) -> None:
    if version:
        typer.echo(f"callus {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
