import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseEngine

class JSONEngine(BaseEngine):
    """
    Engine chuyên gọi API trực tiếp lấy dữ liệu JSON (VD: Reddit).
    Tốc độ cực nhanh, không cần giả lập trình duyệt.
    """
    
    async def crawl(self, source: dict, **kwargs) -> List[Dict[str, Any]]:
        url = source.get("url")
        name = source.get("name")
        self.logger.info(f"⚡ Gọi JSON API: {name} ({url})")
        
        raw_posts = []
        
        try:
            # Fake headers để không bị chặn. Reddit đặc biệt chặn gắt nếu User-Agent chung chung.
            # Đổi sang cấu trúc: <platform>:<app ID>:<version> (by /u/<username>)
            headers = {
                "User-Agent": "web:curiofeed.crawler:v1.0.0 (by /u/curiofeed_dev)",
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        self.logger.error(f"❌ Lỗi HTTP {response.status} từ {url}")
                        return raw_posts
                        
                    data = await response.json()
                    
                    # Hiện tại Engine này hỗ trợ parse đặc thù của Reddit và DummyJSON
                    if "reddit.com" in url:
                        raw_posts = self._parse_reddit_json(data, url)
                    elif "dummyjson.com" in url:
                        raw_posts = self._parse_dummy_json(data, url)
                    else:
                        self.logger.warning("⚠️ Chưa hỗ trợ cấu trúc JSON này.")
                        
        except Exception as e:
            self.logger.error(f"❌ Lỗi khi cào JSON từ {name}: {str(e)}")
            
        return raw_posts
        
    def _parse_dummy_json(self, data: dict, base_url: str) -> List[Dict[str, Any]]:
        posts = []
        try:
            posts_list = data.get("posts", [])
            for p in posts_list:
                posts.append({
                    "content": p.get("body", ""),
                    "likes_count": p.get("reactions", {}).get("likes", 0) if isinstance(p.get("reactions"), dict) else p.get("reactions", 0),
                    "comments_count": 0,
                    "shares_count": 0,
                    "media_urls": [],
                    "source_url": f"https://dummyjson.com/posts/{p.get('id')}"
                })
        except Exception as e:
            self.logger.error(f"Lỗi khi parse DummyJSON: {str(e)}")
        return posts
        
    def _parse_reddit_json(self, data: dict, base_url: str) -> List[Dict[str, Any]]:
        posts = []
        try:
            # Reddit trả về { "data": { "children": [ { "data": { ... } } ] } }
            children = data.get("data", {}).get("children", [])
            for child in children:
                post_data = child.get("data", {})
                
                # Bỏ qua bài ghim hoặc quảng cáo
                if post_data.get("stickied") or post_data.get("promoted"):
                    continue
                    
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                
                # Nối title và nội dung
                full_content = f"{title}\n\n{selftext}" if selftext else title
                
                permalink = post_data.get("permalink", "")
                post_url = f"https://www.reddit.com{permalink}" if permalink else base_url
                
                # Hình ảnh / Video
                media_urls = []
                url_field = post_data.get("url", "")
                if url_field and url_field.endswith((".jpg", ".png", ".gif")):
                    media_urls.append(url_field)
                    
                posts.append({
                    "content": full_content.strip(),
                    "likes_count": post_data.get("score", 0),
                    "comments_count": post_data.get("num_comments", 0),
                    "shares_count": 0,
                    "media_urls": media_urls,
                    "source_url": post_url
                })
        except Exception as e:
            self.logger.error(f"Lỗi khi parse Reddit JSON: {str(e)}")
            
        return posts
