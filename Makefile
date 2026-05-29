.PHONY: test-scanner-safe test-integration-smoke test-tooling-smoke

test-scanner-safe:
	.venv/bin/python -m unittest \
		tests.internal.test_filter_opportunities \
		tests.internal.test_funding_forecast \
		tests.internal.test_scanner \
		tests.internal.test_scanner_config \
		tests.internal.test_scanner_report \
		tests.internal.test_trade_history \
		tests.integration.test_main_entrypoint_smoke \
		tests.integration.test_pnl_summary_entrypoint_smoke \
		tests.integration.test_sweep_tools \
		tests.integration.test_compare_scan_reports \
		tests.integration.test_confirm_candidates

test-integration-smoke:
	.venv/bin/python -m unittest \
		tests.integration.test_main_entrypoint_smoke \
		tests.integration.test_pnl_summary_entrypoint_smoke

test-tooling-smoke:
	.venv/bin/python -m unittest \
		tests.integration.test_sweep_tools \
		tests.integration.test_compare_scan_reports \
		tests.integration.test_confirm_candidates
