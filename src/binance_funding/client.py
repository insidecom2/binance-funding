from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(slots=True)
class BinanceFundingClient:
    """Light wrapper around Binance Futures funding endpoints."""

    base_url: str = "https://fapi.binance.com"
    spot_base_url: str = "https://api.binance.com"
    timeout: float = 10.0

    def get_funding_rates(self, symbol: str, limit: int = 10, api_key: str | None = None) -> list[dict[str, Any]]:
        """Fetch funding rate records for a futures symbol."""
        params = {"symbol": symbol.upper(), "limit": limit}
        headers = {"X-MBX-APIKEY": api_key} if api_key else {}
        response = requests.get(
            f"{self.base_url}/fapi/v1/fundingRate",
            headers=headers,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected API response format")
        return data

    def get_current_price(self, symbol: str) -> float:
        """Get current spot price for a symbol."""
        params = {"symbol": symbol.upper()}
        response = requests.get(
            f"{self.spot_base_url}/api/v3/ticker/price",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return float(data["price"])
