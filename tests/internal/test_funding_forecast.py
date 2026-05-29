import unittest
from unittest.mock import patch

from src.internal.funding import enrich_opportunities_with_forecast


def _opp(symbol, rate):
    return {
        "symbol": symbol,
        "max_rate": {
            "value": rate,
            "percentage": rate * 100,
            "mark_price": 100.0,
        },
        "opportunity_score": {
            "overall_score": 50,
        },
    }


class FundingForecastTest(unittest.TestCase):
    @patch("src.internal.funding.get_next_funding_forecast")
    def test_enrich_opportunities_with_forecast_populates_all_candidates(self, mock_forecast):
        mock_forecast.side_effect = lambda symbol, **_kwargs: {
            "is_valid": True,
            "confidence_pass": True,
            "forecast_pass": True,
            "predicted_next": 0.001,
            "symbol": symbol,
        }
        opportunities = [
            _opp("LOWUSDT", 0.0001),
            _opp("MIDUSDT", 0.0008),
            _opp("HIGHUSDT", 0.0020),
        ]

        result = enrich_opportunities_with_forecast(opportunities, max_workers=1)

        self.assertEqual(result, opportunities)
        self.assertEqual(mock_forecast.call_count, 3)
        self.assertTrue(all("funding_forecast" in opp for opp in opportunities))
        self.assertEqual(opportunities[0]["funding_forecast"]["symbol"], "LOWUSDT")
        self.assertEqual(opportunities[2]["funding_forecast"]["symbol"], "HIGHUSDT")


if __name__ == "__main__":
    unittest.main()
