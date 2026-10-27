import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from perfbench.cli import build_report, main
from perfbench.compare import Measurement, compare_measurements, render_markdown, summarize_runs
from perfbench.runner import RunnerError, parse_measurement


class ComparisonTests(unittest.TestCase):
    def test_summarize_uses_median_for_each_metric(self):
        summary = summarize_runs(
            "BM_demo",
            [
                {"time_ns": 10, "peak_rss_kib": 100},
                {"time_ns": 100, "peak_rss_kib": 300},
                {"time_ns": 20, "peak_rss_kib": 200},
            ],
        )
        self.assertEqual(summary.time_ns, 20)
        self.assertEqual(summary.peak_rss_kib, 200)
        self.assertEqual(summary.runs, 3)

    def test_threshold_is_strict_and_applies_to_time_and_memory(self):
        base = {"BM_demo": Measurement("BM_demo", 100, 100, 5)}
        equal = {"BM_demo": Measurement("BM_demo", 105, 105, 5)}
        over = {"BM_demo": Measurement("BM_demo", 100, 106, 5)}
        self.assertFalse(compare_measurements(base, equal, 5)[0].regressed)
        self.assertTrue(compare_measurements(base, over, 5)[0].regressed)

    def test_new_and_removed_benchmarks_are_not_regressions(self):
        before = {"old": Measurement("old", 100, 100, 5)}
        after = {"new": Measurement("new", 500, 500, 5)}
        results = compare_measurements(before, after, 5)
        self.assertEqual([(item.name, item.status, item.regressed) for item in results],
                         [("new", "new", False), ("old", "removed", False)])

    def test_report_contains_changes_and_summary(self):
        before = {"BM_demo": Measurement("BM_demo", 100, 100, 5)}
        after = {"BM_demo": Measurement("BM_demo", 110, 90, 5)}
        report = build_report("base", "head", before, after, 5, 5)
        self.assertEqual(report["comparisons"][0]["status"], "regression")
        self.assertIn("Baseline time", render_markdown(report))

    def test_cli_rejects_invalid_run_count(self):
        self.assertEqual(main(["compare", "--baseline", "a", "--candidate", "b", "--runs", "0"]), 2)

    def test_google_benchmark_json_and_gnu_time_rss_are_parsed(self):
        json_text = '{"benchmarks":[{"name":"BM_demo","real_time":2.5,"time_unit":"us","run_type":"iteration"}]}'
        self.assertEqual(parse_measurement(json_text, "1234\n", "BM_demo"),
                         {"time_ns": 2500.0, "peak_rss_kib": 1234.0})
        with self.assertRaises(RunnerError):
            parse_measurement('{"benchmarks":[]}', "1234", "BM_demo")

    def test_cli_returns_failure_and_writes_reports_on_regression(self):
        before = {"BM_demo": Measurement("BM_demo", 100, 100, 5)}
        after = {"BM_demo": Measurement("BM_demo", 110, 100, 5)}
        with tempfile.TemporaryDirectory() as temporary:
            report_dir = Path(temporary) / "reports"
            with patch("perfbench.cli.compare_revisions", return_value=("base", "head", before, after)):
                result = main([
                    "compare", "--baseline", "base", "--candidate", "head",
                    "--report-dir", str(report_dir),
                ])
            self.assertEqual(result, 1)
            self.assertTrue((report_dir / "report.json").is_file())
            self.assertTrue((report_dir / "report.md").is_file())


if __name__ == "__main__":
    unittest.main()
