"""Pure comparison and report helpers for the benchmark runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any


@dataclass(frozen=True)
class Measurement:
    name: str
    time_ns: float
    peak_rss_kib: float
    runs: int
    samples: list[dict[str, float]] = field(default_factory=list)


@dataclass(frozen=True)
class Comparison:
    name: str
    status: str
    baseline: Measurement | None
    candidate: Measurement | None
    time_change_pct: float | None
    memory_change_pct: float | None
    regressed: bool


def summarize_runs(name: str, samples: list[dict[str, float]]) -> Measurement:
    if not samples:
        raise ValueError(f"benchmark {name!r} has no measurements")
    return Measurement(
        name=name,
        time_ns=float(median(sample["time_ns"] for sample in samples)),
        peak_rss_kib=float(median(sample["peak_rss_kib"] for sample in samples)),
        runs=len(samples),
        samples=samples,
    )


def _change_pct(baseline: float, candidate: float) -> float | None:
    if baseline <= 0:
        return None
    return ((candidate - baseline) / baseline) * 100.0


def compare_measurements(
    baseline: dict[str, Measurement], candidate: dict[str, Measurement], threshold_pct: float
) -> list[Comparison]:
    comparisons: list[Comparison] = []
    for name in sorted(baseline.keys() | candidate.keys()):
        before = baseline.get(name)
        after = candidate.get(name)
        if before is None:
            comparisons.append(Comparison(name, "new", None, after, None, None, False))
            continue
        if after is None:
            comparisons.append(Comparison(name, "removed", before, None, None, None, False))
            continue
        time_change = _change_pct(before.time_ns, after.time_ns)
        memory_change = _change_pct(before.peak_rss_kib, after.peak_rss_kib)
        regressed = any(
            change is not None and change > threshold_pct
            for change in (time_change, memory_change)
        )
        comparisons.append(
            Comparison(
                name,
                "regression" if regressed else "ok",
                before,
                after,
                time_change,
                memory_change,
                regressed,
            )
        )
    return comparisons


def _fmt(value: float | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:,.2f}{suffix}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# C++ Performance Benchmark Report",
        "",
        f"- **Baseline:** `{report['baseline_revision']}`",
        f"- **Candidate:** `{report['candidate_revision']}`",
        f"- **Runner:** {report['runner']}",
        f"- **Runs per benchmark:** {report['runs_per_benchmark']}",
        f"- **Regression threshold:** {report['threshold_pct']}%",
        "",
        "| Benchmark | Status | Baseline time (ns) | Candidate time (ns) | Time change | Baseline peak RSS (KiB) | Candidate peak RSS (KiB) | Memory change |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["comparisons"]:
        before = item["baseline"] or {}
        after = item["candidate"] or {}
        lines.append(
            "| {name} | {status} | {before_time} | {after_time} | {time_change} | "
            "{before_rss} | {after_rss} | {memory_change} |".format(
                name=item["name"],
                status=item["status"],
                before_time=_fmt(before.get("time_ns")),
                after_time=_fmt(after.get("time_ns")),
                time_change=_fmt(item["time_change_pct"], "%"),
                before_rss=_fmt(before.get("peak_rss_kib")),
                after_rss=_fmt(after.get("peak_rss_kib")),
                memory_change=_fmt(item["memory_change_pct"], "%"),
            )
        )
    regressions = sum(1 for item in report["comparisons"] if item["regressed"])
    lines.extend(["", f"**Regressions:** {regressions}", ""])
    return "\n".join(lines)
