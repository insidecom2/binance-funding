"""Binance API Module"""
from .binance_funding import BinanceFunding, BinanceFundingError, get_btc_funding, get_btc_premium, get_max_funding_in_range
from .trading_bot import FundingBot, get_best_funding_opportunity, auto_get_max_funding

__all__ = [
    'BinanceFunding', 'BinanceFundingError', 'get_btc_funding', 'get_btc_premium', 
    'get_max_funding_in_range', 'FundingBot', 'get_best_funding_opportunity', 'auto_get_max_funding'
]