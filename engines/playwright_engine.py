from playwright.async_api import async_playwright, BrowserContext
from typing import List, Dict, Any
import asyncio
import random
from .base import BaseEngine

class PlaywrightEngine(BaseEngine):
    """
    Engine sử dụng Playwright để giả lập trình duyệt.
    Dành cho các trang web yêu cầu render JS hoặc có cơ chế chống bot mạnh như Facebook.
    """
    
    POST_SELECTORS = [
        'article',
        'div.story_body_container',
        'div[data-sigil="story-div"]',
        'div[role="article"]',
    ]
    
    POST_TEXT_SELECTORS = [
        'div[data-sigil="m-feed-voice-subtitle"]',
        'div.story_body_container > div > span',
        'div[data-ad-preview="message"]',
        'span[data-sigil="expose"]',
        'p',
    ]

    REACTION_SELECTORS = [
        'div[data-sigil="reactions-sentence-container"]',
        'span[data-sigil="reactions-sentence-container"]',
        'a[data-sigil="touchable"] span',
    ]

    PERMALINK_SELECTORS = [
        'a.touchable[href*="/story.php"]',
        'a[href*="/posts/"]',
        'a[href*="/permalink/"]',
    ]

    def _random_delay(self, min_sec=2.0, max_sec=5.0) -> float:
        return random.uniform(min_sec, max_sec)

    async def crawl(self, source: dict, **kwargs) -> List[Dict[str, Any]]:
        url = source.get("url")
        name = source.get("name")
        headless = kwargs.get("headless", True)
        
        self.logger.info(f"🕸️ Khởi chạy Playwright: {name} ({url})")
        raw_posts = []
        
        try:
            async with async_playwright() as p:
                # Mở trình duyệt ẩn (chống phát hiện bot bằng argument args)
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                
                # Tạo ngữ cảnh giống người dùng mobile
                context = await browser.new_context(
                    viewport={"width": 375, "height": 812},
                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                )
                
                raw_posts = await self._crawl_page(context, url, name)
                
                await browser.close()
                
        except Exception as e:
            self.logger.error(f"❌ Lỗi khi cào bằng Playwright từ {name}: {str(e)}")
            
        return raw_posts

    async def _crawl_page(self, context: BrowserContext, page_url: str, page_name: str) -> List[Dict[str, Any]]:
        page = await context.new_page()
        raw_posts = []
        
        try:
            # Ưu tiên giao diện m.facebook.com
            mobile_url = page_url.replace("www.facebook.com", "m.facebook.com")
            await page.goto(mobile_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(self._random_delay(3.0, 6.0))

            # Tự động cuộn trang
            scrolls = random.randint(3, 5)
            self.logger.info(f"  📜 Cuộn trang {scrolls} lần...")
            for i in range(scrolls):
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(self._random_delay())
                except Exception as e:
                    self.logger.warning(f"  ⚠️ Trình duyệt đóng đột ngột khi đang cuộn: {e}")
                    break

            # Bóc tách HTML (Lấy tất cả các thẻ có khả năng là Post)
            post_elements = []
            for selector in self.POST_SELECTORS:
                elements = await page.query_selector_all(selector)
                if elements:
                    post_elements = elements
                    break
                    
            if not post_elements:
                self.logger.warning(f"  ⚠️ Không tìm thấy bài viết bằng selector chính. Thử parse toàn trang.")
                post_elements = await page.query_selector_all('div')

            # Trích xuất dữ liệu từ các elements tìm được
            for element in post_elements:
                # Text
                content = ""
                for selector in self.POST_TEXT_SELECTORS:
                    text_el = await element.query_selector(selector)
                    if text_el:
                        content = await text_el.inner_text()
                        break
                        
                if not content:
                    content = await element.inner_text()
                
                # Số lượt thích (ước lượng lấy số đầu tiên)
                likes_count = 0
                for selector in self.REACTION_SELECTORS:
                    like_el = await element.query_selector(selector)
                    if like_el:
                        like_text = await like_el.inner_text()
                        try:
                            # Lọc số từ chuỗi "1.2K Thích", "500", v.v...
                            num_str = ''.join(filter(str.isdigit, like_text))
                            if num_str:
                                likes_count = int(num_str)
                        except ValueError:
                            pass
                        break

                # Link bài viết
                permalink = page_url
                for selector in self.PERMALINK_SELECTORS:
                    link_el = await element.query_selector(selector)
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            if href.startswith("/"):
                                permalink = f"https://m.facebook.com{href}"
                            else:
                                permalink = href
                        break

                raw_posts.append({
                    "content": content,
                    "likes_count": likes_count,
                    "comments_count": 0,
                    "shares_count": 0,
                    "media_urls": [],
                    "source_url": permalink
                })
                
        except Exception as e:
            self.logger.error(f"  ❌ Lỗi khi phân tích trang {page_name}: {str(e)}")
        finally:
            await page.close()
            
        return raw_posts
