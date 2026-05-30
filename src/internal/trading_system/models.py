from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeStateError(ValueError):
    """Raised when a trade state transition is invalid."""


class TradeState(str, Enum):
    NEW = "NEW"
    PLANNED = "PLANNED"
    ENTRY_SUBMITTING = "ENTRY_SUBMITTING"
    ENTRY_PARTIAL = "ENTRY_PARTIAL"
    ENTRY_HEDGED = "ENTRY_HEDGED"
    ACTIVE = "ACTIVE"
    EXIT_PENDING = "EXIT_PENDING"
    EXIT_PARTIAL = "EXIT_PARTIAL"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class TradeEventType(str, Enum):
    TRADE_CREATED = "trade_created"
    STATE_TRANSITIONED = "state_transitioned"
    NOTE_ADDED = "note_added"


ALLOWED_STATE_TRANSITIONS = {
    TradeState.NEW: {
        TradeState.PLANNED,
        TradeState.FAILED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.PLANNED: {
        TradeState.ENTRY_SUBMITTING,
        TradeState.FAILED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.ENTRY_SUBMITTING: {
        TradeState.ENTRY_PARTIAL,
        TradeState.ENTRY_HEDGED,
        TradeState.ACTIVE,
        TradeState.FAILED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.ENTRY_PARTIAL: {
        TradeState.ENTRY_SUBMITTING,
        TradeState.ENTRY_HEDGED,
        TradeState.ACTIVE,
        TradeState.FAILED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.ENTRY_HEDGED: {
        TradeState.ACTIVE,
        TradeState.EXIT_PENDING,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.ACTIVE: {
        TradeState.EXIT_PENDING,
        TradeState.CLOSED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.EXIT_PENDING: {
        TradeState.EXIT_PARTIAL,
        TradeState.CLOSED,
        TradeState.FAILED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.EXIT_PARTIAL: {
        TradeState.EXIT_PENDING,
        TradeState.CLOSED,
        TradeState.MANUAL_REVIEW,
    },
    TradeState.CLOSED: set(),
    TradeState.FAILED: set(),
    TradeState.MANUAL_REVIEW: {
        TradeState.ENTRY_SUBMITTING,
        TradeState.EXIT_PENDING,
        TradeState.CLOSED,
        TradeState.FAILED,
    },
}


@dataclass(frozen=True)
class TradeEvent:
    trade_id: str
    event_type: TradeEventType
    event_time: str = field(default_factory=utc_now_iso)
    state_before: Optional[TradeState] = None
    state_after: Optional[TradeState] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "event_type": self.event_type.value,
            "event_time": self.event_time,
            "state_before": self.state_before.value if self.state_before else None,
            "state_after": self.state_after.value if self.state_after else None,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeEvent":
        return cls(
            trade_id=data["trade_id"],
            event_type=TradeEventType(data["event_type"]),
            event_time=data.get("event_time", utc_now_iso()),
            state_before=TradeState(data["state_before"]) if data.get("state_before") else None,
            state_after=TradeState(data["state_after"]) if data.get("state_after") else None,
            payload=dict(data.get("payload") or {}),
        )


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    symbol: str
    state: TradeState
    strategy_version: str = "v1"
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    planned_rounds: int = 0
    completed_rounds: int = 0
    entry_futures_qty: float = 0.0
    entry_spot_qty: float = 0.0
    exit_futures_qty: float = 0.0
    exit_spot_qty: float = 0.0
    entry_futures_price: float = 0.0
    entry_spot_price: float = 0.0
    exit_futures_price: float = 0.0
    exit_spot_price: float = 0.0
    funding_received: float = 0.0
    fee_total: float = 0.0
    realized_pnl: float = 0.0
    exit_reason: Optional[str] = None
    error_reason: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: TradeState, patch: Optional[Dict[str, Any]] = None) -> "TradeRecord":
        if new_state == self.state:
            return self.with_updates(**(patch or {}))

        allowed = ALLOWED_STATE_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise TradeStateError(f"invalid trade transition: {self.state.value} -> {new_state.value}")

        values = dict(patch or {})
        values["state"] = new_state
        return self.with_updates(**values)

    def with_updates(self, **updates: Any) -> "TradeRecord":
        values = self.to_dict()
        values.update(updates)
        values["state"] = TradeState(values["state"])
        values["updated_at"] = utc_now_iso()
        return TradeRecord.from_dict(values)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "state": self.state.value,
            "strategy_version": self.strategy_version,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "planned_rounds": self.planned_rounds,
            "completed_rounds": self.completed_rounds,
            "entry_futures_qty": self.entry_futures_qty,
            "entry_spot_qty": self.entry_spot_qty,
            "exit_futures_qty": self.exit_futures_qty,
            "exit_spot_qty": self.exit_spot_qty,
            "entry_futures_price": self.entry_futures_price,
            "entry_spot_price": self.entry_spot_price,
            "exit_futures_price": self.exit_futures_price,
            "exit_spot_price": self.exit_spot_price,
            "funding_received": self.funding_received,
            "fee_total": self.fee_total,
            "realized_pnl": self.realized_pnl,
            "exit_reason": self.exit_reason,
            "error_reason": self.error_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeRecord":
        return cls(
            trade_id=data["trade_id"],
            symbol=data["symbol"],
            state=TradeState(data["state"]),
            strategy_version=data.get("strategy_version", "v1"),
            entry_time=data.get("entry_time"),
            exit_time=data.get("exit_time"),
            planned_rounds=int(data.get("planned_rounds", 0)),
            completed_rounds=int(data.get("completed_rounds", 0)),
            entry_futures_qty=float(data.get("entry_futures_qty", 0.0)),
            entry_spot_qty=float(data.get("entry_spot_qty", 0.0)),
            exit_futures_qty=float(data.get("exit_futures_qty", 0.0)),
            exit_spot_qty=float(data.get("exit_spot_qty", 0.0)),
            entry_futures_price=float(data.get("entry_futures_price", 0.0)),
            entry_spot_price=float(data.get("entry_spot_price", 0.0)),
            exit_futures_price=float(data.get("exit_futures_price", 0.0)),
            exit_spot_price=float(data.get("exit_spot_price", 0.0)),
            funding_received=float(data.get("funding_received", 0.0)),
            fee_total=float(data.get("fee_total", 0.0)),
            realized_pnl=float(data.get("realized_pnl", 0.0)),
            exit_reason=data.get("exit_reason"),
            error_reason=data.get("error_reason"),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            metadata=dict(data.get("metadata") or {}),
        )
