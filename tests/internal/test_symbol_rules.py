import unittest

from src.internal.symbol_rules import round_price, round_quantity, validate_order_inputs


class SymbolRulesTest(unittest.TestCase):
    def test_round_quantity_down_to_step(self):
        self.assertEqual(float(round_quantity(1.23456, "0.001")), 1.234)

    def test_round_price_down_to_tick(self):
        self.assertEqual(float(round_price("123.456", "0.1")), 123.4)

    def test_market_order_uses_market_step(self):
        result = validate_order_inputs(
            symbol="BTCUSDT",
            market="futures",
            side="SELL",
            quantity="1.2345",
            price="100",
            filters={
                "step_size": "0.01",
                "market_step_size": "0.1",
                "tick_size": "0.1",
                "min_qty": "0.01",
                "market_min_qty": "0.1",
                "min_notional": "5",
            },
            order_type="MARKET",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["quantity_str"], "1.2")

    def test_validate_order_inputs_rejects_notional(self):
        result = validate_order_inputs(
            symbol="BTCUSDT",
            market="spot",
            side="BUY",
            quantity="0.001",
            price="100",
            filters={
                "step_size": "0.0001",
                "market_step_size": "0.0001",
                "tick_size": "0.01",
                "min_qty": "0.0001",
                "market_min_qty": "0.0001",
                "min_notional": "20",
            },
            order_type="LIMIT",
        )
        self.assertFalse(result["ok"])
        self.assertIn("minNotional", result["reason"])


if __name__ == "__main__":
    unittest.main()
