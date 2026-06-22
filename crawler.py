import os
import json
import asyncio
import argparse
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

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

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/curiofeed")
DATABASE_NAME = os.getenv("DATABASE_NAME", "curiofeed")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

async def save_posts_to_db(posts: list[dict], source_name: str, test_mode: bool = False):
    """
    Làm sạch, check trùng lặp và lưu bài viết vào MongoDB
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
            cleaned_post["created_at"] = datetime.now(timezone.utc)
            cleaned_post["crawled_at"] = datetime.now(timezone.utc)
            valid_posts.append(cleaned_post)

    if test_mode:
        print("\n" + "="*50)
        logger.info(f"✅ Hoàn tất! Tổng cộng {len(valid_posts)} bài viết hợp lệ.")
        print("="*50 + "\n")
        print("📋 KẾT QUẢ TEST:\n")
        for i, p in enumerate(valid_posts[:5]): # In tối đa 5 bài
            print(f"--- Bài {i+1} ---")
            print(f"Hash: {p['content_hash']}")
            print(f"Content: {p['content'][:200]}...")
            print(f"Link: {p['permalink']}")
            print(f"Reactions: {p['reactions']} | Nguồn: {p['source_name']} | Nền tảng: {p['platform']}\n")
        return len(valid_posts)

    # Lưu vào Database
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        collection = db.posts

        saved_count = 0
        duplicate_count = 0

        for post in valid_posts:
            try:
                # Dùng content_hash làm _id hoặc index unique để chống trùng lặp
                await collection.update_one(
                    {"content_hash": post["content_hash"]},
                    {"$setOnInsert": post},
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                if "duplicate key error" in str(e).lower():
                    duplicate_count += 1
                else:
                    logger.error(f"  ❌ Lỗi khi lưu DB: {str(e)}")

        client.close()
        logger.info(f"  💾 Đã lưu: {saved_count} bài mới (Bỏ qua {duplicate_count} bài trùng lặp).")
        return saved_count

    except Exception as e:
        logger.error(f"❌ Lỗi kết nối MongoDB: {str(e)}")
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
            
            # Làm sạch và lưu DB
            await save_posts_to_db(raw_posts, source_name, test_mode)
            
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
