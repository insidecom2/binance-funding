# Repository Guidelines

## Project Structure & Module Organization
Core application code lives under `src/`. Use `src/binance/` for API clients and exchange-facing logic, `src/internal/` for trading, filtering, funding, and persistence helpers, and `src/xgb/` for forecast/risk model code. CLI entry points are in `cmd/` (`cmd/main.py`, `cmd/pnl_summary.py`). Tests live under `tests/internal/` for unit coverage and `tests/integration/` for smoke flows. SQL migrations are in `migrations/mysql/`, and design notes or phased implementation docs are in `feature/`.

## Build, Test, and Development Commands
Create a virtualenv and install dependencies with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Run the main scanner once with `.venv/bin/python cmd/main.py`. Tune the active thresholds with env vars such as `MIN_FUNDING`, `MIN_BASIS`, `MIN_VOLUME`, `MAX_SPREAD`, `MAX_RISK`, `POSITION_SIZE`, `SCAN_REPORT_PATH`, and `FORECAST_TOP_N`. Use `./run.sh` for the repo’s managed loop; it creates `.venv`, installs changed dependencies, and reruns the scanner every minute. Sweep threshold variants against one market snapshot with `.venv/bin/python cmd/sweep_scanner_configs.py --json-out /tmp/sweep.json`, summarize the best variants with `.venv/bin/python cmd/summarize_sweep_results.py /tmp/sweep.json`, compare two scan runs with `.venv/bin/python cmd/compare_scan_reports.py /tmp/old-scan.json /tmp/new-scan.json`, and confirm top scan candidates with forecast using `.venv/bin/python cmd/confirm_candidates.py --report /tmp/scan-report.json --limit 10 --json-out /tmp/confirm.json`. Run the scanner-safe test suite with `make test-scanner-safe`. Run only CLI smoke coverage with `make test-integration-smoke`. Run tooling-only smoke tests with `make test-tooling-smoke`. For broader discovery, use `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`. Container flow: `docker compose up --build`.

## Coding Style & Naming Conventions
Follow Python 3 conventions: 4-space indentation, snake_case for functions/modules/variables, PascalCase for classes, and uppercase for environment-backed constants. Keep modules focused by concern rather than adding broad utility files. Prefer explicit logic and short helper methods over clever abstractions. No formatter or linter is wired in this repo today, so match the surrounding style and keep imports and docstrings tidy.

## Testing Guidelines
Use `unittest` for both unit and integration tests. Name files `test_*.py` and keep test methods descriptive, for example `test_rejects_invalid_sizing_before_order_call`. Prefer `make test-scanner-safe` for changes in the active scanner workflow. Legacy trading execution tests are not part of the default safe suite. For changes that affect env-driven flows, verify both default and overridden settings.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commit style with prefixes like `feat:`. Continue with `feat:`, `fix:`, `refactor:`, or `test:` followed by a concise summary. Pull requests should describe the trading or data-flow impact, list test commands run, note any new env vars or migrations, and include sample output when CLI behavior changes.

## Security & Configuration Tips
Keep API keys, Telegram tokens, and MySQL credentials in local env files only; never commit secrets. Apply MySQL migrations from `migrations/mysql/` before enabling trade-history persistence. Default new work to dry-run paths (`TRADING_DRY_RUN=1`) unless you are intentionally validating live trading behavior.
