
# =========================
# CONFIG
# =========================
from datetime import datetime, timedelta


import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.binance.trading_bot import FundingBot
from src.internal.funding import get_all_current_funding_opportunities

from src.internal.filter import filter_opportunities, select_best_opportunity


MIN_FUNDING = 0.0002
MIN_FUNDING_EXIT = 0
MIN_BASIS = 0.0005
MIN_BASIS_EXIT = -0.001
MIN_VOLUME = 500_000
MAX_SPREAD = 0.004
MAX_RISK = 0.5

RISK_PER_TRADE = 0.1
MAX_POSITION = 1000
MAX_LOSS = 0.02
MAX_HOLD = timedelta(hours=8)

ENTRY_WINDOW = timedelta(minutes=15)
CONFIDENCE_THRESHOLD = 0.6
TAKE_PROFIT = 0.01

current_position = None

# =========================
# PLACEHOLDER API
# =========================
def get_funding_symbol_rate() -> list:
    print("🚀 Fetching ALL funding rates in one shot...")
    opportunities = get_all_current_funding_opportunities()
    
    if not opportunities:
        print("❌ Failed to get funding data")
        return []
        
    print(f"📊 Processed {len(opportunities)} USDT pairs")
    
    # Sort by rate (highest first) and take top 5 SHORT opportunities
    opportunities.sort(key=lambda x: x['max_rate']['value'], reverse=True)
    
    # Filter for optimal funding rate range (0.05% - 0.10%)
    min_rate = 0.0005  # 0.05%
    max_rate = 0.0010  # 0.10%
    
    optimal_opportunities = [
        opp for opp in opportunities 
        if min_rate <= opp['max_rate']['value'] <= max_rate
    ]
    
    print(f"🎯 Found {len(optimal_opportunities)} symbols in optimal range (0.05% - 0.10%)")
    
    # If no optimal rates found, show nearby rates
    if not optimal_opportunities:
        print("❌ No rates found in optimal range (0.05% - 0.10%)")
        
        # Show rates above 0.10% (too high - risky)
        high_rates = [opp for opp in opportunities if opp['max_rate']['value'] > max_rate][:3]
        if high_rates:
            print(f"\n⚠️  {len(high_rates)} rates ABOVE 0.10% (high risk):")
            for opp in high_rates:
                rate_pct = opp['max_rate']['percentage']
                print(f"   {opp['symbol']:<15} | {rate_pct:>+.4f}%")
        
        # Show rates between 0.02-0.05% (lower but safer)
        medium_rates = [opp for opp in opportunities if 0.0002 <= opp['max_rate']['value'] < min_rate][:3]
        if medium_rates:
            print(f"\n📊 {len([o for o in opportunities if 0.0002 <= o['max_rate']['value'] < min_rate])} rates in 0.02-0.04% range:")
            for opp in medium_rates:
                rate_pct = opp['max_rate']['percentage']
                print(f"   {opp['symbol']:<15} | {rate_pct:>+.4f}%")
        return []
        
    # Skip verbose per-symbol block to keep logs concise.
    top_5_optimal = optimal_opportunities[:5]
        
    # Market summary for optimal rates
    # avg_optimal_rate = sum(opp['max_rate']['value'] for opp in top_5_optimal) / len(top_5_optimal)
    # all_positive = len([opp for opp in opportunities if opp['max_rate']['value'] > 0])
    # print(f"\n📊 Optimal Range Average: {avg_optimal_rate * 100:+.4f}%")
    # print(f"🎯 Optimal Rates (0.04-0.08%): {len(optimal_opportunities)} | All Positive: {all_positive} / {len(opportunities)}")
    if top_5_optimal:
        next_funding_min = (top_5_optimal[0]['next_funding_time'] - int(datetime.now().timestamp() * 1000)) // (1000 * 60)
        # print(f"⭐ OPTIMAL RANGE: Profitable but not too risky!")
        print(f"🔴 Next funding in ~{next_funding_min}min - Perfect timing for balanced risk!")

    return top_5_optimal

def main():
    """Trading bot main entry point - scans ALL symbols for top 5 rates"""
    print("🤖 Binance Funding Rate Trading Bot")
    print("🔍 Scanning for OPTIMAL rates (0.04% - 0.08%)...")
    print("🎯 Sweet spot: Good profits without extreme risk")
    try:
        # Get current live funding rates for ALL symbols (single API call)
        opportunities = get_funding_symbol_rate()
        print(f"✅ Found {len(opportunities)} optimal funding opportunities")
        
        # Filter and rank by risk, basis, funding, volume, spread, net profit
        if opportunities:
            filtered = filter_opportunities(
                opportunities,
                min_basis=MIN_BASIS,
                min_funding=MIN_FUNDING,
                min_volume=MIN_VOLUME,
                max_spread=MAX_SPREAD,
                max_risk=MAX_RISK,
                position_size=MAX_POSITION,
            )
            print(
                "\n🏆 Filtered Opportunities "
                f"(risk <= {MAX_RISK:.2f}, basis > {MIN_BASIS:.2%}, funding >= {MIN_FUNDING:.2%}, "
                f"volume >= {MIN_VOLUME:,.0f}, spread <= {MAX_SPREAD:.2%}, กำไรสุทธิสูงสุด):"
            )
            for i, opp in enumerate(filtered, 1):
                selected_rounds = opp.get('selected_rounds', 1)
                print(f"{i}. {opp['symbol']} | risk={opp['risk']:.2f} | basis={opp['basis']:+.4%} | funding={opp['funding_rate']:+.4%} | volume={opp['volume']:.0f} | spread={opp['spread']:.4%} | net_profit={opp['net_profit']:.6f} | rounds={selected_rounds}")
            if not filtered:
                print("❌ No opportunities passed all filters.")

            # เลือกเหรียญที่ผ่านเงื่อนไข โดยเน้นกำไรสุทธิสูงสุดและใช้ risk ต่ำเป็นตัวตัดสินรอง
            best = select_best_opportunity(
                opportunities,
                min_basis=MIN_BASIS,
                min_funding=MIN_FUNDING,
                min_volume=MIN_VOLUME,
                max_spread=MAX_SPREAD,
                max_risk=MAX_RISK,
                position_size=MAX_POSITION,
            )
            if best:
                print("\n⭐️ Best Opportunity:")
                print(f"{best['symbol']} | risk={best['risk']:.2f} | basis={best['basis']:+.4%} | funding={best['funding_rate']:+.4%} | volume={best['volume']:.0f} | spread={best['spread']:.4%} | net_profit={best['net_profit']:.6f} | selected_rounds={best['best_rounds']}")
            else:
                print("❌ No symbol passed all strict filters for best opportunity.")


    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()