#!/bin/bash

# Binance Funding Rate Data Fetcher
# Run the main Python application every minute

set -e  # Exit on error

cleanup() {
    echo
    echo "⏹️  Stopping Binance Funding Data Fetcher..."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 Starting Binance Funding Data Fetcher (1-minute interval)..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade requirements only when needed
REQ_HASH_FILE=".venv/.requirements.sha256"
CURRENT_REQ_HASH="$(shasum -a 256 requirements.txt | awk '{print $1}')"
SAVED_REQ_HASH=""

if [ -f "$REQ_HASH_FILE" ]; then
    SAVED_REQ_HASH="$(cat "$REQ_HASH_FILE")"
fi

if ! command -v pip >/dev/null 2>&1 || [ "$CURRENT_REQ_HASH" != "$SAVED_REQ_HASH" ]; then
    echo "📥 Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "$CURRENT_REQ_HASH" > "$REQ_HASH_FILE"
else
    echo "✅ Dependencies unchanged, skipping install."
fi

# Run the main application every minute with any passed arguments
echo "▶️  Entering run loop (every 60 seconds)..."
while true; do
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ▶️  Running application..."

    # Keep looping even if one iteration fails.
    if python cmd/main.py "$@"; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ Run completed"
    else
        exit_code=$?
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  Run failed with exit code ${exit_code}; retrying in 60 seconds"
    fi

    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⏳ Sleeping for 60 seconds..."
    sleep 60
done