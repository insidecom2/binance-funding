import pytest

from binance_funding.client import BinanceFundingClient


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_get_funding_rates_returns_list(monkeypatch):
    payload = [{"symbol": "BTCUSDT", "fundingRate": "0.0001"}]

    def fake_get(*args, **kwargs):
        return DummyResponse(payload)

    monkeypatch.setattr("binance_funding.client.requests.get", fake_get)

    client = BinanceFundingClient()
    result = client.get_funding_rates("btcusdt", '124567',limit=1)
    assert result == payload


def test_get_funding_rates_raises_for_invalid_payload(monkeypatch):
    def fake_get(*args, **kwargs):
        return DummyResponse({"bad": "payload"})

    monkeypatch.setattr("binance_funding.client.requests.get", fake_get)

    client = BinanceFundingClient()
    with pytest.raises(ValueError):
        client.get_funding_rates("BTCUSDT", '124567', limit=1)
