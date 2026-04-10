# Phase 2 - Dry-Run Wiring in Main Flow

Date: 2026-04-10
Goal: Connect TradeOrchestrator into runtime without real order placement.

## Tasks

- [ ] Add trading config block in main entrypoint
- [ ] Add TRADING_ENABLED and TRADING_DRY_RUN flags
- [ ] Execute trade path only when best opportunity exists
- [ ] Keep scanner output unchanged when trading is disabled
- [ ] Write dry-run trade records into .trade_history.json

## Deliverables

- Updated cmd/main.py
- Runtime branch for execute_trade(best, dry_run=True)

## Acceptance Criteria

- Running scanner does not place real orders in dry-run
- Trade history file is generated with expected fields

## Notes

- Default should remain safe: trading disabled or dry-run enabled.
- Keep existing console scan summary intact.
