from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.internal.trading_system.models import (
    TradeEvent,
    TradeEventType,
    TradeRecord,
    TradeState,
    TradeStateError,
)


class LedgerTransitionError(ValueError):
    """Raised when a ledger operation would violate trade state rules."""


class FileTradeLedger:
    """Simple JSON-backed ledger for phase-0 trading system scaffolding."""

    def __init__(self, path: str):
        self.path = path

    def create_trade(self, trade: TradeRecord, initial_event_payload: Optional[Dict[str, Any]] = None) -> TradeRecord:
        data = self._load_raw()
        if any(item.get("trade_id") == trade.trade_id for item in data["trades"]):
            raise LedgerTransitionError(f"trade_id already exists: {trade.trade_id}")

        data["trades"].append(trade.to_dict())
        data["events"].append(
            TradeEvent(
                trade_id=trade.trade_id,
                event_type=TradeEventType.TRADE_CREATED,
                state_after=trade.state,
                payload=dict(initial_event_payload or {}),
            ).to_dict()
        )
        self._save_raw(data)
        return trade

    def get_trade(self, trade_id: str) -> Optional[TradeRecord]:
        data = self._load_raw()
        for item in data["trades"]:
            if item.get("trade_id") == trade_id:
                return TradeRecord.from_dict(item)
        return None

    def list_trades(self) -> List[TradeRecord]:
        data = self._load_raw()
        return [TradeRecord.from_dict(item) for item in data["trades"]]

    def load_active_trades(self) -> List[TradeRecord]:
        active_states = {
            TradeState.PLANNED,
            TradeState.ENTRY_SUBMITTING,
            TradeState.ENTRY_PARTIAL,
            TradeState.ENTRY_HEDGED,
            TradeState.ACTIVE,
            TradeState.EXIT_PENDING,
            TradeState.EXIT_PARTIAL,
            TradeState.MANUAL_REVIEW,
        }
        return [trade for trade in self.list_trades() if trade.state in active_states]

    def append_event(
        self,
        trade_id: str,
        event_type: TradeEventType,
        payload: Optional[Dict[str, Any]] = None,
        state_before: Optional[TradeState] = None,
        state_after: Optional[TradeState] = None,
    ) -> TradeEvent:
        trade = self.get_trade(trade_id)
        if trade is None:
            raise LedgerTransitionError(f"trade not found: {trade_id}")

        event = TradeEvent(
            trade_id=trade_id,
            event_type=event_type,
            state_before=state_before,
            state_after=state_after,
            payload=dict(payload or {}),
        )
        data = self._load_raw()
        data["events"].append(event.to_dict())
        self._save_raw(data)
        return event

    def update_state(self, trade_id: str, new_state: TradeState, patch: Optional[Dict[str, Any]] = None) -> TradeRecord:
        data = self._load_raw()
        for index, item in enumerate(data["trades"]):
            if item.get("trade_id") != trade_id:
                continue

            current_trade = TradeRecord.from_dict(item)
            try:
                updated_trade = current_trade.transition_to(new_state, patch=patch)
            except TradeStateError as exc:
                raise LedgerTransitionError(str(exc)) from exc

            data["trades"][index] = updated_trade.to_dict()
            data["events"].append(
                TradeEvent(
                    trade_id=trade_id,
                    event_type=TradeEventType.STATE_TRANSITIONED,
                    state_before=current_trade.state,
                    state_after=updated_trade.state,
                    payload=dict(patch or {}),
                ).to_dict()
            )
            self._save_raw(data)
            return updated_trade

        raise LedgerTransitionError(f"trade not found: {trade_id}")

    def list_events(self, trade_id: Optional[str] = None) -> List[TradeEvent]:
        data = self._load_raw()
        events = [TradeEvent.from_dict(item) for item in data["events"]]
        if trade_id is None:
            return events
        return [event for event in events if event.trade_id == trade_id]

    def _load_raw(self) -> Dict[str, List[Dict[str, Any]]]:
        if not os.path.exists(self.path):
            return {"trades": [], "events": []}

        with open(self.path, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)

        if not isinstance(data, dict):
            return {"trades": [], "events": []}

        trades = data.get("trades")
        events = data.get("events")
        return {
            "trades": trades if isinstance(trades, list) else [],
            "events": events if isinstance(events, list) else [],
        }

    def _save_raw(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2, sort_keys=True)
