# Phase 9: Order Risk Monitoring & Auto-Close

**เป้าหมาย:**

- หลังเปิดออเดอร์ (futures/spot) ให้ระบบ monitor ออเดอร์นั้นอย่างต่อเนื่อง
- ประเมินความเสี่ยงและกำไรสุทธิจาก funding, basis, spread, unrealized PnL
- ถ้าพบว่าออเดอร์เริ่มเสี่ยง (risk score สูง, basis กลับทิศ, unrealized PnL ติดลบเกิน threshold) หรือ funding ไม่คุ้ม ให้ปิดออเดอร์ทั้งสองขาอัตโนมัติ
- แจ้งเตือน Telegram ทุกครั้งที่มีการปิดออเดอร์ด้วยเหตุผลด้านความเสี่ยง

**Flow หลัก:**

1. หลังเปิดออเดอร์สำเร็จ → เข้าสู่ monitoring loop (reuse phase-5/phase-8)
2. ทุก INTERVAL_MONITOR_SEC (60 วินาที):
   - ดึงข้อมูล funding, basis, unrealized PnL, risk score ของออเดอร์ปัจจุบัน
   - ประเมินตามเกณฑ์ (configurable):
     - risk score > max_risk
     - unrealized PnL < max_loss
     - basis < min_basis
     - funding rate ลดลงต่ำกว่า min_funding
   - ถ้าเข้าเงื่อนไขใดเงื่อนไขหนึ่ง → ปิดออเดอร์ทั้งสองขา
   - ส่ง Telegram แจ้งเตือน พร้อมเหตุผลที่ปิด
   - อัปเดตสถานะ order ใน MySQL โดยใช้ table trade_history (status = 'close')
   - เมื่อไม่มี order ที่ถืออยู่แล้ว ให้กลับเข้าสู่ loop forecast/auto-trade เพื่อหาโอกาสใหม่
3. ถ้าออเดอร์ยังปลอดภัยและ funding ยังดี → continue monitoring

**สิ่งที่ควร reuse:**

- ฟังก์ชัน monitoring loop, risk assessment, และ exit condition จาก phase-5
- ฟังก์ชันแจ้งเตือน Telegram จาก phase-7/8
- ฟังก์ชัน orchestrator สำหรับ close position

**Config ที่ควรมี:**

- INTERVAL_MONITOR_SEC = 60
- MAX_RISK, MAX_LOSS, MIN_BASIS, MIN_FUNDING (override ได้จาก .env)
- ENABLE_AUTO_CLOSE (เปิด/ปิดฟีเจอร์นี้)

**Todo/Checklist:**

- [ ] เพิ่ม config ที่จำเป็น
- [ ] เพิ่มฟังก์ชัน monitor_order_risk() (reuse จาก phase-5)
- [ ] เพิ่ม logic ประเมิน risk/exit condition
- [ ] เชื่อม orchestrator สำหรับ close position
- [ ] อัปเดตสถานะ order ใน MySQL โดยใช้ table trade_history (status = 'close') เมื่อปิดออเดอร์
- [ ] อัปเดตสถานะ order ใน MySQL โดยใช้ table trade_history (status = 'close') เมื่อปิดออเดอร์
- [ ] แจ้งเตือน Telegram เมื่อปิดออเดอร์
- [ ] ทดสอบ dry-run และ live
