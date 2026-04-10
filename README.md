# Binance Funding Rate Fetcher 📊

A Python module for fetching Binance Futures funding rate and premium index data from the official Binance API.

## Features ✨

- **Funding Rate Data**: Get historical funding rates for any futures symbol
- **Premium Index**: Fetch real-time premium index and mark price data
- **Error Handling**: Robust error handling with retry logic and logging
- **Easy to Use**: Simple command-line interface and Python module
- **Context Manager**: Safe resource management with automatic cleanup

## API Endpoints 🔗

This tool uses the following Binance Futures API endpoints:

- **Funding Rate**: `https://fapi.binance.com/fapi/v1/fundingRate`
- **Premium Index**: `https://fapi.binance.com/fapi/v1/premiumIndex`

## Installation 🛠️

1. Clone or download this project
2. Run the setup script:

```bash
chmod +x run.sh
./run.sh --help
```

The script will automatically:

- Create a Python virtual environment
- Install required dependencies
- Run the application

## Usage 📖

### Command Line Interface

```bash
# Get last 10 funding rates for BTC (default)
./run.sh

# Get funding rates for specific symbol
./run.sh ETHUSDT --limit 5

# Get premium index data
./run.sh BTCUSDT --premium

# Get comprehensive funding information
./run.sh ADAUSDT --info

# Output raw JSON data
./run.sh BTCUSDT --json

# List popular symbols
./run.sh --list
```

### Python Module Usage

```python
from src.binance_funding import BinanceFunding

# Using context manager (recommended)
with BinanceFunding() as client:
    # Get funding rate history
    funding_data = client.get_funding_rate("BTCUSDT", limit=10)

    # Get premium index
    premium_data = client.get_premium_index("BTCUSDT")

    # Get comprehensive info
    info = client.get_funding_info("BTCUSDT")

# Quick convenience functions
from src.binance_funding import get_btc_funding, get_btc_premium

btc_funding = get_btc_funding(limit=5)
btc_premium = get_btc_premium()
```

## Examples 💡

### Funding Rate Data

```python
funding_rates = client.get_funding_rate("BTCUSDT", limit=3)
for rate in funding_rates:
    print(f"Time: {rate['fundingTime']}")
    print(f"Rate: {rate['fundingRate']}")
    print(f"Mark Price: {rate['markPrice']}")
```

### Premium Index Data

```python
premium = client.get_premium_index("ETHUSDT")[0]
print(f"Mark Price: ${float(premium['markPrice']):,.2f}")
print(f"Index Price: ${float(premium['indexPrice']):,.2f}")
print(f"Funding Rate: {float(premium['lastFundingRate']) * 100:.4f}%")
```

## Project Structure 📁

```
binance-funding/
├── cmd/
│   └── main.py          # CLI entry point
├── src/
│   ├── __init__.py      # Package initialization
│   └── binance_funding.py # Main module
├── requirements.txt     # Python dependencies
├── run.sh              # Setup and run script
└── README.md           # This file
```

## Configuration ⚙️

The `BinanceFunding` class accepts the following parameters:

- `timeout`: Request timeout in seconds (default: 30)
- `retries`: Number of retry attempts (default: 3)

```python
client = BinanceFunding(timeout=60, retries=5)
```

## Error Handling 🔧

The module includes comprehensive error handling:

- **Network errors**: Automatic retry with exponential backoff
- **API errors**: Clear error messages with context
- **Rate limiting**: Built-in request timing and retry logic
- **Custom exceptions**: `BinanceFundingError` for API-specific issues

## API Rate Limits ⚡

Please be aware of Binance API rate limits:

- Weight-based rate limiting applies
- The module includes automatic retry logic
- Consider implementing additional rate limiting for high-frequency usage

## Popular Symbols 📈

Common Binance Futures symbols:

- `BTCUSDT` - Bitcoin
- `ETHUSDT` - Ethereum
- `BNBUSDT` - Binance Coin
- `ADAUSDT` - Cardano
- `XRPUSDT` - Ripple
- `SOLUSDT` - Solana
- `DOGEUSDT` - Dogecoin

## Requirements 📋

- Python 3.7+
- `requests` library
- Internet connection for API access

## License 📄

This project is for educational and personal use. Please make sure to comply with Binance's API terms of service.

## Contributing 🤝

Feel free to submit issues, feature requests, or pull requests to improve this tool!

---

**Disclaimer**: This tool is not affiliated with Binance. Use at your own risk and ensure compliance with Binance's API terms of service.
