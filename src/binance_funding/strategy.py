from __future__ import annotations

import json
from typing import Any

from .analyzer import analyze_funding_trend, rank_by_funding, format_analysis
from .client import BinanceFundingClient
from .order_manager import PlaceOrderManager
from .order_timer import OrderTimer
from .price_analyzer import analyze_price_stability, format_price_analysis


class FundingRateArbitrageStrategy:
    """
    Execute funding rate arbitrage strategy:
    1. Find top 10 highest funding rates
    2. Analyze funding trend
    3. Check price stability (1 hour before)
    4. Place SPOT BUY + FUTURES SHORT simultaneously
    5. Auto-close after funding payment time + 5 minutes
    """
    
    def __init__(self, position_size: float = 1.0, use_real_orders: bool = False):
        """
        Initialize strategy.
        
        Args:
            position_size: Size of each position (e.g., 1.0 = 1 BTC)
            use_real_orders: If True, place real orders (requires API keys)
        """
        self.position_size = position_size
        self.use_real_orders = use_real_orders
        self.client = BinanceFundingClient()
        self.order_manager = PlaceOrderManager() if not use_real_orders else PlaceOrderManager()
        self.timer_manager = OrderTimer()
        self.executed_trades = []
    
    def analyze_opportunity(self, symbols: list[str], limit: int = 100, top_n: int = 10) -> dict[str, Any]:
        """
        Step 1-3: Analyze funding opportunities and price stability.
        
        Args:
            symbols: List of symbols to analyze
            limit: Historical records to fetch
            top_n: Top N symbols to return
        
        Returns:
            Analysis results with trading recommendations
        """
        all_analyses = []
        
        # Step 1 & 2: Get funding rates and analyze trend
        for symbol in symbols:
            rows = self.client.get_funding_rates(symbol=symbol, limit=limit)
            analysis = analyze_funding_trend(rows, position_size=self.position_size)
            if analysis:
                all_analyses.append(analysis)
        
        # Rank by funding rate
        ranked_funding = rank_by_funding(all_analyses, top_n=top_n)
        
        # Step 3: Check price stability for top candidates
        opportunities = []
        
        for funding_analysis in ranked_funding:
            price_analysis = analyze_price_stability(funding_analysis.symbol)
            
            opportunity = {
                "symbol": funding_analysis.symbol,
                "funding": format_analysis(funding_analysis),
                "price": format_price_analysis(price_analysis),
                "recommendation": self._get_recommendation(funding_analysis, price_analysis),
            }
            opportunities.append(opportunity)
        
        return {
            "opportunities": opportunities,
            "timestamp": "now",
            "total_analyzed": len(all_analyses),
        }
    
    def _get_recommendation(self, funding_analysis, price_analysis) -> dict[str, Any]:
        """Determine if we should trade based on funding and price."""
        should_trade = (
            funding_analysis.current_rate > 0 and  # Only positive funding
            price_analysis.is_price_stable and  # Price didn't drop too much
            not funding_analysis.risk_negative  # Funding not going negative
        )
        
        return {
            "should_trade": should_trade,
            "reason": self._get_trade_reason(funding_analysis, price_analysis),
            "projected_profit_usdt": f"${funding_analysis.projected_profit_usdt:.2f}",
        }
    
    def _get_trade_reason(self, funding_analysis, price_analysis) -> str:
        """Get reason for trade recommendation."""
        if not funding_analysis.current_rate > 0:
            return "Funding rate is not positive"
        if not price_analysis.is_price_stable:
            return f"Price dropped too much ({price_analysis.price_change_percent:.2f}%)"
        if funding_analysis.risk_negative:
            return "Funding trending negative - risky"
        return "✅ Good arbitrage opportunity"
    
    def execute_trade(
        self,
        symbol: str,
        spot_price: float,
        funding_rate: float,
        funding_time_unix_ms: int
    ) -> dict[str, Any]:
        """
        Step 4 & 5: Execute trade and schedule auto-close.
        
        Args:
            symbol: Trading symbol
            spot_price: Current spot price
            funding_rate: Current funding rate
            funding_time_unix_ms: Unix timestamp (ms) when funding is paid
        
        Returns:
            Trade execution details
        """
        print(f"\n🚀 Executing arbitrage trade for {symbol}")
        
        # Step 4: Open position (buy spot + short futures)
        spot_order, futures_order = self.order_manager.open_arbitrage_position(
            symbol=symbol,
            quantity=self.position_size,
            spot_price=spot_price,
            funding_rate=funding_rate
        )
        
        print(f"📍 SPOT BUY: {spot_order.order_id}")
        print(f"📍 FUTURES SHORT: {futures_order.order_id}")
        
        # Step 5: Schedule auto-close
        self.timer_manager.schedule_funding_close(
            symbol=symbol,
            funding_time_unix_ms=funding_time_unix_ms,
            delay_after_funding_minutes=5,
            callback=self._close_position_callback,
            symbol=symbol,
            spot_price=spot_price,
        )
        
        trade_record = {
            "symbol": symbol,
            "spot_order": self.order_manager.format_order(spot_order),
            "futures_order": self.order_manager.format_order(futures_order),
            "position_size": self.position_size,
            "funding_rate": funding_rate,
            "status": "open",
        }
        
        self.executed_trades.append(trade_record)
        
        return {
            "status": "✅ Position opened",
            "trade": trade_record,
            "scheduled_close": self.timer_manager.get_upcoming_close_times(),
        }
    
    def _close_position_callback(self, symbol: str, spot_price: float) -> None:
        """Callback to close position when timer expires."""
        # Estimate exit price (current market price)
        exit_price = spot_price * 1.001  # Assume slight price movement
        
        spot_sell, futures_close = self.order_manager.close_arbitrage_position(
            symbol=symbol,
            exit_price=exit_price
        )
        
        print(f"\n✅ Auto-closed position for {symbol}")
        print(f"📊 SPOT SELL: {spot_sell.order_id}")
        print(f"📊 FUTURES CLOSE: {futures_close.order_id}")
        
        # Update trade record
        for trade in self.executed_trades:
            if trade["symbol"] == symbol and trade["status"] == "open":
                trade["status"] = "closed"
                trade["spot_sell_order"] = self.order_manager.format_order(spot_sell)
                trade["futures_close_order"] = self.order_manager.format_order(futures_close)
    
    def get_trade_summary(self) -> dict[str, Any]:
        """Get summary of all executed trades."""
        return {
            "total_trades": len(self.executed_trades),
            "trades": self.executed_trades,
            "scheduled_closures": self.timer_manager.get_upcoming_close_times(),
        }
    
    def start_background_timer(self) -> None:
        """Start background timer for auto-closing positions."""
        self.timer_manager.start_background_timer()
    
    def stop_background_timer(self) -> None:
        """Stop background timer."""
        self.timer_manager.stop_background_timer()
