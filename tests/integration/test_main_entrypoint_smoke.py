import io
import importlib.util
import os
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.internal.scanner_config import ScannerConfig


def _load_main_module():
    module_path = Path(__file__).resolve().parents[2] / "cmd" / "main.py"
    spec = importlib.util.spec_from_file_location("binance_funding_cmd_main", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


main_module = _load_main_module()


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
        telegram_notify_cache_path=os.path.join("/tmp", "main-entrypoint-cache.json"),
        mysql_enabled=False,
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="",
        mysql_password="",
        mysql_database="",
        mysql_table_funding_logs="funding_logs",
        scan_report_path=None,
    )


class MainEntrypointSmokeTest(unittest.TestCase):
    @patch.object(main_module, "run_scanner")
    @patch.object(main_module, "build_scanner_config")
    def test_main_wires_config_into_run_scanner(self, mock_build_config, mock_run_scanner):
        config = _config()
        mock_build_config.return_value = config

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            main_module.main()

        output = stdout.getvalue()
        self.assertIn("Binance Funding Forecast Scanner", output)
        self.assertIn("Forecast gate required: True", output)
        mock_build_config.assert_called_once()
        mock_run_scanner.assert_called_once_with(config)

    @patch.object(main_module, "run_scanner", side_effect=RuntimeError("boom"))
    @patch.object(main_module, "build_scanner_config")
    def test_main_exits_with_code_one_on_scanner_error(self, mock_build_config, mock_run_scanner):
        del mock_run_scanner
        mock_build_config.return_value = _config()

        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as exc_info:
            with redirect_stdout(stdout):
                main_module.main()

        self.assertEqual(exc_info.exception.code, 1)
        self.assertIn("❌ Error: boom", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
