import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout


def _load_module(rel_path, module_name):
    module_path = Path(__file__).resolve().parents[2] / rel_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


compare_module = _load_module("cmd/compare_scan_reports.py", "binance_funding_cmd_compare_scan_reports")


class CompareScanReportsTest(unittest.TestCase):
    def test_compare_reports_returns_deltas(self):
        old_report = {
            "filtered_count": 0,
            "forecast_passed_count": 1,
            "top_candidates": [],
            "reject_counts": {"risk": 2},
        }
        new_report = {
            "filtered_count": 2,
            "forecast_passed_count": 1,
            "top_candidates": [{"symbol": "BTCUSDT", "net_profit": 3.5}],
            "reject_counts": {"risk": 0},
        }

        summary = compare_module.compare_reports(old_report, new_report)

        self.assertEqual(summary["filtered_count_delta"], 2)
        self.assertEqual(summary["top_net_profit_delta"], 3.5)
        self.assertEqual(summary["new_top_symbols"], ["BTCUSDT"])

    def test_print_summary_contains_key_lines(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            compare_module.print_summary(
                {
                    "old_filtered_count": 0,
                    "new_filtered_count": 2,
                    "filtered_count_delta": 2,
                    "old_forecast_passed_count": 0,
                    "new_forecast_passed_count": 1,
                    "forecast_passed_delta": 1,
                    "old_top_net_profit": 0.0,
                    "new_top_net_profit": 3.5,
                    "top_net_profit_delta": 3.5,
                    "old_top_symbols": [],
                    "new_top_symbols": ["BTCUSDT"],
                    "old_reject_counts": {"risk": 2},
                    "new_reject_counts": {"risk": 0},
                }
            )

        output = stdout.getvalue()
        self.assertIn("Scan Report Comparison", output)
        self.assertIn("Filtered count:", output)
        self.assertIn("Top net profit:", output)

    def test_load_report_reads_json(self):
        report = {"filtered_count": 1}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.json")
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(report, file_obj)

            loaded = compare_module.load_report(path)

        self.assertEqual(loaded, report)


if __name__ == "__main__":
    unittest.main()
