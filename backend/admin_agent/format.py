"""Labels and Vietnamese folding shared by the admin reports."""
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
CATEGORIES = {
    "phone": "Điện thoại",
    "laptop": "Laptop",
    "tablet": "Máy tính bảng",
    "headphones": "Tai nghe",
    "smartwatch": "Đồng hồ",
}
STATUS_LABEL = {
    "placed": "Đã đặt",
    "packing": "Đang xử lý",
    "done": "Hoàn tất",
    "cancelled": "Đã hủy",
}
SLOT_LABEL = {"morning": "sáng", "afternoon": "chiều", "evening": "tối"}
PERIODS = {"today", "7d", "30d", "all"}

def _money(value):
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,}".replace(",", ".") + "₫"


def _fold(text):
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return plain.casefold().replace("đ", "d")


def _clean(text, limit=80):
    return re.sub(r"\s+", " ", (text or "").replace("%", "").replace("_", "")).strip()[:limit]


def _when(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZONE)
        return value.astimezone(ZONE).strftime("%d.%m.%Y %H:%M")
    return value.strftime("%d.%m.%Y")


def _period_start(period):
    now = datetime.now(ZONE)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    return None


def _period_label(period):
    return {"today": "hôm nay", "7d": "7 ngày qua", "30d": "30 ngày qua"}.get(period, "toàn bộ")


def _pay_label(method):
    return "Chuyển khoản trên máy" if method == "qr" else "Khi nhận hàng"


def _clip(text, limit=160):
    body = re.sub(r"\s+", " ", (text or "")).strip()
    if len(body) <= limit:
        return body
    return body[: limit - 1].rstrip() + "…"
