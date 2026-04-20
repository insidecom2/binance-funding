
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
from src.internal.trading import TradeOrchestrator
from src.binance.binance_funding import BinanceFunding

load_dotenv()


MIN_FUNDING = 0.0007
MIN_FUNDING_EXIT = 0
MIN_BASIS = float(os.getenv("MIN_BASIS", "0.0002"))
MIN_BASIS_EXIT = -0.001
MIN_VOLUME = float(os.getenv("MIN_VOLUME", "500000"))
MAX_SPREAD = 0.002
MAX_RISK = 0.5
MAX_MINUTES_TO_FUNDING = int(os.getenv("MAX_MINUTES_TO_FUNDING", "60"))

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
MYSQL_TRADES_ENABLED = os.getenv("MYSQL_TRADES_ENABLED", "false").lower() == "true"
MYSQL_TABLE_TRADE_HISTORY = os.getenv("MYSQL_TABLE_TRADE_HISTORY", "trade_history")

TRADING_ENABLED = os.getenv("TRADING_ENABLED", "false").lower() == "true"
TRADING_DRY_RUN = os.getenv("TRADING_DRY_RUN", "true").lower() == "true"
TRADING_POSITION_SIZE = float(os.getenv("TRADING_POSITION_SIZE", str(MAX_POSITION)))
TRADING_LEVERAGE = float(os.getenv("TRADING_LEVERAGE", "1.0"))
TRADING_HEDGE_RATIO = float(os.getenv("TRADING_HEDGE_RATIO", "0.5"))
TRADING_STOP_LOSS_PCT = float(os.getenv("TRADING_STOP_LOSS_PCT", "-0.02"))
TRADING_EXIT_BASIS_THRESHOLD = float(os.getenv("TRADING_EXIT_BASIS_THRESHOLD", "-0.001"))
TRADING_ORDER_TYPE = os.getenv("TRADING_ORDER_TYPE", "LIMIT")
TRADE_HISTORY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '.trade_history.json')
)


current_position = None

# =========================
# PHASE 7: Forecast-Driven Auto Trade
# =========================
def phase7_forecast_auto_trade():
    """เลือก symbol ที่ forecast กำไรดีที่สุด แล้วเปิดเทรด พร้อมแจ้งเตือน Telegram"""
    print("\n🚦 Phase 7: Forecast-Driven Auto Trade")
    try:
        trading_client = BinanceFunding()
        orchestrator = TradeOrchestrator(
            trading_client,
            {
                'position_size': TRADING_POSITION_SIZE,
                'leverage': TRADING_LEVERAGE,
                'hedge_ratio': TRADING_HEDGE_RATIO,
                'stop_loss_pct': TRADING_STOP_LOSS_PCT,
                'exit_basis_threshold': TRADING_EXIT_BASIS_THRESHOLD,
                'order_type': TRADING_ORDER_TYPE,
                'trade_history_path': TRADE_HISTORY_PATH,
                'mysql_trades_enabled': MYSQL_TRADES_ENABLED,
                'mysql_host': MYSQL_HOST,
                'mysql_port': MYSQL_PORT,
                'mysql_user': MYSQL_USER,
                'mysql_password': MYSQL_PASSWORD,
                'mysql_database': MYSQL_DATABASE,
                'mysql_table_trade_history': MYSQL_TABLE_TRADE_HISTORY,
            },
        )
        print(f"🤖 Trading enabled (dry_run={TRADING_DRY_RUN})")

        # 1. ดึง funding opportunities
        opportunities = get_all_current_funding_opportunities()
        if not opportunities:
            print("❌ ไม่พบ funding opportunities")
            return

        # 2. enrich forecast
        print("⚙️ Enriching forecast for all symbols...")
        enrich_opportunities_with_forecast(
            opportunities,
            forecast_periods=FORECAST_PERIODS,
            prediction_edge=FORECAST_EDGE,
            forecast_min_points=FORECAST_MIN_POINTS,
            forecast_min_r2=FORECAST_MIN_R2,
            forecast_max_residual_std=FORECAST_MAX_RESIDUAL_STD,
            forecast_max_relative_std=FORECAST_MAX_RELATIVE_STD,
            forecast_min_predicted=FORECAST_MIN_PREDICTED,
            max_workers=8,
        )


        traded_count = 0
        for i, opp in enumerate(opportunities, 1):
            f = opp.get('funding_forecast') or {}
            if (
                f.get('is_valid') and f.get('confidence_pass') and f.get('forecast_pass')
                and opp.get('net_profit', 0) > 0
                and opp.get('risk', 1) <= MAX_RISK
                and opp.get('basis', 0) >= MIN_BASIS
                and opp.get('volume', 0) >= MIN_VOLUME
                and opp.get('spread', 1) <= MAX_SPREAD
            ):
                print(f"🚦 {i}. {opp['symbol']} ผ่าน forecast+filter | net_profit={opp.get('net_profit', 0):.6f} | risk={opp.get('risk', 0):.2f} | funding={opp.get('funding_rate', 0):+.4%} | basis={opp.get('basis', 0):+.4%} | volume={opp.get('volume', 0):,.0f} | spread={opp.get('spread', 0):.4%} | r2={f.get('r_squared', 0):.3f}")
                trade_result = orchestrator.execute_spot_futures_trade(opp, dry_run=TRADING_DRY_RUN)
                traded_count += 1
                if trade_result.get('success'):
                    print(f"✅ Trade path executed (dry_run={TRADING_DRY_RUN})")
                    print(
                        f"   futures_order={trade_result.get('futures_order_id')} | "
                        f"spot_order={trade_result.get('spot_order_id')} | "
                        f"expected_pnl={trade_result.get('expected_pnl', 0):.2f}"
                    )
                    msg = (
                        f"[Phase7] เปิดออเดอร์ {opp['symbol']}\n"
                        f"net_profit={opp.get('net_profit', 0):.6f} | risk={opp.get('risk', 0):.2f}\n"
                        f"futures_order={trade_result.get('futures_order_id')} | "
                        f"spot_order={trade_result.get('spot_order_id')}\n"
                        f"expected_pnl={trade_result.get('expected_pnl', 0):.2f}"
                    )
                    send_telegram_message(msg)
                else:
                    print(f"❌ Trade path failed: {trade_result.get('error')}")
                    send_telegram_message(f"[Phase7] เปิดออเดอร์ {opp['symbol']} ล้มเหลว: {trade_result.get('error')}")
        if traded_count == 0:
            print("❌ ไม่มี symbol ที่ผ่าน forecast gate")

    except Exception as e:
        print(f"❌ Phase7 Error: {e}")
        send_telegram_message(f"[Phase7] ERROR: {e}")



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
        print(
            "🧾 Forecast-passed symbols for notification: "
            + ", ".join(gate_passed_symbols)
        )

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

        forecast_passed = []
        for opp in top_5_optimal:
            f = opp.get('funding_forecast') or {}
            if f.get('is_valid') and f.get('confidence_pass') and f.get('forecast_pass'):
                forecast_passed.append(opp)

        if forecast_passed:
            names = ", ".join(o.get('symbol', '-') for o in forecast_passed)
            print(f"✅ Forecast-passed symbols ({len(forecast_passed)}): {names}")
        else:
            print("❌ Forecast-passed symbols (0): none")

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
    orchestrator = None
    trading_client = None
    try:
        if TRADING_ENABLED:
            try:
                trading_client = BinanceFunding()
                orchestrator = TradeOrchestrator(
                    trading_client,
                    {
                        'position_size': TRADING_POSITION_SIZE,
                        'leverage': TRADING_LEVERAGE,
                        'hedge_ratio': TRADING_HEDGE_RATIO,
                        'stop_loss_pct': TRADING_STOP_LOSS_PCT,
                        'exit_basis_threshold': TRADING_EXIT_BASIS_THRESHOLD,
                        'order_type': TRADING_ORDER_TYPE,
                        'trade_history_path': TRADE_HISTORY_PATH,
                        'mysql_trades_enabled': MYSQL_TRADES_ENABLED,
                        'mysql_host': MYSQL_HOST,
                        'mysql_port': MYSQL_PORT,
                        'mysql_user': MYSQL_USER,
                        'mysql_password': MYSQL_PASSWORD,
                        'mysql_database': MYSQL_DATABASE,
                        'mysql_table_trade_history': MYSQL_TABLE_TRADE_HISTORY,
                    },
                )
                print(f"🤖 Trading enabled (dry_run={TRADING_DRY_RUN})")
            except Exception as trade_init_err:
                print(f"⚠️ Trading init failed, fallback to scanner-only mode: {trade_init_err}")
                orchestrator = None

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
                print(f"{i}. {opp['symbol']} | risk={opp['risk']:.2f} | basis={opp['basis']:+.4%} | funding={opp['funding_rate']:+.4%} | volume={opp['volume']:.0f} | spread={opp['spread']:.4%} | net_profit={opp['net_profit']:.6f} | rounds={opp['best_rounds']}")
            if not filtered:
                print("❌ No opportunities passed all filters.")

            best = select_best_opportunity(filtered)
            if best:
                print("\n⭐️ Best Opportunity:")
                print(f"{best['symbol']} | risk={best['risk']:.2f} | basis={best['basis']:+.4%} | funding={best['funding_rate']:+.4%} | volume={best['volume']:.0f} | spread={best['spread']:.4%} | net_profit={best['net_profit']:.6f} | selected_rounds={best['best_rounds']}")
                if orchestrator:
                    trade_result = orchestrator.execute_spot_futures_trade(best, dry_run=TRADING_DRY_RUN)
                    if trade_result.get('success'):
                        print(f"✅ Trade path executed (dry_run={TRADING_DRY_RUN})")
                        print(
                            f"   futures_order={trade_result.get('futures_order_id')} | "
                            f"spot_order={trade_result.get('spot_order_id')} | "
                            f"expected_pnl={trade_result.get('expected_pnl', 0):.2f}"
                        )
                    else:
                        print(f"❌ Trade path failed: {trade_result.get('error')}")
            else:
                print("❌ No symbol passed all strict filters for best opportunity.")


        if TRADING_ENABLED and orchestrator is None:
            print("ℹ️ Trading branch skipped (initialization failed).")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)
    finally:
        if trading_client:
            trading_client.close()


if __name__ == "__main__":
    
    phase7_forecast_auto_trade()