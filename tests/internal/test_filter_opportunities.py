import unittest
from unittest.mock import patch

from src.internal.filter import analyze_opportunities, filter_opportunities, select_best_opportunity


def _make_opportunity(
    symbol="BTCUSDT",
    funding_rate=0.0008,
    forecast_pass=True,
    overall_score=75,
):
    return {
        "symbol": symbol,
        "max_rate": {
            "value": funding_rate,
            "percentage": funding_rate * 100,
            "mark_price": 100.0,
        },
        "opportunity_score": {
            "overall_score": overall_score,
        },
        "funding_forecast": {
            "is_valid": True,
            "confidence_pass": forecast_pass,
            "forecast_pass": forecast_pass,
        },
        "next_funding_time": 9999999999999,
    }


class FilterOpportunitiesTest(unittest.TestCase):
    def setUp(self):
        self.default_basis = (0.001, 100.0, 99.9)

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_require_forecast_rejects_non_passing_symbol(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": 1.25}

        opportunities = [
            _make_opportunity("BTCUSDT", 0.0008, forecast_pass=True),
            _make_opportunity("ETHUSDT", 0.0008, forecast_pass=False),
        ]

        filtered = filter_opportunities(opportunities, require_forecast=True)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["symbol"], "BTCUSDT")

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_analyze_opportunities_returns_reject_counts(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": 1.25}

        analysis = analyze_opportunities(
            [
                _make_opportunity("BTCUSDT", funding_rate=0.0008),
                _make_opportunity("ETHUSDT", funding_rate=0.0006),
            ],
            min_funding=0.0007,
        )

        self.assertEqual(len(analysis["filtered"]), 1)
        self.assertEqual(analysis["reject_counts"]["funding"], 1)

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_rejects_below_min_funding_before_other_gates(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": 1.25}

        filtered = filter_opportunities([_make_opportunity(funding_rate=0.0006)], min_funding=0.0007)

        self.assertEqual(filtered, [])
        mock_risk.assert_not_called()

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_rejects_risk_above_threshold(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.8}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": 1.25}

        filtered = filter_opportunities([_make_opportunity()], max_risk=0.5)

        self.assertEqual(filtered, [])
        mock_basis.assert_not_called()

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_rejects_basis_below_threshold(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = (0.0001, 100.0, 99.9)
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": 1.25}

        filtered = filter_opportunities([_make_opportunity()], min_basis=0.0002)

        self.assertEqual(filtered, [])
        mock_volume.assert_not_called()

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_rejects_volume_below_threshold(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 100
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": 1.25}

        filtered = filter_opportunities([_make_opportunity()], min_volume=500_000)

        self.assertEqual(filtered, [])
        mock_spread.assert_not_called()

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_rejects_spread_above_threshold(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.01
        mock_profit.return_value = {"net_profit": 1.25}

        filtered = filter_opportunities([_make_opportunity()], max_spread=0.002)

        self.assertEqual(filtered, [])
        mock_profit.assert_not_called()

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_rejects_when_no_profitable_round_exists(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        mock_risk.return_value = {"score": 0.2}
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001
        mock_profit.return_value = {"net_profit": -1.0}

        filtered = filter_opportunities([_make_opportunity()])

        self.assertEqual(filtered, [])

    @patch("src.internal.filter.calculate_net_profit_with_fees")
    @patch("src.internal.filter.get_spread")
    @patch("src.internal.filter.get_volume")
    @patch("src.internal.filter.get_basis_from_binance")
    @patch("src.internal.filter.predict_xgb_risk")
    def test_select_best_opportunity_prefers_higher_net_profit_then_lower_risk(
        self,
        mock_risk,
        mock_basis,
        mock_volume,
        mock_spread,
        mock_profit,
    ):
        risk_by_symbol = {
            "BTCUSDT": {"score": 0.30},
            "ETHUSDT": {"score": 0.10},
            "SOLUSDT": {"score": 0.20},
        }
        profit_by_rate = {
            0.0008: 2.5,
            0.0009: 1.0,
            0.0010: 2.5,
        }

        def risk_side_effect(symbol, *_args):
            return risk_by_symbol[symbol]

        def profit_side_effect(_position_size, funding_rate, _rounds, spread):
            del spread
            return {"net_profit": profit_by_rate[funding_rate]}

        mock_risk.side_effect = risk_side_effect
        mock_basis.return_value = self.default_basis
        mock_volume.return_value = 1_000_000
        mock_spread.return_value = 0.001

        opportunities = [
            _make_opportunity("BTCUSDT", 0.0008),
            _make_opportunity("ETHUSDT", 0.0009),
            _make_opportunity("SOLUSDT", 0.0010),
        ]

        mock_profit.side_effect = profit_side_effect
        filtered = filter_opportunities(opportunities, require_forecast=False)

        best = select_best_opportunity(filtered)

        self.assertEqual(len(filtered), 3)
        self.assertEqual(best["symbol"], "SOLUSDT")


if __name__ == "__main__":
    unittest.main()
