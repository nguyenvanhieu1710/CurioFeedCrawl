"""
CurioFeed - Scheduler (Bộ lập lịch tự động)
Chạy crawler theo lịch định kỳ mỗi 6 giờ bằng APScheduler.

Sử dụng:
    python scheduler.py
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# ===== Cấu hình =====
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Tạo thư mục logs nếu chưa có
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Cấu hình logging: ghi ra cả console và file
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# File handler - ghi log vào file, xoay vòng theo ngày
file_handler = logging.FileHandler(
    LOGS_DIR / "scheduler.log",
    encoding="utf-8",
    mode="a",  # Append mode
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Root logger cho scheduler
logger = logging.getLogger("curiofeed.scheduler")
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)
logger.addHandler(file_handler)



async def scheduled_crawl_job():
    """
    Job chạy theo lịch: crawl tất cả nguồn và lưu vào MongoDB.
    Được APScheduler gọi tự động mỗi 6 giờ.
    """
    # Import ở đây để tránh circular import
    from crawler import crawl_all_sources

    start_time = datetime.now(timezone.utc)
    logger.info(f"{'='*60}")
    logger.info(f"⏰ BẮT ĐẦU CRAWL ĐỊNH KỲ - {start_time.isoformat()}")
    logger.info(f"{'='*60}")

    try:
        # crawl_all_sources đã bao gồm cả việc lưu DB bên trong
        await crawl_all_sources(test_mode=False)
        logger.info("✅ Crawl định kỳ hoàn tất!")

    except Exception as e:
        logger.error(f"❌ Lỗi trong quá trình crawl định kỳ: {e}", exc_info=True)

    finally:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        logger.info(f"⏱️ Thời gian chạy: {duration:.1f} giây")
        logger.info(f"{'='*60}\n")


def main():
    """Khởi chạy scheduler với lịch crawl mỗi 6 giờ."""
    logger.info("🚀 Khởi động CurioFeed Scheduler...")
    logger.info(f"📁 Thư mục gốc: {BASE_DIR}")
    logger.info(f"📝 Log file: {LOGS_DIR / 'scheduler.log'}")

    # Tạo event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Khởi tạo scheduler
    scheduler = AsyncIOScheduler(event_loop=loop)

    # Đăng ký job crawl mỗi 6 giờ
    scheduler.add_job(
        scheduled_crawl_job,
        trigger=IntervalTrigger(hours=6),
        id="crawl_all_sources",
        name="CurioFeed - Crawl tất cả nguồn",
        max_instances=1,                  # Chỉ cho phép 1 instance chạy cùng lúc
        replace_existing=True,
        next_run_time=datetime.now(),     # Chạy ngay lần đầu khi khởi động
    )

    logger.info("📅 Đã đăng ký job: crawl mỗi 6 giờ")
    logger.info("   Lần chạy đầu tiên: ngay bây giờ")

    # Xử lý tắt chương trình an toàn (graceful shutdown)
    shutdown_event = asyncio.Event()

    def handle_shutdown(sig, frame):
        sig_name = signal.Signals(sig).name
        logger.info(f"\n🛑 Nhận tín hiệu {sig_name} - Đang tắt scheduler...")
        scheduler.shutdown(wait=False)
        shutdown_event.set()

    # Đăng ký handler cho SIGINT (Ctrl+C) và SIGTERM
    signal.signal(signal.SIGINT, handle_shutdown)
    # SIGTERM chỉ có trên Unix, bỏ qua trên Windows
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    # Khởi chạy scheduler
    scheduler.start()
    logger.info("✅ Scheduler đang chạy. Nhấn Ctrl+C để dừng.\n")

    try:
        loop.run_until_complete(shutdown_event.wait())
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n🛑 Đang tắt scheduler...")
        scheduler.shutdown(wait=False)
    finally:
        # Dọn dẹp event loop
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        logger.info("👋 Scheduler đã dừng. Tạm biệt!")


if __name__ == "__main__":
    main()
