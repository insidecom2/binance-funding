# Trading System Architecture Blueprint

Date: 2026-05-30
Scope: New post-scan trading system separated from the current scanner-only runtime

## Goal

Design a new trading workflow with clear separation of responsibilities:

1. `selection` chooses what is worth trading
2. `planner` turns a candidate into an executable trade plan
3. `execution` opens and closes real positions
4. `monitor` decides whether to hold or exit after entry
5. `ledger/state` keeps control, recovery, and auditability

## Non-Goals

- Replacing the current scanner logic in one step
- Multi-exchange support
- Portfolio optimization across many symbols
- Advanced auto-rebalancing during an open trade

## Design Principles

- Keep scanner and trade execution separate
- Treat exchange interaction as unreliable and stateful
- Make every trade resumable after process restart
- Prefer explicit state transitions over implicit flags
- Record every important event before and after exchange actions

## Proposed Module Layout

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
```

## Responsibilities

### 1. Selection

Purpose:
- Reduce scanner output to symbols that are still tradable now

Inputs:
- scanner opportunities
- runtime thresholds
- active trade list from ledger

Outputs:
- `SelectedCandidate`
- reject reasons for skipped symbols

Should handle:
- funding floor
- basis floor
- spread ceiling
- liquidity floor
- risk ceiling
- skip symbols with active trades
- skip stale candidates too close to funding cutoff

Should not handle:
- order sizing
- broken hedge policy
- exit policy

### 2. Planner

Purpose:
- Convert one selected candidate into a concrete plan

Inputs:
- selected candidate
- account constraints
- market snapshot
- strategy config

Outputs:
- `TradePlan`
- or explicit rejection with reason

`TradePlan` should contain:
- `trade_id`
- `symbol`
- `entry_orders`
- `target_rounds`
- `max_hold_minutes`
- `entry_order_type`
- `close_order_type`
- `stop_loss_policy`
- `basis_exit_policy`
- `funding_exit_policy`
- `hedge_repair_policy`
- `retry_policy`

Planner owns decisions such as:
- whether to trust scanner `selected_rounds`
- how to cap holding rounds using risk model output
- whether to use market or limit entry
- how much notional to allocate

### 3. Execution

Purpose:
- Turn a plan into filled entry or exit legs on the exchange

Inputs:
- `TradePlan`
- `TradeState`
- exchange client

Outputs:
- `EntryResult`
- `ExitResult`
- normalized order and fill events

Must handle:
- submit order
- poll status
- partial fill
- timeout
- cancel remainder
- retry under policy
- detect hedge imbalance
- trigger repair or flatten on broken hedge

Recommended first policy:
- staged hedge instead of fully parallel entry

Reason:
- simpler reconciliation
- easier recovery
- safer for first live rollout

### 4. Monitor

Purpose:
- Watch active trades until exit conditions are met

Inputs:
- active trades from ledger
- exchange open positions
- exchange open orders
- current premium, mark, index, and funding data

Outputs:
- `HoldDecision`
- `ExitDecision`
- monitor snapshots and events

Monitor must be funding-aware:
- know target rounds
- know completed rounds
- know next funding timestamp
- know whether edge still exists after each funding event

Monitor rule groups:
- time-based
- funding-based
- basis-based
- pnl/risk-based
- execution-health-based

### 5. Ledger/State

Purpose:
- Keep source-of-truth state for every trade

Inputs:
- plans
- order results
- monitor decisions
- close results

Outputs:
- active trade list
- event history
- resumable trade records

Must support:
- create trade
- append event
- update state
- mark active
- mark closed
- load active trades on startup

## State Machine

Recommended states:

- `NEW`
- `PLANNED`
- `ENTRY_SUBMITTING`
- `ENTRY_PARTIAL`
- `ENTRY_HEDGED`
- `ACTIVE`
- `EXIT_PENDING`
- `EXIT_PARTIAL`
- `CLOSED`
- `FAILED`
- `MANUAL_REVIEW`

Key rule:
- no exchange action should happen without a recorded trade state transition

## Data Model

### Trade Record

Required fields:
- `trade_id`
- `symbol`
- `strategy_version`
- `state`
- `entry_time`
- `exit_time`
- `planned_rounds`
- `completed_rounds`
- `entry_futures_qty`
- `entry_spot_qty`
- `exit_futures_qty`
- `exit_spot_qty`
- `entry_futures_price`
- `entry_spot_price`
- `exit_futures_price`
- `exit_spot_price`
- `funding_received`
- `fee_total`
- `realized_pnl`
- `exit_reason`
- `error_reason`

### Trade Event

Required fields:
- `trade_id`
- `event_type`
- `event_time`
- `state_before`
- `state_after`
- `payload`

Examples:
- `candidate_selected`
- `plan_created`
- `entry_order_submitted`
- `entry_order_filled`
- `hedge_broken`
- `funding_round_completed`
- `exit_triggered`
- `position_closed`

## Recovery Model

Startup recovery should:

1. load active trades from ledger
2. query exchange for current open orders and positions
3. reconcile local state against exchange truth
4. move unresolved trades to `MANUAL_REVIEW` if reconciliation fails
5. resume monitor loop for valid active trades

## External Interfaces

Suggested service interfaces:

```python
class SelectionService:
    def select(self, opportunities, active_trades, config):
        ...


class TradePlanner:
    def plan(self, candidate, account_snapshot, market_snapshot, config):
        ...


class ExecutionEngine:
    def open(self, trade_plan):
        ...

    def close(self, trade_state, exit_decision):
        ...


class PositionMonitor:
    def evaluate(self, trade_state, market_snapshot):
        ...


class TradeLedger:
    def create_trade(self, trade_plan):
        ...

    def append_event(self, trade_id, event_type, payload):
        ...

    def update_state(self, trade_id, new_state, patch):
        ...

    def load_active_trades(self):
        ...
```

## Recommended Runtime Flow

1. scanner produces ranked opportunities
2. selection filters tradable candidates
3. planner creates a trade plan
4. ledger records `PLANNED`
5. execution opens entry legs
6. ledger records fill events and sets `ACTIVE`
7. monitor evaluates active trades on a loop
8. monitor triggers exit decision when needed
9. execution closes both legs
10. ledger records final pnl and sets `CLOSED`

## Acceptance Criteria

- Every trade has a durable `trade_id`
- Every state transition is recorded
- Entry and exit can be resumed after restart
- Broken hedge cases are explicitly handled
- Funding rounds are counted and persisted
- Close decisions are explainable from recorded events
