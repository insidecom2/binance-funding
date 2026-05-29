#!/usr/bin/env python3
import argparse
import json
import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.internal.filter import analyze_opportunities
from src.internal.funding import enrich_opportunities_with_forecast, get_all_current_funding_opportunities
from src.internal.scanner_config import build_scanner_config

load_dotenv()


def load_scan_report(path):
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def select_report_symbols(report, limit):
    symbols = []
    for candidate in report.get("top_candidates", [])[:limit]:
        symbol = candidate.get("symbol")
        if symbol:
            symbols.append(symbol)
    return symbols


def main():
    parser = argparse.ArgumentParser(description="Confirm top scan candidates with forecast enrichment.")
    parser.add_argument("--report", type=str, required=True, help="Path to scan-report.json")
    parser.add_argument("--limit", type=int, default=10, help="How many top scan candidates to confirm")
    parser.add_argument("--json-out", type=str, default="", help="Optional path to save confirmation JSON")
    args = parser.parse_args()

    if not os.path.exists(args.report):
        raise SystemExit(f"File not found: {args.report}")

    report = load_scan_report(args.report)
    symbols = select_report_symbols(report, args.limit)
    if not symbols:
        raise SystemExit("No top candidates found in scan report")

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = build_scanner_config(base_dir)

    print(f"🔎 Confirming {len(symbols)} candidate(s) with forecast: {', '.join(symbols)}")
    opportunities = get_all_current_funding_opportunities()
    selected = [opp for opp in opportunities if opp.get("symbol") in symbols]
    selected.sort(key=lambda opp: symbols.index(opp["symbol"]))

    enrich_opportunities_with_forecast(
        selected,
        forecast_periods=config.forecast_periods,
        prediction_edge=config.forecast_edge,
        forecast_min_points=config.forecast_min_points,
        forecast_min_r2=config.forecast_min_r2,
        forecast_max_residual_std=config.forecast_max_residual_std,
        forecast_max_relative_std=config.forecast_max_relative_std,
        forecast_min_predicted=config.forecast_min_predicted,
        max_workers=min(8, max(1, len(selected))),
    )

    analysis = analyze_opportunities(
        selected,
        min_basis=config.min_basis,
        min_funding=config.min_funding,
        min_volume=config.min_volume,
        max_spread=config.max_spread,
        max_risk=config.max_risk,
        position_size=config.position_size,
        require_forecast=True,
    )

    confirmed = analysis["filtered"]
    print("\n=== Forecast Confirmation ===")
    if not confirmed:
        print("No candidates passed forecast confirmation.")
    else:
        for idx, candidate in enumerate(confirmed, 1):
            forecast = candidate.get("funding_forecast") or {}
            print(
                f"{idx}. {candidate['symbol']} | net_profit={candidate['net_profit']:+.6f} "
                f"| risk={candidate['risk']:.2f} | funding={candidate['funding_rate']:+.4%} "
                f"| predicted_next={forecast.get('predicted_next', 0):+.6f}"
            )
    print(f"Reject counts: {analysis['reject_counts']}")

    if args.json_out:
        payload = {
            "symbols": symbols,
            "confirmed": confirmed,
            "reject_counts": analysis["reject_counts"],
        }
        with open(args.json_out, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, indent=2, ensure_ascii=False, default=str)
        print(f"\n📝 Confirmation report written to {args.json_out}")


if __name__ == "__main__":
    main()
