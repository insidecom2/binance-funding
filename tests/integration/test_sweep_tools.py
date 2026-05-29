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


sweep_module = _load_module("cmd/sweep_scanner_configs.py", "binance_funding_cmd_sweep")
summarize_module = _load_module("cmd/summarize_sweep_results.py", "binance_funding_cmd_summarize_sweep")


class SweepToolsTest(unittest.TestCase):
    def test_build_variants_creates_multiple_configs(self):
        from src.internal.scanner_config import ScannerConfig

        base = ScannerConfig(
            min_funding=0.0007,
            min_basis=0.0002,
            min_volume=500000,
            max_spread=0.002,
            max_risk=0.5,
            position_size=1000,
            require_forecast=True,
            forecast_periods=20,
            forecast_edge=-0.0001,
            forecast_min_points=6,
            forecast_min_r2=0.05,
            forecast_max_residual_std=0.0012,
            forecast_max_relative_std=1.5,
            forecast_min_predicted=0.0001,
            telegram_bot_token="",
            telegram_chat_id="",
            telegram_notify_cooldown_minutes=5,
            telegram_notify_cache_path="/tmp/cache.json",
            mysql_enabled=False,
            mysql_host="127.0.0.1",
            mysql_port=3306,
            mysql_user="",
            mysql_password="",
            mysql_database="",
            mysql_table_funding_logs="funding_logs",
            scan_report_path=None,
        )

        variants = sweep_module.build_variants(base)

        self.assertGreater(len(variants), 5)
        self.assertEqual(variants[0][0], "baseline")

    def test_summarize_module_prints_best_variant(self):
        reports = [
            {
                "variant": "baseline",
                "score": {"filtered_count": 1, "top_net_profit": 1.0, "avg_top_net_profit": 1.0},
                "reject_counts": {"forecast": 2},
                "top_candidates": [{"symbol": "BTCUSDT", "net_profit": 1.0, "risk": 0.2, "funding_rate": 0.0008}],
            },
            {
                "variant": "better",
                "score": {"filtered_count": 2, "top_net_profit": 2.0, "avg_top_net_profit": 1.5},
                "reject_counts": {"forecast": 1},
                "top_candidates": [{"symbol": "ETHUSDT", "net_profit": 2.0, "risk": 0.1, "funding_rate": 0.0009}],
            },
        ]

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            summarize_module.print_summary(reports, top_n=2)

        output = stdout.getvalue()
        self.assertIn("Best variant: better", output)
        self.assertIn("Top variants:", output)
        self.assertIn("Aggregate reject reasons:", output)

    def test_summarize_module_loads_json_file(self):
        reports = [{"variant": "baseline", "score": {}, "reject_counts": {}, "top_candidates": []}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sweep.json")
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(reports, file_obj)

            loaded = summarize_module.load_reports(path)

        self.assertEqual(loaded, reports)


if __name__ == "__main__":
    unittest.main()
