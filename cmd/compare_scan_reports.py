#!/usr/bin/env python3
import argparse
import json
import os


def load_report(path):
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def _candidate_symbols(report):
    return [candidate.get("symbol") for candidate in report.get("top_candidates", [])]


def compare_reports(old_report, new_report):
    old_top = old_report.get("top_candidates", [])
    new_top = new_report.get("top_candidates", [])
    old_top_net = old_top[0]["net_profit"] if old_top else 0.0
    new_top_net = new_top[0]["net_profit"] if new_top else 0.0

    return {
        "old_filtered_count": old_report.get("filtered_count", 0),
        "new_filtered_count": new_report.get("filtered_count", 0),
        "filtered_count_delta": new_report.get("filtered_count", 0) - old_report.get("filtered_count", 0),
        "old_forecast_passed_count": old_report.get("forecast_passed_count", 0),
        "new_forecast_passed_count": new_report.get("forecast_passed_count", 0),
        "forecast_passed_delta": new_report.get("forecast_passed_count", 0) - old_report.get("forecast_passed_count", 0),
        "old_top_net_profit": old_top_net,
        "new_top_net_profit": new_top_net,
        "top_net_profit_delta": new_top_net - old_top_net,
        "old_top_symbols": _candidate_symbols(old_report),
        "new_top_symbols": _candidate_symbols(new_report),
        "old_reject_counts": old_report.get("reject_counts", {}),
        "new_reject_counts": new_report.get("reject_counts", {}),
    }


def print_summary(summary):
    print("=== Scan Report Comparison ===")
    print(
        f"Filtered count: {summary['old_filtered_count']} -> {summary['new_filtered_count']} "
        f"(delta {summary['filtered_count_delta']:+d})"
    )
    print(
        f"Forecast passed: {summary['old_forecast_passed_count']} -> {summary['new_forecast_passed_count']} "
        f"(delta {summary['forecast_passed_delta']:+d})"
    )
    print(
        f"Top net profit: {summary['old_top_net_profit']:+.6f} -> {summary['new_top_net_profit']:+.6f} "
        f"(delta {summary['top_net_profit_delta']:+.6f})"
    )
    print(f"Old top symbols: {summary['old_top_symbols']}")
    print(f"New top symbols: {summary['new_top_symbols']}")
    print(f"Old rejects: {summary['old_reject_counts']}")
    print(f"New rejects: {summary['new_reject_counts']}")


def main():
    parser = argparse.ArgumentParser(description="Compare two scan-report.json files.")
    parser.add_argument("old_report", type=str, help="Path to older scan report")
    parser.add_argument("new_report", type=str, help="Path to newer scan report")
    args = parser.parse_args()

    if not os.path.exists(args.old_report):
        raise SystemExit(f"File not found: {args.old_report}")
    if not os.path.exists(args.new_report):
        raise SystemExit(f"File not found: {args.new_report}")

    old_report = load_report(args.old_report)
    new_report = load_report(args.new_report)
    print_summary(compare_reports(old_report, new_report))


if __name__ == "__main__":
    main()
