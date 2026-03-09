# Binance Funding

Python starter project for fetching and exploring Binance Futures funding rates.

## Quick Start

1. Create and activate a virtual environment.
2. Install the project in editable mode:

```bash
pip install -e .
```

3. Configure [config.yaml](config.yaml):

- `mode`: `analyze` | `execute` | `summary` | `raw`
- `symbols`: list of symbols
- `limit`: historical records to fetch
- `top`: top N opportunities for analyze mode
- `position_size`: position size per trade

4. Run the CLI (no arguments):

```bash
binance-funding
```

## Development

Run tests:

```bash
pytest
```
