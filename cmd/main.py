import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.internal.scanner import run_scanner
from src.internal.scanner_config import build_scanner_config

load_dotenv()


def main() -> None:
    config = build_scanner_config(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    print("🤖 Binance Funding Forecast Scanner")
    print("🔍 Scanning opportunities without trade execution")
    print(f"🧠 Forecast gate required: {config.require_forecast}")

    try:
        run_scanner(config)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(0)
    except Exception as exc:
        print(f"❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
