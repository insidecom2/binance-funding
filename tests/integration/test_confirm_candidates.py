import importlib.util
from pathlib import Path
import unittest


def _load_module(rel_path, module_name):
    module_path = Path(__file__).resolve().parents[2] / rel_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


confirm_module = _load_module("cmd/confirm_candidates.py", "binance_funding_cmd_confirm_candidates")


class ConfirmCandidatesTest(unittest.TestCase):
    def test_select_report_symbols_respects_limit(self):
        report = {
            "top_candidates": [
                {"symbol": "BTCUSDT"},
                {"symbol": "ETHUSDT"},
                {"symbol": "SOLUSDT"},
            ]
        }

        symbols = confirm_module.select_report_symbols(report, limit=2)

        self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT"])


if __name__ == "__main__":
    unittest.main()
