"""Offline admin router. The eval scores these calls without calling the model."""
import re

from .format import _clean, _fold

def _category_from_text(folded):
    if "may tinh bang" in folded or "tablet" in folded or "ipad" in folded:
        return "tablet"
    if "tai nghe" in folded:
        return "headphones"
    if "dong ho" in folded:
        return "smartwatch"
    if "laptop" in folded or "macbook" in folded:
        return "laptop"
    if "dien thoai" in folded or "iphone" in folded:
        return "phone"
    return ""


def _period_from_text(folded):
    if "hom nay" in folded or "ngay nay" in folded:
        return "today"
    if "tuan" in folded or "7 ngay" in folded:
        return "7d"
    if "thang" in folded or "30 ngay" in folded:
        return "30d"
    return "all"


def _lookup_query(question):
    folded = _fold(question)
    stop = {
        "bao", "nhieu", "may", "con", "hang", "ton", "kho", "san", "pham", "nao", "cua",
        "het", "duoi", "thap", "kiem", "tra", "xem", "cho", "toi", "minh", "cai", "nhung",
        "dang", "ban", "trong", "shop", "cua", "hang",
    }
    words = [word for word in re.findall(r"[a-z0-9]{2,}", folded) if word not in stop]
    return " ".join(words[:4])


def local_calls(question):
    folded = _fold(question)
    if re.search(r"cho duyet|ho tro|lien he|yeu cau", folded):
        return [("work_queue", {})]
    if re.search(r"ban chay|doanh thu|ban nhieu", folded):
        return [("sales_report", {"period": _period_from_text(folded), "category": _category_from_text(folded)})]
    if re.search(r"het hang|ton kho|duoi 10|sap het", folded):
        category = _category_from_text(folded)
        if "duoi 10" in folded or "sap het" in folded:
            return [("inventory_report", {"mode": "low", "category": category})]
        if "het hang" in folded:
            return [("inventory_report", {"mode": "out", "category": category})]
        query = _lookup_query(question)
        if query:
            return [("inventory_report", {"mode": "lookup", "query": query})]
        return [("inventory_report", {"mode": "out"}), ("inventory_report", {"mode": "low"})]
    if re.search(r"\bdon\b|don hang|trang thai", folded):
        found = re.search(r"(?:don|ma)\s*#?\s*(\d+)|#(\d+)", folded)
        if found:
            return [("order_report", {"mode": "one", "order_id": int(found.group(1) or found.group(2))})]
        if re.search(r"moi nhat|gan day|vua dat", folded):
            return [("order_report", {"mode": "recent"})]
        return [("order_report", {"mode": "status"})]
    named = _lookup_query(question)
    if named and re.search(r"con bao nhieu|ton kho|may nao", folded):
        return [("inventory_report", {"mode": "lookup", "query": named})]
    return [("store_summary", {})]
