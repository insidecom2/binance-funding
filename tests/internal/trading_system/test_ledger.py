import os
import tempfile
import unittest

from src.internal.trading_system.ledger import FileTradeLedger, LedgerTransitionError
from src.internal.trading_system.models import TradeEventType, TradeRecord, TradeState


class FileTradeLedgerTest(unittest.TestCase):
    def test_create_trade_persists_and_restores_active_trade(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.json")
            ledger = FileTradeLedger(path)
            trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.PLANNED)

            ledger.create_trade(trade, initial_event_payload={"source": "test"})

            restored = ledger.get_trade("t-1")
            active = ledger.load_active_trades()
            events = ledger.list_events("t-1")

            self.assertEqual(restored, trade)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].trade_id, "t-1")
            self.assertEqual(events[0].event_type, TradeEventType.TRADE_CREATED)
            self.assertEqual(events[0].payload["source"], "test")

    def test_update_state_records_transition_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.json")
            ledger = FileTradeLedger(path)
            trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.NEW)
            ledger.create_trade(trade)

            updated = ledger.update_state(
                "t-1",
                TradeState.PLANNED,
                patch={"planned_rounds": 2, "metadata": {"reason": "selected"}},
            )

            events = ledger.list_events("t-1")

            self.assertEqual(updated.state, TradeState.PLANNED)
            self.assertEqual(updated.planned_rounds, 2)
            self.assertEqual(updated.metadata["reason"], "selected")
            self.assertEqual(events[-1].event_type, TradeEventType.STATE_TRANSITIONED)
            self.assertEqual(events[-1].state_before, TradeState.NEW)
            self.assertEqual(events[-1].state_after, TradeState.PLANNED)

    def test_rejects_invalid_ledger_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.json")
            ledger = FileTradeLedger(path)
            trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.NEW)
            ledger.create_trade(trade)

            with self.assertRaises(LedgerTransitionError):
                ledger.update_state("t-1", TradeState.ACTIVE)

    def test_closed_trade_is_not_returned_as_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.json")
            ledger = FileTradeLedger(path)
            trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.ACTIVE)
            ledger.create_trade(trade)
            ledger.update_state("t-1", TradeState.CLOSED, patch={"exit_time": "2026-05-30T00:00:00+00:00"})

            self.assertEqual(ledger.load_active_trades(), [])
