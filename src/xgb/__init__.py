"""
XGBoost Machine Learning Module for Funding Rate Trading
========================================================

This module provides XGBoost-powered risk assessment, multi-round sustainability
predictions, and comprehensive fee analysis for Binance funding rate arbitrage.
"""

from .risk_predictor import (
    create_xgb_risk_features,
    predict_xgb_risk, 
    predict_multi_round_sustainability,
    get_multi_round_recommendation,
    calculate_net_profit_with_fees,
    get_optimal_timing
)

__all__ = [
    'create_xgb_risk_features',
    'predict_xgb_risk',
    'predict_multi_round_sustainability', 
    'get_multi_round_recommendation',
    'calculate_net_profit_with_fees',
    'get_optimal_timing'
]