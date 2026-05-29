"""
Compatibility shim for legacy trade execution.

The active repository workflow is scanner-only. Order execution code lives in
`src.internal.legacy_trading` and is kept only for backward compatibility with
older commands, tests, and experiments that still import `src.internal.trading`.
"""

from src.internal.legacy_trading import TradeExecutionError, TradeOrchestrator

__all__ = ["TradeExecutionError", "TradeOrchestrator"]
