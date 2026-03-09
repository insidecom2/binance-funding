from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PricePoint:
    """Price data at specific time."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    

@dataclass
class PriceAnalysis:
    """Price analysis results."""
    symbol: str
    current_price: float
    price_1h_ago: float
    price_change_percent: float
    is_price_stable: bool  # ราคายังสูงไหม (not dropped too much)
    max_price_1h: float
    min_price_1h: float
    

def get_price_history_1h(symbol: str, use_real_api: bool = False) -> list[PricePoint]:
    """
    Fetch price history for the last 1 hour.
    
    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        use_real_api: If True, call real Binance API. If False, return mock data.
    
    Returns:
        List of PricePoint objects for the last 1 hour
    """
    if use_real_api:
        # TODO: Implement real API call
        # import requests
        # response = requests.get(
        #     f"https://api.binance.com/api/v3/klines",
        #     params={
        #         "symbol": symbol,
        #         "interval": "1m",
        #         "limit": 60  # Last 60 minutes
        #     }
        # )
        # Parse and convert to PricePoint
        pass
    else:
        # Mock data for now
        return _mock_price_history(symbol)


def _mock_price_history(symbol: str) -> list[PricePoint]:
    """Generate mock price history for testing."""
    mock_data = []
    base_price = {"BTCUSDT": 42000, "ETHUSDT": 2300, "BNBUSDT": 320}.get(symbol, 100)
    
    for minute in range(60):
        # Simulate slight price fluctuations
        price_change = (minute - 30) * 0.02  # ±0.6% variance
        close = base_price * (1 + price_change / 100)
        
        mock_data.append(PricePoint(
            timestamp=1000 + minute * 60,
            open=close * 0.999,
            high=close * 1.005,
            low=close * 0.995,
            close=close,
        ))
    
    return mock_data


def analyze_price_stability(symbol: str, price_history: list[PricePoint] | None = None) -> PriceAnalysis:
    """
    Check if price is still high (didn't drop too much).
    
    Args:
        symbol: Trading symbol
        price_history: Price history from get_price_history_1h(). If None, fetches mock data.
    
    Returns:
        PriceAnalysis with stability assessment
    """
    if price_history is None:
        price_history = get_price_history_1h(symbol, use_real_api=False)
    
    if len(price_history) < 2:
        return None
    
    current_price = price_history[-1].close
    price_1h_ago = price_history[0].close
    price_change_percent = ((current_price - price_1h_ago) / price_1h_ago) * 100
    
    # Consider price stable if it didn't drop more than 2% from 1h ago
    is_price_stable = price_change_percent > -2.0
    
    max_price = max(p.high for p in price_history)
    min_price = min(p.low for p in price_history)
    
    return PriceAnalysis(
        symbol=symbol,
        current_price=current_price,
        price_1h_ago=price_1h_ago,
        price_change_percent=price_change_percent,
        is_price_stable=is_price_stable,
        max_price_1h=max_price,
        min_price_1h=min_price,
    )


def format_price_analysis(analysis: PriceAnalysis) -> dict[str, Any]:
    """Format price analysis for display."""
    return {
        "symbol": analysis.symbol,
        "current_price": f"${analysis.current_price:.2f}",
        "price_1h_ago": f"${analysis.price_1h_ago:.2f}",
        "price_change_1h": f"{analysis.price_change_percent:.2f}%",
        "is_stable": analysis.is_price_stable,
        "max_1h": f"${analysis.max_price_1h:.2f}",
        "min_1h": f"${analysis.min_price_1h:.2f}",
    }
