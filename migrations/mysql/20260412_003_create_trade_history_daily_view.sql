-- Daily trading summary view
-- Provides quick monitoring for PnL and execution quality.

CREATE OR REPLACE VIEW `v_trade_history_daily_summary` AS
SELECT
  DATE(`event_time`) AS `trade_date`,
  `symbol`,
  `is_dry_run`,
  COUNT(*) AS `records_total`,
  SUM(CASE WHEN `event_type` = 'ENTRY' THEN 1 ELSE 0 END) AS `entry_records`,
  SUM(CASE WHEN `event_type` = 'EXIT' THEN 1 ELSE 0 END) AS `exit_records`,
  SUM(CASE WHEN `success` = 1 THEN 1 ELSE 0 END) AS `successful_records`,
  SUM(CASE WHEN `success` = 0 THEN 1 ELSE 0 END) AS `failed_records`,
  SUM(COALESCE(`realized_pnl`, 0)) AS `realized_pnl_sum`,
  SUM(COALESCE(`expected_pnl`, 0)) AS `expected_pnl_sum`,
  AVG(CASE WHEN `realized_pnl` IS NOT NULL THEN `realized_pnl` END) AS `avg_realized_pnl`,
  AVG(CASE WHEN `expected_pnl` IS NOT NULL THEN `expected_pnl` END) AS `avg_expected_pnl`,
  SUM(COALESCE(`fee_futures`, 0)) AS `fee_futures_sum`,
  SUM(COALESCE(`fee_spot`, 0)) AS `fee_spot_sum`,
  SUM(COALESCE(`fee_total`, 0)) AS `fee_total_sum`,
  AVG(CASE WHEN `fee_total` IS NOT NULL THEN `fee_total` END) AS `avg_fee_total`
FROM `trade_history`
GROUP BY DATE(`event_time`), `symbol`, `is_dry_run`;
