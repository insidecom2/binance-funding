# Phase 4 - Entry/Exit Risk Controls

Date: 2026-04-10
Goal: Prevent broken hedges and reduce operational risk.

## Tasks

- [ ] Add pre-trade balance checks (spot + futures)
- [ ] Add max slippage guard for limit/market flow
- [ ] Add partial-fill rollback logic for 2-leg entry
- [ ] Add timeouts for unfilled orders with cancel-and-exit
- [ ] Confirm reduce-only close behavior for futures leg

## Deliverables

- Guard rails in orchestrator execution path
- Structured failure states and rollback logs

## Acceptance Criteria

- One-leg-only open state is auto-corrected or closed
- Stop-loss/basis reversal exits execute reliably

## Notes

- Rollback path should be idempotent and safe to retry.
- Prefer explicit state transitions for easier debugging.
