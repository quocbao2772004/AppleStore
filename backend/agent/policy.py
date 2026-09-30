"""Offline gate used by route() for eval and for the no-API fallback.

The live chat does not consult this file. With an API key, the model chooses
the tool and Python only executes it.
"""

import re

from .slots import _signals

CHAT_REPLY = (
    "Mình là trợ lý của Octopus Store. "
    "Mình tìm máy, so sánh hai máy, xem còn hàng, xem đơn của bạn và đặt giúp. "
    "Bạn đang cần điện thoại, laptop, tai nghe, máy tính bảng hay đồng hồ?"
)

_SMALLTALK_RE = re.compile(
    r"xin chào|chào bạn|chào shop|chào anh|chào chị|chào buổi|"
    r"\bchào\b|\bhello\b|\bhi\b|\bhey\b|"
    r"cảm ơn|cám ơn|cam on|thank you|\bthanks\b|"
    r"bạn là ai|ban la ai|bạn tên|mày là ai|"
    r"làm được gì|lam duoc gi|giúp được gì|giup duoc gi|"
    r"thời tiết|thoi tiet|kể chuyện|ke chuyen|chuyện cười|chuyen cuoi|"
    r"bao nhiêu tuổi|bao nhieu tuoi",
    re.I,
)
_SHOPPING_RE = re.compile(
    r"tư vấn|tu van|giới thiệu|gioi thieu|gợi ý|goi ý|goi y|"
    r"máy nào|may nao|có máy|co may|mua gì|mua gi|"
    r"cần máy|can may|muốn mua|muon mua|xem hàng|tìm máy|tim may",
    re.I,
)
_SIGNAL_KEYS = (
    "category",
    "query",
    "color",
    "brand",
    "use",
    "price_min",
    "price_max",
    "price_target",
    "ram_gb",
    "min_ram",
    "storage_gb",
    "screen",
    "line",
    "variant",
    "chip",
    "family",
    "order_id",
)


def has_catalog_signal(question):
    """True when this sentence itself names a product, a price, or an order id."""
    signal = _signals(question)
    if signal.get("specific") or signal.get("priorities"):
        return True
    return any(signal.get(key) for key in _SIGNAL_KEYS)


def needs_tool(question):
    """True when the sentence is about the catalog, an order, or a purchase.

    Action words such as đặt, so sánh, and xóa are decided in route().
    This function only stops a sentence with no catalog cue from becoming a search.
    """
    if has_catalog_signal(question):
        return True
    text = question or ""
    if _SMALLTALK_RE.search(text):
        return False
    if _SHOPPING_RE.search(text):
        return True
    return False
