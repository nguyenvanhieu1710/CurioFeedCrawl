from abc import ABC, abstractmethod
import logging

class BaseEngine(ABC):
    def __init__(self):
        self.logger = logging.getLogger(f"curiofeed.engine.{self.__class__.__name__}")

    @abstractmethod
    async def crawl(self, source: dict, **kwargs) -> list[dict]:
        """
        Crawl data from a source.
        
        Args:
            source (dict): Dictionary chứa thông tin nguồn từ sources.json (ví dụ: url, name)
            
        Returns:
            list[dict]: Danh sách các bài post chưa qua làm sạch (raw_posts).
                        Mỗi post nên có dạng:
                        {
                            "content": str,
                            "likes_count": int,
                            "comments_count": int,
                            "shares_count": int,
                            "media_urls": list[str],
                            "source_url": str
                        }
        """
        pass
