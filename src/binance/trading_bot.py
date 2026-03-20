"""
Binance Funding Rate Trading Bot
===============================

This module provides automated trading bot functionality for Binance funding rate trading.
The bot can monitor funding rates, identify opportunities, and execute trades automatically.

Features:
- Auto-detect maximum funding rates
- Monitor funding rate changes
- Alert system for trading opportunities
- Foundation for automated trading strategies

Example:
    from src.binance.trading_bot import FundingBot
    
    bot = FundingBot()
    max_rate = bot.get_last_max_funding_rate("BTCUSDT")
    bot.start_monitoring(symbols=["BTCUSDT", "ETHUSDT"])
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import json

from .binance_funding import BinanceFunding, BinanceFundingError

logger = logging.getLogger(__name__)


class FundingBot:
    """
    Binance Funding Rate Trading Bot
    
    Monitors funding rates and provides automated trading capabilities
    """
    
    def __init__(self, 
                 check_interval: int = 300,  # 5 minutes
                 max_rate_threshold: float = 0.001,  # 0.1%
                 min_rate_threshold: float = -0.001,  # -0.1%
                 lookback_hours: int = 24):
        """
        Initialize Funding Rate Trading Bot
        
        Args:
            check_interval (int): Seconds between funding rate checks (default: 300)
            max_rate_threshold (float): Alert threshold for high funding rates
            min_rate_threshold (float): Alert threshold for low funding rates  
            lookback_hours (int): Hours of historical data to analyze (default: 24)
        """
        self.check_interval = check_interval
        self.max_rate_threshold = max_rate_threshold
        self.min_rate_threshold = min_rate_threshold
        self.lookback_hours = lookback_hours
        self.is_running = False
        self.client = None
        
        # Callbacks for events
        self.on_max_rate_found: Optional[Callable] = None
        self.on_opportunity_detected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        logger.info(f"FundingBot initialized with {lookback_hours}h lookback")
    
    def get_last_max_funding_rate(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get the most recent maximum funding rate for a symbol
        
        Args:
            symbol (str): Trading symbol (e.g., "BTCUSDT")
            limit (int): Number of recent records to analyze (default: 100)
            
        Returns:
            Dict: Information about the last maximum funding rate
        """
        logger.info(f"🔍 Searching for last max funding rate: {symbol}")
        
        with BinanceFunding() as client:
            # Get recent funding rate data
            funding_data = client.get_funding_rate(symbol, limit=limit)
            
            if not funding_data:
                return {
                    'symbol': symbol,
                    'error': 'No funding data available',
                    'max_rate': None
                }
            
            # Find maximum funding rate
            max_record = max(funding_data, key=lambda x: float(x['fundingRate']))
            max_rate = float(max_record['fundingRate'])
            
            # Calculate some statistics  
            all_rates = [float(r['fundingRate']) for r in funding_data]
            avg_rate = sum(all_rates) / len(all_rates)
            min_rate = min(all_rates)
            
            result = {
                'symbol': symbol,
                'timestamp': int(time.time() * 1000),
                'analysis_period': f"Last {limit} funding periods",
                'max_rate': {
                    'value': max_rate,
                    'percentage': max_rate * 100,
                    'time': max_record['fundingTime'],
                    'time_readable': datetime.fromtimestamp(max_record['fundingTime'] / 1000).strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'mark_price': float(max_record['markPrice']),
                },
                'statistics': {
                    'average_rate': avg_rate,
                    'min_rate': min_rate,
                    'rate_volatility': max_rate - min_rate,
                    'total_periods': len(funding_data)
                },
                'opportunity_score': self._calculate_opportunity_score(max_rate, avg_rate)
            }
            
            logger.info(f"📊 Max rate found: {max_rate * 100:.6f}% at {result['max_rate']['time_readable']}")
            return result
    
    def _calculate_opportunity_score(self, max_rate: float, avg_rate: float) -> Dict[str, Any]:
        """
        Calculate trading opportunity score based on funding rate analysis
        
        Args:
            max_rate (float): Maximum funding rate found
            avg_rate (float): Average funding rate  
            
        Returns:
            Dict: Opportunity analysis scores
        """
        # Score based on how extreme the rate is
        abs_max = abs(max_rate)
        abs_avg = abs(avg_rate)
        
        # Extreme rate score (0-100)
        extreme_score = min(100, abs_max * 100000)  # Scale to percentage
        
        # Deviation from average score
        deviation = abs(max_rate - avg_rate)
        deviation_score = min(100, deviation * 100000)
        
        # Overall opportunity score  
        overall_score = (extreme_score + deviation_score) / 2
        
        # Determine opportunity type
        if max_rate > self.max_rate_threshold:
            opportunity_type = "SHORT_OPPORTUNITY"  # High positive rate = short position profitable
            signal_strength = "STRONG" if abs_max > 0.002 else "MODERATE" if abs_max > 0.001 else "WEAK"
        elif max_rate < self.min_rate_threshold:
            opportunity_type = "LONG_OPPORTUNITY"   # High negative rate = long position profitable  
            signal_strength = "STRONG" if abs_max > 0.002 else "MODERATE" if abs_max > 0.001 else "WEAK"
        else:
            opportunity_type = "NO_OPPORTUNITY"
            signal_strength = "NEUTRAL"
        
        return {
            'overall_score': round(overall_score, 2),
            'extreme_score': round(extreme_score, 2),
            'deviation_score': round(deviation_score, 2),
            'opportunity_type': opportunity_type,
            'signal_strength': signal_strength,
            'recommendation': self._get_trading_recommendation(max_rate, opportunity_type, signal_strength)
        }
    
    def _get_trading_recommendation(self, rate: float, opp_type: str, strength: str) -> str:
        """Generate trading recommendation based on analysis"""
        if opp_type == "SHORT_OPPORTUNITY":
            if strength == "STRONG":
                return f"🔴 STRONG SHORT: Rate {rate*100:.4f}% is very high - consider short position"
            elif strength == "MODERATE":
                return f"🟡 MODERATE SHORT: Rate {rate*100:.4f}% shows short opportunity"
            else:
                return f"🔵 WEAK SHORT: Rate {rate*100:.4f}% shows minimal short signal"
        elif opp_type == "LONG_OPPORTUNITY":
            if strength == "STRONG":
                return f"🟢 STRONG LONG: Rate {rate*100:.4f}% is very negative - consider long position"
            elif strength == "MODERATE":
                return f"🟡 MODERATE LONG: Rate {rate*100:.4f}% shows long opportunity"
            else:
                return f"🔵 WEAK LONG: Rate {rate*100:.4f}% shows minimal long signal"
        else:
            return f"⚪ NEUTRAL: Rate {rate*100:.4f}% shows no clear opportunity"
    
    def monitor_multiple_symbols(self, symbols: List[str], limit: int = 50) -> Dict[str, Any]:
        """
        Monitor funding rates across multiple symbols and rank by opportunity
        
        Args:
            symbols (List[str]): List of symbols to monitor
            limit (int): Records per symbol to analyze
            
        Returns:
            Dict: Ranked opportunities across all symbols
        """
        logger.info(f"🔍 Monitoring {len(symbols)} symbols for funding opportunities...")
        
        opportunities = []
        
        for symbol in symbols:
            try:
                analysis = self.get_last_max_funding_rate(symbol, limit)
                if 'error' not in analysis:
                    opportunities.append(analysis)
                    
            except Exception as e:
                logger.warning(f"Failed to analyze {symbol}: {e}")
                continue
        
        # Sort by opportunity score (highest first)
        opportunities.sort(key=lambda x: x['opportunity_score']['overall_score'], reverse=True)
        
        # Prepare summary
        summary = {
            'timestamp': int(time.time() * 1000),
            'symbols_analyzed': len(opportunities),
            'symbols_requested': len(symbols),
            'top_opportunities': opportunities[:3],  # Top 3
            'all_opportunities': opportunities,
            'market_summary': self._generate_market_summary(opportunities)
        }
        
        logger.info(f"📊 Found {len(opportunities)} opportunities. Top: {opportunities[0]['symbol'] if opportunities else 'None'}")
        return summary
    
    def _generate_market_summary(self, opportunities: List[Dict]) -> Dict[str, Any]:
        """Generate overall market funding rate summary"""
        if not opportunities:
            return {'status': 'No data available'}
        
        # Extract all rates and scores
        all_rates = [opp['max_rate']['value'] for opp in opportunities]
        all_scores = [opp['opportunity_score']['overall_score'] for opp in opportunities]
        
        # Count opportunity types
        opp_types = [opp['opportunity_score']['opportunity_type'] for opp in opportunities]
        type_counts = {t: opp_types.count(t) for t in set(opp_types)}
        
        return {
            'market_avg_rate': sum(all_rates) / len(all_rates),
            'market_max_rate': max(all_rates),
            'market_min_rate': min(all_rates),
            'avg_opportunity_score': sum(all_scores) / len(all_scores),
            'opportunity_distribution': type_counts,
            'market_status': self._determine_market_status(type_counts, all_rates)
        }
    
    def _determine_market_status(self, type_counts: Dict, rates: List[float]) -> str:
        """Determine overall market funding status"""
        strong_opps = sum(1 for opp in type_counts if 'STRONG' in str(opp))
        total_opps = len(rates)
        
        avg_rate = sum(rates) / len(rates) if rates else 0
        
        if strong_opps > total_opps * 0.3:
            return "🔥 HIGH OPPORTUNITY MARKET"
        elif abs(avg_rate) > 0.001:
            return "⚡ ACTIVE FUNDING MARKET" 
        elif abs(avg_rate) > 0.0005:
            return "📊 MODERATE FUNDING MARKET"
        else:
            return "😴 QUIET FUNDING MARKET"
    
    async def start_monitoring(self, symbols: List[str], continuous: bool = True):
        """
        Start continuous monitoring of funding rates
        
        Args:
            symbols (List[str]): Symbols to monitor
            continuous (bool): Whether to run continuously or just once
        """
        logger.info(f"🤖 Starting funding rate monitoring for {symbols}")
        self.is_running = True
        
        while self.is_running:
            try:
                # Get opportunities across all symbols
                opportunities = self.monitor_multiple_symbols(symbols)
                
                # Check for significant opportunities
                top_opp = opportunities.get('top_opportunities', [])
                if top_opp:
                    best = top_opp[0]
                    score = best['opportunity_score']['overall_score']
                    
                    if score > 50:  # Significant opportunity threshold
                        logger.info(f"🎯 OPPORTUNITY DETECTED: {best['symbol']} - Score: {score}")
                        
                        if self.on_opportunity_detected:
                            self.on_opportunity_detected(best)
                
                # Call max rate callback if set
                if self.on_max_rate_found and top_opp:
                    self.on_max_rate_found(top_opp[0])
                
                if not continuous:
                    break
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
                if self.on_error:
                    self.on_error(e)
                
                if not continuous:
                    break
                    
                await asyncio.sleep(30)  # Wait 30s on error
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        logger.info("🛑 Stopping funding rate monitoring...")
        self.is_running = False
    
    def set_callbacks(self, 
                     on_max_rate: Optional[Callable] = None,
                     on_opportunity: Optional[Callable] = None, 
                     on_error: Optional[Callable] = None):
        """
        Set callback functions for bot events
        
        Args:
            on_max_rate: Called when new max rate is found
            on_opportunity: Called when trading opportunity detected
            on_error: Called when error occurs
        """
        self.on_max_rate_found = on_max_rate
        self.on_opportunity_detected = on_opportunity  
        self.on_error = on_error
        
        logger.info("📞 Bot callbacks configured")


# Quick utility functions
def get_best_funding_opportunity(symbols: List[str] = None, limit: int = 100) -> Dict[str, Any]:
    """
    Quick function to find the best funding rate opportunity
    
    Args:
        symbols: List of symbols to check (default: major pairs)
        limit: Historical records to analyze per symbol
        
    Returns:
        Dict: Best opportunity found across all symbols
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
    
    bot = FundingBot()
    opportunities = bot.monitor_multiple_symbols(symbols, limit)
    
    if opportunities['top_opportunities']:
        return opportunities['top_opportunities'][0]
    else:
        return {'error': 'No opportunities found'}


def auto_get_max_funding(symbol: str = "BTCUSDT", limit: int = 100) -> Dict[str, Any]:
    """
    Automatically get the latest maximum funding rate for a symbol
    
    Args:
        symbol: Trading symbol to analyze
        limit: Number of recent periods to analyze
        
    Returns:
        Dict: Maximum funding rate analysis
    """
    bot = FundingBot()
    return bot.get_last_max_funding_rate(symbol, limit)


if __name__ == "__main__":
    # Example usage
    print("🤖 Binance Funding Rate Trading Bot")
    print("=" * 50)
    
    try:
        # Test auto max funding detection
        print("\n📊 Testing Auto Max Funding Detection:")
        result = auto_get_max_funding("BTCUSDT", limit=50)
        
        if 'error' not in result:
            max_info = result['max_rate']
            score_info = result['opportunity_score']
            
            print(f"Symbol: {result['symbol']}")
            print(f"Max Rate: {max_info['percentage']:.6f}%")
            print(f"Time: {max_info['time_readable']}")
            print(f"Price: ${max_info['mark_price']:,.2f}")
            print(f"Opportunity: {score_info['opportunity_type']}")
            print(f"Signal: {score_info['signal_strength']}")
            print(f"Recommendation: {score_info['recommendation']}")
        
        # Test multi-symbol monitoring
        print("\n🔍 Testing Multi-Symbol Monitoring:")
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        
        bot = FundingBot()
        opportunities = bot.monitor_multiple_symbols(symbols, limit=30)
        
        print(f"Market Status: {opportunities['market_summary']['market_status']}")
        print("\nTop 3 Opportunities:")
        for i, opp in enumerate(opportunities['top_opportunities'], 1):
            rate = opp['max_rate']['percentage']
            score = opp['opportunity_score']['overall_score']
            signal = opp['opportunity_score']['signal_strength']
            print(f"  {i}. {opp['symbol']}: {rate:+.6f}% (Score: {score:.1f}, {signal})")
        
    except Exception as e:
        print(f"❌ Error: {e}")