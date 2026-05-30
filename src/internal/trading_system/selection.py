from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from src.internal.trading_system.models import TradeRecord


@dataclass(frozen=True)
class SelectionReject:
    symbol: str
    reason: str
    candidate: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SelectionResult:
    selected: List[Dict[str, Any]]
    rejected: List[SelectionReject]


class SelectionService:
    """Filters ranked scanner candidates into symbols that are still safe to trade now."""

    def __init__(self, min_minutes_to_funding: Optional[float] = None, max_selected: int = 1):
        self.min_minutes_to_funding = min_minutes_to_funding
        self.max_selected = max_selected

    def select(
        self,
        candidates: Iterable[Dict[str, Any]],
        active_trades: Optional[Iterable[TradeRecord]] = None,
    ) -> SelectionResult:
        active_symbols = {trade.symbol for trade in (active_trades or [])}
        selected: List[Dict[str, Any]] = []
        rejected: List[SelectionReject] = []

        ranked_candidates = sorted(
            list(candidates),
            key=lambda item: (
                -float(item.get("net_profit", 0.0)),
                float(item.get("risk", 0.0)),
                -float(item.get("funding_rate", 0.0)),
                -float(item.get("basis", 0.0)),
                -float(item.get("volume", 0.0)),
                float(item.get("spread", 0.0)),
            ),
        )

        for candidate in ranked_candidates:
            symbol = str(candidate.get("symbol") or "").strip()
            if not symbol:
                rejected.append(
                    SelectionReject(symbol="", reason="missing_symbol", candidate=dict(candidate))
                )
                continue

            if symbol in active_symbols:
                rejected.append(
                    SelectionReject(symbol=symbol, reason="active_trade_exists", candidate=dict(candidate))
                )
                continue

            if self._is_too_close_to_funding(candidate):
                rejected.append(
                    SelectionReject(symbol=symbol, reason="too_close_to_funding", candidate=dict(candidate))
                )
                continue

            if candidate.get("net_profit") is None:
                rejected.append(
                    SelectionReject(symbol=symbol, reason="missing_net_profit", candidate=dict(candidate))
                )
                continue

            selected.append(dict(candidate))
            if len(selected) >= self.max_selected:
                break

        return SelectionResult(selected=selected, rejected=rejected)

    def _is_too_close_to_funding(self, candidate: Dict[str, Any]) -> bool:
        if self.min_minutes_to_funding is None:
            return False

        minutes_to_funding = candidate.get("minutes_to_funding")
        if minutes_to_funding is None:
            return True

        try:
            return float(minutes_to_funding) < float(self.min_minutes_to_funding)
        except (TypeError, ValueError):
            return True
