from src.binance.binance_funding import BinanceFunding

def get_volume(symbol, interval="1h", limit=1):
    """
    Fetch the latest volume for a symbol from Binance Futures klines.
    Returns the volume as float, or None on error.
    """
    try:
        with BinanceFunding() as client:
            klines = client.get_klines(symbol, interval=interval, limit=limit)
            if not klines or not klines[-1]:
                return None
            # Binance kline: [open, high, low, close, volume, ...]
            volume = float(klines[-1][5])
            return volume
    except Exception:
        return None
