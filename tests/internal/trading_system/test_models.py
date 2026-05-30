import unittest

from src.internal.trading_system.models import TradeRecord, TradeState, TradeStateError


class TradeModelsTest(unittest.TestCase):
    def test_allows_valid_state_transition(self):
        trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.NEW)

        updated = trade.transition_to(TradeState.PLANNED, patch={"planned_rounds": 2})

        self.assertEqual(updated.state, TradeState.PLANNED)
        self.assertEqual(updated.planned_rounds, 2)
        self.assertEqual(updated.trade_id, trade.trade_id)

    def test_rejects_invalid_state_transition(self):
        trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.NEW)

        with self.assertRaises(TradeStateError):
            trade.transition_to(TradeState.ACTIVE)

    def test_serializes_and_restores_trade_record(self):
        trade = TradeRecord(
            trade_id="t-1",
            symbol="BTCUSDT",
            state=TradeState.ACTIVE,
            planned_rounds=3,
            completed_rounds=1,
            metadata={"source": "unit-test"},
        )

        restored = TradeRecord.from_dict(trade.to_dict())

        self.assertEqual(restored, trade)
