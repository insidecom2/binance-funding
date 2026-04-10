"""
Binance Funding Data Module
============================

This module provides functionality to fetch funding rate and premium index data 
from Binance Futures API endpoints.

API Endpoints:
- Funding Rate: https://fapi.binance.com/fapi/v1/fundingRate
- Premium Index: https://fapi.binance.com/fapi/v1/premiumIndex

Example:
    from src.binance_funding import BinanceFunding
    
    client = BinanceFunding()
    funding_data = client.get_funding_rate("BTCUSDT", limit=10)
    premium_data = client.get_premium_index("BTCUSDT")
"""

import requests
import time
from typing import Optional, Dict, Any, List
import logging
import hmac
import hashlib
from urllib.parse import urlencode
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BinanceFundingError(Exception):
    """Custom exception for Binance API errors"""
    pass


class BinanceFunding:

    BASE_URL = "https://fapi.binance.com"

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100, start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        """
        Get historical candlestick (kline) data from Binance Futures API
        Args:
            symbol (str): Trading symbol (e.g., "BTCUSDT")
            interval (str): Kline interval (e.g., "1m", "5m", "1h", "1d")
            limit (int): Number of records to return (default: 100, max: 1500)
            start_time (int, optional): Start timestamp in milliseconds
            end_time (int, optional): End timestamp in milliseconds
        Returns:
            list: List of kline data (open, high, low, close, volume, ...)
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': min(limit, 1500)
        }
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        logger.info(f"Fetching klines for {symbol} interval={interval} limit={limit}")
        data = self._make_request("/fapi/v1/klines", params)
        return data
    
    def __init__(self, timeout: int = 30, retries: int = 3):
        """
        Initialize BinanceFunding client
        
        Args:
            timeout (int): Request timeout in seconds (default: 30)
            retries (int): Number of retry attempts for failed requests (default: 3)
        """
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request to Binance API with retry logic
        
        Args:
            endpoint (str): API endpoint path
            params (Dict): Query parameters
            
        Returns:
            Dict: JSON response from API
            
        Raises:
            BinanceFundingError: If request fails after all retries
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self.retries):
            try:
                logger.info(f"Requesting {url} (attempt {attempt + 1})")
                
                response = self.session.get(
                    url, 
                    params=params, 
                    timeout=self.timeout,
                    headers={
                        'User-Agent': 'Binance-Funding-Client/1.0'
                    }
                )
                
                # Check if request was successful
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Successfully fetched data from {endpoint}")
                return data
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {str(e)}")
                
                if attempt == self.retries - 1:  # Last attempt
                    raise BinanceFundingError(f"Failed to fetch data after {self.retries} attempts: {str(e)}")
                
                # Wait before retry (exponential backoff)
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
    
    def get_funding_rate(self, symbol: str, start_time: Optional[int] = None, 
                        end_time: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get funding rate history for a symbol
        
        Args:
            symbol (str): Trading symbol (e.g., "BTCUSDT")
            start_time (int, optional): Start timestamp in milliseconds
            end_time (int, optional): End timestamp in milliseconds  
            limit (int): Number of records to return (default: 100, max: 1000)
            
        Returns:
            List[Dict]: List of funding rate records
            
        Example:
            >>> client = BinanceFunding()
            >>> data = client.get_funding_rate("BTCUSDT", limit=10)
            >>> print(data[0])
            {
                'symbol': 'BTCUSDT', 
                'fundingTime': 1640995200000, 
                'fundingRate': '0.00010000',
                'markPrice': '46929.41293813'
            }
        """
        params = {
            'symbol': symbol,
            'limit': min(limit, 1000)  # API limit is 1000
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
            
        logger.info(f"Fetching funding rate for {symbol} (limit: {limit})")
        return self._make_request("/fapi/v1/fundingRate", params)
    
    def get_premium_index(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get mark price and funding rate for symbol(s)
        
        Args:
            symbol (str, optional): Trading symbol (e.g., "BTCUSDT"). 
                                   If None, returns data for all symbols.
            
        Returns:
            List[Dict]: List of premium index data
            
        Example:
            >>> client = BinanceFunding()
            >>> data = client.get_premium_index("BTCUSDT")
            >>> print(data[0])
            {
                'symbol': 'BTCUSDT',
                'markPrice': '46929.41293813',
                'indexPrice': '46956.80977356', 
                'estimatedSettlePrice': '46929.41293813',
                'lastFundingRate': '0.00010000',
                'nextFundingTime': 1640995200000,
                'interestRate': '0.00010000',
                'time': 1640991693453
            }
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
            
        logger.info(f"Fetching premium index for {'all symbols' if not symbol else symbol}")
        data = self._make_request("/fapi/v1/premiumIndex", params)
        
        # If single symbol requested, API returns single object, convert to list
        if symbol and isinstance(data, dict):
            return [data]
        
        return data if isinstance(data, list) else [data]
    
    def get_funding_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get comprehensive funding information for a symbol
        
        Args:
            symbol (str): Trading symbol (e.g., "BTCUSDT")
            
        Returns:
            Dict: Combined funding rate and premium index data
        """
        logger.info(f"Fetching comprehensive funding info for {symbol}")
        
        # Fetch both funding rate and premium index data
        funding_rates = self.get_funding_rate(symbol, limit=1)
        premium_data = self.get_premium_index(symbol)
        
        result = {
            'symbol': symbol,
            'timestamp': int(time.time() * 1000),
            'latest_funding_rate': funding_rates[0] if funding_rates else None,
            'premium_index': premium_data[0] if premium_data else None
        }
        
        return result
    
    def get_max_funding_rate_in_range(self, symbol: str, min_rate: float = -0.008, 
                                     max_rate: float = 0.004, limit: int = 1000) -> Dict[str, Any]:
        """
        Get maximum funding rate within a specific range
        
        Args:
            symbol (str): Trading symbol (e.g., "BTCUSDT")
            min_rate (float): Minimum funding rate threshold (default: -0.008)
            max_rate (float): Maximum funding rate threshold (default: 0.004)
            limit (int): Number of historical records to analyze (default: 1000)
            
        Returns:
            Dict: Analysis of funding rates within the specified range
            
        Example:
            >>> client = BinanceFunding()
            >>> result = client.get_max_funding_rate_in_range("BTCUSDT")
            >>> print(f"Max rate in range: {result['max_rate_in_range']}")
        """
        logger.info(f"Analyzing funding rates for {symbol} in range [{min_rate}, {max_rate}]")
        
        # Fetch historical funding rate data
        funding_data = self.get_funding_rate(symbol, limit=limit)
        
        if not funding_data:
            return {
                'symbol': symbol,
                'analysis_range': {'min': min_rate, 'max': max_rate},
                'total_records': 0,
                'records_in_range': 0,
                'max_rate_in_range': None,
                'min_rate_in_range': None,
                'avg_rate_in_range': None,
                'rates_in_range': []
            }
        
        # Filter rates within the specified range
        rates_in_range = []
        for record in funding_data:
            rate = float(record['fundingRate'])
            if min_rate <= rate <= max_rate:
                rates_in_range.append({
                    'fundingRate': rate,
                    'fundingTime': record['fundingTime'],
                    'markPrice': float(record['markPrice']),
                    'symbol': record['symbol']
                })
        
        # Calculate statistics
        if rates_in_range:
            funding_rates = [r['fundingRate'] for r in rates_in_range]
            max_rate_found = max(funding_rates)
            min_rate_found = min(funding_rates)
            avg_rate = sum(funding_rates) / len(funding_rates)
            
            # Find the record with maximum rate
            max_rate_record = next(r for r in rates_in_range if r['fundingRate'] == max_rate_found)
        else:
            max_rate_found = min_rate_found = avg_rate = None
            max_rate_record = None
        
        result = {
            'symbol': symbol,
            'analysis_range': {'min': min_rate, 'max': max_rate},
            'total_records': len(funding_data),
            'records_in_range': len(rates_in_range),
            'max_rate_in_range': max_rate_found,
            'min_rate_in_range': min_rate_found,
            'avg_rate_in_range': avg_rate,
            'max_rate_record': max_rate_record,
            'rates_in_range': rates_in_range,
            'percentage_in_range': (len(rates_in_range) / len(funding_data)) * 100 if funding_data else 0
        }
        
        logger.info(f"Found {len(rates_in_range)} records in range out of {len(funding_data)} total")
        return result
    
    def close(self):
        """Close the session"""
        self.session.close()
        logger.info("BinanceFunding session closed")
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience functions for quick access
def get_btc_funding(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Quick function to get BTC funding rate data
    
    Args:
        limit (int): Number of records to return
        
    Returns:
        List[Dict]: BTC funding rate data
    """
    with BinanceFunding() as client:
        return client.get_funding_rate("BTCUSDT", limit=limit)


def get_btc_premium() -> List[Dict[str, Any]]:
    """
    Quick function to get BTC premium index data
    
    Returns:
        List[Dict]: BTC premium index data
    """
    with BinanceFunding() as client:
        return client.get_premium_index("BTCUSDT")


def get_max_funding_in_range(symbol: str = "BTCUSDT", min_rate: float = -0.008, 
                           max_rate: float = 0.004, limit: int = 1000) -> Dict[str, Any]:
    """
    Quick function to get maximum funding rate within specified range
    
    Args:
        symbol (str): Trading symbol (default: "BTCUSDT")
        min_rate (float): Minimum funding rate threshold (default: -0.008)
        max_rate (float): Maximum funding rate threshold (default: 0.004)  
        limit (int): Number of records to analyze (default: 1000)
        
    Returns:
        Dict: Analysis of funding rates within the specified range
    """
    with BinanceFunding() as client:
        return client.get_max_funding_rate_in_range(symbol, min_rate, max_rate, limit)


if __name__ == "__main__":
    # Example usage
    print("Binance Funding Data Module")
    print("=" * 30)
    
    try:
        with BinanceFunding() as client:
            # Test funding rate
            print("\n🔸 Testing Funding Rate API:")
            funding_data = client.get_funding_rate("BTCUSDT", limit=3)
            for item in funding_data:
                print(f"  Time: {item['fundingTime']}, Rate: {item['fundingRate']}")
            
            # Test premium index  
            print("\n🔸 Testing Premium Index API:")
            premium_data = client.get_premium_index("BTCUSDT")
            if premium_data:
                item = premium_data[0]
                print(f"  Mark Price: {item['markPrice']}")
                print(f"  Index Price: {item['indexPrice']}")
                print(f"  Next Funding Rate: {item['lastFundingRate']}")
            
            # Test comprehensive info
            print("\n🔸 Testing Comprehensive Info:")
            info = client.get_funding_info("BTCUSDT")
            print(f"  Symbol: {info['symbol']}")
            print(f"  Timestamp: {info['timestamp']}")
            
    except BinanceFundingError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")