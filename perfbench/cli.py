"""Command line interface for revision-to-revision benchmark comparisons."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .compare import compare_measurements, render_markdown
from .runner import RunnerError, compare_revisions


def _measurement_json(measurement: Any) -> dict[str, Any] | None:
    return None if measurement is None else asdict(measurement)


def build_report(
    baseline_revision: str,
    candidate_revision: str,
    baseline_results: dict[str, Any],
    candidate_results: dict[str, Any],
    runs: int,
    threshold_pct: float,
) -> dict[str, Any]:
    comparisons = compare_measurements(baseline_results, candidate_results, threshold_pct)
    return {
        "schema_version": 1,
        "baseline_revision": baseline_revision,
        "candidate_revision": candidate_revision,
        "runner": f"{platform.system()} {platform.release()} ({platform.machine()}) / Python {platform.python_version()}",
        "runs_per_benchmark": runs,
        "threshold_pct": threshold_pct,
        "comparisons": [
            {
                "name": item.name,
                "status": item.status,
                "baseline": _measurement_json(item.baseline),
                "candidate": _measurement_json(item.candidate),
                "time_change_pct": item.time_change_pct,
                "memory_change_pct": item.memory_change_pct,
                "regressed": item.regressed,
            }
            for item in comparisons
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare C++ benchmark performance between Git revisions")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare", help="build and compare two Git revisions")
    compare.add_argument("--repo", type=Path, default=Path.cwd(), help="Git repository (default: current directory)")
    compare.add_argument("--baseline", required=True, help="baseline Git revision")
    compare.add_argument("--candidate", required=True, help="candidate Git revision")
    compare.add_argument("--runs", type=int, default=5, help="independent process runs per benchmark (default: 5)")
    compare.add_argument("--threshold", type=float, default=5.0, help="regression threshold percentage (default: 5)")
    compare.add_argument("--report-dir", type=Path, default=Path("reports"), help="output directory (default: reports)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.runs < 1:
        print("error: --runs must be at least 1", file=sys.stderr)
        return 2
    if args.threshold < 0:
        print("error: --threshold must be non-negative", file=sys.stderr)
        return 2
    try:
        baseline, candidate, before, after = compare_revisions(
            args.repo, args.baseline, args.candidate, args.runs
        )
        report = build_report(baseline, candidate, before, after, args.runs, args.threshold)
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        markdown = render_markdown(report)
        (args.report_dir / "report.md").write_text(markdown, encoding="utf-8")
        print(markdown)
        return 1 if any(item["regressed"] for item in report["comparisons"]) else 0
    except (RunnerError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
