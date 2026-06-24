import os
import json
import asyncio
import argparse
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from confluent_kafka import Producer

from cleaner import clean_post, generate_content_hash
from engines import get_engine

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("curiofeed.crawler.orchestrator")

# Load biến môi trường ưu tiên .env.local
load_dotenv(".env.local")
load_dotenv(".env")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "curiofeed.new_articles")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Khởi tạo Kafka Producer
kafka_conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': 'curiofeed-crawler'
}
try:
    producer = Producer(kafka_conf)
except Exception as e:
    logger.error(f"❌ Không thể khởi tạo Kafka Producer: {str(e)}")
    producer = None

async def publish_posts_to_kafka(posts: list[dict], source_name: str, test_mode: bool = False):
    """
    Làm sạch và đẩy bài viết vào Kafka
    """
    if not posts:
        logger.warning(f"  ❌ Không tìm thấy bài viết nào trên {source_name}")
        return 0

    valid_posts = []
    for raw_post in posts:
        # Map dữ liệu thô sang đúng Schema của MongoDB (NestJS Schema)
        post_data = {
            "content": raw_post.get("content", ""),
            "reactions": str(raw_post.get("likes_count", "0")),
            "comments_count": str(raw_post.get("comments_count", "0")),
            "shares_count": str(raw_post.get("shares_count", "0")),
            "image_urls": raw_post.get("media_urls", []),
            "video_urls": [],
            "source_name": source_name,
            "source_url": "", 
            "permalink": raw_post.get("source_url", ""),
            "platform": "facebook" if "facebook" in raw_post.get("source_url", "") else ("reddit" if "reddit" in raw_post.get("source_url", "") else "api")
        }

        # Làm sạch bài viết
        cleaned_post = clean_post(post_data)
        if cleaned_post:
            # Kafka cần JSON serializable datetime
            cleaned_post["created_at"] = datetime.now(timezone.utc).isoformat()
            cleaned_post["crawled_at"] = datetime.now(timezone.utc).isoformat()
            valid_posts.append(cleaned_post)

    if test_mode:
        print("\n" + "="*50)
        logger.info(f"✅ Hoàn tất! Tổng cộng {len(valid_posts)} bài viết hợp lệ.")
        print("="*50 + "\n")
        print("📋 KẾT QUẢ TEST (SẼ ĐƯỢC ĐẨY VÀO KAFKA):\n")
        for i, p in enumerate(valid_posts[:5]): # In tối đa 5 bài
            print(f"--- Bài {i+1} ---")
            print(f"Hash: {p['content_hash']}")
            print(f"Content: {p['content'][:200]}...")
            print(f"Link: {p['permalink']}")
            print(f"Reactions: {p['reactions']} | Nguồn: {p['source_name']} | Nền tảng: {p['platform']}\n")
        return len(valid_posts)

    if not producer:
        logger.error("  ❌ Kafka Producer chưa được khởi tạo!")
        return 0

    # Lưu vào Kafka
    try:
        published_count = 0
        for post in valid_posts:
            # Đẩy message, dùng content_hash làm message key để xử lý deduplication hoặc partitioning nếu cần
            producer.produce(
                KAFKA_TOPIC,
                key=post["content_hash"],
                value=json.dumps(post).encode('utf-8')
            )
            published_count += 1

        # Chờ flush hết tất cả message lên broker
        producer.flush()
        logger.info(f"  🚀 Đã đẩy: {published_count} bài lên Kafka Topic '{KAFKA_TOPIC}'.")
        return published_count

    except Exception as e:
        logger.error(f"❌ Lỗi kết nối Kafka: {str(e)}")
        return 0


async def crawl_all_sources(test_mode: bool = False):
    """
    Hàm tổng điều phối: Đọc file cấu hình và gọi Engine tương ứng
    """
    try:
        with open("sources.json", "r", encoding="utf-8") as f:
            sources = json.load(f)
    except Exception as e:
        logger.error(f"❌ Lỗi khi đọc sources.json: {str(e)}")
        return

    if test_mode:
        sources = sources[:2]  # Lấy 1 hoặc 2 nguồn để test
        logger.info("🧪 Chế độ test: chỉ crawl tối đa 2 nguồn")

    logger.info(f"🚀 Bắt đầu crawl {len(sources)} nguồn...")

    for i, source in enumerate(sources):
        source_name = source.get("name", "Unknown")
        engine_type = source.get("engine", "playwright")  # Mặc định dùng Playwright nếu không khai báo
        
        print("\n" + "="*50)
        logger.info(f"[{i+1}/{len(sources)}] Crawling: {source_name} (Engine: {engine_type.upper()})")
        print("="*50)

        try:
            # Lấy Engine tương ứng (Factory pattern)
            engine = get_engine(engine_type)
            
            # Khởi chạy cào dữ liệu thô
            raw_posts = await engine.crawl(source, headless=HEADLESS)
            
            # Làm sạch và đẩy lên Kafka
            await publish_posts_to_kafka(raw_posts, source_name, test_mode)
            
        except Exception as e:
            logger.error(f"❌ Lỗi không xác định khi cào nguồn {source_name}: {str(e)}")

        # Đợi 1 chút giữa các nguồn để tránh spam
        if not test_mode and i < len(sources) - 1:
            await asyncio.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CurioFeed Multi-Engine Crawler")
    parser.add_argument("--test", action="store_true", help="Chạy thử nghiệm trên 1 nguồn và in ra console, không lưu DB")
    args = parser.parse_args()

    asyncio.run(crawl_all_sources(test_mode=args.test))
