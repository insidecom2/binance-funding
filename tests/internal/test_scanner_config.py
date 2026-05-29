import os
import tempfile
import unittest
from unittest.mock import patch

from src.internal.scanner_config import build_scanner_config


class ScannerConfigTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "MIN_FUNDING": "0.0006",
            "MIN_BASIS": "0.0003",
            "MIN_VOLUME": "750000",
            "MAX_SPREAD": "0.0025",
            "MAX_RISK": "0.65",
            "POSITION_SIZE": "1500",
            "REQUIRE_FORECAST": "true",
            "FORECAST_PERIODS": "12",
            "MYSQL_ENABLED": "true",
            "MYSQL_HOST": "db.local",
            "SCAN_REPORT_PATH": "/tmp/scan-report.json",
        },
        clear=False,
    )
    def test_build_scanner_config_reads_environment(self):
        base_dir = tempfile.gettempdir()
        config = build_scanner_config(base_dir)

        self.assertEqual(config.min_funding, 0.0006)
        self.assertEqual(config.min_basis, 0.0003)
        self.assertEqual(config.min_volume, 750000)
        self.assertEqual(config.max_spread, 0.0025)
        self.assertEqual(config.max_risk, 0.65)
        self.assertEqual(config.position_size, 1500)
        self.assertTrue(config.require_forecast)
        self.assertEqual(config.forecast_periods, 12)
        self.assertEqual(config.forecast_edge, -0.0001)
        self.assertEqual(config.forecast_max_relative_std, 1.5)
        self.assertEqual(config.forecast_min_predicted, 0.0001)
        self.assertTrue(config.mysql_enabled)
        self.assertEqual(config.mysql_host, "db.local")
        self.assertEqual(config.scan_report_path, "/tmp/scan-report.json")
        self.assertTrue(config.telegram_notify_cache_path.endswith(".telegram_notify_cache.json"))


if __name__ == "__main__":
    unittest.main()
