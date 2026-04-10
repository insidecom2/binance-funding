# Phase 1 - Trading API Foundation

Date: 2026-04-10
Goal: Add authenticated order/account methods in Binance client.

## Tasks

- [ ] Add environment keys loading for trading credentials
- [ ] Implement request signing (HMAC SHA256)
- [ ] Add futures order endpoint wrapper (create/cancel/query)
- [ ] Add spot order endpoint wrapper (create/cancel/query)
- [ ] Add account balance and position query methods
- [ ] Add robust retry and clear API error mapping

## Deliverables

- Updated src/binance/binance_funding.py
- Verified methods:
  - place_futures_order
  - place_spot_order
  - cancel_order
  - get_account_balance
  - get_position_info

## Acceptance Criteria

- Methods return parsed JSON and fail with clear custom exceptions
- Authentication and signature work on test requests

## Notes

- Keep backward compatibility for existing read-only methods.
- Do not break scanner path while adding authenticated methods.
