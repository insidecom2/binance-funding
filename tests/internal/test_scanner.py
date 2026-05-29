import os
import tempfile
import unittest
from unittest.mock import patch

from src.internal.scanner import format_filtered_results, run_scanner
from src.internal.scanner_config import ScannerConfig


def _config(require_forecast=True):
    return ScannerConfig(
        min_funding=0.0007,
        min_basis=0.0002,
        min_volume=500000,
        max_spread=0.002,
        max_risk=0.5,
        position_size=1000,
        require_forecast=require_forecast,
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
        telegram_notify_cache_path=os.path.join(tempfile.gettempdir(), "scanner-test-cache.json"),
        mysql_enabled=False,
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="",
        mysql_password="",
        mysql_database="",
        mysql_table_funding_logs="funding_logs",
        scan_report_path=None,
    )


class ScannerTest(unittest.TestCase):
    def test_format_filtered_results_includes_best_candidate(self):
        lines = format_filtered_results(
            [
                {
                    "symbol": "BTCUSDT",
                    "risk": 0.2,
                    "basis": 0.001,
                    "funding_rate": 0.0008,
                    "volume": 1_000_000,
                    "spread": 0.001,
                    "net_profit": 2.0,
                    "best_rounds": 2,
                }
            ],
            _config(),
        )

        joined = "\n".join(lines)
        self.assertIn("Filtered Opportunities", joined)
        self.assertIn("Best Candidate", joined)
        self.assertIn("BTCUSDT", joined)

    @patch("src.internal.scanner.write_scan_report")
    @patch("src.internal.scanner.analyze_market_opportunities")
    @patch("src.internal.scanner.scan_market")
    def test_run_scanner_returns_filtered_results(self, mock_scan_market, mock_analyze, mock_write_report):
        mock_scan_market.return_value = [{"symbol": "BTCUSDT"}]
        mock_analyze.return_value = {
            "filtered": [
                {
                    "symbol": "BTCUSDT",
                    "risk": 0.2,
                    "basis": 0.001,
                    "funding_rate": 0.0008,
                    "volume": 1_000_000,
                    "spread": 0.001,
                    "net_profit": 2.0,
                    "best_rounds": 2,
                }
            ],
            "reject_counts": {
                "funding": 0,
                "forecast": 0,
                "risk": 0,
                "basis": 0,
                "volume": 0,
                "spread": 0,
                "net_profit": 0,
            },
        }

        captured = []
        result = run_scanner(_config(), printer=captured.append)

        self.assertEqual(result, mock_analyze.return_value["filtered"])
        self.assertTrue(any("BTCUSDT" in line for line in captured))
        mock_write_report.assert_called_once()

    @patch("src.internal.scanner.write_scan_report")
    @patch("src.internal.scanner.notify_forecast_passed_symbols")
    @patch("src.internal.scanner.save_forecast_passed_symbols_to_mysql")
    @patch("src.internal.scanner.analyze_market_opportunities")
    @patch("src.internal.scanner.enrich_opportunities_with_forecast")
    @patch("src.internal.scanner.get_all_current_funding_opportunities")
    def test_smoke_run_scanner_end_to_end_without_network(
        self,
        mock_get_opportunities,
        mock_enrich,
        mock_analyze,
        mock_save_mysql,
        mock_notify,
        mock_write_report,
    ):
        raw_opportunities = [
            {
                "symbol": "BTCUSDT",
                "max_rate": {
                    "value": 0.0008,
                    "percentage": 0.08,
                    "mark_price": 100.0,
                },
                "opportunity_score": {
                    "overall_score": 80,
                },
            }
        ]
        filtered_results = [
            {
                "symbol": "BTCUSDT",
                "risk": 0.2,
                "basis": 0.001,
                "funding_rate": 0.0008,
                "volume": 1_000_000,
                "spread": 0.001,
                "net_profit": 2.0,
                "best_rounds": 2,
            }
        ]

        def enrich_side_effect(opportunities, **_kwargs):
            opportunities[0]["funding_forecast"] = {
                "is_valid": True,
                "confidence_pass": True,
                "forecast_pass": True,
                "predicted_next": 0.0009,
                "relative_std": 0.5,
                "r_squared": 0.8,
                "fail_reason": None,
            }
            return opportunities

        mock_get_opportunities.return_value = raw_opportunities
        mock_enrich.side_effect = enrich_side_effect
        mock_analyze.return_value = {
            "filtered": filtered_results,
            "reject_counts": {
                "funding": 0,
                "forecast": 0,
                "risk": 0,
                "basis": 0,
                "volume": 0,
                "spread": 0,
                "net_profit": 0,
            },
        }

        captured = []
        result = run_scanner(_config(require_forecast=True), printer=captured.append)

        self.assertEqual(result, filtered_results)
        mock_get_opportunities.assert_called_once()
        mock_enrich.assert_called_once()
        mock_analyze.assert_called_once()
        mock_save_mysql.assert_called_once()
        mock_notify.assert_called_once()
        mock_write_report.assert_called_once()
        self.assertTrue(any("Best Candidate" in line for line in captured))
        self.assertEqual(raw_opportunities[0]["funding_forecast"]["predicted_next"], 0.0009)


if __name__ == "__main__":
    unittest.main()
