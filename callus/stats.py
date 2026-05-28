"""Aggregate runs.jsonl into a usage report.

Reads the per-call log produced by :mod:`callus.runlog` and returns a
markdown summary covering:

* Total operations (score, rewrite) for the chosen period.
* Distribution of initial scores by band (low / medium / high).
* Rewriter convergence: target-reached rate, average score drop, average
  iterations to best.
* Most-cited tell categories across drafts.
* Estimated cumulative inference cost.
* Latency p50 / p99 per operation.

The default period is the last 30 days. Pass ``period="all"`` for the
entire history or ``period="7d"`` for the last week.
"""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from callus.runlog import read_runs

PERIOD_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}


def _filter_period(rows: list[dict], period: str) -> list[dict]:
    if period == "all":
        return rows
    days = PERIOD_DAYS.get(period, 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    for r in rows:
        ts = r.get("ts", "")
        try:
            d = datetime.fromisoformat(ts)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d >= cutoff:
                out.append(r)
        except (TypeError, ValueError):
            continue
    return out


def _score_band(score: int) -> str:
    if score < 30:
        return "low_ai"
    if score <= 65:
        return "medium_ai"
    return "high_ai"


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def aggregate(rows: list[dict]) -> dict:
    """Compute the full summary dict from a list of run records."""
    scores = [r for r in rows if r.get("op") == "score"]
    rewrites = [r for r in rows if r.get("op") == "rewrite"]

    score_bands = Counter(_score_band(int(r.get("ai_score") or 0)) for r in scores)

    rw_target_hit = sum(1 for r in rewrites if r.get("target_reached"))
    rw_drops = [int(r.get("score_drop") or 0) for r in rewrites]
    rw_iters = [int(r.get("iterations") or 0) for r in rewrites]

    tell_counter: Counter = Counter()
    for r in scores:
        for cat in r.get("tell_categories", []):
            if cat and cat != "?":
                tell_counter[cat] += 1
    for r in rewrites:
        for cat in r.get("final_tell_categories", []):
            if cat and cat != "?":
                tell_counter[cat] += 1

    score_latency = [float(r.get("latency_sec") or 0) for r in scores]
    rewrite_latency = [float(r.get("latency_sec") or 0) for r in rewrites]

    cost = sum(float(r.get("cost_usd_estimated") or 0) for r in rows)

    return {
        "totals": {
            "score": len(scores),
            "rewrite": len(rewrites),
            "all": len(rows),
        },
        "score_bands": dict(score_bands),
        "rewriter_convergence": {
            "n": len(rewrites),
            "target_reached": rw_target_hit,
            "target_reached_pct": (
                round(100 * rw_target_hit / len(rewrites), 1) if rewrites else 0.0
            ),
            "avg_drop": round(statistics.mean(rw_drops), 1) if rw_drops else 0.0,
            "avg_iter": round(statistics.mean(rw_iters), 1) if rw_iters else 0.0,
        },
        "top_tells": tell_counter.most_common(8),
        "latency": {
            "score_p50": round(_percentile(score_latency, 0.5), 1),
            "score_p99": round(_percentile(score_latency, 0.99), 1),
            "rewrite_p50": round(_percentile(rewrite_latency, 0.5), 1),
            "rewrite_p99": round(_percentile(rewrite_latency, 0.99), 1),
        },
        "cost_usd_total": round(cost, 3),
    }


def render_markdown(summary: dict, *, period: str) -> str:
    t = summary["totals"]
    sb = summary["score_bands"]
    rw = summary["rewriter_convergence"]
    lat = summary["latency"]

    lines = [
        f"# callus stats ({period})",
        "",
        f"Total operations: **{t['all']}** ({t['score']} score, {t['rewrite']} rewrite)",
        f"Cumulative estimated cost: **${summary['cost_usd_total']:.3f} USD**",
        "",
        "## Score distribution (initial score)",
        "",
        f"- low_ai (<30):    {sb.get('low_ai', 0)}",
        f"- medium_ai (30-65): {sb.get('medium_ai', 0)}",
        f"- high_ai (>65):   {sb.get('high_ai', 0)}",
        "",
        "## Rewriter convergence",
        "",
        f"- runs: {rw['n']}",
        f"- target reached: {rw['target_reached']}/{rw['n']} ({rw['target_reached_pct']}%)",
        f"- average score drop: {rw['avg_drop']}",
        f"- average iterations: {rw['avg_iter']}",
        "",
        "## Top tells (across all runs)",
        "",
    ]
    if summary["top_tells"]:
        for cat, n in summary["top_tells"]:
            lines.append(f"- {cat}: cited {n} times")
    else:
        lines.append("- (no tells recorded yet)")
    lines += [
        "",
        "## Latency",
        "",
        f"- score:   p50 {lat['score_p50']}s  ·  p99 {lat['score_p99']}s",
        f"- rewrite: p50 {lat['rewrite_p50']}s  ·  p99 {lat['rewrite_p99']}s",
        "",
    ]
    return "\n".join(lines)


def build_stats(*, period: str = "30d", log_path: Path | None = None) -> str:
    """Top-level helper: read log, filter, aggregate, render markdown."""
    rows = read_runs(log_path=log_path)
    filtered = _filter_period(rows, period)
    summary = aggregate(filtered)
    return render_markdown(summary, period=period)


__all__ = ["aggregate", "build_stats", "render_markdown"]
