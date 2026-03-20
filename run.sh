#!/bin/bash

# Binance Funding Rate Data Fetcher
# Run the main Python application

set -e  # Exit on error

echo "🚀 Starting Binance Funding Data Fetcher..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade requirements
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run the main application with any passed arguments
echo "▶️  Running application..."
python cmd/main.py "$@"