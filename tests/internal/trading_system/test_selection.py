import unittest

from src.internal.trading_system.models import TradeRecord, TradeState
from src.internal.trading_system.selection import SelectionService


def _make_candidate(
    symbol="BTCUSDT",
    net_profit=2.0,
    risk=10.0,
    funding_rate=0.0008,
    basis=0.001,
    volume=1_000_000,
    spread=0.0005,
    minutes_to_funding=45.0,
):
    return {
        "symbol": symbol,
        "net_profit": net_profit,
        "risk": risk,
        "funding_rate": funding_rate,
        "basis": basis,
        "volume": volume,
        "spread": spread,
        "minutes_to_funding": minutes_to_funding,
        "best_rounds": 2,
    }


class SelectionServiceTest(unittest.TestCase):
    def test_rejects_symbol_with_active_trade(self):
        service = SelectionService()
        active_trade = TradeRecord(trade_id="t-1", symbol="BTCUSDT", state=TradeState.ACTIVE)

        result = service.select([_make_candidate("BTCUSDT")], active_trades=[active_trade])

        self.assertEqual(result.selected, [])
        self.assertEqual(len(result.rejected), 1)
        self.assertEqual(result.rejected[0].reason, "active_trade_exists")

    def test_rejects_candidates_too_close_to_funding(self):
        service = SelectionService(min_minutes_to_funding=15)

        result = service.select(
            [
                _make_candidate("BTCUSDT", minutes_to_funding=10),
                _make_candidate("ETHUSDT", minutes_to_funding=None),
            ]
        )

        self.assertEqual(result.selected, [])
        self.assertEqual(
            [reject.reason for reject in result.rejected],
            ["too_close_to_funding", "too_close_to_funding"],
        )

    def test_prefers_higher_ranked_candidate_even_when_input_is_unsorted(self):
        service = SelectionService(max_selected=1)

        result = service.select(
            [
                _make_candidate("LOW", net_profit=1.0, risk=5.0),
                _make_candidate("HIGH", net_profit=3.0, risk=20.0),
            ]
        )

        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.selected[0]["symbol"], "HIGH")

    def test_returns_multiple_selected_candidates_when_configured(self):
        service = SelectionService(max_selected=2)

        result = service.select(
            [
                _make_candidate("BTCUSDT", net_profit=3.0),
                _make_candidate("ETHUSDT", net_profit=2.0),
                _make_candidate("SOLUSDT", net_profit=1.0),
            ]
        )

        self.assertEqual([item["symbol"] for item in result.selected], ["BTCUSDT", "ETHUSDT"])
