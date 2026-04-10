#!/bin/bash

# Docker entrypoint for Binance Funding Rate Scanner (Linux-compatible)

set -e

cleanup() {
    echo
    echo "⏹️  Stopping Binance Funding Data Fetcher..."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 Starting Binance Funding Data Fetcher (aligned to minute boundary)..."
echo "▶️  Entering run loop..."

while true; do
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ▶️  Running application..."

    if python cmd/main.py "$@"; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ Run completed"
    else
        exit_code=$?
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  Run failed with exit code ${exit_code}; retrying next cycle"
    fi

    # Sleep until the next minute boundary (Linux-compatible)
    sleep_seconds=$(( 60 - 10#$(date +%S) ))
    [ "$sleep_seconds" -le 0 ] && sleep_seconds=1
    next_run=$(date -d "+${sleep_seconds} seconds" +'%H:%M:%S' 2>/dev/null || date -r $(( $(date +%s) + sleep_seconds )) +'%H:%M:%S')
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⏳ Sleeping for ${sleep_seconds}s (next run at ${next_run})..."
    echo "============================================================="
    sleep "$sleep_seconds"
done
