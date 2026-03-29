def select_best_opportunity(opportunities, min_basis=0.001, min_funding=0.0005, min_volume=1_000_000, max_spread=0.002, max_rounds=5):
    """
    เลือกเหรียญที่ผ่านทุกเงื่อนไข โดยหาจำนวนรอบสูงสุดที่ net_profit > 0 และ risk ต่ำสุด
    Return dict: symbol, risk, basis, funding_rate, volume, spread, net_profit, best_rounds, mark_price, index_price
    """
    best = None
    for opp in opportunities:
        symbol = opp['symbol']
        funding_rate = opp['max_rate']['value']
        risk_info = predict_xgb_risk(symbol, funding_rate, opp['max_rate'].get('mark_price', 0), opp['opportunity_score']['overall_score'])
        risk = risk_info['score']
        basis, mark_price, index_price = get_basis_from_binance(symbol)
        if basis is None or basis < min_basis:
            continue
        volume = get_volume(symbol)
        if volume is None or volume < min_volume:
            continue
        spread = get_spread(symbol)
        if spread is None or spread > max_spread:
            continue
        # หารอบสูงสุดที่ net_profit > 0
        best_net_profit = None
        best_rounds = 0
        for rounds in range(1, max_rounds+1):
            net_profit_info = calculate_net_profit_with_fees(mark_price, funding_rate, rounds)
            net_profit = net_profit_info['net_profit'] if isinstance(net_profit_info, dict) and 'net_profit' in net_profit_info else None
            if net_profit is not None and net_profit > 0:
                best_net_profit = net_profit
                best_rounds = rounds
            else:
                break
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
        if best is None or candidate['best_rounds'] > best['best_rounds'] or (candidate['best_rounds'] == best['best_rounds'] and candidate['risk'] < best['risk']):
            best = candidate
    return best
from src.internal.basis import get_basis_from_binance
from src.internal.volume import get_volume
from src.internal.spread import get_spread
from src.xgb import predict_xgb_risk, calculate_net_profit_with_fees


def filter_opportunities(opportunities, min_basis=0.001, min_funding=0.0005, min_volume=1_000_000, max_spread=0.002):
    """
    Filter and rank opportunities by:
    - risk ต่ำ (lowest risk)
    - basis > min_basis (default 0.10%)
    - funding rate > min_funding
    - volume > min_volume
    - spread < max_spread
    - กำไรสุทธิหลังหักค่าธรรมเนียมสูงสุด
    Returns a sorted list of dicts with extra info for each symbol.
    """
    filtered = []
    max_rounds = 5
    pass_count_by_round = {r: 0 for r in range(1, max_rounds+1)}
    for opp in opportunities:
        symbol = opp['symbol']
        funding_rate = opp['max_rate']['value']
        # Risk prediction (lower is better)
        risk_info = predict_xgb_risk(symbol, funding_rate, opp['max_rate'].get('mark_price', 0), opp['opportunity_score']['overall_score'])
        risk = risk_info['score']
        # Basis
        basis, mark_price, index_price = get_basis_from_binance(symbol)
        if basis is None or basis < min_basis:
            continue
        # Volume
        volume = get_volume(symbol)
        if volume is None or volume < min_volume:
            continue
        # Spread
        spread = get_spread(symbol)
        if spread is None or spread > max_spread:
            continue
        # Count how many rounds (1..max_rounds) would pass all filters (ignore net_profit sign)
        for rounds in range(1, max_rounds+1):
            net_profit_info = calculate_net_profit_with_fees(mark_price, funding_rate, rounds)
            net_profit = net_profit_info['net_profit'] if isinstance(net_profit_info, dict) and 'net_profit' in net_profit_info else None
            pass_count_by_round[rounds] += 1
        # Still only append the 1-round result for main filter
        net_profit_info = calculate_net_profit_with_fees(mark_price, funding_rate, 1)
        net_profit = net_profit_info['net_profit'] if isinstance(net_profit_info, dict) and 'net_profit' in net_profit_info else None
        if net_profit is None or net_profit < 0:
            print(f"[FILTER] {symbol} ตกรอบ net_profit: {net_profit}")
            continue
        filtered.append({
            'symbol': symbol,
            'risk': risk,
            'basis': basis,
            'funding_rate': funding_rate,
            'volume': volume,
            'spread': spread,
            'net_profit': net_profit,
            'mark_price': mark_price,
            'index_price': index_price,
        })
    # Sort by: risk (asc), net_profit (desc)
    filtered.sort(key=lambda x: (x['risk'], -x['net_profit']))
    for r in range(1, max_rounds+1):
        print(f"  รอบที่ {r}: {pass_count_by_round[r]} symbols")
    return filtered
