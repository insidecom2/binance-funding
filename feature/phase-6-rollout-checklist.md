# Phase-6 Rollout Checklist (binance-funding)

## 1. Automated Testing

- [ ] All unit tests pass (run: `python3 -m unittest discover -s tests/internal/ -v`)
- [ ] Integration smoke test (dry-run):
  - [ ] Run `run.sh` with `TRADING_ENABLED=0` and verify no errors in logs
  - [ ] Check `.trade_history.json` for expected dry-run entries

## 2. Coverage & CI/CD (optional)

- [ ] (Optional) Run coverage: `coverage run -m unittest discover -s tests/internal/`
- [ ] (Optional) Review coverage report: `coverage report`
- [ ] (Optional) CI pipeline runs all tests on push

## 3. Rollout Controls

- [ ] Confirm 3+ stable dry-run cycles (no errors, expected trades in history)
- [ ] Validate trade history and logs for correctness
- [ ] Set `TRADING_ENABLED=1` and `TRADING_DRY_RUN=0` for live mode
- [ ] Start live with a single symbol and low notional (e.g., `MAX_POSITION=100`)
- [ ] Monitor logs, PnL, and notifications for anomalies

## 4. Notification & Logging

- [ ] Verify Telegram and MySQL logging in both dry-run and live modes

## 5. Rollback Plan

- [ ] If any error or anomaly, immediately set `TRADING_ENABLED=0` and/or `TRADING_DRY_RUN=1`
- [ ] Review logs and trade history for root cause
- [ ] Only resume live after issue is fixed and dry-run passes

---

**Go/No-Go Decision:**

- [ ] All above checks are green
- [ ] Team sign-off (names/date):

---

# End of checklist
