from __future__ import annotations

import argparse
import json

from .client import BinanceFundingClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Binance funding rates")
    parser.add_argument("--symbol", default="BTCUSDT", help="Futures symbol, e.g. BTCUSDT")
    parser.add_argument("--limit", type=int, default=5, help="Number of rows to fetch")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = BinanceFundingClient()
    rows = client.get_funding_rates(symbol=args.symbol, limit=args.limit)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
