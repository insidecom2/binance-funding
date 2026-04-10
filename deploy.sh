# ก่อน deploy ต้องสร้าง cache file ว่างก่อน (ไม่งั้น Docker mount เป็น directory)
touch .telegram_notify_cache.json

# stop docker container ถ้ามีอยู่แล้ว
docker compose down

# Build และรัน
docker compose up -d --build

# ดู log
docker compose logs -f binance-funding