import time
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================
MIN_FUNDING = 0.0005
MIN_FUNDING_EXIT = 0
MIN_BASIS = 0
MIN_BASIS_EXIT = -0.001
MIN_VOLUME = 1_000_000
MAX_SPREAD = 0.002
MIN_PROFIT = 0.0002

RISK_PER_TRADE = 0.1
MAX_POSITION = 1000
MAX_LOSS = 0.02
MAX_HOLD = timedelta(hours=8)

ENTRY_WINDOW = timedelta(minutes=15)
CONFIDENCE_THRESHOLD = 0.6
TAKE_PROFIT = 0.01

current_position = None

# =========================
# MOCK / PLACEHOLDER API
# =========================
def get_all_symbols():
    return ["BTCUSDT", "ETHUSDT"]

def get_funding_rate(symbol):
    return 0.001  # mock

def get_basis(symbol):
    return 0.002  # mock

def get_volume(symbol):
    return 2_000_000  # mock

def get_spread(symbol):
    return 0.001  # mock

def get_fee(symbol):
    return 0.0004

def estimate_slippage(symbol):
    return 0.0002

def get_balance():
    return 10000

def get_spot_price(symbol):
    return 100

def get_future_price(symbol):
    return 100

def get_next_funding_time():
    now = datetime.utcnow()
    return now + timedelta(hours=1)

def predict_funding(symbol):
    return 0.7  # mock AI

# =========================
# EXECUTION MOCK
# =========================
def place_spot_buy(symbol, size):
    return {"filled": True, "price": get_spot_price(symbol)}

def place_future_short(symbol, size):
    return {"filled": True, "price": get_future_price(symbol)}

def sell_spot(symbol, size):
    return {"filled": True}

def close_future_short(symbol, size):
    return {"filled": True}

def cancel_all_orders():
    print("Cancel all orders")

# =========================
# CORE LOGIC
# =========================
def calc_expected_profit(symbol):
    funding = get_funding_rate(symbol)
    fee = get_fee(symbol)
    slippage = estimate_slippage(symbol)
    return funding - (fee * 2 + slippage)

def calculate_position_size():
    balance = get_balance()
    size = balance * RISK_PER_TRADE
    return min(size, MAX_POSITION)

def calculate_pnl(position):
    spot_pnl = get_spot_price(position["symbol"]) - position["entry_spot"]
    future_pnl = position["entry_future"] - get_future_price(position["symbol"])
    return (spot_pnl + future_pnl) / position["entry_spot"]

def both_filled(o1, o2):
    return o1["filled"] and o2["filled"]

def rollback_orders():
    cancel_all_orders()
    print("Order mismatch rollback")

# =========================
# ENTRY
# =========================
def handle_entry(symbol, time_to_funding):
    global current_position

    if symbol is None:
        return

    if time_to_funding > ENTRY_WINDOW:
        return

    size = calculate_position_size()

    spot = place_spot_buy(symbol, size)
    future = place_future_short(symbol, size)

    if not both_filled(spot, future):
        rollback_orders()
        return

    current_position = {
        "symbol": symbol,
        "size": size,
        "entry_time": datetime.utcnow(),
        "entry_spot": spot["price"],
        "entry_future": future["price"],
        "funding_time": get_next_funding_time()
    }

    print(f"Entered position: {symbol}")

# =========================
# EXIT
# =========================
def close_position(position):
    global current_position

    sell_spot(position["symbol"], position["size"])
    close_future_short(position["symbol"], position["size"])

    print("Closed position")
    current_position = None

# =========================
# MAINTAIN
# =========================
def handle_maintain(position, time_to_funding):
    symbol = position["symbol"]

    funding = get_funding_rate(symbol)
    basis = get_basis(symbol)
    pnl = calculate_pnl(position)

    # funding invalid
    if funding < MIN_FUNDING_EXIT:
        close_position(position)
        return

    # funding received
    if datetime.utcnow() > position["funding_time"]:
        if pnl > TAKE_PROFIT:
            close_position(position)
            return
        position["funding_time"] = get_next_funding_time()

    # risk
    if pnl < -MAX_LOSS:
        close_position(position)
        return

    # basis collapse
    if basis < MIN_BASIS_EXIT:
        close_position(position)
        return

    # max hold
    if datetime.utcnow() - position["entry_time"] > MAX_HOLD:
        close_position(position)
        return

# =========================
# MAIN LOOP
# =========================
def main():
    global current_position

    while True:
        funding_time = get_next_funding_time()
        time_to_funding = funding_time - datetime.utcnow()

        candidates = []

        for sym in get_all_symbols():
            funding = get_funding_rate(sym)
            basis = get_basis(sym)
            volume = get_volume(sym)
            spread = get_spread(sym)

            if funding < MIN_FUNDING:
                continue
            if basis < MIN_BASIS:
                continue
            if volume < MIN_VOLUME:
                continue
            if spread > MAX_SPREAD:
                continue

            expected_profit = calc_expected_profit(sym)
            if expected_profit < MIN_PROFIT:
                continue

            if predict_funding(sym) < CONFIDENCE_THRESHOLD:
                continue

            candidates.append((sym, expected_profit))

        best_symbol = max(candidates, key=lambda x: x[1])[0] if candidates else None

        if current_position is None:
            handle_entry(best_symbol, time_to_funding)
        else:
            handle_maintain(current_position, time_to_funding)

        time.sleep(60)


if __name__ == "__main__":
    main()