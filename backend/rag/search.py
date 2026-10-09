"""Embed the question with the same model as the documents, then read Qdrant."""
import re

from .settings import DOC_TYPE_KEYS, MIN_SCORE
from .documents import brand_key
from .embed import embed_texts, public_error

# Catalog brands whose terms were not crawled. A hit from another brand must not answer them.
_GAP_BRANDS = (
    "philips", "baseus", "sennheiser", "razer", "havit", "jbl", "nokia", "amazfit",
    "motorola", "sony", "lenovo", "msi", "huawei", "garmin", "asus", "kidcare",
    "thunderobot", "gigabyte", "masstel",
)


_INDEXED = (
    ("apple", ("iphone", "ipad", "macbook", "apple", "beats", "airpods")),
    ("samsung", ("samsung", "galaxy")),
    ("xiaomi", ("xiaomi", "redmi")),
    ("oppo", ("oppo",)),
    ("vivo", ("vivo",)),
    ("honor", ("honor",)),
    ("realme", ("realme",)),
    ("acer", ("acer",)),
    ("logitech", ("logitech",)),
    ("dell", ("dell",)),
)


def indexed_brand(query):
    text = (query or "").casefold()
    for key, names in _INDEXED:
        for name in names:
            if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", text):
                return key
    return ""


def gap_brand(query):
    """A known catalog brand in the question whose terms were never crawled."""
    text = (query or "").casefold()
    for name in _GAP_BRANDS:
        if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", text):
            return name
    if re.search(r"(?<![a-z0-9])hp(?![a-z0-9])", text):
        return "hp"
    return ""


_CATALOG_NAMES = None


def _catalog_brand_names():
    """Live catalog brands. Empty when the database cannot be read, and not cached then."""
    global _CATALOG_NAMES
    if _CATALOG_NAMES is not None:
        return _CATALOG_NAMES
    try:
        from .documents import connect

        conn = connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT brand FROM products WHERE is_live_catalog AND btrim(brand) <> ''"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []
    _CATALOG_NAMES = [row[0] for row in rows if row and row[0]]
    return _CATALOG_NAMES


def _named_unindexed_brand(query):
    """A brand written in the question that has no terms in the index.

    The denylist is only the brands already known to be missing. Any other live
    catalog brand, such as Marshall or Tecno, is the same kind of gap.
    """
    if indexed_brand(query):
        return ""
    named = gap_brand(query)
    if named:
        return named
    text = (query or "").casefold()
    indexed_keys = {item[0] for item in _INDEXED}
    found = ""
    found_len = 0
    for name in _catalog_brand_names():
        bare = re.sub(r"\s*\([^)]*\)\s*$", "", name.casefold()).strip()
        if len(bare) < 2:
            continue
        if not re.search(r"(?<![a-z0-9])" + re.escape(bare) + r"(?![a-z0-9])", text):
            continue
        key = brand_key(bare)
        if key in indexed_keys:
            continue
        if len(bare) > found_len:
            found = key or bare
            found_len = len(bare)
    return found


def apple_line(query):
    text = (query or "").casefold()
    if "iphone" in text or "ipad" in text:
        return "iphone"
    if "macbook" in text or re.search(r"(?<![a-z0-9])mac(?![a-z0-9])", text):
        return "mac"
    if "apple watch" in text or "đồng hồ" in text:
        return "watch"
    if "beats" in text or "airpods" in text:
        return "accessory"
    return ""


def search_documents(query, brand="", doc_type="warranty", limit=4):
    """Passages for a policy question. An empty list means the index has no matching terms."""
    query = " ".join((query or "").split())
    if not query:
        return {"note": "Thiếu câu hỏi.", "passages": []}
    if doc_type not in DOC_TYPE_KEYS:
        doc_type = "warranty"
    key = brand_key(brand) if (brand or "").strip() else ""
    if key and key not in {item[0] for item in _INDEXED}:
        return {
            "note": "Không có điều khoản của hãng này trong kho. Đừng lấy điều khoản hãng khác.",
            "passages": [],
        }
    if not key:
        if _named_unindexed_brand(query):
            return {
                "note": "Không có điều khoản của hãng này trong kho. Đừng lấy điều khoản hãng khác.",
                "passages": [],
            }
        key = indexed_brand(query)
    line = apple_line(query) if key == "apple" else ""
    try:
        vector = embed_texts([query])[0]
        from .vectors import query_passages

        hits = query_passages(vector, doc_type=doc_type, brand_key=key, line=line, limit=limit)
    except Exception as exc:
        return {
            "note": "Chưa đọc được kho tài liệu. {0}".format(public_error(exc)),
            "passages": [],
        }
    kept = [hit for hit in hits if hit["score"] >= MIN_SCORE]
    if not kept:
        if key:
            note = "Không có điều khoản của hãng này trong kho. Đừng lấy điều khoản hãng khác."
        else:
            note = "Không có đoạn điều khoản đủ gần. Đừng suy từ hãng khác hoặc từ câu mô tả trên trang sản phẩm."
        return {"note": note, "passages": []}
    return {
        "note": (
            "Chỉ được kể các đoạn dưới đây. "
            "Nếu scope không đúng nhóm máy khách hỏi, nói chưa có điều khoản cho nhóm đó."
        ),
        "passages": kept,
    }
