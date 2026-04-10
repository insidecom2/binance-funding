
# =========================
# CONFIG
# =========================
from datetime import datetime, timedelta


import sys
import os
import requests
import json
from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.binance.trading_bot import FundingBot
from src.internal.funding import get_all_current_funding_opportunities, enrich_opportunities_with_forecast

from src.internal.filter import filter_opportunities, select_best_opportunity
from src.internal.mysql_logger import insert_funding_logs

load_dotenv()


MIN_FUNDING = 0.0002
MIN_FUNDING_EXIT = 0
MIN_BASIS = float(os.getenv("MIN_BASIS", "0.0005"))
MIN_BASIS_EXIT = -0.001
MIN_VOLUME = float(os.getenv("MIN_VOLUME", "500000"))
MAX_SPREAD = 0.004
MAX_RISK = 0.5

RISK_PER_TRADE = 0.1
MAX_POSITION = 1000
MAX_LOSS = 0.02
MAX_HOLD = timedelta(hours=8)

ENTRY_WINDOW = timedelta(minutes=15)
CONFIDENCE_THRESHOLD = 0.6
TAKE_PROFIT = 0.01
REQUIRE_FORECAST = os.getenv("REQUIRE_FORECAST", "false").lower() == "true"
FORECAST_PERIODS = int(os.getenv("FORECAST_PERIODS", "20"))
FORECAST_EDGE = float(os.getenv("FORECAST_EDGE", "0.0"))
FORECAST_MIN_POINTS = int(os.getenv("FORECAST_MIN_POINTS", "6"))
FORECAST_MIN_R2 = float(os.getenv("FORECAST_MIN_R2", "0.05"))
FORECAST_MAX_RESIDUAL_STD = float(os.getenv("FORECAST_MAX_RESIDUAL_STD", "0.0012"))
FORECAST_MAX_RELATIVE_STD = float(os.getenv("FORECAST_MAX_RELATIVE_STD", "1.0"))
FORECAST_MIN_PREDICTED = float(os.getenv("FORECAST_MIN_PREDICTED", str(MIN_FUNDING)))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_NOTIFY_COOLDOWN_MINUTES = int(os.getenv("TELEGRAM_NOTIFY_COOLDOWN_MINUTES", "5"))
TELEGRAM_NOTIFY_CACHE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '.telegram_notify_cache.json')
)

MYSQL_ENABLED = os.getenv("MYSQL_ENABLED", "false").lower() == "true"
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "")
MYSQL_TABLE_FUNDING_LOGS = os.getenv("MYSQL_TABLE_FUNDING_LOGS", "funding_logs")

current_position = None


def send_telegram_message(text: str, timeout: int = 20) -> bool:
    """Send a plain text message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not set; skip notification")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
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
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")
        return False


def _load_notify_cache() -> dict:
    """Load notification cache from disk."""
    try:
        if not os.path.exists(TELEGRAM_NOTIFY_CACHE_PATH):
            return {}
        with open(TELEGRAM_NOTIFY_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_notify_cache(cache: dict) -> None:
    """Persist notification cache to disk."""
    try:
        with open(TELEGRAM_NOTIFY_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"⚠️ Failed to save Telegram cache: {e}")


def notify_forecast_passed_symbols(opportunities: list) -> None:
    """Notify Telegram for symbols that pass forecast gate."""
    now_ts = datetime.now().timestamp()
    cooldown_seconds = TELEGRAM_NOTIFY_COOLDOWN_MINUTES * 60
    cache = _load_notify_cache()
    passed = []
    for opp in opportunities:
        forecast = opp.get("funding_forecast") or {}
        if forecast.get("is_valid") and forecast.get("confidence_pass") and forecast.get("forecast_pass"):
            symbol = opp.get("symbol")
            if not symbol:
                continue
            last_sent = float(cache.get(symbol, 0) or 0)
            if now_ts - last_sent < cooldown_seconds:
                remaining_sec = int(cooldown_seconds - (now_ts - last_sent))
                print(f"⏳ Skip Telegram for {symbol}: cooldown {remaining_sec}s remaining")
                continue
            passed.append((opp, forecast))

    if not passed:
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
    sent = send_telegram_message("\n".join(lines))
    if sent:
        sent_ts = datetime.now().timestamp()
        for opp, _ in passed:
            cache[opp["symbol"]] = sent_ts
        _save_notify_cache(cache)
        print(f"📨 Telegram sent for {len(passed)} forecast-passed symbol(s)")


def save_forecast_passed_symbols_to_mysql(opportunities: list) -> None:
    """Save forecast-passed symbols to MySQL as 1 symbol per row."""
    if not MYSQL_ENABLED:
        return
    if not MYSQL_USER or not MYSQL_DATABASE:
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
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        table_name=MYSQL_TABLE_FUNDING_LOGS,
    )
    print(f"🗃️ MySQL funding_logs inserted rows: {inserted}")

# =========================
# PLACEHOLDER API
# =========================
def get_funding_symbol_rate() -> list:
    print("🚀 Fetching ALL funding rates in one shot...")
    opportunities = get_all_current_funding_opportunities()
    
    if not opportunities:
        print("❌ Failed to get funding data")
        return []
        
    print(f"📊 Processed {len(opportunities)} USDT pairs")
    
    # Sort by rate (highest first) and take top 5 SHORT opportunities
    opportunities.sort(key=lambda x: x['max_rate']['value'], reverse=True)
    
    # Filter for optimal funding rate range (0.05% - 0.10%)
    min_rate = 0.0005  # 0.05%
    max_rate = 0.0010  # 0.10%
    
    optimal_opportunities = [
        opp for opp in opportunities 
        if min_rate <= opp['max_rate']['value'] <= max_rate
    ]
    
    print(f"🎯 Found {len(optimal_opportunities)} symbols in optimal range (0.05% - 0.10%)")
    
    # If no optimal rates found, show nearby rates
    if not optimal_opportunities:
        print("❌ No rates found in optimal range (0.05% - 0.10%)")
        
        # Show rates above 0.10% (too high - risky)
        high_rates = [opp for opp in opportunities if opp['max_rate']['value'] > max_rate][:3]
        if high_rates:
            print(f"\n⚠️  {len(high_rates)} rates ABOVE 0.10% (high risk):")
            for opp in high_rates:
                rate_pct = opp['max_rate']['percentage']
                print(f"   {opp['symbol']:<15} | {rate_pct:>+.4f}%")
        
        # Show rates between 0.02-0.05% (lower but safer)
        medium_rates = [opp for opp in opportunities if 0.0002 <= opp['max_rate']['value'] < min_rate][:3]
        if medium_rates:
            print(f"\n📊 {len([o for o in opportunities if 0.0002 <= o['max_rate']['value'] < min_rate])} rates in 0.02-0.04% range:")
            for opp in medium_rates:
                rate_pct = opp['max_rate']['percentage']
                print(f"   {opp['symbol']:<15} | {rate_pct:>+.4f}%")
        return []
        
    # Skip verbose per-symbol block to keep logs concise.
    top_5_optimal = optimal_opportunities[:5]
    if top_5_optimal:
        passed_symbols = ", ".join(
            f"{opp['symbol']}({opp['max_rate']['percentage']:+.4f}%)" for opp in top_5_optimal
        )
        print(f"✅ Symbols passed pre-forecast condition: {passed_symbols}")

    if top_5_optimal and REQUIRE_FORECAST:
        print("⚙️ Enriching forecast for selected symbols...")
        print(
            "🛠️ Forecast config: "
            f"periods={FORECAST_PERIODS}, edge={FORECAST_EDGE}, "
            f"min_points={FORECAST_MIN_POINTS}, min_r2={FORECAST_MIN_R2}, "
            f"max_residual_std={FORECAST_MAX_RESIDUAL_STD}, "
            f"max_relative_std={FORECAST_MAX_RELATIVE_STD}, "
            f"min_predicted={FORECAST_MIN_PREDICTED}"
        )
        enrich_opportunities_with_forecast(
            top_5_optimal,
            forecast_periods=FORECAST_PERIODS,
            prediction_edge=FORECAST_EDGE,
            forecast_min_points=FORECAST_MIN_POINTS,
            forecast_min_r2=FORECAST_MIN_R2,
            forecast_max_residual_std=FORECAST_MAX_RESIDUAL_STD,
            forecast_max_relative_std=FORECAST_MAX_RELATIVE_STD,
            forecast_min_predicted=FORECAST_MIN_PREDICTED,
            max_workers=5,
        )
        print("🧪 Forecast debug status:")
        for opp in top_5_optimal:
            f = opp.get('funding_forecast') or {}
            print(
                f"   {opp['symbol']}: "
                f"valid={f.get('is_valid')} "
                f"conf={f.get('confidence_pass')} "
                f"pass={f.get('forecast_pass')} "
                f"rel_std={f.get('relative_std', 0):.2f} "
                f"r2={f.get('r_squared', 0):.3f} "
                f"reason={f.get('fail_reason')}"
            )
        save_forecast_passed_symbols_to_mysql(top_5_optimal)
        notify_forecast_passed_symbols(top_5_optimal)
        
    # Market summary for optimal rates
    # avg_optimal_rate = sum(opp['max_rate']['value'] for opp in top_5_optimal) / len(top_5_optimal)
    # all_positive = len([opp for opp in opportunities if opp['max_rate']['value'] > 0])
    # print(f"\n📊 Optimal Range Average: {avg_optimal_rate * 100:+.4f}%")
    # print(f"🎯 Optimal Rates (0.04-0.08%): {len(optimal_opportunities)} | All Positive: {all_positive} / {len(opportunities)}")
    if top_5_optimal:
        next_funding_min = (top_5_optimal[0]['next_funding_time'] - int(datetime.now().timestamp() * 1000)) // (1000 * 60)
        # print(f"⭐ OPTIMAL RANGE: Profitable but not too risky!")
        print(f"🔴 Next funding in ~{next_funding_min}min - Perfect timing for balanced risk!")

    return top_5_optimal

def main():
    """Trading bot main entry point - scans ALL symbols for top 5 rates"""
    print("🤖 Binance Funding Rate Trading Bot")
    print("🔍 Scanning for OPTIMAL rates (0.04% - 0.08%)...")
    print("🎯 Sweet spot: Good profits without extreme risk")
    print(f"🧠 Forecast gate required: {REQUIRE_FORECAST}")
    try:
        # Get current live funding rates for ALL symbols (single API call)
        opportunities = get_funding_symbol_rate()
        print(f"✅ Found {len(opportunities)} optimal funding opportunities")
        
        # Filter and rank by risk, basis, funding, volume, spread, net profit
        if opportunities:
            filtered = filter_opportunities(
                opportunities,
                min_basis=MIN_BASIS,
                min_funding=MIN_FUNDING,
                min_volume=MIN_VOLUME,
                max_spread=MAX_SPREAD,
                max_risk=MAX_RISK,
                position_size=MAX_POSITION,
                require_forecast=REQUIRE_FORECAST,
            )
            print(
                "\n🏆 Filtered Opportunities "
                f"(risk <= {MAX_RISK:.2f}, basis > {MIN_BASIS:.2%}, funding >= {MIN_FUNDING:.2%}, "
                f"volume >= {MIN_VOLUME:,.0f}, spread <= {MAX_SPREAD:.2%}, กำไรสุทธิสูงสุด):"
            )
            for i, opp in enumerate(filtered, 1):
                selected_rounds = opp.get('selected_rounds', 1)
                print(f"{i}. {opp['symbol']} | risk={opp['risk']:.2f} | basis={opp['basis']:+.4%} | funding={opp['funding_rate']:+.4%} | volume={opp['volume']:.0f} | spread={opp['spread']:.4%} | net_profit={opp['net_profit']:.6f} | rounds={selected_rounds}")
            if not filtered:
                print("❌ No opportunities passed all filters.")

            # เลือกเหรียญที่ผ่านเงื่อนไข โดยเน้นกำไรสุทธิสูงสุดและใช้ risk ต่ำเป็นตัวตัดสินรอง
            best = select_best_opportunity(
                opportunities,
                min_basis=MIN_BASIS,
                min_funding=MIN_FUNDING,
                min_volume=MIN_VOLUME,
                max_spread=MAX_SPREAD,
                max_risk=MAX_RISK,
                position_size=MAX_POSITION,
                require_forecast=REQUIRE_FORECAST,
            )
            if best:
                print("\n⭐️ Best Opportunity:")
                print(f"{best['symbol']} | risk={best['risk']:.2f} | basis={best['basis']:+.4%} | funding={best['funding_rate']:+.4%} | volume={best['volume']:.0f} | spread={best['spread']:.4%} | net_profit={best['net_profit']:.6f} | selected_rounds={best['best_rounds']}")
            else:
                print("❌ No symbol passed all strict filters for best opportunity.")


    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()