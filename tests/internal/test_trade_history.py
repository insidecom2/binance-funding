import os
import tempfile
import unittest

from src.internal.trade_history import append_trade_history, summarize_trade_history


class TradeHistoryTest(unittest.TestCase):
    def test_summarize_trade_history_reports_closed_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            append_trade_history(
                history_path,
                {
                    "symbol": "BTCUSDT",
                    "entry_time": "2026-01-01T00:00:00",
                    "exit_time": "2026-01-01T08:00:00",
                    "success": True,
                    "pnl": 5.0,
                },
            )
            append_trade_history(
                history_path,
                {
                    "symbol": "ETHUSDT",
                    "entry_time": "2026-01-01T00:00:00",
                    "exit_time": "2026-01-01T08:00:00",
                    "success": False,
                    "pnl": -2.0,
                },
            )

            summary = summarize_trade_history(history_path)

            self.assertEqual(summary["total_trades"], 2)
            self.assertEqual(summary["successful_trades"], 1)
            self.assertEqual(summary["winning_trades"], 1)
            self.assertEqual(summary["total_pnl"], 3.0)
            self.assertEqual(summary["average_pnl"], 1.5)
            self.assertEqual(summary["win_rate"], 50.0)


if __name__ == "__main__":
    unittest.main()
