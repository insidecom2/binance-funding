from datetime import datetime
import json
import os
from typing import Optional

import requests

from src.internal.scanner_config import ScannerConfig


def send_telegram_message(
    text: str,
    timeout: int = 20,
    *,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """Send a plain text message to Telegram."""
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    target_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not target_chat_id:
        print("⚠️ Telegram credentials not set; skip notification")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok", False):
            print(f"⚠️ Telegram API rejected message: {result}")
            return False
        return True
    except Exception as exc:
        print(f"⚠️ Telegram send error: {exc}")
        return False


def _load_notify_cache(path: str) -> dict:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_notify_cache(path: str, cache: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as file_obj:
            json.dump(cache, file_obj)
    except Exception as exc:
        print(f"⚠️ Failed to save Telegram cache: {exc}")


def notify_forecast_passed_symbols(opportunities: list, config: ScannerConfig) -> None:
    """Notify Telegram for symbols that pass forecast gate."""
    now_ts = datetime.now().timestamp()
    cooldown_seconds = config.telegram_notify_cooldown_minutes * 60
    cache = _load_notify_cache(config.telegram_notify_cache_path)
    gate_passed_count = 0
    gate_passed_symbols = []
    passed = []

    for opp in opportunities:
        forecast = opp.get("funding_forecast") or {}
        if forecast.get("is_valid") and forecast.get("confidence_pass") and forecast.get("forecast_pass"):
            gate_passed_count += 1
            symbol = opp.get("symbol")
            if not symbol:
                continue
            gate_passed_symbols.append(symbol)
            last_sent = float(cache.get(symbol, 0) or 0)
            if now_ts - last_sent < cooldown_seconds:
                remaining_sec = int(cooldown_seconds - (now_ts - last_sent))
                print(f"⏳ Skip Telegram for {symbol}: cooldown {remaining_sec}s remaining")
                continue
            passed.append((opp, forecast))

    if gate_passed_symbols:
        print("🧾 Forecast-passed symbols for notification: " + ", ".join(gate_passed_symbols))

    if not passed:
        if gate_passed_count > 0:
            print(
                "📭 Forecast passed but no Telegram sent "
                f"(all {gate_passed_count} symbol(s) still in cooldown)"
            )
        else:
            print("📭 No symbols passed forecast gate for Telegram notification")
        return

    lines = ["Forecast passed symbols"]
    lines.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    for opp, forecast in passed:
        lines.append(
            f"- {opp['symbol']} | current={opp['max_rate']['percentage']:+.4f}% "
            f"| next={forecast.get('predicted_next', 0) * 100:+.4f}% "
            f"| delta={forecast.get('delta_next_vs_current', 0) * 100:+.4f}% "
            f"| r2={forecast.get('r_squared', 0):.3f}"
        )

    sent = send_telegram_message(
        "\n".join(lines),
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    if sent:
        sent_ts = datetime.now().timestamp()
        for opp, _ in passed:
            cache[opp["symbol"]] = sent_ts
        _save_notify_cache(config.telegram_notify_cache_path, cache)
        print(f"📨 Telegram sent for {len(passed)} forecast-passed symbol(s)")
