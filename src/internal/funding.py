import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _compute_linear_forecast(rates):
    """Return slope/intercept/r2/residual_std and one-step-ahead forecast for a numeric rate series."""
    n = len(rates)
    if n < 2:
        return None

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(rates) / n

    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, rates))

    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    fitted = [slope * x + intercept for x in xs]
    ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(rates, fitted))
    ss_tot = sum((y - mean_y) ** 2 for y in rates)
    r_squared = 1.0 if ss_tot == 0 else max(0.0, min(1.0, 1 - (ss_res / ss_tot)))
    residual_std = math.sqrt(ss_res / n) if n > 0 else float('inf')

    current_rate = rates[-1]
    predicted_next = slope * n + intercept

    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_squared,
        'residual_std': residual_std,
        'current_rate': current_rate,
        'predicted_next': predicted_next,
        'delta_next_vs_current': predicted_next - current_rate,
        'points_used': n,
    }


def get_next_funding_forecast(
    symbol,
    periods=20,
    prediction_edge=0.0,
    min_points=8,
    min_r2=0.20,
    max_residual_std=0.0004,
    max_relative_std=0.5,
    min_predicted_next=0.0002,
):
    """Forecast next funding period from recent history with confidence guards."""
    try:
        with BinanceFunding() as client:
            history = client.get_funding_rate(symbol, limit=periods)
    except Exception as e:
        return {
            'is_valid': False,
            'forecast_pass': False,
            'confidence_pass': False,
            'fail_reason': f'fetch_error: {e}',
            'points_used': 0,
        }

    if not history:
        return {
            'is_valid': False,
            'forecast_pass': False,
            'confidence_pass': False,
            'fail_reason': 'insufficient_points',
            'points_used': 0,
        }

    parsed = []
    for record in history:
        try:
            parsed.append((int(record['fundingTime']), float(record['fundingRate'])))
        except (KeyError, TypeError, ValueError):
            continue

    if len(parsed) < min_points:
        return {
            'is_valid': False,
            'forecast_pass': False,
            'confidence_pass': False,
            'fail_reason': 'insufficient_points',
            'points_used': len(parsed),
        }

    parsed.sort(key=lambda x: x[0])
    parsed = parsed[-periods:]
    rates = [rate for _, rate in parsed]

    forecast = _compute_linear_forecast(rates)
    if forecast is None:
        return {
            'is_valid': False,
            'forecast_pass': False,
            'confidence_pass': False,
            'fail_reason': 'regression_error',
            'points_used': len(rates),
        }

    mean_rate = sum(rates) / len(rates)
    relative_std = forecast['residual_std'] / abs(mean_rate) if abs(mean_rate) > 1e-10 else float('inf')

    confidence_pass = (
        forecast['points_used'] >= min_points
        and forecast['r_squared'] >= min_r2
        and forecast['residual_std'] <= max_residual_std
        and relative_std <= max_relative_std
    )
    forecast_pass = (
        forecast['predicted_next'] >= (forecast['current_rate'] + prediction_edge)
        and forecast['predicted_next'] >= min_predicted_next
    )

    fail_reason = None
    if not confidence_pass:
        if relative_std > max_relative_std:
            fail_reason = 'noisy_signal'
        else:
            fail_reason = 'low_confidence'
    elif not forecast_pass:
        if forecast['predicted_next'] < min_predicted_next:
            fail_reason = 'predicted_below_floor'
        else:
            fail_reason = 'predicted_below_edge'

    return {
        'is_valid': True,
        'forecast_pass': forecast_pass,
        'confidence_pass': confidence_pass,
        'fail_reason': fail_reason,
        'periods': periods,
        'prediction_edge': prediction_edge,
        'mean_rate': mean_rate,
        'relative_std': relative_std,
        **forecast,
    }

def get_all_current_funding_opportunities(
    compute_forecast=False,
    forecast_periods=20,
    prediction_edge=0.0,
    forecast_min_points=8,
    forecast_min_r2=0.20,
    forecast_max_residual_std=0.0004,
):
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
                    funding_forecast = None
                    if compute_forecast:
                        funding_forecast = get_next_funding_forecast(
                            symbol,
                            periods=forecast_periods,
                            prediction_edge=prediction_edge,
                            min_points=forecast_min_points,
                            min_r2=forecast_min_r2,
                            max_residual_std=forecast_max_residual_std,
                        )
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
                        'funding_forecast': funding_forecast,
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


def enrich_opportunities_with_forecast(
    opportunities,
    forecast_periods=20,
    prediction_edge=0.0,
    forecast_min_points=8,
    forecast_min_r2=0.20,
    forecast_max_residual_std=0.0004,
    forecast_max_relative_std=0.5,
    forecast_min_predicted=0.0002,
    max_workers=5,
):
    """Populate funding_forecast for each provided opportunity in parallel."""
    if not opportunities:
        return opportunities

    def _compute_for_opp(opp):
        symbol = opp.get('symbol', '')
        if not symbol:
            return opp, {
                'is_valid': False,
                'forecast_pass': False,
                'confidence_pass': False,
                'fail_reason': 'missing_symbol',
                'points_used': 0,
            }
        forecast = get_next_funding_forecast(
            symbol,
            periods=forecast_periods,
            prediction_edge=prediction_edge,
            min_points=forecast_min_points,
            min_r2=forecast_min_r2,
            max_residual_std=forecast_max_residual_std,
            max_relative_std=forecast_max_relative_std,
            min_predicted_next=forecast_min_predicted,
        )
        return opp, forecast

    workers = max(1, min(max_workers, len(opportunities)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(_compute_for_opp, opp): opp for opp in opportunities}
        for future in as_completed(future_map):
            opp = future_map[future]
            try:
                resolved_opp, forecast = future.result()
                resolved_opp['funding_forecast'] = forecast
            except Exception as e:
                opp['funding_forecast'] = {
                    'is_valid': False,
                    'forecast_pass': False,
                    'confidence_pass': False,
                    'fail_reason': f'forecast_enrich_error: {e}',
                    'points_used': 0,
                }
    return opportunities
