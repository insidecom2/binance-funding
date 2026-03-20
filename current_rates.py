#!/usr/bin/env python3
"""
Alternative bot that uses CURRENT funding rates instead of historical max
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.binance import BinanceFunding

def get_current_funding_opportunities(symbols):
    """Get current funding rates for all symbols"""
    opportunities = []
    
    with BinanceFunding() as client:
        for symbol in symbols:
            try:
                # Get current funding rate
                premium_data = client.get_premium_index(symbol)
                if premium_data:
                    data = premium_data[0]
                    current_rate = float(data['lastFundingRate'])
                    
                    opportunity = {
                        'symbol': symbol,
                        'current_rate': current_rate,
                        'rate_percentage': current_rate * 100,
                        'mark_price': float(data['markPrice']),
                        'next_funding_time': int(data['nextFundingTime']),
                        'is_short_profitable': current_rate > 0
                    }
                    opportunities.append(opportunity)
                    
            except Exception as e:
                print(f"❌ Error getting {symbol}: {e}")
                
    return opportunities

def get_symbol_risk_level_simple(symbol):
    """Get risk level for symbol"""
    if symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
        return '🟢', 'SAFE'
    elif symbol in ['SOLUSDT', 'ADAUSDT', 'XRPUSDT', 'AVAXUSDT', 'MATICUSDT', 'ATOMUSDT', 'APRUSDT']:
        return '🟡', 'MED'
    elif symbol.endswith('PEPEUSDT') or symbol in ['SHIBUSDT', 'DOGEUSDT']:
        return '🔴', 'HIGH'
    else:
        return '🟠', 'RISK'

def main():
    """Current funding rate bot"""
    symbols = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 
        'ADAUSDT', 'XRPUSDT', 'MATICUSDT', 'ATOMUSDT',
        'SHIBUSDT', '1000PEPEUSDT', 'DOGEUSDT', 'APRUSDT'
    ]
    
    print("🤖 CURRENT Funding Rate Scanner")
    print("🔍 Live rates (not historical max)")
    print()
    
    opportunities = get_current_funding_opportunities(symbols)
    
    # Filter for positive rates (SHORT profitable)
    short_opps = [opp for opp in opportunities if opp['is_short_profitable']]
    
    if not short_opps:
        print("❌ No current SHORT opportunities (all rates negative)")
        print("\n📊 All Current Rates:")
        for opp in sorted(opportunities, key=lambda x: x['current_rate'], reverse=True)[:10]:
            risk_emoji, risk_level = get_symbol_risk_level_simple(opp['symbol'])
            print(f"   {opp['symbol']:<12} | {opp['rate_percentage']:>+.6f}% | {risk_emoji} {risk_level}")
        return
    
    # Sort by rate (highest first) 
    short_opps.sort(key=lambda x: x['current_rate'], reverse=True)
    
    print(f"🔻 LIVE SHORT Opportunities ({len(short_opps)} found)")
    print("=" * 70)
    
    for i, opp in enumerate(short_opps[:5], 1):
        rate_pct = opp['rate_percentage']
        risk_emoji, risk_level = get_symbol_risk_level_simple(opp['symbol'])
        
        # Profit calculations
        profit_1k = 1000 * opp['current_rate']  
        profit_10k = 10000 * opp['current_rate']
        
        # Next funding time
        next_funding = datetime.fromtimestamp(opp['next_funding_time']/1000)
        time_to_funding = next_funding - datetime.now()
        hours_left = time_to_funding.total_seconds() / 3600
        
        print(f"{i}. {opp['symbol']:<12} | LIVE Rate: +{rate_pct:.6f}%")
        print(f"   💵 $1K: ${profit_1k:.2f} | $10K: ${profit_10k:.2f} (per 8h)")
        print(f"   {risk_emoji} Risk: {risk_level:<4} | Price: ${opp['mark_price']:,.2f}")
        print(f"   ⏰ Next funding: {hours_left:.1f}h ({next_funding.strftime('%H:%M')})")
        print()
    
    avg_rate = sum(opp['current_rate'] for opp in short_opps) / len(short_opps)
    print(f"📊 Average SHORT rate: +{avg_rate*100:.6f}%")
    print("🔴 These are LIVE rates - updated every 8 hours!")

if __name__ == "__main__":
    main()