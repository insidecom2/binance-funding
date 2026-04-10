# Phase 6 - Test and Rollout Plan

Date: 2026-04-10
Goal: Move from safe simulation to controlled live trading.

## Tasks

- [ ] Add unit tests for sizing and exit-condition logic
- [ ] Add integration smoke test for dry-run path
- [ ] Run paper cycle with 1 symbol and low notional
- [ ] Enable live mode only after 3+ stable dry-run cycles
- [ ] Start live with single symbol + strict limits

## Deliverables

- Test coverage for critical trading logic
- Rollout checklist and go/no-go criteria

## Acceptance Criteria

- No blocking error in dry-run cycles
- Live mode only enabled with explicit env flag and small capital

## Notes

- Use staged rollout and keep hard limits for early live cycles.
- Log all go/no-go decisions with timestamp.
