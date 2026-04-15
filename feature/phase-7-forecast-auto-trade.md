# Phase 7: Forecast-Driven Auto Trade

## เป้าหมาย

- เลือก symbol ที่มีโอกาสกำไรสูงสุดจากการ forecast funding rate
- เปิดสถานะเทรด (futures short + spot long) อัตโนมัติทันทีที่พบโอกาส
- ใช้ logic risk/basis/volume/spread/net profit + forecast pass
- รองรับ dry-run และ live mode

## Flow หลัก (ควร reuse logic เดิม)

1. ดึง funding opportunities ทั้งตลาด (get_all_current_funding_opportunities)
2. enrich ด้วย forecast (enrich_opportunities_with_forecast)
3. filter ด้วย filter_opportunities (reuse logic risk/basis/volume/spread/net profit/forecast pass)
4. เลือก symbol ที่ดีที่สุดด้วย select_best_opportunity (tie-breaker: net profit, risk, basis, volume)
5. เปิดสถานะเทรดผ่าน TradeOrchestrator.execute_spot_futures_trade
6. หลังเปิด order ให้ insert ข้อมูล order ลง MySQL โดยใช้ table trade_history (เพิ่ม/อัปเดต field status = 'order')
7. log ผลลัพธ์และแจ้งเตือน (console/telegram)
8. หากไม่มี symbol ผ่าน filter ให้แจ้งเตือน (console/telegram)

## Logic เงื่อนไข (ควรเหมือน main flow)

- forecast pass: is_valid, confidence_pass, forecast_pass == True
- net profit > 0
- risk <= max_risk, basis >= min_basis, volume >= min_volume, spread <= max_spread
- ใช้ config เดิมจาก main flow (MIN_BASIS, MIN_VOLUME, MAX_SPREAD, MAX_RISK ฯลฯ)
- เรียก filter_opportunities และ select_best_opportunity เพื่อความสอดคล้อง

## Implementation Steps

1. เพิ่มฟังก์ชัน phase7_forecast_auto_trade() ใน cmd/main.py หรือแยกไฟล์ใหม่
2. ใช้ TradeOrchestrator และ BinanceFunding ที่ wiring ไว้แล้ว
3. enrich forecast ด้วย config ครบถ้วน (min_points, r2, std ฯลฯ)
4. filter ด้วย filter_opportunities (reuse logic)
5. เลือก symbol ที่ดีที่สุดด้วย select_best_opportunity
6. เปิดสถานะเทรดผ่าน orchestrator (รองรับ dry-run/live)
7. หลังเปิด order ให้ insert ข้อมูล order ลง MySQL โดยใช้ table trade_history (เพิ่ม/อัปเดต field status = 'order')
8. log trade history และแจ้งเตือน (console/telegram)
9. หากไม่มี symbol ผ่าน filter ให้แจ้งเตือน (console/telegram)
10. ตรวจสอบ error handling ครบถ้วน (เช่น orchestrator, telegram, forecast enrich)

## Todo

- [ ] เพิ่มฟังก์ชัน phase7_forecast_auto_trade()
- [ ] enrich forecast ให้ทุก symbol (config ครบ)
- [ ] filter ด้วย filter_opportunities (reuse logic)
- [ ] เลือก symbol ที่ดีที่สุดด้วย select_best_opportunity
- [ ] เปิดสถานะเทรดผ่าน orchestrator (dry-run/live)
- [ ] log ผลลัพธ์และแจ้งเตือน (console/telegram)
- [ ] insert ข้อมูล order ลง MySQL โดยใช้ table trade_history (เพิ่ม/อัปเดต field status = 'order')
- [ ] แจ้งเตือนกรณีไม่มี symbol ผ่าน filter
- [ ] ตรวจสอบ error handling orchestrator/telegram/forecast enrich
- [ ] ทดสอบ dry-run
- [ ] ทดสอบ live (notional ต่ำ)
