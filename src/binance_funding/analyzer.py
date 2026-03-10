from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FundingAnalysis:
    """Funding rate analysis results."""
    symbol: str
    current_rate: float
    previous_rate: float
    trend: str  # "upward", "downward", "stable"
    avg_rate: float
    projected_profit_usdt: float  # 1초 short position로 얻을 수 있는 profit
    risk_negative: bool
    

def analyze_funding_trend(rates: list[dict[str, Any]], position_size: float = 1.0, current_price: float | None = None) -> FundingAnalysis | None:
    """
    Analyze funding rate trend and calculate profit potential.
    
    Args:
        rates: List of funding rate records from API
        position_size: Position size in asset amount (default 1.0 for 1 BTC)
        current_price: Current market price of the symbol
    
    Returns:
        FundingAnalysis with trend and profit calculation
    """
    if not rates or len(rates) < 2:
        return None
    
    # Reverse to get chronological order (oldest first)
    sorted_rates = sorted(rates, key=lambda x: x.get("fundingTime", 0))
    
    symbol = sorted_rates[0].get("symbol", "UNKNOWN")
    current_rate = float(sorted_rates[-1].get("fundingRate", 0))
    previous_rate = float(sorted_rates[-2].get("fundingRate", 0)) if len(sorted_rates) > 1 else current_rate
    
    # Calculate average
    all_rates = [float(r.get("fundingRate", 0)) for r in sorted_rates]
    avg_rate = sum(all_rates) / len(all_rates) if all_rates else 0
    
    # Determine trend
    if current_rate > previous_rate:
        trend = "upward"
    elif current_rate < previous_rate:
        trend = "downward"
    else:
        trend = "stable"
    
    # Calculate profit using real price if provided
    if current_price is None:
        # Fallback to approximate prices for common symbols
        price_lookup = {
            "BTCUSDT": 42000, "ETHUSDT": 2300, "BNBUSDT": 320,
            "ADAUSDT": 0.5, "DOGEUSDT": 0.08, "SOLUSDT": 90,
            "XRPUSDT": 0.6, "MATICUSDT": 0.8, "LINKUSDT": 18,
            "LTCUSDT": 70, "AVAXUSDT": 25, "UNIUSDT": 6,
            "ATOMUSDT": 8, "ARBUSDT": 1.2
        }
        current_price = price_lookup.get(symbol, 100)  # Default $100
    
    # Funding happens every 8 hours, so 3x per day for short position
    projected_profit = position_size * current_price * current_rate
    
    # Risk: is funding going negative?
    risk_negative = current_rate < 0 or (trend == "downward" and current_rate < avg_rate)
    
    return FundingAnalysis(
        symbol=symbol,
        current_rate=current_rate,
        previous_rate=previous_rate,
        trend=trend,
        avg_rate=avg_rate,
        projected_profit_usdt=projected_profit,
        risk_negative=risk_negative,
    )


def rank_by_funding(analyses: list[FundingAnalysis], top_n: int = 10) -> list[FundingAnalysis]:
    """
    Rank funding rates from highest to lowest (best for short selling).
    
    Args:
        analyses: List of FundingAnalysis objects
        top_n: Number of top results to return
    
    Returns:
        Top N symbols by funding rate (highest first)
    """
    sorted_analyses = sorted(
        analyses,
        key=lambda x: x.current_rate,
        reverse=True
    )
    return sorted_analyses[:top_n]


def format_analysis(analysis: FundingAnalysis) -> dict[str, Any]:
    """Format analysis result for display."""
    # Calculate daily profit (funding happens 3x per day)
    daily_profit = analysis.projected_profit_usdt * 3
    annual_profit = daily_profit * 365
    
    return {
        "symbol": analysis.symbol,
        "current_funding_rate": f"{analysis.current_rate:.6f}",
        "current_funding_rate_percent": f"{analysis.current_rate * 100:.4f}%",
        "previous_funding_rate": f"{analysis.previous_rate:.6f}",
        "trend": analysis.trend,
        "avg_funding_rate": f"{analysis.avg_rate:.6f}",
        "profit_per_funding": f"${analysis.projected_profit_usdt:.4f}",
        "profit_per_day": f"${daily_profit:.4f}",
        "profit_per_year": f"${annual_profit:.0f}",
        "risk_going_negative": analysis.risk_negative,
        "next_funding_in_hours": "≤8hrs",  # Funding happens every 8 hours
    }
