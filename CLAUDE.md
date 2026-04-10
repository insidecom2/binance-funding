# CLAUDE PROJECT NOTES

อัปเดตล่าสุด: 2026-04-10
สถานะเอกสารนี้อิงจากโค้ดที่ใช้งานจริงในโปรเจกต์ ณ ตอนนี้

## ภาพรวมระบบปัจจุบัน

โปรเจกต์นี้เป็น Funding Rate Scanner สำหรับ Binance Futures โดย flow หลักที่รันจริงตอนนี้คือ

1. ดึงข้อมูล premium index ทุกคู่ที่ลงท้ายด้วย USDT
2. คัดเฉพาะ funding rate ที่อยู่ในช่วงเป้าหมาย 0.05% - 0.10%
3. ส่งต่อเข้า filter หลายชั้น (funding, risk, basis, volume, spread, net profit)
4. แสดงรายการที่ผ่านเงื่อนไข และเลือกเหรียญที่ดีที่สุด 1 ตัว

หมายเหตุสำคัญ:

- โมดูล forecast มีอยู่ในระบบแล้ว แต่ main flow ตอนนี้ยังไม่ได้เปิดใช้งานแบบ require forecast
- โมดูล trading orchestration ถูกสร้างไว้แล้ว แต่ยังไม่ได้เชื่อมเข้ากับ main flow

## STACK TECH

- Python3
- Telegram
- Binance API

## Main Runtime Behavior

ไฟล์คำสั่งหลักทำงานแบบ Scanner เป็นหลัก ยังไม่ยิง order จริง

พฤติกรรมหลัก:

- อ่านค่าคอนฟิก threshold จากตัวแปรคงที่ในโค้ด
- ดึงโอกาสจาก get_all_current_funding_opportunities
- เลือก top 5 ในช่วง funding ที่กำหนด
- เรียก filter_opportunities เพื่อจัดอันดับตามกำไรสุทธิและความเสี่ยง
- เรียก select_best_opportunity เพื่อหา best single symbol
- พิมพ์ผลลัพธ์ออกทาง console

## Filtering Logic ที่ใช้งานอยู่

เงื่อนไขหลักใน pipeline:

- funding_rate ต้องมากกว่าหรือเท่ากับ min_funding
- risk score (normalize แล้ว) ต้องไม่เกิน max_risk
- basis ต้องมากกว่าหรือเท่ากับ min_basis
- volume ต้องมากกว่าหรือเท่ากับ min_volume
- spread ต้องไม่เกิน max_spread
- net profit หลังหัก fee ต้องไม่ติดลบ (ยอม fallback ไปรอบที่ 2 ได้)

การจัดอันดับผลลัพธ์:

- เรียงตาม net_profit มากไปน้อย
- ถ้าเท่ากันใช้ risk ต่ำกว่าเป็นตัวชนะ
- ตามด้วย funding, basis, volume, spread เป็น tie-breaker

## Forecast Module Status

มีโค้ดรองรับ forecast แล้วใน internal funding

สิ่งที่มีอยู่แล้ว:

- linear regression forecasting จาก funding history
- metric ที่คำนวณได้: slope, intercept, r_squared, residual_std, predicted_next
- confidence gates: min points, min r2, max residual std
- helper สำหรับ enrich forecast แบบ parallel

สถานะ integration:

- ฟังก์ชันพร้อมใช้
- แต่ใน main flow ตอนนี้ยังเรียก scanner แบบปกติ (ไม่บังคับ forecast gate)

## Trading Execution Module Status

มีโมดูล orchestration สำหรับ futures short + spot long แล้ว

ความสามารถในโมดูล:

- คำนวณขนาด position ตาม position size, leverage, hedge ratio
- flow เปิดสถานะ 2 ขา (futures short + spot long)
- monitoring loop สำหรับ stop-loss, basis reversal, age timeout
- close position และสรุป PnL
- เขียน trade history ลงไฟล์ json

ข้อจำกัดปัจจุบัน:

- main flow ยังไม่เรียกใช้งาน module นี้
- BinanceFunding client ปัจจุบันยังเป็นแนว read API เป็นหลัก
- หากต้องการ live execution ต้องเติม authenticated order endpoints และ wiring เพิ่มใน main

## Config Snapshot (Current Defaults)

ค่าหลักในระบบตอนนี้:

- MIN_FUNDING = 0.0002
- MIN_BASIS = 0.0005
- MIN_VOLUME = 500000
- MAX_SPREAD = 0.004
- MAX_RISK = 0.5
- MAX_POSITION = 1000

ช่วง funding ที่ scanner ใช้คัดก่อนเข้า filter:

- min_rate = 0.0005
- max_rate = 0.0010

## สิ่งที่พร้อมใช้งานทันที

- Funding scanner แบบเต็มตลาด USDT futures
- Ranking opportunities ด้วย risk + basis + volume + spread + net profit
- Best opportunity selection

## สิ่งที่ยังต้องต่อให้ครบก่อนเทรดจริง

1. เพิ่ม authenticated trading methods ใน Binance client
2. เชื่อม TradeOrchestrator เข้า main flow พร้อมสวิตช์ dry run และ live
3. เพิ่มการจัดการ precision/step size/min notional ตาม symbol filter
4. เพิ่ม safety checks (balance, slippage, partial fill rollback)
5. เพิ่ม tests สำหรับ sizing, exit condition, และ error handling

## Recommended Next Step

เริ่มจาก phase ที่ปลอดภัยที่สุดก่อน:

- ทำ dry-run integration ใน main โดยไม่ยิง order จริง
- ตรวจ log output และ trade history ว่าตรรกะครบ
- ค่อยเปิด live execution เฉพาะ symbol เดียวและ notional ต่ำ
