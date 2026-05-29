#!/usr/bin/env python3
import argparse
from dataclasses import replace
import json
import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.internal.scanner import analyze_market_opportunities, scan_market
from src.internal.scanner_config import build_scanner_config
from src.internal.scanner_report import build_scan_report

load_dotenv()


def build_variants(base_config):
    variants = [("baseline", base_config)]
    seen = {"baseline"}

    min_funding_values = sorted(
        {
            max(0.0, base_config.min_funding - 0.0001),
            base_config.min_funding,
            base_config.min_funding + 0.0001,
        }
    )
    max_risk_values = sorted(
        {
            max(0.1, base_config.max_risk - 0.1),
            base_config.max_risk,
            min(0.9, base_config.max_risk + 0.1),
        }
    )
    max_spread_values = sorted(
        {
            max(0.0005, base_config.max_spread - 0.0005),
            base_config.max_spread,
            base_config.max_spread + 0.0005,
        }
    )
    forecast_edge_values = sorted(
        {
            base_config.forecast_edge - 0.00005,
            base_config.forecast_edge,
            base_config.forecast_edge + 0.00005,
        }
    )
    forecast_relative_std_values = sorted(
        {
            max(0.5, base_config.forecast_max_relative_std - 0.25),
            base_config.forecast_max_relative_std,
            base_config.forecast_max_relative_std + 0.25,
        }
    )

    for min_funding in min_funding_values:
        for max_risk in max_risk_values:
            for max_spread in max_spread_values:
                for forecast_edge in forecast_edge_values:
                    for forecast_relative_std in forecast_relative_std_values:
                        name = (
                            f"f{min_funding:.4f}_r{max_risk:.2f}_"
                            f"s{max_spread:.4f}_e{forecast_edge:+.5f}_"
                            f"rs{forecast_relative_std:.2f}"
                        )
                        if name in seen:
                            continue
                        variants.append(
                            (
                                name,
                                replace(
                                    base_config,
                                    min_funding=min_funding,
                                    max_risk=max_risk,
                                    max_spread=max_spread,
                                    forecast_edge=forecast_edge,
                                    forecast_max_relative_std=forecast_relative_std,
                                ),
                            )
                        )
                        seen.add(name)

    return variants


def score_variant(report):
    top_candidates = report.get("top_candidates", [])
    filtered_count = report.get("filtered_count", 0)
    top_net_profit = top_candidates[0]["net_profit"] if top_candidates else 0.0
    avg_net_profit = (
        sum(candidate["net_profit"] for candidate in top_candidates) / len(top_candidates)
        if top_candidates
        else 0.0
    )
    return {
        "filtered_count": filtered_count,
        "top_net_profit": round(top_net_profit, 6),
        "avg_top_net_profit": round(avg_net_profit, 6),
    }


def rank_reports(reports):
    reports.sort(
        key=lambda item: (
            -item["score"]["filtered_count"],
            -item["score"]["top_net_profit"],
            -item["score"]["avg_top_net_profit"],
        )
    )
    return reports


def evaluate_variants(opportunities, variants):
    reports = []
    for name, config in variants:
        analysis = analyze_market_opportunities(opportunities, config)
        report = build_scan_report(opportunities, analysis, config, top_n=5)
        report["variant"] = name
        report["score"] = score_variant(report)
        reports.append(report)
    return rank_reports(reports)


def print_reports(reports):
    print("\n=== Sweep Results ===")
    for idx, report in enumerate(reports, 1):
        score = report["score"]
        print(
            f"{idx}. {report['variant']:<32} "
            f"| filtered={score['filtered_count']:<3} "
            f"| top_net={score['top_net_profit']:+.6f} "
            f"| avg_top_net={score['avg_top_net_profit']:+.6f}"
        )
        print(f"   rejects={report['reject_counts']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep scanner configs against one market snapshot.")
    parser.add_argument("--json-out", type=str, default="", help="Optional path to save sweep report JSON")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of variants to evaluate")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    base_config = build_scanner_config(base_dir)

    print("🧪 Fetching one market snapshot for config sweep...")
    opportunities = scan_market(base_config, emit_side_effects=False)
    variants = build_variants(base_config)
    if args.limit > 0:
        variants = variants[:args.limit]

    reports = evaluate_variants(opportunities, variants)
    print_reports(reports)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as file_obj:
            json.dump(reports, file_obj, indent=2, ensure_ascii=False, default=str)
        print(f"\n📝 Sweep report written to {args.json_out}")


if __name__ == "__main__":
    main()
