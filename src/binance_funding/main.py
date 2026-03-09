from __future__ import annotations

import json

from .client import BinanceFundingClient
from .config import load_config
from .strategy import FundingRateArbitrageStrategy


def main() -> None:
    config = load_config()

    symbols = config.get("symbols", ["BTCUSDT"])
    position_size = float(config.get("position_size", 1.0))
    limit = int(config.get("limit", 100))
    top_n = int(config.get("top", 10))
    mode = str(config.get("mode", "analyze")).lower()

    if mode == "analyze":
        print("📊 Analyzing funding rate opportunities...\n")

        strategy = FundingRateArbitrageStrategy(position_size=position_size)
        analysis = strategy.analyze_opportunity(
            symbols=symbols,
            limit=limit,
            top_n=top_n
        )

        print(json.dumps(analysis, indent=2))

    elif mode == "execute":
        print("⚠️  Execute mode (simulation only - no real API key)")
        print("    To trade for real, connect Binance API keys\n")

        strategy = FundingRateArbitrageStrategy(position_size=position_size)
        analysis = strategy.analyze_opportunity(symbols=symbols, limit=limit, top_n=1)

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

    elif mode == "summary":
        print("📋 Trade Summary\n")
        strategy = FundingRateArbitrageStrategy(position_size=position_size)
        summary = strategy.get_trade_summary()
        print(json.dumps(summary, indent=2))

    elif mode == "raw":
        # Show raw funding rates
        client = BinanceFundingClient()
        results = {}
        for symbol in symbols:
            rows = client.get_funding_rates(symbol=symbol, limit=limit)
            results[symbol] = rows
        print(json.dumps(results, indent=2))

    else:
        raise ValueError("Invalid mode in config. Use one of: analyze, execute, summary, raw")


if __name__ == "__main__":
    main()
