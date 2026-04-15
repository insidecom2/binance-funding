#!/usr/bin/env python3
"""
Integration smoke test for binance-funding (phase-6)
Runs main.py in dry-run mode and asserts no errors in log/trade history.
"""
import os
import subprocess
import tempfile
import json
import sys

def main():
    # Use a temp file for trade history
    with tempfile.TemporaryDirectory() as tmp:
        history_path = os.path.join(tmp, "history.json")
        env = os.environ.copy()
        env["TRADING_ENABLED"] = "0"
        env["TRADING_DRY_RUN"] = "1"
        env["TRADE_HISTORY_PATH"] = history_path
        # Run main.py (dry-run)
        proc = subprocess.run([
            sys.executable, "cmd/main.py"
        ], env=env, capture_output=True, text=True, timeout=60)
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        assert proc.returncode == 0, "main.py exited with error"
        # Check trade history file
        if os.path.exists(history_path):
            with open(history_path) as f:
                history = json.load(f)
            assert isinstance(history, list), "Trade history is not a list"
            print(f"Trade history entries: {len(history)}")
        else:
            print("No trade history file generated.")

if __name__ == "__main__":
    main()
