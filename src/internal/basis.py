from src.binance.binance_funding import BinanceFunding

def get_basis(symbol, mark_price, index_price):
    """
    Calculate basis for a symbol.
    Basis = (mark_price - index_price) / index_price
    Returns basis as a float (can be positive or negative).
    """
    if index_price == 0:
        return 0.0
    return (mark_price - index_price) / index_price


def get_basis_from_binance(symbol):
    """
    Fetch mark price and index price from Binance for a symbol and calculate basis.
    Returns (basis, mark_price, index_price)
    """
    with BinanceFunding() as client:
        premium_data = client.get_premium_index(symbol)
        if not premium_data or not isinstance(premium_data, list) or not premium_data[0]:
            return None, None, None
        mark_price = float(premium_data[0]['markPrice'])
        index_price = float(premium_data[0]['indexPrice'])
        basis = get_basis(symbol, mark_price, index_price)
        return basis, mark_price, index_price
