from __future__ import annotations

import argparse
import json

from .analyzer import analyze_funding_trend, rank_by_funding, format_analysis
from .client import BinanceFundingClient
from .config import load_config
from .strategy import FundingRateArbitrageStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binance Funding Rate Arbitrage")
    
    # Config
    parser.add_argument("--config", help="Path to config file (default: config.yaml)")
    parser.add_argument("--position-size", type=float, default=1.0, help="Position size per trade (default 1.0)")
    
    # Analysis
    parser.add_argument("--symbol", help="Specific symbol to fetch (overrides config)")
    parser.add_argument("--limit", type=int, default=100, help="Historical records to fetch (default 100)")
    parser.add_argument("--top", type=int, default=10, help="Show top N funding rates (default 10)")
    
    # Strategy mode
    parser.add_argument("--analyze", action="store_true", help="Analyze opportunities (step 1-3)")
    parser.add_argument("--execute", action="store_true", help="Execute trades (step 4-5) [NOT REAL - REQUIRES API KEY]")
    parser.add_argument("--summary", action="store_true", help="Show trade summary")
    
    # Output
    parser.add_argument("--raw", action="store_true", help="Show raw API response")
    
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    
    symbols = [args.symbol] if args.symbol else config.get("symbols", ["BTCUSDT"])
    position_size = args.position_size
    
    if args.analyze or (not args.execute and not args.summary):
        # Default: Analyze opportunities
        print("📊 Analyzing funding rate opportunities...\n")
        
        strategy = FundingRateArbitrageStrategy(position_size=position_size)
        analysis = strategy.analyze_opportunity(
            symbols=symbols,
            limit=args.limit,
            top_n=args.top
        )
        
        print(json.dumps(analysis, indent=2))
    
    elif args.execute:
        print("⚠️  Execute mode (simulation only - no real API key)")
        print("    To trade for real, connect Binance API keys\n")
        
        strategy = FundingRateArbitrageStrategy(position_size=position_size)
        analysis = strategy.analyze_opportunity(symbols=symbols, limit=args.limit, top_n=1)
        
        # Get top opportunity
        if analysis["opportunities"]:
            top_opp = analysis["opportunities"][0]
            symbol = top_opp["symbol"]
            
            if top_opp["recommendation"]["should_trade"]:
                # Example execution (you would get real-time prices here)
                spot_price = 42000  # Mock price
                funding_rate = float(top_opp["funding"]["current_funding_rate"])
                funding_time_ms = int(1000 * 1000000)  # Mock timestamp
                
                result = strategy.execute_trade(
                    symbol=symbol,
                    spot_price=spot_price,
                    funding_rate=funding_rate,
                    funding_time_unix_ms=funding_time_ms
                )
                
                print(json.dumps(result, indent=2))
            else:
                print(f"❌ Skipping {symbol}: {top_opp['recommendation']['reason']}")
    
    elif args.summary:
        print("📋 Trade Summary\n")
        strategy = FundingRateArbitrageStrategy(position_size=position_size)
        summary = strategy.get_trade_summary()
        print(json.dumps(summary, indent=2))
    
    elif args.raw:
        # Show raw funding rates
        client = BinanceFundingClient()
        results = {}
        for symbol in symbols:
            rows = client.get_funding_rates(symbol=symbol, limit=args.limit)
            results[symbol] = rows
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
