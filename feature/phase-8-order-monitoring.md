# Phase 8: Order Monitoring & Forecast Pause

## เป้าหมาย

- เมื่อมีการเปิด order แล้ว ให้หยุดการ forecast/scan symbol ใหม่ชั่วคราว
- เปลี่ยน flow เป็น monitor order ที่เปิดอยู่ (spot/futures)
- ตรวจสอบสถานะ order ว่า match แล้วหรือยัง (filled/partially filled)
- เมื่อ order match (filled) ให้ส่ง noti แจ้งเตือนผ่าน Telegram
- รองรับทั้ง dry-run และ live mode

## Flow หลัก

1. เริ่มต้นด้วยการเปิด order (spot/futures) ตาม logic phase 7
2. เมื่อเปิด order แล้ว ให้หยุดการ forecast/scan symbol ใหม่ (pause auto-trade loop)
3. เข้าสู่ loop monitor order ที่เปิดอยู่

- ตรวจสอบสถานะ order (ผ่าน Binance API)
  - ถ้า order match (filled/partially filled):
    - อัปเดตสถานะ order ใน MySQL โดยใช้ table trade_history (status = 'match')
    - สร้าง table ใหม่ชื่อ funding_reward (ถ้ายังไม่มี) โดยมี trade_history_id เป็น foreign key
    - ทุกครั้งที่ได้รับ funding reward ให้ insert ข้อมูลลง funding_reward (เช่น reward_time, reward_amount, funding_rate, trade_history_id)
    - ส่ง noti Telegram
- ถ้ายังไม่ match ให้รอและเช็คซ้ำ (interval เช่น 10-30 วินาที)

4. เมื่อ order ทั้งหมด match แล้ว (หรือ timeout) ให้จบ loop monitoring
5. สามารถ resume forecast/auto-trade ได้หลัง monitoring จบ (optional)

## Logic เงื่อนไข

- หยุด forecast/scan symbol ใหม่ทันทีที่มี order เปิด
- ตรวจสอบสถานะ order ด้วย Binance API (ดู field เช่น status, filledQty)
- อัปเดตสถานะ order ใน MySQL เป็น 'match' เมื่อ order match (แยก spot/futures ได้)
- สร้าง table funding_reward (ถ้ายังไม่มี) โดยมี trade_history_id เป็น foreign key
- บันทึกข้อมูลการได้รับรางวัล funding (funding reward) ของ symbol นั้นลง funding_reward ทุกครั้งที่ได้รับ (ระหว่าง monitoring)
- ส่ง noti Telegram เมื่อ order match (แยก spot/futures ได้)
- รองรับ error handling (API error, network, order not found)
- รองรับ dry-run (mock order status)

## Implementation Steps

## ตัวอย่าง SQL Schema (funding_reward)

```sql
CREATE TABLE funding_reward (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  trade_history_id BIGINT NOT NULL,
  reward_time DATETIME NOT NULL,
  reward_amount DECIMAL(18,8) NOT NULL,
  funding_rate DECIMAL(10,8),
  remark VARCHAR(255),
  FOREIGN KEY (trade_history_id) REFERENCES trade_history(id)
);
```

1. เพิ่ม state/flag สำหรับ pause/resume forecast loop
2. หลังเปิด order ให้เข้าสู่ monitoring loop
3. ดึงสถานะ order (spot/futures) เป็นระยะ
4. เมื่อ order match:

- อัปเดตสถานะ order ใน MySQL โดยใช้ table trade_history (status = 'match')
- สร้าง table funding_reward (ถ้ายังไม่มี) โดยมี trade_history_id เป็น foreign key
- ทุกครั้งที่ได้รับ funding reward ให้ insert ข้อมูลลง funding_reward
- ส่ง noti Telegram

5. รองรับ resume/exit monitoring ตาม config หรือ timeout

### คำแนะนำเพิ่มเติม (Best Practice)

- **ควร reuse ฟังก์ชัน monitoring, polling, order status check, error handling, และ notification จาก phase 5 (Monitoring & PnL)**
  - เช่น ถ้ามีฟังก์ชัน monitor_position, monitor_order, หรือ event-driven callback สำหรับ order filled ใน phase 5 ให้นำมาใช้หรือปรับใช้กับ phase 8
- **ควร reuse ฟังก์ชัน send_telegram_message และ TradeOrchestrator จาก phase 7**
- ไม่ควร duplicate logic monitoring/notification ใหม่ ให้แยกเป็น utility หรือเรียกใช้ร่วมกัน
- หากต้องการ mock order status สำหรับ dry-run ให้แยก logic mock ไว้ชัดเจน
- เพิ่ม unit test สำหรับ monitoring loop และ notification

## Todo

- [ ] เพิ่ม state/flag สำหรับ pause/resume forecast/auto-trade
- [ ] หลังเปิด order ให้ pause forecast แล้วเข้าสู่ monitoring loop
- [ ] ตรวจสอบสถานะ order (spot/futures) เป็นระยะ
- [ ] อัปเดตสถานะ order ใน MySQL โดยใช้ table trade_history (status = 'match') เมื่อ order match
- [ ] สร้าง table funding_reward (ถ้ายังไม่มี) โดยมี trade_history_id เป็น foreign key
- [ ] ทุกครั้งที่ได้รับ funding reward ให้ insert ข้อมูลลง funding_reward
- [ ] ส่ง noti Telegram เมื่อ order match
- [ ] รองรับ error handling และ dry-run
- [ ] ทดสอบ flow ทั้งหมด (dry-run/live)
