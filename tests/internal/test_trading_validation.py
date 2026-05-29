import os
import tempfile
import unittest

from src.internal.trading import TradeOrchestrator


class FakeClient:
    def __init__(self):
        self.futures_calls = 0
        self.spot_calls = 0

    def get_symbol_filters(self, symbol, is_futures=True, force_refresh=False):
        del symbol, force_refresh
        if is_futures:
            return {
                "step_size": "0.001",
                "market_step_size": "0.001",
                "tick_size": "0.1",
                "min_qty": "0.001",
                "market_min_qty": "0.001",
                "min_notional": "50",
            }
        return {
            "step_size": "0.001",
            "market_step_size": "0.001",
            "tick_size": "0.1",
            "min_qty": "0.001",
            "market_min_qty": "0.001",
            "min_notional": "50",
        }

    def place_futures_order(self, **kwargs):
        del kwargs
        self.futures_calls += 1
        return {"orderId": "F1", "avgPrice": "100"}

    def place_spot_order(self, **kwargs):
        del kwargs
        self.spot_calls += 1
        return {"orderId": "S1", "cummulativeQuoteQty": "100"}


@unittest.skip("Legacy trading execution path is not part of the active scanner workflow")
class TradeValidationTest(unittest.TestCase):
    def _make_orchestrator(self, history_path):
        return TradeOrchestrator(
            FakeClient(),
            {
                "position_size": 10,
                "leverage": 1,
                "hedge_ratio": 0.5,
                "stop_loss_pct": -0.02,
                "exit_basis_threshold": 0,
                "order_type": "LIMIT",
                "trade_history_path": history_path,
                "mysql_trades_enabled": False,
            },
        )

    def test_rejects_invalid_sizing_before_order_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            orchestrator = self._make_orchestrator(history_path)

            result = orchestrator.execute_spot_futures_trade(
                {
                    "symbol": "BTCUSDT",
                    "mark_price": 100,
                    "funding_rate": 0.001,
                    "basis": 0.1,
                    "risk": 0.2,
                },
                dry_run=False,
            )

            self.assertFalse(result["success"])
            self.assertIn("sizing rejected", (result.get("error") or "").lower())
            self.assertEqual(orchestrator.client.futures_calls, 0)
            self.assertEqual(orchestrator.client.spot_calls, 0)

    def test_dry_run_validates_and_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            orchestrator = self._make_orchestrator(history_path)
            orchestrator.config["position_size"] = 200

            result = orchestrator.execute_spot_futures_trade(
                {
                    "symbol": "BTCUSDT",
                    "mark_price": 100,
                    "funding_rate": 0.001,
                    "basis": 0.1,
                    "risk": 0.2,
                },
                dry_run=True,
            )

            self.assertTrue(result["success"])
            self.assertEqual(orchestrator.client.futures_calls, 0)
            self.assertEqual(orchestrator.client.spot_calls, 0)


if __name__ == "__main__":
    unittest.main()
