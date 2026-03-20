#!/usr/bin/env python3
"""
Binance Funding Rate SHORT Trading Bot
=====================================

Specialized trading bot that finds SHORT profit opportunities from funding rates.
Shows only positive funding rates where SHORT positions get paid by LONG positions.

Usage:
    python cmd/main.py
    ./run.sh

No arguments needed - automatically scans for profitable SHORT opportunities.
Focus: Find high funding rates to profit from SHORT positions.
"""

import sys
import json
import logging
from datetime import datetime, timedelta
import os

# Handle ML dependencies
try:
    import numpy as np
except ImportError:
    print("⚙️  Installing numpy...")
    os.system("pip install numpy")
    import numpy as np

try:
    import xgboost as xgb
except ImportError:
    print("⚙️  Installing XGBoost...")
    os.system("pip install xgboost")
    import xgboost as xgb

# Add src to path so we can import our module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.binance import BinanceFunding, FundingBot, auto_get_max_funding, get_best_funding_opportunity
from src.xgb import predict_xgb_risk, predict_multi_round_sustainability, get_multi_round_recommendation, calculate_net_profit_with_fees, create_xgb_risk_features, get_optimal_timing

# Set logging to WARNING to reduce noise
logging.getLogger('src.binance').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def format_timestamp(timestamp_ms: int) -> str:
    """Convert millisecond timestamp to readable format"""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')


def display_max_funding_result(data: dict, symbol: str):
    """Display trading bot max funding rate result (simplified)"""
    if 'error' in data:
        print(f"❌ {data['error']}")
        return
    
    max_info = data['max_rate']
    score = data['opportunity_score']
    
    print(f"\n🤖 {symbol} | Rate: {max_info['percentage']:+.6f}% | Score: {score['overall_score']:.0f}/100")
    print(f"🎯 {score['opportunity_type']} | {score['signal_strength']}")
    print(f"💡 {score['recommendation']}")


# calculate_net_profit_with_fees moved to src/xgb/risk_predictor.py


def display_short_opportunities(opportunities: list, limit: int = 5):
    """Display SHORT opportunities with profit focus"""
    if not opportunities:
        print("❌ No SHORT opportunities found")
        return
    
    print(f"\n🎯 TOP {min(limit, len(opportunities))} OPTIMAL Rates (0.04%-0.08%) | {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    print("💰 OPTIMAL = Sweet spot for funding profits")
    print("🎯 Range: 0.04-0.08% = Good profits + Reasonable risk")
    print("🤖 XGBoost ML Risk Prediction: Rate + Price + Symbol analysis")
    print("🌐 AUTO-SCANNED from all available futures pairs")
    print("🔴 LIVE RATES - Real-time data, not historical!")
    print()
    
    for i, opp in enumerate(opportunities[:limit], 1):
        max_info = opp['max_rate']
        score = opp['opportunity_score']
        funding_rate = max_info['value'] * 100  # Convert to percentage
        
        # Calculate potential profits for different position sizes
        rate_decimal = max_info['value']
        profit_1k = 1000 * rate_decimal  # Per $1000 position
        profit_10k = 10000 * rate_decimal  # Per $10k position  
        daily_profit_1k = profit_1k * 3  # 3 funding periods per day
        monthly_profit_1k = daily_profit_1k * 30  # Approximate monthly
        
        # Calculate net profit after fees
        net_1k = calculate_net_profit_with_fees(1000, rate_decimal, 1)
        net_10k = calculate_net_profit_with_fees(10000, rate_decimal, 1)
        net_1k_2rounds = calculate_net_profit_with_fees(1000, rate_decimal, 2)
        
        # Determine profit level including fees
        if net_1k['net_profit'] > 0:  # Profitable after fees
            profit_emoji = "🔥💰"
            profit_level = f"HIGH PROFIT {net_1k['profit_color']}"
        elif net_1k['net_profit'] > -0.20:  # Close to break-even
            profit_emoji = "⚠️💵"
            profit_level = f"MARGINAL {net_1k['profit_color']}"
        else:  # Loss after fees
            profit_emoji = "❌💸"
            profit_level = f"LOSS AFTER FEES {net_1k['profit_color']}"
            
        # Get XGBoost risk prediction
        symbol_risk_emoji, symbol_risk_label = get_symbol_risk_level(opp['symbol'])
        xgb_risk = predict_xgb_risk(opp['symbol'], max_info['value'], max_info['mark_price'], score['overall_score'])
        
        # Get multi-round sustainability prediction
        sustainability = predict_multi_round_sustainability(opp['symbol'], max_info['value'], max_info['mark_price'], xgb_risk)
        
        # Get timing recommendations  
        timing = get_optimal_timing(xgb_risk)
        
        print(f"{i}. {profit_emoji} {opp['symbol']:<12} | Rate: +{funding_rate:.4f}% | {profit_level}")
        print(f"   � GROSS: $1K=${profit_1k:.2f} | $10K=${profit_10k:.2f} per 8h (before fees)")
        print(f"   💸 FEES: Entry+Exit = ${net_1k['trading_fees']:.2f} (0.08% total)")
        print(f"   {net_1k['profit_color']} NET: $1K=${net_1k['net_profit']:+.2f} | $10K=${net_10k['net_profit']:+.2f} per 8h")
        print(f"   📊 Fee Coverage: {net_1k['fee_coverage_ratio']:.1f}x | {net_1k['profitability']}")
        
        # Show 2-round analysis
        if net_1k_2rounds['net_profit'] > 0:
            print(f"   🔄 2 Rounds NET: $1K=${net_1k_2rounds['net_profit']:+.2f} (${net_1k_2rounds['funding_profit']:.2f} - ${net_1k_2rounds['trading_fees']:.2f})")
        else:
            print(f"   🔄 2 Rounds NET: $1K=${net_1k_2rounds['net_profit']:+.2f} ❌ Still unprofitable")
        print(f"   📊 Score: {score['overall_score']:>3.0f}/100 | 🤖 XGB Risk: {xgb_risk['color']} {xgb_risk['level']} ({xgb_risk['score']}%) | Price: ${max_info['mark_price']:>8,.0f}")
        print(f"   🎯 ML Confidence: {xgb_risk['confidence']}% | Features: {xgb_risk['features_count']}")
        print(f"   ⏱️  Recommend Hold: {xgb_risk['recommended_hold_rounds']} rounds ({xgb_risk['recommended_hold_rounds'] * 8}h) | {xgb_risk['hold_reason']}")
        
        # Multi-round prediction display
        print(f"   📈 Next 1 Round: {sustainability['profit_1_round']} ({sustainability['sustainability_1_round']}% sustainable)")
        print(f"   📊 Next 2 Rounds: {sustainability['profit_2_rounds']} ({sustainability['sustainability_2_rounds']}% sustainable)")  
        print(f"   🚨 Long Squeeze Risk: {sustainability['squeeze_level']} ({sustainability['squeeze_risk']}%)")
        print(f"   💡 Multi-Round Strategy: {sustainability['recommendation']}")
        
        print(f"   {timing['entry_color']} Entry: {timing['entry_timing']}")
        print(f"   🚪 Exit: {timing['exit_timing']}")
        
        # Show time of peak rate
        time_ago = datetime.fromtimestamp(max_info['time'] / 1000).strftime('%m-%d %H:%M')
        
        # Show next funding time if available
        if 'next_funding_time' in opp:
            next_funding = datetime.fromtimestamp(opp['next_funding_time'] / 1000)
            time_until = next_funding - datetime.now()
            minutes_left = int(time_until.total_seconds() / 60)
            print(f"   ⏰ Last Rate: {time_ago} UTC | Next Funding: {minutes_left}min ({next_funding.strftime('%H:%M')})")
        else:
            print(f"   ⏰ Rate Time: {time_ago} UTC")
        print()
    
    print("=" * 80)
    print("🤖 XGBoost ML + Multi-Round + Fee Analysis")
    print("🎯 Best strategy: Open SHORT when funding rate is high (get paid by longs)")
    print("🟢 LOW (2-3 rounds) | 🟡 MEDIUM (1-2 rounds) | 🟠 HIGH (1 round) | 🔴 EXTREME (1 round) - ML recommended")
    print("⏱️  Hold Duration: 1round=8h, 2rounds=16h, 3rounds=24h (based on risk level)")
    print("📈 Multi-Round: Predicts sustainability & long squeeze risk for next 1-2 funding rounds")  
    print("🚨 Long Squeeze: Risk of price reversal due to overleveraged short positions")
    print("💸 Fee Analysis: Trading fees ~0.08% total (0.04% entry + 0.04% exit)")
    print("⚠️  Minimum profitable position: Usually $2K+ for rates 0.04-0.08%")
    print("📝 Risk: Price movement can exceed funding profits")


def display_top_opportunities(opportunities: list, limit: int = 5):
    """Display top funding opportunities (1-5 results)"""
    if not opportunities:
        print("❌ No opportunities found")
        return
    
    print(f"\n📊 Top {min(limit, len(opportunities))} Opportunities | {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 75)
    
    for i, opp in enumerate(opportunities[:limit], 1):
        max_info = opp['max_rate']
        score = opp['opportunity_score']
        
        # Determine emoji and color based on signal strength and score
        if score['overall_score'] > 60:
            emoji = "🔥"
            strength_color = "STRONG"
        elif score['overall_score'] > 40:
            emoji = "⚡"
            strength_color = "MODERATE"
        else:
            emoji = "📊"
            strength_color = "WEAK"
            
        # Determine action based on opportunity type
        if score['opportunity_type'] == 'SHORT_OPPORTUNITY':
            action = f"SHORT ({max_info['percentage']:+.4f}%)"
            action_emoji = "🔻"
        elif score['opportunity_type'] == 'LONG_OPPORTUNITY':
            action = f"LONG ({max_info['percentage']:+.4f}%)"
            action_emoji = "🔺"
        else:
            action = f"HOLD ({max_info['percentage']:+.4f}%)"
            action_emoji = "⏸️"
        
        print(f"\n{i}. {emoji} {opp['symbol']:<8} {action_emoji} {action}")
        print(f"   Score: {score['overall_score']:>3.0f}/100 | Signal: {strength_color:<8} | ${max_info['mark_price']:>8,.0f}")
        
        # Show time of max rate  
        time_ago = datetime.fromtimestamp(max_info['time'] / 1000).strftime('%m-%d %H:%M')
        print(f"   Peak Rate Time: {time_ago} UTC")
    
    print(f"\n{'─' * 75}")
    if any(opp['opportunity_score']['overall_score'] > 50 for opp in opportunities[:limit]):
        print("🎯 Found strong signals! Consider taking positions on high-scoring opportunities.")
    else:
        print("⏳ Market is relatively quiet. Monitor for better opportunities.")


def get_symbol_risk_level(symbol: str) -> tuple:
    """Simple placeholder - replaced by XGB prediction"""
    return ('🤖', 'ML')


# create_xgb_risk_features moved to src/xgb/risk_predictor.py


# get_optimal_timing moved to src/xgb/risk_predictor.py
def get_optimal_timing(xgb_risk: dict) -> dict:
    """Calculate optimal entry/exit timing based on funding schedule and risk"""
    # Funding happens every 8 hours: 00:00, 08:00, 16:00 UTC
    base_funding_times = [0, 8, 16]
    current_utc = datetime.now()
    current_hour = current_utc.hour
    
    # Find next funding time
    next_funding_hour = None
    for h in base_funding_times:
        if h > current_hour:
            next_funding_hour = h
            break
    
    if next_funding_hour is None:
        next_funding_hour = base_funding_times[0] + 24  # Next day first funding
        
    if next_funding_hour >= 24:
        next_funding_hour -= 24
        next_funding_day = current_utc + timedelta(days=1)
    else:
        next_funding_day = current_utc
        
    next_funding_dt = datetime(next_funding_day.year, next_funding_day.month, next_funding_day.day, next_funding_hour)
    minutes_to_funding = int((next_funding_dt - current_utc).total_seconds() / 60)
    
    # Entry timing recommendations
    if minutes_to_funding <= 30:
        entry_timing = "URGENT: Enter NOW! (Before funding!)"
        entry_color = "\ud83d\udd25"
    elif minutes_to_funding <= 90:
        entry_timing = "Good timing - Enter soon"
        entry_color = "⚡"
    else:
        entry_timing = "Wait closer to funding time"
        entry_color = "⏳"
        
    # Exit timing based on risk and hold rounds
    exit_rounds = xgb_risk['recommended_hold_rounds']
    exit_time = next_funding_dt + timedelta(hours=8 * exit_rounds)
    
    if exit_rounds == 1:
        exit_timing = f"Exit after next funding ({exit_time.strftime('%H:%M')} UTC)"
    else:
        exit_timing = f"Exit after {exit_rounds} rounds ({exit_time.strftime('%H:%M')} UTC)"
        
    return {
        'entry_timing': entry_timing,
        'entry_color': entry_color,
        'exit_timing': exit_timing,
        'minutes_to_funding': minutes_to_funding,
        'next_funding_time': next_funding_dt.strftime('%H:%M UTC')
    }


# predict_multi_round_sustainability moved to src/xgb/risk_predictor.py


# get_multi_round_recommendation moved to src/xgb/risk_predictor.py


# predict_xgb_risk moved to src/xgb/risk_predictor.py


def get_all_current_funding_opportunities():
    """Get current live funding rates for ALL symbols at once (faster)"""
    opportunities = []
    
    try:
        with BinanceFunding() as client:
            # Get ALL premium index data in one call (much faster)
            logger.info("Fetching ALL symbols funding data in one API call...")
            all_premium_data = client.get_premium_index()  # No symbol = all symbols
            
            logger.info(f"Processing {len(all_premium_data)} symbols...")
            
            for data in all_premium_data:
                symbol = data['symbol']
                
                # Only process USDT pairs
                if not symbol.endswith('USDT'):
                    continue
                    
                try:
                    current_rate = float(data['lastFundingRate'])
                    
                    # Create opportunity data structure
                    opportunity = {
                        'symbol': symbol,
                        'max_rate': {
                            'value': current_rate,
                            'percentage': current_rate * 100,
                            'time': int(data['nextFundingTime']) - (8 * 60 * 60 * 1000),
                            'mark_price': float(data['markPrice'])
                        },
                        'opportunity_score': {
                            'overall_score': min(100, abs(current_rate) * 100000),
                            'opportunity_type': 'SHORT_OPPORTUNITY' if current_rate > 0 else 'LONG_OPPORTUNITY',
                            'signal_strength': 'STRONG' if abs(current_rate) > 0.01 else 'MODERATE' if abs(current_rate) > 0.005 else 'WEAK'
                        },
                        'next_funding_time': int(data['nextFundingTime']),
                        'is_live': True
                    }
                    opportunities.append(opportunity)
                    
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping {symbol}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Failed to get funding data: {e}")
        return []
        
    return opportunities


def main():
    """Trading bot main entry point - scans ALL symbols for top 5 rates"""
    
    print("🤖 Binance Funding Rate Trading Bot")
    print("🔍 Scanning for OPTIMAL rates (0.04% - 0.08%)...")
    print("🎯 Sweet spot: Good profits without extreme risk")
    
    try:
        # Get current live funding rates for ALL symbols (single API call)
        print("🚀 Fetching ALL funding rates in one shot...")
        opportunities = get_all_current_funding_opportunities()
        
        if not opportunities:
            print("❌ Failed to get funding data")
            return
            
        print(f"📊 Processed {len(opportunities)} USDT pairs")
        
        # Sort by rate (highest first) and take top 5 SHORT opportunities
        opportunities.sort(key=lambda x: x['max_rate']['value'], reverse=True)
        
        # Filter for optimal funding rate range (0.04% - 0.08%)
        min_rate = 0.0004  # 0.04%
        max_rate = 0.0008  # 0.08%
        
        optimal_opportunities = [
            opp for opp in opportunities 
            if min_rate <= opp['max_rate']['value'] <= max_rate
        ]
        
        print(f"🎯 Found {len(optimal_opportunities)} symbols in optimal range (0.04% - 0.08%)")
        
        # If no optimal rates found, show nearby rates
        if not optimal_opportunities:
            print("❌ No rates found in optimal range (0.04% - 0.08%)")
            
            # Show rates above 0.08% (too high - risky)
            high_rates = [opp for opp in opportunities if opp['max_rate']['value'] > max_rate][:3]
            if high_rates:
                print(f"\n⚠️  {len(high_rates)} rates ABOVE 0.08% (high risk):")
                for opp in high_rates:
                    rate_pct = opp['max_rate']['percentage']
                    print(f"   {opp['symbol']:<15} | {rate_pct:>+.4f}%")
            
            # Show rates between 0.02-0.04% (lower but safer)
            medium_rates = [opp for opp in opportunities if 0.0002 <= opp['max_rate']['value'] < min_rate][:3]
            if medium_rates:
                print(f"\n📊 {len([o for o in opportunities if 0.0002 <= o['max_rate']['value'] < min_rate])} rates in 0.02-0.04% range:")
                for opp in medium_rates:
                    rate_pct = opp['max_rate']['percentage']
                    print(f"   {opp['symbol']:<15} | {rate_pct:>+.4f}%")
            return
            
        # Show top 5 optimal opportunities
        top_5_optimal = optimal_opportunities[:5]
        display_short_opportunities(top_5_optimal, len(top_5_optimal))
            
        # Market summary for optimal rates
        avg_optimal_rate = sum(opp['max_rate']['value'] for opp in top_5_optimal) / len(top_5_optimal)
        all_positive = len([opp for opp in opportunities if opp['max_rate']['value'] > 0])
        print(f"\n📊 Optimal Range Average: {avg_optimal_rate * 100:+.4f}%")
        print(f"🎯 Optimal Rates (0.04-0.08%): {len(optimal_opportunities)} | All Positive: {all_positive} / {len(opportunities)}")
        if top_5_optimal:
            next_funding_min = (top_5_optimal[0]['next_funding_time'] - int(datetime.now().timestamp() * 1000)) // (1000 * 60)
            print(f"⭐ OPTIMAL RANGE: Profitable but not too risky!")
            print(f"🔴 Next funding in ~{next_funding_min}min - Perfect timing for balanced risk!")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
