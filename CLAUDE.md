# CLAUDE PROJECT NOTES

อัปเดตล่าสุด: 2026-04-20

## ภาพรวมระบบ

Funding Rate Scanner และ Trading Bot สำหรับ Binance Futures
Strategy: **Short Futures + Long Spot** (delta-neutral hedge) เพื่อรับ funding payment ทุก 8 ชั่วโมง

## Stack

- Python 3
- Binance Futures + Spot API
- XGBoost (risk scoring)
- MySQL (trade/funding log)
- Telegram (notification)

---

## โครงสร้างไฟล์หลัก

```
cmd/main.py                   # Entry point (phase7_forecast_auto_trade)
src/binance/binance_funding.py # Binance API client
src/internal/filter.py         # Filter pipeline (7 gates)
src/internal/funding.py        # Funding scanner + forecast enrichment
src/internal/trading.py        # TradeOrchestrator (ยังไม่ได้เปิดใช้งาน)
src/internal/basis.py          # Basis calculation
src/internal/spread.py         # Spread calculation
src/internal/volume.py         # Volume fetching
src/internal/mysql_logger.py   # MySQL logging
src/xgb/risk_predictor.py      # XGBoost risk + fee calculation
```

---

## สถานะการทำงานปัจจุบัน

| ส่วน | สถานะ |
|---|---|
| Funding Scanner | ✅ ทำงานอยู่ |
| Filter Pipeline (7 gates) | ✅ ทำงานอยู่ |
| Forecast Module | ✅ เปิดใช้งาน (`REQUIRE_FORECAST=true`) |
| MySQL Logging (funding_logs) | ✅ เปิดใช้งาน |
| Telegram Notification | ✅ เปิดใช้งาน |
| Trading Execution | ❌ ปิดอยู่ (`TRADING_ENABLED=false`) |
| Dry Run Mode | ✅ เปิดอยู่ (`TRADING_DRY_RUN=true`) |
| MySQL Trade History | ❌ ปิดอยู่ (`MYSQL_TRADES_ENABLED=false`) |

---

## Filter Pipeline — 7 Gates (เรียงตามลำดับ)

ทุก gate ใช้ `continue` — ถ้าไม่ผ่านจะถูก reject ทันที

| # | Gate | ค่า (hardcode ใน main.py) | หมายเหตุ |
|---|---|---|---|
| 1 | `funding_rate >=` | **0.0007 (0.07%)** | floor สำหรับ break-even ที่ 10 รอบ |
| 2 | `forecast` | optional (`REQUIRE_FORECAST`) | confidence_pass + forecast_pass ต้องผ่านทั้งคู่ |
| 3 | `risk score <=` | **0.5** | XGBoost normalized score |
| 4 | `basis >=` | **0.0002 (0.02%)** | futures premium over spot |
| 5 | `volume >=` | **500,000** | 1h kline volume (USDT) |
| 6 | `spread <=` | **0.002 (0.2%)** | mark vs index spread |
| 7 | `net_profit >= 0` | best of 10 rounds | รวม spot fee + spread cost |

`select_best_opportunity(filtered)` คืน `filtered[0]` เลย (sorted แล้ว)

---

## Fee Calculation (ครบทุกต้นทุน)

```python
# calculate_net_profit_with_fees(position_size, funding_rate, rounds, spread)
futures_taker = 0.04% per side
spot_taker    = 0.10% per side  ← สำคัญ ต้องนับ spot ด้วย
total_fees    = position_size × (0.0004 + 0.001) × 2  = $2.80 ต่อ $1,000
spread_cost   = position_size × spread × 2
total_cost    = total_fees + spread_cost
net_profit    = (funding_rate × rounds × position_size) - total_cost
```

**Break-even reference ($1,000 position, spread 0.2%)**

| Rounds | ระยะเวลา | funding rate ที่ต้อง break-even |
|---|---|---|
| 2 | 16 ชม. | 0.34% |
| 5 | 40 ชม. | 0.136% |
| 10 | 80 ชม. | **0.068%** ← ใช้เป็น MIN_FUNDING |

---

## Forecast Module

**ฟังก์ชัน**: `get_next_funding_forecast()` ใน `src/internal/funding.py`

**ทำงานอย่างไร**: Linear regression บน funding rate history 20 periods

**Confidence Gate** (ต้องผ่านทุกข้อ):
- `points_used >= 6`
- `r_squared >= 0.05`
- `residual_std <= 0.0012`
- `relative_std <= 1.5`

**Forecast Gate** (ต้องผ่านทั้งคู่):
- `predicted_next >= current_rate + (-0.0001)`
- `predicted_next >= 0.0001`

**Enrichment**: ทำแบบ parallel ด้วย `ThreadPoolExecutor` ก่อนส่งเข้า filter

---

## Thresholds ใน .env (override ค่า hardcode ได้)

```bash
MIN_BASIS=0.0005              # override MIN_BASIS ใน main.py
MIN_VOLUME=20000              # override MIN_VOLUME ใน main.py (ต่ำกว่า hardcode!)
REQUIRE_FORECAST=true
FORECAST_PERIODS=20
FORECAST_EDGE=-0.0001
FORECAST_MIN_POINTS=6
FORECAST_MIN_R2=0.05
FORECAST_MAX_RESIDUAL_STD=0.0012
FORECAST_MAX_RELATIVE_STD=1.5
FORECAST_MIN_PREDICTED=0.0001
MAX_MINUTES_TO_FUNDING=60     # ข้อมูล info เท่านั้น ไม่ใช่ hard gate
```

> ⚠️ **หมายเหตุ**: `MIN_VOLUME` ใน `.env` = 20,000 ต่ำกว่า hardcode 500,000 มาก
> ต้องตรวจสอบว่าตั้งใจหรือไม่

---

## ข้อควรระวัง (Gotchas)

### 1. Invalid Symbol Error (400 -1121)
Bulk `premiumIndex` call คืน symbol ที่กำลัง delisting กลับมาด้วย
พอเรียก `klines` / `premiumIndex` แบบ individual จะได้ 400 -1121
**แก้แล้ว**: `get_basis`, `get_volume`, `get_spread` ทุกตัว try/except → return None → reject ที่ filter

### 2. Timing Gate ถูกลบออกจาก Filter แล้ว
`max_minutes_to_funding` ไม่ใช่ hard gate อีกต่อไป
แสดงเป็น `minutes_to_funding` ใน candidate เท่านั้น
ถ้าต้องการ gate ต้องทำที่ execution layer

### 3. `filter_opportunities` vs `select_best_opportunity`
`select_best_opportunity(filtered)` รับเฉพาะ `filtered` list (ผ่าน filter แล้ว)
**อย่า** ส่ง raw `opportunities` เข้า `select_best_opportunity`

### 4. Spot Fee ต้องนับใน net profit
fee เดิมนับแค่ futures ($0.80) — แก้แล้วให้นับ spot ด้วย ($2.80 รวม)

---

## Trading Orchestration (ยังไม่ได้เปิด)

`src/internal/trading.py` — `TradeOrchestrator`

ความสามารถที่มีแล้ว:
- คำนวณขนาด position (futures qty + spot qty)
- เปิด 2 ขา: SELL futures + BUY spot
- Retry + rollback ถ้า leg ใด leg หนึ่งล้มเหลว
- Monitoring loop: stop-loss, basis reversal, age timeout
- ปิด position + คำนวณ realized PnL
- บันทึก trade history (JSON + MySQL)

**ก่อนเปิดใช้งาน live trading ต้องทำ**:
1. ใส่ `BINANCE_API_KEY` และ `BINANCE_SECRET_KEY` ใน `.env`
2. ตั้ง `TRADING_ENABLED=true`
3. ตั้ง `TRADING_DRY_RUN=false` เมื่อพร้อม live
4. ตรวจสอบ precision/step size ผ่าน `src/internal/symbol_rules.py`
5. ทดสอบ dry-run ให้ครบก่อน

---

## MySQL Tables

| Table | เนื้อหา | สถานะ |
|---|---|---|
| `funding_logs` | symbol ที่ผ่าน forecast gate (current, next, delta, r2) | ✅ Active |
| `trade_history` | entry/exit event, order IDs, PnL, exit_reason | ❌ Disabled |

---

## Binance API Endpoints ที่ใช้

| Endpoint | วัตถุประสงค์ |
|---|---|
| `GET /fapi/v1/premiumIndex` (no symbol) | ดึง funding rate ทุก symbol ในคราวเดียว |
| `GET /fapi/v1/premiumIndex?symbol=X` | basis + spread (individual) |
| `GET /fapi/v1/fundingRate` | history สำหรับ forecast |
| `GET /fapi/v1/klines` | volume |
| `GET /fapi/v1/exchangeInfo` | symbol filters (step size, min notional) |

Authenticated endpoints (order placement) มีอยู่ในโค้ดแต่ยังไม่ได้ใช้งาน
