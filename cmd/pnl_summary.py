#!/usr/bin/env python3
"""
Show PnL and fee summary from trade history (JSON file)
"""
import argparse

from src.internal.trade_history import summarize_trade_history

def main():
    parser = argparse.ArgumentParser(description="Show PnL and fee summary from trade history.")
    parser.add_argument('--history', type=str, default='.trade_history.json', help='Path to trade history JSON file')
    args = parser.parse_args()

    summary = summarize_trade_history(args.history)

    print("\n=== Trade PnL & Fee Summary ===")
    for k, v in summary.items():
        print(f"{k:20}: {v}")
    print("(Fields: total_trades, successful_trades, winning_trades, total_pnl, average_pnl, win_rate)")

if __name__ == '__main__':
    main()
