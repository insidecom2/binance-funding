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
    

def analyze_funding_trend(rates: list[dict[str, Any]], position_size: float = 1.0) -> FundingAnalysis | None:
    """
    Analyze funding rate trend and calculate profit potential.
    
    Args:
        rates: List of funding rate records from API
        position_size: Position size in asset amount (default 1.0 for 1 BTC)
    
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
    
    # Calculate profit (funding every 8 hours for short position)
    # Funding = position_size * price * funding_rate
    # Assuming price ~42000 for BTC (approximate)
    approximate_btc_price = 42000
    projected_profit = position_size * approximate_btc_price * current_rate
    
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
    return {
        "symbol": analysis.symbol,
        "current_funding_rate": f"{analysis.current_rate:.6f}",
        "previous_funding_rate": f"{analysis.previous_rate:.6f}",
        "trend": analysis.trend,
        "avg_funding_rate": f"{analysis.avg_rate:.6f}",
        "projected_profit_8hrs": f"${analysis.projected_profit_usdt:.2f}",
        "risk_going_negative": analysis.risk_negative,
    }
