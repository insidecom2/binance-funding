from typing import Callable, List

from src.internal.funding_log_sink import save_forecast_passed_symbols_to_mysql
from src.internal.filter import analyze_opportunities, select_best_opportunity
from src.internal.funding import (
    enrich_opportunities_with_forecast,
    get_all_current_funding_opportunities,
)
from src.internal.scanner_config import ScannerConfig
from src.internal.scanner_report import build_scan_report, write_scan_report
from src.internal.telegram_notifier import notify_forecast_passed_symbols


def print_forecast_debug(opportunities: list) -> None:
    if not opportunities:
        return

    print("🧪 Forecast debug status:")
    for opp in opportunities:
        forecast = opp.get("funding_forecast") or {}
        print(
            f"   {opp['symbol']}: "
            f"valid={forecast.get('is_valid')} "
            f"conf={forecast.get('confidence_pass')} "
            f"pass={forecast.get('forecast_pass')} "
            f"rel_std={forecast.get('relative_std', 0):.2f} "
            f"r2={forecast.get('r_squared', 0):.3f} "
            f"reason={forecast.get('fail_reason')}"
        )


def scan_market(config: ScannerConfig, emit_side_effects: bool = True) -> list:
    """Fetch market opportunities and optionally enrich them with forecast data."""
    print("🚀 Fetching live funding opportunities...")
    opportunities = get_all_current_funding_opportunities()
    if not opportunities:
        print("❌ Failed to get funding data")
        return []

    print(f"📊 Processed {len(opportunities)} symbols")
    opportunities.sort(key=lambda item: item["max_rate"]["value"], reverse=True)

    if not config.require_forecast:
        return opportunities

    forecast_candidates = opportunities[: max(0, config.forecast_top_n)]
    print("⚙️ Enriching forecast for funding opportunities...")
    print(
        "🛠️ Forecast config: "
        f"periods={config.forecast_periods}, edge={config.forecast_edge}, "
        f"min_points={config.forecast_min_points}, min_r2={config.forecast_min_r2}, "
        f"max_residual_std={config.forecast_max_residual_std}, "
        f"max_relative_std={config.forecast_max_relative_std}, "
        f"min_predicted={config.forecast_min_predicted}, "
        f"top_n={config.forecast_top_n}"
    )
    enrich_opportunities_with_forecast(
        forecast_candidates,
        forecast_periods=config.forecast_periods,
        prediction_edge=config.forecast_edge,
        forecast_min_points=config.forecast_min_points,
        forecast_min_r2=config.forecast_min_r2,
        forecast_max_residual_std=config.forecast_max_residual_std,
        forecast_max_relative_std=config.forecast_max_relative_std,
        forecast_min_predicted=config.forecast_min_predicted,
        max_workers=8,
    )
    print_forecast_debug(forecast_candidates)
    if emit_side_effects:
        save_forecast_passed_symbols_to_mysql(forecast_candidates, config)
        notify_forecast_passed_symbols(forecast_candidates, config)
    return opportunities


def analyze_market_opportunities(opportunities: list, config: ScannerConfig) -> dict:
    return analyze_opportunities(
        opportunities,
        min_basis=config.min_basis,
        min_funding=config.min_funding,
        min_volume=config.min_volume,
        max_spread=config.max_spread,
        max_risk=config.max_risk,
        position_size=config.position_size,
        require_forecast=config.require_forecast,
    )


def rank_opportunities(opportunities: list, config: ScannerConfig) -> list:
    return analyze_market_opportunities(opportunities, config)["filtered"]


def format_filtered_results(filtered: list, config: ScannerConfig) -> List[str]:
    lines = [
        "\n🏆 Filtered Opportunities "
        f"(risk <= {config.max_risk:.2f}, basis >= {config.min_basis:.2%}, "
        f"funding >= {config.min_funding:.2%}, volume >= {config.min_volume:,.0f}, "
        f"spread <= {config.max_spread:.2%}, net_profit >= 0):"
    ]
    if not filtered:
        lines.append("❌ No opportunities passed all filters.")
        return lines

    for idx, opp in enumerate(filtered, 1):
        lines.append(
            f"{idx}. {opp['symbol']} | risk={opp['risk']:.2f} | "
            f"basis={opp['basis']:+.4%} | funding={opp['funding_rate']:+.4%} | "
            f"volume={opp['volume']:.0f} | spread={opp['spread']:.4%} | "
            f"net_profit={opp['net_profit']:.6f} | rounds={opp['best_rounds']}"
        )

    best = select_best_opportunity(filtered)
    if best:
        lines.append("\n⭐ Best Candidate:")
        lines.append(
            f"{best['symbol']} | risk={best['risk']:.2f} | basis={best['basis']:+.4%} | "
            f"funding={best['funding_rate']:+.4%} | volume={best['volume']:.0f} | "
            f"spread={best['spread']:.4%} | net_profit={best['net_profit']:.6f} | "
            f"selected_rounds={best['best_rounds']}"
        )
    return lines


def run_scanner(config: ScannerConfig, printer: Callable[[str], None] = print) -> list:
    opportunities = scan_market(config)
    analysis = analyze_market_opportunities(opportunities, config)
    filtered = analysis["filtered"]
    report = build_scan_report(opportunities, analysis, config)
    write_scan_report(config.scan_report_path, report)
    for line in format_filtered_results(filtered, config):
        printer(line)
    return filtered
