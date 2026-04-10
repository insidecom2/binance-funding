# Phase 3 - Symbol Rules and Order Sizing Safety

Date: 2026-04-10
Goal: Ensure order quantities and prices follow exchange constraints.

## Tasks

- [ ] Fetch symbol filters (stepSize, tickSize, minQty, minNotional)
- [ ] Add quantity/price rounding helpers
- [ ] Validate notional before sending orders
- [ ] Reject trade early when constraints are not met

## Deliverables

- Helper functions for precision and notional checks
- Pre-trade validation integrated before order submit

## Acceptance Criteria

- No invalid precision payload is sent
- Clear logs for rejected sizing

## Notes

- Centralize rounding logic to avoid duplicated precision bugs.
- Validate before both entry and exit orders.
