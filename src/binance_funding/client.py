from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(slots=True)
class BinanceFundingClient:
    """Light wrapper around Binance Futures funding endpoints."""

    base_url: str = "https://fapi.binance.com"
    timeout: float = 10.0

    def get_funding_rates(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch funding rate records for a futures symbol."""
        params = {"symbol": symbol.upper(), "limit": limit}
        response = requests.get(
            f"{self.base_url}/fapi/v1/fundingRate",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected API response format")
        return data
