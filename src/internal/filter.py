from datetime import datetime

from src.internal.basis import get_basis_from_binance
from src.internal.volume import get_volume
from src.internal.spread import get_spread
from src.xgb import predict_xgb_risk, calculate_net_profit_with_fees


def _normalize_risk_score(risk_score):
    """Normalize risk score to 0..1 for threshold comparison."""
    if risk_score is None:
        return None
    return risk_score / 100.0 if risk_score > 1 else risk_score


def select_best_opportunity(filtered):
    """
    คืน opportunity ที่ดีที่สุดจาก filtered list ที่ผ่าน filter_opportunities แล้ว
    (sorted by net_profit desc, risk asc อยู่แล้ว — คืนตัวแรกเลย)
    """
    return filtered[0] if filtered else None


def analyze_opportunities(
    opportunities,
    min_basis=0.0002,
    min_funding=0.0007,
    min_volume=500_000,
    max_spread=0.002,
    max_risk=0.5,
    max_rounds=10,
    position_size=1000,
    require_forecast=False,
):
    """
    Filter and rank opportunities for short-futures + long-spot funding harvest.

    Gates (in order):
      1. funding_rate  >= min_funding
      2. forecast      confidence_pass + forecast_pass  (if require_forecast)
      3. risk score    <= max_risk
      4. basis         >= min_basis  (futures premium over spot)
      5. volume        >= min_volume
      6. spread        <= max_spread
      7. net_profit    >= 0  (after fees + spread cost, best of max_rounds)

    next_funding_time ถูก log ไว้ใน candidate แต่ไม่ใช้เป็น hard gate —
    ควรเช็คที่ execution layer แทน เพื่อให้ scanner หาโอกาสได้ตลอดเวลา

    Returns a dict with filtered candidates and reject counts.
    """
    filtered = []
    reject_counts = {
        'funding': 0,
        'forecast': 0,
        'risk': 0,
        'basis': 0,
        'volume': 0,
        'spread': 0,
        'net_profit': 0,
    }

    for opp in opportunities:
        symbol = opp['symbol']
        funding_rate = opp['max_rate']['value']

        # 1. Funding rate floor
        if funding_rate < min_funding:
            reject_counts['funding'] += 1
            continue

        # 2. Forecast gate (optional)
        if require_forecast:
            forecast = opp.get('funding_forecast')
            if not forecast or not forecast.get('is_valid') or not forecast.get('confidence_pass') or not forecast.get('forecast_pass'):
                reject_counts['forecast'] += 1
                continue

        # 3. Risk prediction (lower is better)
        risk_info = predict_xgb_risk(symbol, funding_rate, opp['max_rate'].get('mark_price', 0), opp['opportunity_score']['overall_score'])
        risk = risk_info['score']
        normalized_risk = _normalize_risk_score(risk)
        if normalized_risk is None or normalized_risk > max_risk:
            reject_counts['risk'] += 1
            continue

        # 4. Basis (futures premium over spot)
        basis, mark_price, index_price = get_basis_from_binance(symbol)
        if basis is None or basis < min_basis:
            reject_counts['basis'] += 1
            continue

        # 5. Volume
        volume = get_volume(symbol)
        if volume is None or volume < min_volume:
            reject_counts['volume'] += 1
            continue

        # 6. Spread
        spread = get_spread(symbol)
        if spread is None or spread > max_spread:
            reject_counts['spread'] += 1
            continue

        # 7. Net profit — includes spread cost + spot fee
        best_net_profit = None
        best_rounds = 0
        for rounds in range(1, max_rounds + 1):
            net_profit_info = calculate_net_profit_with_fees(position_size, funding_rate, rounds, spread=spread)
            net_profit = net_profit_info['net_profit'] if isinstance(net_profit_info, dict) and 'net_profit' in net_profit_info else None
            if net_profit is not None and net_profit >= 0 and (best_net_profit is None or net_profit > best_net_profit):
                best_net_profit = net_profit
                best_rounds = rounds

        if best_rounds == 0:
            reject_counts['net_profit'] += 1
            continue

        next_funding_ms = opp.get('next_funding_time')
        now_ms = int(datetime.now().timestamp() * 1000)
        minutes_to_funding = round((next_funding_ms - now_ms) / 60000, 1) if next_funding_ms else None

        candidate = {
            'symbol': symbol,
            'risk': risk,
            'basis': basis,
            'funding_rate': funding_rate,
            'volume': volume,
            'spread': spread,
            'net_profit': best_net_profit,
            'best_rounds': best_rounds,
            'mark_price': mark_price,
            'index_price': index_price,
            'funding_forecast': opp.get('funding_forecast'),
            'next_funding_time': next_funding_ms,
            'minutes_to_funding': minutes_to_funding,
        }
        filtered.append(candidate)

    # Sort by: net_profit (desc), risk (asc), then quality tie-breakers.
    filtered.sort(
        key=lambda x: (
            -x['net_profit'],
            x['risk'],
            -x['funding_rate'],
            -x['basis'],
            -x['volume'],
            x['spread'],
        )
    )

    print("[FILTER] Reject summary:", reject_counts)
    return {
        "filtered": filtered,
        "reject_counts": reject_counts,
    }


def filter_opportunities(
    opportunities,
    min_basis=0.0002,
    min_funding=0.0007,
    min_volume=500_000,
    max_spread=0.002,
    max_risk=0.5,
    max_rounds=10,
    position_size=1000,
    require_forecast=False,
):
    analysis = analyze_opportunities(
        opportunities,
        min_basis=min_basis,
        min_funding=min_funding,
        min_volume=min_volume,
        max_spread=max_spread,
        max_risk=max_risk,
        max_rounds=max_rounds,
        position_size=position_size,
        require_forecast=require_forecast,
    )
    return analysis["filtered"]
