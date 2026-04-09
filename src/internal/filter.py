from src.internal.basis import get_basis_from_binance
from src.internal.volume import get_volume
from src.internal.spread import get_spread
from src.xgb import predict_xgb_risk, calculate_net_profit_with_fees


def _normalize_risk_score(risk_score):
    """Normalize risk score to 0..1 for threshold comparison."""
    if risk_score is None:
        return None
    return risk_score / 100.0 if risk_score > 1 else risk_score


def select_best_opportunity(
    opportunities,
    min_basis=0.0005,
    min_funding=0.0002,
    min_volume=500_000,
    max_spread=0.004,
    max_risk=0.5,
    max_rounds=5,
    position_size=1000,
):
    """
    เลือกเหรียญที่ผ่านทุกเงื่อนไข โดยเน้นกำไรสุทธิสูงสุดก่อน และใช้ risk ต่ำสุดเป็นตัวตัดสินรอง
    Return dict: symbol, risk, basis, funding_rate, volume, spread, net_profit, best_rounds, mark_price, index_price
    """
    best = None
    for opp in opportunities:
        symbol = opp['symbol']
        funding_rate = opp['max_rate']['value']
        if funding_rate < min_funding:
            continue
        risk_info = predict_xgb_risk(symbol, funding_rate, opp['max_rate'].get('mark_price', 0), opp['opportunity_score']['overall_score'])
        risk = risk_info['score']
        normalized_risk = _normalize_risk_score(risk)
        if normalized_risk is None or normalized_risk > max_risk:
            continue
        basis, mark_price, index_price = get_basis_from_binance(symbol)
        if basis is None or basis < min_basis:
            continue
        volume = get_volume(symbol)
        if volume is None or volume < min_volume:
            continue
        spread = get_spread(symbol)
        if spread is None or spread > max_spread:
            continue
        # หารอบที่ทำกำไรสุทธิสูงสุด (รองรับกรณีรอบ 1 ติดลบแต่รอบถัดไปกลับมาบวก)
        best_net_profit = None
        best_rounds = 0
        for rounds in range(1, max_rounds+1):
            net_profit_info = calculate_net_profit_with_fees(position_size, funding_rate, rounds)
            net_profit = net_profit_info['net_profit'] if isinstance(net_profit_info, dict) and 'net_profit' in net_profit_info else None
            if net_profit is not None and net_profit >= 0 and (best_net_profit is None or net_profit > best_net_profit):
                best_net_profit = net_profit
                best_rounds = rounds
        if best_rounds == 0:
            continue
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
        }
        if (
            best is None
            or candidate['net_profit'] > best['net_profit']
            or (
                candidate['net_profit'] == best['net_profit']
                and candidate['risk'] < best['risk']
            )
            or (
                candidate['net_profit'] == best['net_profit']
                and candidate['risk'] == best['risk']
                and candidate['best_rounds'] > best['best_rounds']
            )
        ):
            best = candidate
    return best


def filter_opportunities(
    opportunities,
    min_basis=0.0005,
    min_funding=0.0002,
    min_volume=500_000,
    max_spread=0.004,
    max_risk=0.5,
    max_rounds=5,
    position_size=1000,
):
    """
    Filter and rank opportunities by:
    - risk ต่ำ (<= max_risk)
    - basis > min_basis (default 0.05%)
    - funding rate > min_funding
    - volume > min_volume
    - spread < max_spread
    - กำไรสุทธิหลังหักค่าธรรมเนียมสูงสุด
    Returns a sorted list of dicts with extra info for each symbol.
    """
    filtered = []
    pass_count_by_round = {r: 0 for r in range(1, max_rounds+1)}
    reject_counts = {
        'funding': 0,
        'risk': 0,
        'basis': 0,
        'volume': 0,
        'spread': 0,
        'net_profit': 0,
    }

    for opp in opportunities:
        symbol = opp['symbol']
        funding_rate = opp['max_rate']['value']
        if funding_rate < min_funding:
            reject_counts['funding'] += 1
            continue

        # Risk prediction (lower is better)
        risk_info = predict_xgb_risk(symbol, funding_rate, opp['max_rate'].get('mark_price', 0), opp['opportunity_score']['overall_score'])
        risk = risk_info['score']
        normalized_risk = _normalize_risk_score(risk)
        if normalized_risk is None or normalized_risk > max_risk:
            reject_counts['risk'] += 1
            continue

        # Basis
        basis, mark_price, index_price = get_basis_from_binance(symbol)
        if basis is None or basis < min_basis:
            reject_counts['basis'] += 1
            continue

        # Volume
        volume = get_volume(symbol)
        if volume is None or volume < min_volume:
            reject_counts['volume'] += 1
            continue

        # Spread
        spread = get_spread(symbol)
        if spread is None or spread > max_spread:
            reject_counts['spread'] += 1
            continue

        # Count how many rounds (1..max_rounds) would remain profitable.
        for rounds in range(1, max_rounds+1):
            net_profit_info = calculate_net_profit_with_fees(position_size, funding_rate, rounds)
            net_profit = net_profit_info['net_profit'] if isinstance(net_profit_info, dict) and 'net_profit' in net_profit_info else None
            if net_profit is not None and net_profit > 0:
                pass_count_by_round[rounds] += 1

        # Accept if 1-round is profitable, else fallback to 2-round profitability.
        round_1_info = calculate_net_profit_with_fees(position_size, funding_rate, 1)
        round_1_net = round_1_info['net_profit'] if isinstance(round_1_info, dict) and 'net_profit' in round_1_info else None
        selected_rounds = 1
        selected_net_profit = round_1_net

        if round_1_net is None or round_1_net < 0:
            round_2_info = calculate_net_profit_with_fees(position_size, funding_rate, 2)
            round_2_net = round_2_info['net_profit'] if isinstance(round_2_info, dict) and 'net_profit' in round_2_info else None
            if round_2_net is not None and round_2_net >= 0:
                selected_rounds = 2
                selected_net_profit = round_2_net

        if selected_net_profit is None or selected_net_profit < 0:
            reject_counts['net_profit'] += 1
            print(f"[FILTER] {symbol} ตกรอบ net_profit: round1={round_1_net}")
            continue

        filtered.append({
            'symbol': symbol,
            'risk': risk,
            'basis': basis,
            'funding_rate': funding_rate,
            'volume': volume,
            'spread': spread,
            'net_profit': selected_net_profit,
            'selected_rounds': selected_rounds,
            'mark_price': mark_price,
            'index_price': index_price,
        })

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
    for r in range(1, max_rounds+1):
        print(f"  รอบที่ {r} (net_profit > 0): {pass_count_by_round[r]} symbols")
    return filtered
