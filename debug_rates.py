#!/usr/bin/env python3
"""
Debug script to check if API is returning same rates for different symbols
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.binance import BinanceFunding

def test_funding_rates():
    """Test funding rates for multiple symbols"""
    symbols = ['BTCUSDT', 'ETHUSDT', 'DOTUSDT', 'SOLUSDT', 'XRPUSDT']
    
    print("🔍 Testing funding rates for different symbols...")
    print("=" * 60)
    
    with BinanceFunding() as client:
        for symbol in symbols:
            try:
                # Get recent funding data (last 5 records)
                funding_data = client.get_funding_rate(symbol, limit=5)
                
                if funding_data:
                    latest = funding_data[-1]  # Most recent
                    rate = float(latest['fundingRate'])
                    
                    print(f"{symbol:<10} | Latest Rate: {rate:>+.8f} ({rate*100:+.6f}%)")
                    print(f"           | Time: {latest['fundingTime']} | Price: ${float(latest['markPrice']):.2f}")
                    
                    # Show last 3 rates to see variation
                    print(f"           | Last 3 rates: ", end="")
                    for i, record in enumerate(funding_data[-3:]):
                        r = float(record['fundingRate'])
                        print(f"{r*100:+.4f}%", end="")
                        if i < 2: print(", ", end="")
                    print()
                    print("-" * 60)
                else:
                    print(f"{symbol:<10} | No data available")
                    
            except Exception as e:
                print(f"{symbol:<10} | Error: {e}")

if __name__ == "__main__":
    test_funding_rates()