from src.internal.mysql_logger import insert_funding_logs
from src.internal.scanner_config import ScannerConfig


def save_forecast_passed_symbols_to_mysql(opportunities: list, config: ScannerConfig) -> None:
    """Save forecast-passed symbols to MySQL as one symbol per row."""
    if not config.mysql_enabled:
        return
    if not config.mysql_user or not config.mysql_database:
        print("⚠️ MySQL enabled but MYSQL_USER / MYSQL_DATABASE not set; skip DB logging")
        return

    rows = []
    for opp in opportunities:
        forecast = opp.get("funding_forecast") or {}
        if forecast.get("is_valid") and forecast.get("confidence_pass") and forecast.get("forecast_pass"):
            rows.append(
                {
                    "symbol": opp.get("symbol"),
                    "current": opp.get("max_rate", {}).get("value"),
                    "next": forecast.get("predicted_next"),
                    "delta": forecast.get("delta_next_vs_current"),
                    "r2": forecast.get("r_squared"),
                }
            )

    if not rows:
        print("🗃️ No forecast-passed symbols to save in MySQL")
        return

    inserted = insert_funding_logs(
        rows=rows,
        host=config.mysql_host,
        port=config.mysql_port,
        user=config.mysql_user,
        password=config.mysql_password,
        database=config.mysql_database,
        table_name=config.mysql_table_funding_logs,
    )
    print(f"🗃️ MySQL funding_logs inserted rows: {inserted}")
