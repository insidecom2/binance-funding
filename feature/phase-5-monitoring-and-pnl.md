# Phase 5 - Monitoring and PnL Reporting

Date: 2026-04-10
Goal: Close the loop with observable lifecycle and performance data.

## Tasks

- [ ] Start monitoring loop after live entry
- [ ] Evaluate stop-loss, basis reversal, and max-age conditions
- [ ] Track entry/exit values for both legs
- [ ] Compute realized PnL with fee breakdown
- [ ] Summarize win rate and average PnL from history

## Deliverables

- Monitoring outputs in logs
- PnL summary command/output using trade history

## Acceptance Criteria

- Closed trades include exit reason and realized PnL
- Summary metrics match raw records in history file

## Notes

- Separate unrealized and realized PnL in reporting.
- Keep trade history schema stable for later analytics.
