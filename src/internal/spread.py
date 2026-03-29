from src.binance.binance_funding import BinanceFunding

def get_spread(symbol):
    """
    Fetch mark price and index price for a symbol and calculate spread.
    Spread = abs(mark_price - index_price) / index_price
    Returns spread as a float (proportion).
    """
    with BinanceFunding() as client:
        premium_data = client.get_premium_index(symbol)
        if not premium_data or not isinstance(premium_data, list) or not premium_data[0]:
            return None
        mark_price = float(premium_data[0]['markPrice'])
        index_price = float(premium_data[0]['indexPrice'])
        spread = abs(mark_price - index_price) / index_price if index_price != 0 else None
        return spread
