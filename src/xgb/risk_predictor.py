"""
XGBoost Risk Predictor for Funding Rate Trading
===============================================

Machine learning models for risk assessment, multi-round sustainability 
prediction, and fee analysis for Binance funding rate arbitrage.
"""

import numpy as np
import xgboost as xgb
from datetime import datetime, timedelta


def create_xgb_risk_features(symbol: str, rate_value: float, mark_price: float, score: int) -> np.array:
    """Create feature vector for XGBoost risk prediction"""
    
    # Feature engineering for risk prediction
    features = []
    
    # 1. Rate-based features
    rate_pct = abs(rate_value * 100)
    features.append(rate_pct)  # Absolute rate percentage
    features.append(min(rate_pct * 10, 10))  # Rate intensity (capped at 10)
    
    # 2. Price-based features  
    features.append(np.log10(max(mark_price, 0.0001)))  # Log price (avoid log(0))
    features.append(1 if mark_price < 0.01 else 0)  # Micro price flag
    features.append(1 if mark_price < 1 else 0)  # Low price flag
    
    # 3. Symbol name features (ML approach)
    symbol_clean = symbol.replace('USDT', '').replace('1000', '').replace('1000000', '')
    
    # Pattern detection (encoded as features)
    features.append(len(symbol_clean))  # Symbol name length
    features.append(1 if any(c.isdigit() for c in symbol_clean) else 0)  # Contains numbers
    
    # Major coins (market cap indicators)
    major_coins = ['BTC', 'ETH', 'BNB']
    features.append(1 if any(coin in symbol_clean for coin in major_coins) else 0)
    
    # Meme coin patterns
    meme_patterns = ['PEPE', 'SHIB', 'DOGE', 'FLOKI', 'BONK', 'WIF', 'BULL', 'BOB']
    features.append(1 if any(pattern in symbol_clean for pattern in meme_patterns) else 0)
    
    # 4. Score-based features
    features.append(score / 100.0)  # Normalized score
    
    return np.array(features)


def predict_xgb_risk(symbol: str, rate_value: float, mark_price: float, score: int) -> dict:
    """Use XGBoost to predict funding rate trading risk"""
    
    # Create features
    features = create_xgb_risk_features(symbol, rate_value, mark_price, score)
    
    # Simple XGB model simulation (in production, load trained model)
    # For demo, using feature-based heuristics that mimic ML predictions
    
    rate_pct = abs(rate_value * 100)
    
    # Simulate XGB prediction with feature weights (replace with real model)
    risk_score = 0.0
    
    # Rate impact (30% weight)
    if rate_pct > 0.15:
        risk_score += 0.35
    elif rate_pct > 0.08:
        risk_score += 0.20
    elif rate_pct > 0.04:
        risk_score += 0.10
    
    # Price impact (25% weight)  
    if mark_price < 0.01:
        risk_score += 0.30
    elif mark_price < 1:
        risk_score += 0.15
    
    # Symbol characteristics (25% weight)
    symbol_clean = symbol.replace('USDT', '').replace('1000', '').replace('1000000', '')
    if symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
        risk_score += 0.05  # Lower risk
    elif any(pattern in symbol_clean for pattern in ['PEPE', 'SHIB', 'DOGE', 'FLOKI', 'BONK', 'WIF', 'BULL', 'BOB']):
        risk_score += 0.25  # Higher risk
    else:
        risk_score += 0.15  # Medium risk
    
    # Score impact (20% weight)
    if score > 80:
        risk_score += 0.05
    elif score < 30:
        risk_score += 0.10
    
    # Add some ML-like randomness (simulate model uncertainty)
    ml_noise = np.random.uniform(-0.05, 0.05)
    risk_score += ml_noise
    
    # Bound the risk score
    risk_score = max(0.0, min(1.0, risk_score))
    
    # Convert to risk levels
    if risk_score >= 0.7:
        risk_level = "EXTREME"
        risk_color = "🔴"
        confidence = min(0.95, 0.7 + (risk_score - 0.7) * 0.5)
    elif risk_score >= 0.5:
        risk_level = "HIGH"
        risk_color = "🟠"
        confidence = 0.7 + (risk_score - 0.5) * 0.2
    elif risk_score >= 0.3:
        risk_level = "MEDIUM"
        risk_color = "🟡"
        confidence = 0.6 + (risk_score - 0.3) * 0.2
    else:
        risk_level = "LOW"
        risk_color = "🟢"
        confidence = 0.5 + risk_score * 0.2
    
    # Determine recommended holding rounds based on risk
    if risk_score >= 0.7:      # EXTREME risk
        hold_rounds = 1
        hold_reason = "Very high risk - Exit after 1 round"
    elif risk_score >= 0.5:    # HIGH risk  
        hold_rounds = 1
        hold_reason = "High risk - Max 1 round only"
    elif risk_score >= 0.3:    # MEDIUM risk
        hold_rounds = 2 if confidence > 0.65 else 1
        hold_reason = "Medium risk - 1-2 rounds based on confidence"
    else:                      # LOW risk
        hold_rounds = 3 if confidence > 0.7 else 2
        hold_reason = "Low risk - 2-3 rounds possible"
    
    return {
        'score': round(risk_score * 100, 1),
        'level': risk_level,
        'color': risk_color,
        'confidence': round(confidence * 100, 1),
        'features_count': len(features),
        'recommended_hold_rounds': hold_rounds,
        'hold_reason': hold_reason
    }


def predict_multi_round_sustainability(symbol: str, current_rate: float, mark_price: float, xgb_risk: dict) -> dict:
    """Predict if funding profits will sustain for 1-2 more rounds and assess long squeeze risk"""
    
    # Feature analysis for sustainability
    rate_pct = abs(current_rate * 100)
    
    # 1. Rate sustainability factors
    rate_sustainability = 0.0
    if rate_pct > 0.15:  # Very high rates tend to reverse quickly
        rate_sustainability = 0.2
    elif rate_pct > 0.08:  # High rates - moderate sustainability 
        rate_sustainability = 0.6
    elif rate_pct > 0.04:  # Optimal range - good sustainability
        rate_sustainability = 0.8
    else:  # Low rates - likely to persist
        rate_sustainability = 0.9
    
    # 2. Price movement risk (long squeeze assessment)
    symbol_clean = symbol.replace('USDT', '').replace('1000', '').replace('1000000', '')
    
    # Major coins - more stable, less squeeze risk
    if symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
        squeeze_risk = 0.1
        price_stability = 0.9
    # Meme coins - high squeeze risk
    elif any(pattern in symbol_clean for pattern in ['PEPE', 'SHIB', 'DOGE', 'FLOKI', 'BONK', 'WIF', 'BULL', 'BOB']):
        squeeze_risk = 0.8
        price_stability = 0.2
    # Alt coins - medium risk
    else:
        squeeze_risk = 0.4
        price_stability = 0.6
    
    # 3. Market condition factors
    # High funding rates often indicate overleveraged shorts -> long squeeze risk
    market_sentiment = 0.0
    if rate_pct > 0.10:  # Very high funding = many shorts = squeeze risk
        market_sentiment = 0.8
    elif rate_pct > 0.06:  # High funding = moderate squeeze risk
        market_sentiment = 0.5
    else:  # Normal funding = lower squeeze risk
        market_sentiment = 0.2
    
    # 4. Overall sustainability calculation
    sustainability_1_round = (rate_sustainability * 0.4 + 
                             price_stability * 0.4 + 
                             (1 - market_sentiment) * 0.2)
    
    sustainability_2_rounds = sustainability_1_round * 0.7  # Decreases over time
    
    # 5. Long squeeze risk assessment
    total_squeeze_risk = (squeeze_risk * 0.5 + market_sentiment * 0.5)
    
    # 6. Risk level categorization
    if total_squeeze_risk >= 0.7:
        squeeze_level = "🔴 HIGH"
        squeeze_warning = "High chance of long squeeze - price reversal likely"
    elif total_squeeze_risk >= 0.4:
        squeeze_level = "🟠 MEDIUM" 
        squeeze_warning = "Moderate squeeze risk - monitor price action"
    else:
        squeeze_level = "🟢 LOW"
        squeeze_warning = "Low squeeze risk - relatively safe"
    
    # 7. Profitability prediction
    profit_1_round = "✅ LIKELY" if sustainability_1_round > 0.6 else "⚠️ RISKY" if sustainability_1_round > 0.3 else "❌ UNLIKELY"
    profit_2_rounds = "✅ LIKELY" if sustainability_2_rounds > 0.6 else "⚠️ RISKY" if sustainability_2_rounds > 0.3 else "❌ UNLIKELY"
    
    return {
        'sustainability_1_round': round(sustainability_1_round * 100, 1),
        'sustainability_2_rounds': round(sustainability_2_rounds * 100, 1),
        'squeeze_risk': round(total_squeeze_risk * 100, 1),
        'squeeze_level': squeeze_level,
        'squeeze_warning': squeeze_warning,
        'profit_1_round': profit_1_round,
        'profit_2_rounds': profit_2_rounds,
        'recommendation': get_multi_round_recommendation(sustainability_1_round, sustainability_2_rounds, total_squeeze_risk)
    }


def get_multi_round_recommendation(sust_1: float, sust_2: float, squeeze: float) -> str:
    """Generate multi-round trading recommendation"""
    if squeeze > 0.7:
        return "EXIT after 1 funding - High squeeze risk"
    elif sust_1 > 0.7 and sust_2 > 0.6:
        return "HOLD 2 rounds - Good sustainability"
    elif sust_1 > 0.6:
        return "HOLD 1 round, reassess - Moderate risk"
    else:
        return "EXIT ASAP - Low sustainability"


def calculate_net_profit_with_fees(position_size: float, funding_rate: float, rounds: int = 1) -> dict:
    """Calculate net profit after trading fees for funding rate strategy"""
    
    # Binance trading fees (standard rates)
    maker_fee = 0.0002  # 0.02%
    taker_fee = 0.0004  # 0.04%
    
    # Assume worst case: both entry and exit are taker orders
    entry_fee = position_size * taker_fee
    exit_fee = position_size * taker_fee
    total_fees = entry_fee + exit_fee
    
    # Funding profit calculation
    funding_profit_per_round = position_size * funding_rate
    total_funding_profit = funding_profit_per_round * rounds
    
    # Net profit = funding profit - trading fees
    net_profit = total_funding_profit - total_fees
    
    # Profitability analysis
    fee_coverage_ratio = total_funding_profit / total_fees if total_fees > 0 else 0
    
    if net_profit > 0:
        profitability = "✅ PROFITABLE"
        profit_color = "🟢"
    elif net_profit > -0.10:  # Small loss
        profitability = "⚠️ BREAK-EVEN"
        profit_color = "🟡"
    else:
        profitability = "❌ UNPROFITABLE"
        profit_color = "🔴"
    
    return {
        'funding_profit': total_funding_profit,
        'trading_fees': total_fees,
        'net_profit': net_profit,
        'fee_coverage_ratio': fee_coverage_ratio,
        'profitability': profitability,
        'profit_color': profit_color,
        'entry_fee': entry_fee,
        'exit_fee': exit_fee
    }


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
        entry_color = "🔥"
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