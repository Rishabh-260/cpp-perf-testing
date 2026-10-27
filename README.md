# C++ Performance Regression Testing Framework

A small, extensible C++ benchmark project and Python runner that compares execution time and peak process memory across Git revisions. Google Benchmark measures each registered workload; the runner builds both revisions in Release mode and repeats each benchmark in a fresh process.

## Requirements

- CMake 3.16 or newer and a C++17 compiler
- Python 3.10 or newer
- Git
- Linux with GNU `/usr/bin/time` for peak RSS collection
- Network access for CMake to fetch the pinned Google Benchmark dependency

## Run a comparison

From a clone with both revisions available locally:

```bash
python -m perfbench.cli compare --baseline main --candidate HEAD
```

The runner uses five independent process runs and a 5% regression threshold by default. Reports are written to `reports/report.md` and `reports/report.json`. Override the defaults with `--runs`, `--threshold`, and `--report-dir`. A comparable benchmark is flagged when median execution time or peak RSS increases by more than the threshold. New and removed benchmarks are listed but do not fail the comparison. The command exits with status 1 on a regression and status 2 on invalid input or an execution error.

## Add a benchmark

Register workloads in `benchmarks/sample_benchmarks.cpp` using Google Benchmark's `BENCHMARK(function)` interface. Parameterized registrations are discovered and compared as individual benchmark cases. Keep setup outside the `for (auto _ : state)` loop when it should not be included in execution time.

## GitHub Actions

The workflow compares pull requests with their target branch and pushes to `main` with the prior pushed revision. It writes a Markdown summary to the Actions run, uploads Markdown and JSON reports, and fails the job when a comparable benchmark exceeds the threshold. It uses read-only repository permissions and does not post pull request comments.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Measurement notes

Each benchmark is run in its own process and collected separately for baseline and candidate. Google Benchmark's `real_time` is normalized to nanoseconds; GNU `time` reports peak resident set size in KiB. The report includes the machine and Python runtime metadata. Repeated runs and medians reduce noise, but shared CI runners can still vary; use a controlled runner for release-grade performance decisions.
