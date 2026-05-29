from dataclasses import dataclass
import os
from typing import Optional


@dataclass(frozen=True)
class ScannerConfig:
    min_funding: float
    min_basis: float
    min_volume: float
    max_spread: float
    max_risk: float
    position_size: float
    require_forecast: bool
    forecast_periods: int
    forecast_edge: float
    forecast_min_points: int
    forecast_min_r2: float
    forecast_max_residual_std: float
    forecast_max_relative_std: float
    forecast_min_predicted: float
    forecast_top_n: int
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_notify_cooldown_minutes: int
    telegram_notify_cache_path: str
    mysql_enabled: bool
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_table_funding_logs: str
    scan_report_path: Optional[str]


def build_scanner_config(base_dir: str) -> ScannerConfig:
    min_funding = float(os.getenv("MIN_FUNDING", "0.0007"))
    return ScannerConfig(
        min_funding=min_funding,
        min_basis=float(os.getenv("MIN_BASIS", "0.0002")),
        min_volume=float(os.getenv("MIN_VOLUME", "500000")),
        max_spread=float(os.getenv("MAX_SPREAD", "0.002")),
        max_risk=float(os.getenv("MAX_RISK", "0.6")),
        position_size=float(os.getenv("POSITION_SIZE", "1000")),
        require_forecast=os.getenv("REQUIRE_FORECAST", "false").lower() == "true",
        forecast_periods=int(os.getenv("FORECAST_PERIODS", "20")),
        forecast_edge=float(os.getenv("FORECAST_EDGE", "-0.0001")),
        forecast_min_points=int(os.getenv("FORECAST_MIN_POINTS", "6")),
        forecast_min_r2=float(os.getenv("FORECAST_MIN_R2", "0.05")),
        forecast_max_residual_std=float(os.getenv("FORECAST_MAX_RESIDUAL_STD", "0.0012")),
        forecast_max_relative_std=float(os.getenv("FORECAST_MAX_RELATIVE_STD", "1.5")),
        forecast_min_predicted=float(os.getenv("FORECAST_MIN_PREDICTED", "0.0001")),
        forecast_top_n=int(os.getenv("FORECAST_TOP_N", "20")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        telegram_notify_cooldown_minutes=int(os.getenv("TELEGRAM_NOTIFY_COOLDOWN_MINUTES", "5")),
        telegram_notify_cache_path=os.path.abspath(
            os.path.join(base_dir, ".telegram_notify_cache.json")
        ),
        mysql_enabled=os.getenv("MYSQL_ENABLED", "false").lower() == "true",
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_user=os.getenv("MYSQL_USER", ""),
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        mysql_database=os.getenv("MYSQL_DATABASE", ""),
        mysql_table_funding_logs=os.getenv("MYSQL_TABLE_FUNDING_LOGS", "funding_logs"),
        scan_report_path=os.getenv("SCAN_REPORT_PATH") or None,
    )
