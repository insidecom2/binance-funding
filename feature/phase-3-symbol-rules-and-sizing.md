# Phase 3 - Symbol Rules and Order Sizing Safety

Date: 2026-04-10
Goal: Ensure order quantities and prices follow exchange constraints.

## Tasks

- [x] Fetch symbol filters (stepSize, tickSize, minQty, minNotional)
- [x] Add quantity/price rounding helpers
- [x] Validate notional before sending orders
- [x] Reject trade early when constraints are not met

## Deliverables

- Helper functions for precision and notional checks
- Pre-trade validation integrated before order submit

## Acceptance Criteria

- No invalid precision payload is sent
- Clear logs for rejected sizing

## Notes

- Centralize rounding logic to avoid duplicated precision bugs.
- Validate before both entry and exit orders.

## Implementation Status (2026-04-13)

- Added filter retrieval + cache in [src/binance/binance_funding.py](src/binance/binance_funding.py).
- Added centralized precision/notional helpers in [src/internal/symbol_rules.py](src/internal/symbol_rules.py).
- Integrated strict pre-trade rejection for entry and exit in [src/internal/trading.py](src/internal/trading.py).
- Added unit tests in [tests/internal/test_symbol_rules.py](tests/internal/test_symbol_rules.py) and [tests/internal/test_trading_validation.py](tests/internal/test_trading_validation.py).
