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

### Trading API Credentials

Authenticated account/order methods require Binance API credentials in `env`:

```bash
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
BINANCE_RECV_WINDOW=5000
```

The read-only scanner methods (`get_funding_rate`, `get_premium_index`, `get_klines`) continue to work without these credentials.

### Authenticated Methods

The client now supports authenticated wrappers for account and order workflows:

- `place_futures_order(...)`
- `place_spot_order(...)`
- `cancel_order(...)`
- `get_order(...)`
- `get_account_balance(...)`
- `get_position_info(...)`

All authenticated failures raise `BinanceFundingError` with mapped API context (HTTP status + Binance error code/message).

### MySQL Trade History Logging

To persist trade history into MySQL, enable these env keys:

```bash
MYSQL_ENABLED=true
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database
MYSQL_TRADES_ENABLED=true
MYSQL_TABLE_TRADE_HISTORY=trade_history
```

Apply migration:

```bash
mysql -h 127.0.0.1 -P 3306 -u your_user -p your_database < migrations/mysql/20260412_001_create_trade_history.sql
```

For MySQL 5.7 compatibility (uses LONGTEXT for `raw_payload`), use:

```bash
mysql -h 127.0.0.1 -P 3306 -u your_user -p your_database < migrations/mysql/20260412_002_create_trade_history_mysql57.sql
```

Create daily summary view:

```bash
mysql -h 127.0.0.1 -P 3306 -u your_user -p your_database < migrations/mysql/20260412_003_create_trade_history_daily_view.sql
```

Trade history fields include:

- `trade_group_id` (correlates ENTRY and EXIT of the same trade lifecycle)
- `event_time`, `entry_time`, `exit_time`
- `symbol`, `event_type`, `is_dry_run`, `success`
- Order identifiers: `futures_order_id`, `spot_order_id`, `futures_close_id`, `spot_close_id`
- Sizing/pricing: `entry_price`, `futures_qty`, `spot_qty`, `position_size`
- Performance/risk: `expected_pnl`, `realized_pnl`, `funding_rate`, `basis`, `risk_score`
- Diagnostics: `exit_reason`, `error_message`, `raw_payload`

Example query:

```sql
SELECT *
FROM v_trade_history_daily_summary
WHERE trade_date >= CURDATE() - INTERVAL 7 DAY
ORDER BY trade_date DESC, symbol;
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
