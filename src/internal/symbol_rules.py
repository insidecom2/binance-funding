"""Helpers for symbol precision and order sizing validation."""

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, Optional


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def decimal_to_str(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if text else "0"


def round_quantity(quantity: Any, step_size: Any) -> Decimal:
    qty = _to_decimal(quantity)
    step = _to_decimal(step_size)
    if step <= 0:
        return qty
    return (qty / step).to_integral_value(rounding=ROUND_DOWN) * step


def round_price(price: Any, tick_size: Any) -> Decimal:
    px = _to_decimal(price)
    tick = _to_decimal(tick_size)
    if tick <= 0:
        return px
    return (px / tick).to_integral_value(rounding=ROUND_DOWN) * tick


def validate_min_qty(quantity: Decimal, min_qty: Any) -> bool:
    minimum = _to_decimal(min_qty)
    if minimum <= 0:
        return True
    return quantity >= minimum


def validate_min_notional(quantity: Decimal, price: Decimal, min_notional: Any) -> bool:
    minimum = _to_decimal(min_notional)
    if minimum <= 0:
        return True
    notional = quantity * price
    return notional >= minimum


def validate_order_inputs(
    *,
    symbol: str,
    market: str,
    side: str,
    quantity: Any,
    price: Any,
    filters: Dict[str, Any],
    order_type: str,
) -> Dict[str, Any]:
    is_market = str(order_type).upper() == "MARKET"

    step_size = filters.get("market_step_size") if is_market else filters.get("step_size")
    min_qty = filters.get("market_min_qty") if is_market else filters.get("min_qty")
    tick_size = filters.get("tick_size")
    min_notional = filters.get("min_notional")

    raw_qty = _to_decimal(quantity)
    raw_price = _to_decimal(price)
    rounded_qty = round_quantity(raw_qty, step_size)
    rounded_price = round_price(raw_price, tick_size)

    result = {
        "ok": True,
        "symbol": symbol,
        "market": market,
        "side": side,
        "order_type": str(order_type).upper(),
        "raw_quantity": float(raw_qty),
        "raw_price": float(raw_price),
        "quantity": float(rounded_qty),
        "price": float(rounded_price),
        "quantity_str": decimal_to_str(rounded_qty),
        "price_str": decimal_to_str(rounded_price),
        "notional": float(rounded_qty * rounded_price),
        "reason": None,
        "required": {
            "step_size": step_size,
            "tick_size": tick_size,
            "min_qty": min_qty,
            "min_notional": min_notional,
        },
    }

    if rounded_qty <= 0:
        result["ok"] = False
        result["reason"] = "Quantity rounded to zero after step-size adjustment"
        return result

    if rounded_price <= 0:
        result["ok"] = False
        result["reason"] = "Price rounded to zero after tick-size adjustment"
        return result

    if not validate_min_qty(rounded_qty, min_qty):
        result["ok"] = False
        result["reason"] = (
            f"Quantity {result['quantity_str']} is below minQty {min_qty}"
        )
        return result

    if not validate_min_notional(rounded_qty, rounded_price, min_notional):
        result["ok"] = False
        result["reason"] = (
            f"Notional {decimal_to_str(rounded_qty * rounded_price)} is below minNotional {min_notional}"
        )
        return result

    return result
