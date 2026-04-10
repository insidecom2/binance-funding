#!/usr/bin/env python3
"""
Quick diagnostic to check live funding rate data
"""
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.binance import BinanceFunding

def check_live_rates():
    """Check live funding rates vs historical data"""
    symbols = ['BTCUSDT', 'ETHUSDT', '1000PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT']
    
    print("🔍 LIVE vs HISTORICAL Funding Rate Diagnosis")
    print("=" * 60)
    
    with BinanceFunding() as client:
        for symbol in symbols:
            print(f"\n📊 {symbol}")
            
            try:
                # Get current premium index (live rate)
                premium_data = client.get_premium_index(symbol)
                if premium_data:
                    current_rate = float(premium_data[0]['lastFundingRate'])
                    print(f"  🔴 LIVE Rate:       {current_rate:>+.8f} ({current_rate*100:+.6f}%)")
                
                # Get recent historical (last 3 records)
                historical = client.get_funding_rate(symbol, limit=3)
                if historical:
                    print(f"  📈 Historical rates:")
                    for i, record in enumerate(historical[-3:], 1):
                        rate = float(record['fundingRate'])
                        time_str = datetime.fromtimestamp(record['fundingTime']/1000).strftime('%m-%d %H:%M')
                        print(f"     {i}. {rate:>+.8f} ({rate*100:+.6f}%) - {time_str}")
                        
                    # Check if they're all the same
                    rates = [float(r['fundingRate']) for r in historical]
                    if len(set(rates)) == 1:
                        print(f"  ⚠️  WARNING: All historical rates identical!")
                    else:
                        print(f"  ✅ Rates vary as expected")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
            
            print("-" * 40)

if __name__ == "__main__":
    check_live_rates()