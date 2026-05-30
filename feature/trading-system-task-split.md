# Trading System Task Split

Date: 2026-05-30
Scope: Incremental implementation plan for the new trading system

## Build Order

1. Ledger and state model
2. Selection service
3. Planner service
4. Entry execution engine
5. Position monitor
6. Exit execution engine
7. Recovery flow
8. Reporting and notifications

## Phase 0: Ledger and State Model

Goal:
- Create the source-of-truth for all future trading actions

Tasks:
- Define trade states in `models.py`
- Define `TradeRecord` and `TradeEvent`
- Add `TradeLedger` interface
- Implement file-backed ledger first
- Add `load_active_trades()` and `append_event()`

Done when:
- A planned trade can be created and moved through states locally
- Active trades survive process restart from persisted storage

Tests:
- state transition validation
- event append and reload
- active trade restore after restart

## Phase 1: Selection Service

Goal:
- Decide what is still tradable after scan output is produced

Tasks:
- Create `SelectionService`
- Reuse scanner candidate fields where possible
- Reject active symbols already in the ledger
- Emit reject reasons per symbol
- Add a single ranked selection output

Done when:
- Scanner output can be reduced to a list of selected candidates with reasons

Tests:
- rejects below thresholds
- rejects duplicate active symbol
- prefers higher quality candidate

## Phase 2: Planner Service

Goal:
- Turn one selected candidate into a concrete trade plan

Tasks:
- Create `TradePlanner`
- Define `TradePlan`
- Add hold-round resolution policy
- Add order sizing policy
- Add entry and exit policy fields
- Add broken hedge fallback policy

Done when:
- A selected candidate produces a deterministic `TradePlan`

Tests:
- sizing policy
- round-cap policy
- risk override behavior
- invalid plan rejection

## Phase 3: Entry Execution Engine

Goal:
- Open hedged entry positions safely

Tasks:
- Create `ExecutionEngine.open()`
- Normalize order request and order result models
- Implement staged hedge entry policy
- Add timeout, cancel, and retry behavior
- Detect partial fill and broken hedge
- Record entry events in the ledger

Done when:
- A trade plan can open entry legs and produce a reconciled result

Tests:
- full fill happy path
- partial fill then retry
- first leg filled and second leg fails
- timeout then cancel

## Phase 4: Position Monitor

Goal:
- Hold active positions only while edge is still valid

Tasks:
- Create `PositionMonitor`
- Define monitor snapshot model
- Track completed funding rounds
- Evaluate hold vs exit decision
- Add basis, funding, pnl, and execution-health rules
- Emit monitor events and exit candidates

Done when:
- Active trades can be evaluated repeatedly with explainable decisions

Tests:
- hold before first funding
- exit after target rounds
- exit on basis reversal
- exit on hedge imbalance
- exit on stop-loss

## Phase 5: Exit Execution Engine

Goal:
- Close active positions safely and persist realized outcome

Tasks:
- Implement `ExecutionEngine.close()`
- Reconcile close fills
- Compute realized pnl, fees, and funding received
- Persist final close event and final state
- Mark unresolved close failures as `MANUAL_REVIEW`

Done when:
- An active trade can be closed and finalized in the ledger

Tests:
- close happy path
- close partial fill
- close rejection
- pnl calculation

## Phase 6: Recovery Flow

Goal:
- Resume safely after restart or process crash

Tasks:
- Create `recovery.py`
- Load active trades from ledger
- Query exchange open orders and positions
- Reconcile state mismatches
- Resume monitor only for trusted active trades
- Move ambiguous trades to `MANUAL_REVIEW`

Done when:
- Restarted process can recover active trades without duplicate entry or exit

Tests:
- active trade recovery
- missing exchange position
- open exit order recovery
- ambiguous state to manual review

## Phase 7: Reporting and Notifications

Goal:
- Make the system observable for operators

Tasks:
- Add summary views for active and closed trades
- Add event-based Telegram notifications
- Add ledger-driven pnl summary
- Add concise broken-hedge alerts
- Add operator-facing manual review alerts

Done when:
- Important trade lifecycle events are visible without reading raw logs

Tests:
- notification payload formatting
- summary generation
- manual review alert path

## Suggested File Mapping

```text
src/internal/trading_system/
  __init__.py
  models.py
  selection.py
  planner.py
  execution.py
  monitor.py
  ledger.py
  recovery.py
  policies.py

tests/internal/trading_system/
  test_models.py
  test_selection.py
  test_planner.py
  test_execution_entry.py
  test_monitor.py
  test_execution_exit.py
  test_recovery.py
```

## Risks to Address Early

- broken hedge after first leg fill
- stale candidate data between scan and entry
- funding round counting drift
- process restart with open exposure
- duplicate close attempts

## First Implementation Slice

Recommended smallest useful slice:

1. file-backed ledger
2. selection service with reject reasons
3. planner that returns a `TradePlan`
4. dry-run entry execution only
5. monitor that tracks target rounds without live close

Reason:
- enough to validate interfaces and state flow
- low risk compared with direct live execution
