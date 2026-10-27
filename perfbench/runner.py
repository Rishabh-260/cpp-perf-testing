"""Git, CMake, Google Benchmark, and peak-RSS orchestration."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .compare import Measurement, summarize_runs


class RunnerError(RuntimeError):
    pass


def _run(command: list[str], *, cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            check=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except FileNotFoundError as exc:
        raise RunnerError(f"required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RunnerError(f"command failed ({' '.join(command)}): {detail}") from exc


def resolve_revision(repo: Path, revision: str) -> str:
    result = _run(["git", "rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=repo, capture=True)
    return result.stdout.strip()


def _benchmark_names(executable: Path, cwd: Path) -> list[str]:
    result = _run([str(executable), "--benchmark_list_tests=true"], cwd=cwd, capture=True)
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not names:
        raise RunnerError(f"no benchmarks registered in {executable}")
    return names


def parse_measurement(json_text: str, rss_text: str, name: str) -> dict[str, float]:
    """Parse one Google Benchmark JSON record and GNU time's peak-RSS value."""
    try:
        benchmark_output: dict[str, Any] = json.loads(json_text)
        entries = [entry for entry in benchmark_output["benchmarks"] if entry.get("run_type") != "aggregate"]
        if len(entries) != 1:
            raise RunnerError(f"expected one result for {name!r}, found {len(entries)}")
        entry = entries[0]
        unit_scale = {"ns": 1.0, "us": 1_000.0, "ms": 1_000_000.0, "s": 1_000_000_000.0}
        scale = unit_scale[entry["time_unit"]]
        peak_rss_kib = float(rss_text.strip())
        return {"time_ns": float(entry["real_time"]) * scale, "peak_rss_kib": peak_rss_kib}
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"could not parse benchmark output for {name!r}: {exc}") from exc


def _run_one(executable: Path, name: str, cwd: Path, output_dir: Path, run_index: int) -> dict[str, float]:
    time_bin = Path("/usr/bin/time")
    if not time_bin.exists():
        raise RunnerError("GNU /usr/bin/time is required to measure peak process RSS")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    json_path = output_dir / f"{safe_name}-{run_index}.json"
    rss_path = output_dir / f"{safe_name}-{run_index}.rss"
    command = [
        str(time_bin), "-f", "%M", "-o", str(rss_path), str(executable),
        f"--benchmark_filter=^{name}$",
        "--benchmark_repetitions=1",
        f"--benchmark_out={json_path}",
        "--benchmark_out_format=json",
        "--benchmark_report_aggregates_only=false",
    ]
    _run(command, cwd=cwd)
    try:
        json_text = json_path.read_text(encoding="utf-8")
        rss_text = rss_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RunnerError(f"could not parse benchmark output for {name!r}: {exc}") from exc
    return parse_measurement(json_text, rss_text, name)


def _build_revision(worktree: Path, build_dir: Path) -> Path:
    _run(["cmake", "-S", str(worktree), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"], cwd=worktree)
    _run(["cmake", "--build", str(build_dir), "--config", "Release", "--parallel"], cwd=worktree)
    executable = build_dir / "perfbench_samples"
    if os.name == "nt":
        executable = build_dir / "Release" / "perfbench_samples.exe"
    elif not executable.exists():
        executable = build_dir / "perfbench_samples.exe"
    if not executable.exists():
        raise RunnerError(f"expected benchmark executable was not produced: {executable}")
    return executable


def benchmark_revision(repo: Path, revision: str, scratch: Path, runs: int) -> tuple[str, dict[str, Measurement]]:
    commit = resolve_revision(repo, revision)
    worktree = scratch / f"worktree-{commit[:12]}"
    build_dir = scratch / f"build-{commit[:12]}"
    _run(["git", "worktree", "add", "--detach", str(worktree), commit], cwd=repo)
    executable = _build_revision(worktree, build_dir)
    names = _benchmark_names(executable, worktree)
    raw: dict[str, list[dict[str, float]]] = {name: [] for name in names}
    measurement_dir = scratch / f"measurements-{commit[:12]}"
    measurement_dir.mkdir(parents=True)
    for run_index in range(runs):
        for name in names:
            raw[name].append(_run_one(executable, name, worktree, measurement_dir, run_index))
    return commit, {name: summarize_runs(name, samples) for name, samples in raw.items()}


def compare_revisions(repo: Path, baseline: str, candidate: str, runs: int) -> tuple[str, str, dict[str, Measurement], dict[str, Measurement]]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise RunnerError(f"not a Git repository: {repo}")
    if runs < 1:
        raise RunnerError("runs must be at least 1")
    baseline_commit = resolve_revision(repo, baseline)
    candidate_commit = resolve_revision(repo, candidate)
    if baseline_commit == candidate_commit:
        raise RunnerError("baseline and candidate resolve to the same commit")
    cmake = shutil.which("cmake")
    if not cmake:
        raise RunnerError("CMake is required; install CMake and ensure it is on PATH")
    with tempfile.TemporaryDirectory(prefix="perfbench-") as temporary:
        scratch = Path(temporary)
        try:
            actual_baseline, baseline_results = benchmark_revision(repo, baseline_commit, scratch, runs)
            actual_candidate, candidate_results = benchmark_revision(repo, candidate_commit, scratch, runs)
            return actual_baseline, actual_candidate, baseline_results, candidate_results
        finally:
            for worktree in scratch.glob("worktree-*"):
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=repo,
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
