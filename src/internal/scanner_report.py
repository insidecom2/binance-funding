from datetime import datetime, timezone
import json
import os

from src.internal.scanner_config import ScannerConfig


def build_scan_report(
    opportunities: list,
    analysis: dict,
    config: ScannerConfig,
    *,
    top_n: int = 10,
) -> dict:
    filtered = analysis.get("filtered", [])
    reject_counts = analysis.get("reject_counts", {})
    forecast_passed = 0
    for opp in opportunities:
        forecast = opp.get("funding_forecast") or {}
        if forecast.get("is_valid") and forecast.get("confidence_pass") and forecast.get("forecast_pass"):
            forecast_passed += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "opportunity_count": len(opportunities),
        "forecast_passed_count": forecast_passed,
        "filtered_count": len(filtered),
        "reject_counts": reject_counts,
        "config": {
            "min_funding": config.min_funding,
            "min_basis": config.min_basis,
            "min_volume": config.min_volume,
            "max_spread": config.max_spread,
            "max_risk": config.max_risk,
            "position_size": config.position_size,
            "require_forecast": config.require_forecast,
            "forecast_periods": config.forecast_periods,
            "forecast_edge": config.forecast_edge,
            "forecast_min_points": config.forecast_min_points,
            "forecast_min_r2": config.forecast_min_r2,
            "forecast_max_residual_std": config.forecast_max_residual_std,
            "forecast_max_relative_std": config.forecast_max_relative_std,
            "forecast_min_predicted": config.forecast_min_predicted,
        },
        "top_candidates": filtered[:top_n],
    }


def write_scan_report(path: str | None, report: dict) -> None:
    if not path:
        return

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(report, file_obj, indent=2, ensure_ascii=False, default=str)

    print(f"📝 Scan report written to {path}")
