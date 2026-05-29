import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


def _load_pnl_summary_module():
    module_path = Path(__file__).resolve().parents[2] / "cmd" / "pnl_summary.py"
    spec = importlib.util.spec_from_file_location("binance_funding_cmd_pnl_summary", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


pnl_summary_module = _load_pnl_summary_module()


class PnlSummaryEntrypointSmokeTest(unittest.TestCase):
    def test_main_prints_summary_from_history_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            with open(history_path, "w") as file_obj:
                json.dump(
                    [
                        {
                            "symbol": "BTCUSDT",
                            "entry_time": "2026-01-01T00:00:00",
                            "exit_time": "2026-01-01T08:00:00",
                            "success": True,
                            "pnl": 5.0,
                        }
                    ],
                    file_obj,
                )

            stdout = io.StringIO()
            with patch.object(sys, "argv", ["pnl_summary.py", "--history", history_path]):
                with redirect_stdout(stdout):
                    pnl_summary_module.main()

            output = stdout.getvalue()
            self.assertIn("Trade PnL & Fee Summary", output)
            self.assertIn("total_trades", output)
            self.assertIn("1", output)

    def test_main_prints_zero_summary_for_missing_history_file(self):
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["pnl_summary.py", "--history", "/tmp/does-not-exist-history.json"]):
            with redirect_stdout(stdout):
                pnl_summary_module.main()

        output = stdout.getvalue()
        self.assertIn("Trade PnL & Fee Summary", output)
        self.assertIn("total_trades", output)
        self.assertIn("0", output)


if __name__ == "__main__":
    unittest.main()
