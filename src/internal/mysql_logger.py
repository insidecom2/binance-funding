from datetime import datetime
import json
from typing import Any, Dict


def insert_funding_logs(
    rows,
    host,
    port,
    user,
    password,
    database,
    table_name="funding_logs",
    connect_timeout=5,
):
    """Insert forecast-passed rows into MySQL funding_logs table."""
    if not rows:
        return 0

    try:
        import pymysql
    except Exception as e:
        print(f"⚠️ MySQL logger unavailable (PyMySQL missing): {e}")
        return 0

    sql = (
        f"INSERT INTO `{table_name}` "
        "(`timestamp`, `symbol`, `current`, `next`, `delta`, `r2`) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )

    values = []
    now = datetime.now()
    for row in rows:
        values.append(
            (
                now,
                row.get("symbol"),
                row.get("current"),
                row.get("next"),
                row.get("delta"),
                row.get("r2"),
            )
        )

    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=connect_timeout,
        )
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)
        connection.commit()
        return len(values)
    except Exception as e:
        print(f"⚠️ MySQL insert failed: {e}")
        try:
            if connection:
                connection.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            if connection:
                connection.close()
        except Exception:
            pass


def insert_trade_history_row(
    trade_record: Dict[str, Any],
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    table_name: str = "trade_history",
    connect_timeout: int = 5,
) -> bool:
    """Insert one trade history row into MySQL trade_history table."""
    if not trade_record:
        return False

    try:
        import pymysql
    except Exception as e:
        print(f"⚠️ MySQL trade logger unavailable (PyMySQL missing): {e}")
        return False

    def _to_datetime(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return None
        return None

    def _to_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    event_type = "EXIT" if trade_record.get("exit_time") else "ENTRY"
    payload_json = json.dumps(trade_record, ensure_ascii=False, default=str)

    sql = (
        f"INSERT INTO `{table_name}` "
        "(" 
        "event_time, entry_time, exit_time, trade_group_id, symbol, event_type, is_dry_run, success, "
        "order_type, futures_order_id, spot_order_id, futures_close_id, spot_close_id, "
        "entry_price, futures_qty, spot_qty, position_size, expected_pnl, realized_pnl, "
        "funding_rate, basis, risk_score, exit_reason, error_message, raw_payload" 
        ") VALUES (" 
        "%s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s, %s, %s, %s, "
        "%s, %s, %s, %s, %s, %s, "
        "%s, %s, %s, %s, %s, %s" 
        ")"
    )

    values = (
        _to_datetime(trade_record.get("exit_time") or trade_record.get("entry_time")) or datetime.now(),
        _to_datetime(trade_record.get("entry_time")),
        _to_datetime(trade_record.get("exit_time")),
        trade_record.get("trade_group_id"),
        trade_record.get("symbol"),
        event_type,
        1 if trade_record.get("dry_run", False) else 0,
        1 if trade_record.get("success", False) else 0,
        trade_record.get("order_type"),
        trade_record.get("futures_order_id"),
        trade_record.get("spot_order_id"),
        trade_record.get("futures_close_id"),
        trade_record.get("spot_close_id"),
        _to_float(trade_record.get("entry_price")),
        _to_float(trade_record.get("futures_qty")),
        _to_float(trade_record.get("spot_qty")),
        _to_float(trade_record.get("position_size")),
        _to_float(trade_record.get("expected_pnl")),
        _to_float(trade_record.get("pnl")),
        _to_float(trade_record.get("funding_rate")),
        _to_float(trade_record.get("basis")),
        _to_float(trade_record.get("risk")),
        trade_record.get("exit_reason"),
        trade_record.get("error"),
        payload_json,
    )

    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=connect_timeout,
        )
        with connection.cursor() as cursor:
            cursor.execute(sql, values)
        connection.commit()
        return True
    except Exception as e:
        print(f"⚠️ MySQL trade history insert failed: {e}")
        try:
            if connection:
                connection.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            if connection:
                connection.close()
        except Exception:
            pass
