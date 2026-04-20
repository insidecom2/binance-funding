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
    SPOT_BASE_URL = "https://api.binance.com"

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
        self.api_key = os.getenv("BINANCE_API_KEY", "").strip()
        self.secret_key = os.getenv("BINANCE_SECRET_KEY", "").strip()
        self.recv_window = int(os.getenv("BINANCE_RECV_WINDOW", "5000"))
        self.exchange_info_ttl_seconds = int(os.getenv("BINANCE_EXCHANGE_INFO_TTL", "300"))
        self._exchange_info_cache: Dict[str, Dict[str, Any]] = {}

    def _ensure_credentials(self) -> None:
        """Ensure API key and secret key are available for signed endpoints."""
        if not self.api_key or not self.secret_key:
            raise BinanceFundingError(
                "Missing Binance trading credentials. Set BINANCE_API_KEY and BINANCE_SECRET_KEY."
            )

    def _sign_request(self, params: Dict[str, Any]) -> str:
        """Create Binance HMAC SHA256 signature from request params."""
        encoded = urlencode(params, doseq=True)
        return hmac.new(
            self.secret_key.encode("utf-8"),
            encoded.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _raise_mapped_api_error(self, response: requests.Response) -> None:
        """Raise BinanceFundingError with mapped details from HTTP/API response."""
        status = response.status_code
        default_msg = response.text.strip() or "Unknown Binance API error"

        code = "HTTP_ERROR"
        message = default_msg
        try:
            payload = response.json()
            if isinstance(payload, dict):
                code = payload.get("code", code)
                message = payload.get("msg", message)
        except ValueError:
            pass

        hints = {
            400: "Bad request or invalid order parameters",
            401: "Unauthorized API key or signature",
            403: "Forbidden or restricted IP permissions",
            418: "IP auto-banned due to rate limit violations",
            429: "Rate limit exceeded",
        }
        hint = hints.get(status, "Binance API request failed")
        raise BinanceFundingError(f"{hint} (status={status}, code={code}): {message}")

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        *,
        signed: bool = False,
        use_spot: bool = False,
    ) -> Any:
        """Execute HTTP request with retries for both public and signed Binance endpoints."""
        method = method.upper()
        params = dict(params or {})
        base_url = self.SPOT_BASE_URL if use_spot else self.BASE_URL
        url = f"{base_url}{endpoint}"

        headers = {
            "User-Agent": "Binance-Funding-Client/1.0",
        }

        if signed:
            self._ensure_credentials()
            params["timestamp"] = int(time.time() * 1000)
            params.setdefault("recvWindow", self.recv_window)
            params["signature"] = self._sign_request(params)
            headers["X-MBX-APIKEY"] = self.api_key

        for attempt in range(self.retries):
            try:
                logger.info(f"Requesting {url} (attempt {attempt + 1})")

                request_args: Dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "timeout": self.timeout,
                    "headers": headers,
                }
                if method == "GET":
                    request_args["params"] = params
                else:
                    request_args["data"] = params

                response = self.session.request(**request_args)

                if response.status_code >= 400:
                    if response.status_code in {418, 429, 500, 502, 503, 504} and attempt < self.retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(
                            "HTTP %s from %s (attempt %s). Retrying in %ss",
                            response.status_code,
                            endpoint,
                            attempt + 1,
                            wait_time,
                        )
                        time.sleep(wait_time)
                        continue
                    self._raise_mapped_api_error(response)

                data = response.json()
                logger.info(f"Successfully fetched data from {endpoint}")
                return data

            except requests.exceptions.Timeout as e:
                if attempt == self.retries - 1:
                    raise BinanceFundingError(f"Request timeout after {self.retries} attempts: {str(e)}")
                wait_time = 2 ** attempt
                logger.warning("Timeout on %s (attempt %s). Retrying in %ss", endpoint, attempt + 1, wait_time)
                time.sleep(wait_time)
            except requests.exceptions.ConnectionError as e:
                if attempt == self.retries - 1:
                    raise BinanceFundingError(f"Connection error after {self.retries} attempts: {str(e)}")
                wait_time = 2 ** attempt
                logger.warning("Connection error on %s (attempt %s). Retrying in %ss", endpoint, attempt + 1, wait_time)
                time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                if attempt == self.retries - 1:
                    raise BinanceFundingError(f"Failed to fetch data after {self.retries} attempts: {str(e)}")
                wait_time = 2 ** attempt
                logger.warning("Request failed on %s (attempt %s). Retrying in %ss", endpoint, attempt + 1, wait_time)
                time.sleep(wait_time)
            except ValueError as e:
                raise BinanceFundingError(f"Invalid JSON response from Binance API: {str(e)}")
        
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
        return self._request(endpoint=endpoint, method="GET", params=params, signed=False, use_spot=False)

    def _make_authenticated_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        *,
        use_spot: bool = False,
    ) -> Any:
        """Make signed request to Binance API with API key header and signature."""
        return self._request(endpoint=endpoint, method=method, params=params, signed=True, use_spot=use_spot)

    def place_futures_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        reduce_only: bool = False,
        time_in_force: str = "GTC",
        **extra_params: Any,
    ) -> Dict[str, Any]:
        """Create a futures order on Binance USD-M futures."""
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if params["type"] == "LIMIT":
            if price is None:
                raise BinanceFundingError("price is required for LIMIT futures orders")
            params["price"] = price
            params["timeInForce"] = time_in_force
        if reduce_only:
            params["reduceOnly"] = "true"

        params.update(extra_params)
        return self._make_authenticated_request("/fapi/v1/order", method="POST", params=params, use_spot=False)

    def place_spot_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        **extra_params: Any,
    ) -> Dict[str, Any]:
        """Create a spot order on Binance spot market."""
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if params["type"] == "LIMIT":
            if price is None:
                raise BinanceFundingError("price is required for LIMIT spot orders")
            params["price"] = price
            params["timeInForce"] = time_in_force

        params.update(extra_params)
        return self._make_authenticated_request("/api/v3/order", method="POST", params=params, use_spot=True)

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        *,
        is_futures: bool = True,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an order by order ID or client order ID in futures or spot market."""
        if not order_id and not orig_client_order_id:
            raise BinanceFundingError("Either order_id or orig_client_order_id is required for cancellation")

        params: Dict[str, Any] = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        endpoint = "/fapi/v1/order" if is_futures else "/api/v3/order"
        return self._make_authenticated_request(endpoint, method="DELETE", params=params, use_spot=not is_futures)

    def get_order(
        self,
        symbol: str,
        *,
        order_id: Optional[str] = None,
        is_futures: bool = True,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query a futures or spot order."""
        if not order_id and not orig_client_order_id:
            raise BinanceFundingError("Either order_id or orig_client_order_id is required for order query")

        params: Dict[str, Any] = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        endpoint = "/fapi/v1/order" if is_futures else "/api/v3/order"
        return self._make_authenticated_request(endpoint, method="GET", params=params, use_spot=not is_futures)

    def get_account_balance(self, *, is_futures: bool = True, asset: Optional[str] = None) -> Any:
        """Get account balances for futures or spot account."""
        if is_futures:
            balances = self._make_authenticated_request("/fapi/v2/balance", method="GET", params={}, use_spot=False)
            if asset:
                asset = asset.upper()
                return [b for b in balances if str(b.get("asset", "")).upper() == asset]
            return balances

        account = self._make_authenticated_request("/api/v3/account", method="GET", params={}, use_spot=True)
        if asset:
            asset = asset.upper()
            balances = account.get("balances", [])
            return [b for b in balances if str(b.get("asset", "")).upper() == asset]
        return account

    def get_exchange_info(self, *, is_futures: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """Get exchange metadata (symbol filters, precision rules) for futures or spot."""
        cache_key = "futures" if is_futures else "spot"
        now = time.time()

        if not force_refresh:
            cached = self._exchange_info_cache.get(cache_key)
            if cached and (now - cached.get("updated_at", 0)) < self.exchange_info_ttl_seconds:
                return cached["payload"]

        endpoint = "/fapi/v1/exchangeInfo" if is_futures else "/api/v3/exchangeInfo"
        payload = self._request(endpoint=endpoint, method="GET", params={}, signed=False, use_spot=not is_futures)
        self._exchange_info_cache[cache_key] = {
            "payload": payload,
            "updated_at": now,
        }
        return payload

    def get_symbol_filters(self, symbol: str, *, is_futures: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """Return normalized sizing filters for a symbol from exchange info."""
        symbol = symbol.upper()
        exchange_info = self.get_exchange_info(is_futures=is_futures, force_refresh=force_refresh)
        symbols = exchange_info.get("symbols", []) if isinstance(exchange_info, dict) else []

        symbol_info = None
        for item in symbols:
            if str(item.get("symbol", "")).upper() == symbol:
                symbol_info = item
                break

        if not symbol_info:
            market_name = "futures" if is_futures else "spot"
            raise BinanceFundingError(f"Symbol {symbol} not found in {market_name} exchange info")

        filters_by_type = {
            f.get("filterType"): f
            for f in symbol_info.get("filters", [])
            if isinstance(f, dict) and f.get("filterType")
        }

        lot_size = filters_by_type.get("LOT_SIZE", {})
        market_lot_size = filters_by_type.get("MARKET_LOT_SIZE", {})
        price_filter = filters_by_type.get("PRICE_FILTER", {})
        notional_filter = filters_by_type.get("NOTIONAL") or filters_by_type.get("MIN_NOTIONAL") or {}

        min_notional = notional_filter.get("minNotional")
        if min_notional is None:
            min_notional = notional_filter.get("notional")

        return {
            "symbol": symbol,
            "market": "futures" if is_futures else "spot",
            "step_size": lot_size.get("stepSize"),
            "market_step_size": market_lot_size.get("stepSize") or lot_size.get("stepSize"),
            "tick_size": price_filter.get("tickSize"),
            "min_qty": lot_size.get("minQty"),
            "market_min_qty": market_lot_size.get("minQty") or lot_size.get("minQty"),
            "min_notional": min_notional,
            "max_qty": lot_size.get("maxQty"),
            "max_price": price_filter.get("maxPrice"),
            "min_price": price_filter.get("minPrice"),
            "raw": symbol_info,
        }

    def get_position_info(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get futures position information, optionally filtered by symbol."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol.upper()

        positions = self._make_authenticated_request("/fapi/v2/positionRisk", method="GET", params=params, use_spot=False)
        if symbol and isinstance(positions, list):
            symbol = symbol.upper()
            return [p for p in positions if str(p.get("symbol", "")).upper() == symbol]
        return positions if isinstance(positions, list) else [positions]
    
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
    
    def get_trading_symbols(self) -> set:
        """Return set of USDT-margined perpetual futures symbols that are currently TRADING."""
        data = self._make_request("/fapi/v1/exchangeInfo", {})
        symbols = set()
        for s in data.get("symbols", []):
            if (
                s.get("status") == "TRADING"
                and s.get("contractType") == "PERPETUAL"
                and str(s.get("symbol", "")).endswith("USDT")
            ):
                symbols.add(s["symbol"])
        return symbols

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