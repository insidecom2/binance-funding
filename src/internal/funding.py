import logging
from datetime import datetime
from src.binance import BinanceFunding
from src.xgb import predict_xgb_risk, predict_multi_round_sustainability, calculate_net_profit_with_fees, get_optimal_timing

logging.getLogger('src.binance').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

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


def display_short_opportunities(opportunities: list, limit: int = 5):
    """Display SHORT opportunities with profit focus"""
    if not opportunities:
        print("❌ No SHORT opportunities found")
        return
    print("=" * 80)
    print("💰 OPTIMAL = Sweet spot for funding profits")
    print("🎯 Range: 0.04-0.08% = Good profits + Reasonable risk")
    print("🤖 XGBoost ML Risk Prediction: Rate + Price + Symbol analysis")
    print("🌐 AUTO-SCANNED from all available futures pairs")
    print("🔴 LIVE RATES - Real-time data, not historical!")
    print()
    
    from src.binance.trading_bot import FundingBot
    bot = FundingBot()
    # Precompute xgb_risk for sorting
    scored_opps = []
    for opp in opportunities:
        max_info = opp['max_rate']
        score = opp['opportunity_score']
        xgb_risk = predict_xgb_risk(opp['symbol'], max_info['value'], max_info['mark_price'], score['overall_score'])
        scored_opps.append((xgb_risk['score'], opp, xgb_risk))
    # Sort by xgb_risk['score'] ascending (low risk first)
    scored_opps.sort(key=lambda x: x[0])
    for i, (risk_score, opp, xgb_risk) in enumerate(scored_opps[:limit], 1):
        # Fetch EMA/RSI info for this symbol
        ema_rsi_info = bot.get_ema_rsi_info(opp['symbol'], interval="1h", limit=100)
        max_info = opp['max_rate']
        score = opp['opportunity_score']
        funding_rate = max_info['value'] * 100  # Convert to percentage
        
        # Calculate potential profits for different position sizes
        # Show EMA/RSI/Price info if available
        if 'error' not in ema_rsi_info:
            print(f"   📈 EMA20: {ema_rsi_info['ema20']:.2f} | EMA50: {ema_rsi_info['ema50']:.2f} | Trend: {ema_rsi_info['ema_trend'].upper()} | RSI: {ema_rsi_info['rsi']:.2f}")
        else:
            print(f"   📈 EMA/RSI: {ema_rsi_info['error']}")
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
            
        # Get multi-round sustainability prediction
        sustainability = predict_multi_round_sustainability(opp['symbol'], max_info['value'], max_info['mark_price'], xgb_risk)
        # Get timing recommendations  
        timing = get_optimal_timing(xgb_risk)
        
        print(f"{i}. {profit_emoji} {opp['symbol']:<12} | Rate: +{funding_rate:.4f}% | {profit_level}")
        print(f"   💵 GROSS: $1K=${profit_1k:.2f} | $10K=${profit_10k:.2f} per 8h (before fees)")
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

def get_symbol_risk_level(symbol: str) -> tuple:
    """Simple placeholder - replaced by XGB prediction"""
    return ('🤖', 'ML')

def get_all_current_funding_opportunities():
    """Get current live funding rates for ALL symbols at once (faster)"""
    opportunities = []
    try:
        with BinanceFunding() as client:
            all_premium_data = client.get_premium_index()  # No symbol = all symbols
            for data in all_premium_data:
                symbol = data['symbol']
                if not symbol.endswith('USDT'):
                    continue
                try:
                    current_rate = float(data['lastFundingRate'])
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
