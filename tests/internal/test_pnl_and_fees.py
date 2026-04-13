import os
import tempfile
import unittest
from src.internal.trading import TradeOrchestrator

class FakeClient:
    def get_symbol_filters(self, symbol, is_futures=True, force_refresh=False):
        return {
            "step_size": "0.001",
            "market_step_size": "0.001",
            "tick_size": "0.1",
            "min_qty": "0.001",
            "market_min_qty": "0.001",
            "min_notional": "1",
        }
    def place_futures_order(self, **kwargs):
        return {"orderId": "F1", "avgPrice": 100}
    def place_spot_order(self, **kwargs):
        return {"orderId": "S1", "cummulativeQuoteQty": 100}
    def get_premium_index(self, symbol):
        return [{"markPrice": 105, "lastFundingRate": 0.001}]
    def get_position_info(self, symbol):
        return [{"markPrice": 105}]
    def get_spot_balance(self, symbol):
        return 10000
    def get_futures_margin_balance(self, symbol):
        return 10000

class PnLTests(unittest.TestCase):
    def _make_orchestrator(self, history_path):
        return TradeOrchestrator(
            FakeClient(),
            {
                "position_size": 100,
                "leverage": 1,
                "hedge_ratio": 0.5,
                "stop_loss_pct": -0.02,
                "exit_basis_threshold": 0,
                "order_type": "LIMIT",
                "trade_history_path": history_path,
                "mysql_trades_enabled": False,
                "fee_rate_futures": 0.001,
                "fee_rate_spot": 0.001,
            },
        )

    def test_realized_pnl_and_fees(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = os.path.join(tmp, "history.json")
            orch = self._make_orchestrator(history_path)
            # Simulate a trade
            orch.active_trades["BTCUSDT"] = {
                "trade_group_id": "TG1",
                "opportunity": {"funding_rate": 0.001, "basis": 0.1, "risk": 0.2},
                "position": {"futures_qty": 0.5, "spot_qty": 0.5, "entry_price": 100},
                "entry_time": orch._resolve_validation_price("BTCUSDT", 100),
                "dry_run": False,
            }
            result = orch._close_position("BTCUSDT", "test_exit")
            self.assertTrue(result["success"])
            self.assertIn("fee_futures", result)
            self.assertIn("fee_spot", result)
            self.assertIn("fee_total", result)
            self.assertIsInstance(result["pnl"], float)

    def test_unrealized_pnl_reporting(self):
        orch = self._make_orchestrator("/dev/null")
        orch.active_trades["BTCUSDT"] = {
            "trade_group_id": "TG1",
            "opportunity": {"funding_rate": 0.001, "basis": 0.1, "risk": 0.2},
            "position": {"futures_qty": 1, "spot_qty": 1, "entry_price": 100},
            "entry_time": orch._resolve_validation_price("BTCUSDT", 100),
            "dry_run": False,
        }
        unreal = orch.get_unrealized_pnl()
        self.assertIn("BTCUSDT", unreal)
        self.assertAlmostEqual(unreal["BTCUSDT"]["unrealized_pnl"], (100-105)*1)

if __name__ == "__main__":
    unittest.main()
