import unittest

from src.internal.scanner_config import ScannerConfig
from src.internal.scanner_report import build_scan_report


def _config():
    return ScannerConfig(
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
        forecast_top_n=20,
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_notify_cooldown_minutes=5,
        telegram_notify_cache_path="/tmp/scan-report-cache.json",
        mysql_enabled=False,
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="",
        mysql_password="",
        mysql_database="",
        mysql_table_funding_logs="funding_logs",
        scan_report_path=None,
    )


class ScannerReportTest(unittest.TestCase):
    def test_build_scan_report_includes_counts_and_candidates(self):
        opportunities = [
            {
                "symbol": "BTCUSDT",
                "funding_forecast": {
                    "is_valid": True,
                    "confidence_pass": True,
                    "forecast_pass": True,
                },
            },
            {
                "symbol": "ETHUSDT",
                "funding_forecast": {
                    "is_valid": True,
                    "confidence_pass": False,
                    "forecast_pass": False,
                },
            },
        ]
        analysis = {
            "filtered": [
                {
                    "symbol": "BTCUSDT",
                    "net_profit": 2.0,
                }
            ],
            "reject_counts": {
                "funding": 1,
                "forecast": 2,
                "risk": 0,
                "basis": 0,
                "volume": 0,
                "spread": 0,
                "net_profit": 0,
            },
        }

        report = build_scan_report(opportunities, analysis, _config(), top_n=5)

        self.assertEqual(report["opportunity_count"], 2)
        self.assertEqual(report["forecast_passed_count"], 1)
        self.assertEqual(report["filtered_count"], 1)
        self.assertEqual(report["reject_counts"]["forecast"], 2)
        self.assertEqual(report["top_candidates"][0]["symbol"], "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
