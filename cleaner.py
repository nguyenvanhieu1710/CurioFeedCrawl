"""
CurioFeed - Bộ làm sạch dữ liệu bài viết (Data Cleaner)
Lọc và chuẩn hoá nội dung bài viết thu thập từ Facebook.
"""

import hashlib
import re
import unicodedata
import html


def generate_content_hash(content: str) -> str:
    """
    Tạo SHA256 hash từ nội dung bài viết.
    Dùng để phát hiện bài trùng lặp (duplicate detection).
    """
    normalized = content.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_only_urls(text: str) -> bool:
    """Kiểm tra xem nội dung chỉ toàn URL hay không."""
    # Xoá tất cả URL ra khỏi text
    url_pattern = r"https?://\S+"
    remaining = re.sub(url_pattern, "", text).strip()
    # Nếu sau khi xoá URL không còn gì → chỉ toàn link
    return len(remaining) == 0


def _is_only_hashtags(text: str) -> bool:
    """Kiểm tra xem nội dung chỉ toàn hashtag hay không."""
    hashtag_pattern = r"#\w+"
    remaining = re.sub(hashtag_pattern, "", text).strip()
    return len(remaining) == 0


def _has_too_many_special_chars(text: str, threshold: float = 0.4) -> bool:
    """
    Kiểm tra nội dung có quá nhiều ký tự đặc biệt không.
    Nếu tỷ lệ ký tự đặc biệt > threshold → có thể là text bị lỗi mã hoá.
    """
    if not text:
        return True
    # Ký tự "bình thường": chữ cái, số, khoảng trắng, dấu câu tiếng Việt cơ bản
    normal_chars = re.findall(r"[\w\s.,!?;:\-–—\"'()…]", text, re.UNICODE)
    ratio = 1 - (len(normal_chars) / len(text))
    return ratio > threshold


def _strip_excessive_whitespace(text: str) -> str:
    """Loại bỏ khoảng trắng và xuống dòng thừa."""
    # Thay nhiều dòng trống liên tiếp bằng 1 dòng
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Thay nhiều khoảng trắng liên tiếp (trên cùng 1 dòng) bằng 1
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    return text.strip()


def _normalize_unicode(text: str) -> str:
    """Chuẩn hoá Unicode về dạng NFC (quan trọng cho tiếng Việt)."""
    return unicodedata.normalize("NFC", text)


def clean_post(post_dict: dict) -> dict | None:
    """
    Làm sạch và lọc một bài viết.

    Args:
        post_dict: Dict chứa thông tin bài viết (phải có key 'content').

    Returns:
        Dict bài viết đã làm sạch, hoặc None nếu bài bị lọc bỏ.
    """
    content = post_dict.get("content", "")

    if not content or not isinstance(content, str):
        return None

    # Bước 0: Giải mã HTML Entities
    content = html.unescape(content)

    # Bước 1: Chuẩn hoá Unicode (NFC) cho tiếng Việt
    content = _normalize_unicode(content)

    # Bước 2: Loại bỏ khoảng trắng thừa
    content = _strip_excessive_whitespace(content)

    # Bước 3: Lọc bài quá ngắn (< 50 ký tự)
    if len(content) < 50:
        return None

    # Bước 4: Lọc bài chỉ toàn URL
    if _is_only_urls(content):
        return None

    # Bước 5: Lọc bài chỉ toàn hashtag
    if _is_only_hashtags(content):
        return None

    # Bước 6: Lọc bài có quá nhiều ký tự đặc biệt (text bị lỗi)
    if _has_too_many_special_chars(content):
        return None

    # Bài đạt yêu cầu → cập nhật content đã làm sạch và thêm hash
    cleaned = post_dict.copy()
    cleaned["content"] = content
    cleaned["content_hash"] = generate_content_hash(content)

    return cleaned
