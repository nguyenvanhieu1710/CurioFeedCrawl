import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from .base import BaseEngine

class RSSEngine(BaseEngine):
    """
    Engine chuyên cào dữ liệu từ các luồng RSS (VD: VNExpress, Tuổi Trẻ, Spiderum).
    Tuyệt đối ổn định, không bao giờ bị block.
    """
    
    async def crawl(self, source: dict, **kwargs) -> List[Dict[str, Any]]:
        url = source.get("url")
        name = source.get("name")
        self.logger.info(f"⚡ Gọi RSS Feed: {name} ({url})")
        
        raw_posts = []
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        self.logger.error(f"❌ Lỗi HTTP {response.status} từ {url}")
                        return raw_posts
                        
                    xml_data = await response.text()
                    
                    # Tự động parse XML cơ bản
                    root = ET.fromstring(xml_data)
                    
                    # Tìm tất cả thẻ <item> (chuẩn RSS 2.0)
                    for item in root.findall(".//item"):
                        title = item.findtext("title") or ""
                        description = item.findtext("description") or ""
                        link = item.findtext("link") or url
                        
                        # Xóa các thẻ HTML trong description nếu có
                        import re
                        clean_desc = re.sub('<[^<]+>', '', description)
                        
                        full_content = f"{title}\n\n{clean_desc}"
                        
                        raw_posts.append({
                            "content": full_content.strip(),
                            "likes_count": 0,
                            "comments_count": 0,
                            "shares_count": 0,
                            "media_urls": [],
                            "source_url": link
                        })
                        
        except Exception as e:
            self.logger.error(f"❌ Lỗi khi cào RSS từ {name}: {str(e)}")
            
        return raw_posts
