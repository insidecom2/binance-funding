import json
import os
from typing import Any, Dict, List


def load_trade_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []

    with open(path, "r") as file_obj:
        history = json.load(file_obj)
    return history if isinstance(history, list) else []


def append_trade_history(path: str, trade_record: Dict[str, Any]) -> None:
    history = load_trade_history(path)
    history.append(trade_record)
    with open(path, "w") as file_obj:
        json.dump(history, file_obj, indent=2, default=str)


def summarize_trade_history(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {
            "total_trades": 0,
            "successful_trades": 0,
            "total_pnl": 0,
            "average_pnl": 0,
            "win_rate": 0,
        }

    history = load_trade_history(path)
    closed_trades = [trade for trade in history if "exit_time" in trade]
    successful = [trade for trade in closed_trades if trade.get("success")]
    total_pnl = sum(trade.get("pnl", 0) for trade in closed_trades)
    win_count = sum(1 for trade in closed_trades if trade.get("pnl", 0) > 0)

    return {
        "total_trades": len(closed_trades),
        "successful_trades": len(successful),
        "winning_trades": win_count,
        "total_pnl": total_pnl,
        "average_pnl": total_pnl / len(closed_trades) if closed_trades else 0,
        "win_rate": (win_count / len(closed_trades) * 100) if closed_trades else 0,
    }
