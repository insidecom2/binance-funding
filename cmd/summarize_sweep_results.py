#!/usr/bin/env python3
import argparse
import json
import os
import sys


def load_reports(path):
    with open(path, "r", encoding="utf-8") as file_obj:
        reports = json.load(file_obj)
    if not isinstance(reports, list):
        raise ValueError("Sweep report must be a list of report objects")
    return reports


def rank_reports(reports):
    return sorted(
        reports,
        key=lambda item: (
            -item.get("score", {}).get("filtered_count", 0),
            -item.get("score", {}).get("top_net_profit", 0.0),
            -item.get("score", {}).get("avg_top_net_profit", 0.0),
        ),
    )


def aggregate_rejects(reports):
    totals = {}
    for report in reports:
        for reason, count in report.get("reject_counts", {}).items():
            totals[reason] = totals.get(reason, 0) + count
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def print_summary(reports, top_n):
    ranked = rank_reports(reports)
    if not ranked:
        print("No sweep reports found.")
        return

    best = ranked[0]
    print("=== Sweep Summary ===")
    print(f"Best variant: {best.get('variant')}")
    print(f"Filtered count: {best.get('score', {}).get('filtered_count', 0)}")
    print(f"Top net profit: {best.get('score', {}).get('top_net_profit', 0.0):+.6f}")
    print(f"Avg top net profit: {best.get('score', {}).get('avg_top_net_profit', 0.0):+.6f}")
    print(f"Reject counts: {best.get('reject_counts', {})}")

    top_candidates = best.get("top_candidates", [])
    if top_candidates:
        print("\nTop candidates:")
        for idx, candidate in enumerate(top_candidates[:top_n], 1):
            print(
                f"{idx}. {candidate.get('symbol')} | net_profit={candidate.get('net_profit', 0):+.6f} "
                f"| risk={candidate.get('risk', 0):.2f} | funding={candidate.get('funding_rate', 0):+.4%}"
            )

    print("\nTop variants:")
    for idx, report in enumerate(ranked[:top_n], 1):
        score = report.get("score", {})
        print(
            f"{idx}. {report.get('variant'):<32} "
            f"| filtered={score.get('filtered_count', 0):<3} "
            f"| top_net={score.get('top_net_profit', 0.0):+.6f} "
            f"| avg_top_net={score.get('avg_top_net_profit', 0.0):+.6f}"
        )

    print("\nAggregate reject reasons:")
    for reason, count in aggregate_rejects(ranked).items():
        print(f"- {reason}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Summarize scanner sweep JSON results.")
    parser.add_argument("path", type=str, help="Path to sweep.json")
    parser.add_argument("--top", type=int, default=5, help="How many top variants/candidates to show")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        raise SystemExit(f"File not found: {args.path}")

    reports = load_reports(args.path)
    print_summary(reports, args.top)


if __name__ == "__main__":
    main()
