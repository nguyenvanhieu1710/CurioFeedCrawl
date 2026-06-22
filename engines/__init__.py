from .base import BaseEngine
from .playwright_engine import PlaywrightEngine
from .json_engine import JSONEngine
from .rss_engine import RSSEngine

def get_engine(engine_type: str) -> BaseEngine:
    if engine_type == "playwright":
        return PlaywrightEngine()
    elif engine_type == "json":
        return JSONEngine()
    elif engine_type == "rss":
        return RSSEngine()
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
