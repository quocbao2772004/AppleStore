"""Read a customer sentence into catalog slots. This step does not query the database."""
import re

from .constants import CATEGORIES, HEADPHONE_BRANDS, LAPTOP_BRANDS
from .debug import debug

_CHEAPEST_RE = re.compile(
    r"rẻ nhất|re nhat|rẻ hơn|re hon|mẫu nào rẻ|mau nao re|giá rẻ nhất|gia re nhat|"
    r"con nào rẻ|máy nào rẻ|may nao re"
)

def _money_phrase(folded):
    price_max = None
    price_min = None
    under = re.search(r"dưới\s+(\d+(?:[.,]\d+)?)\s*(triệu|tr)\b", folded)
    if under:
        price_max = int(float(under.group(1).replace(",", ".")) * 1_000_000)
    over = re.search(r"trên\s+(\d+(?:[.,]\d+)?)\s*(triệu|tr)\b", folded)
    if over:
        price_min = int(float(over.group(1).replace(",", ".")) * 1_000_000)
    return price_min, price_max


def _million(raw):
    return int(float(raw.replace(",", ".")) * 1_000_000)


def budget_stretch(text):
    """'Cố thêm 2 triệu' raises the current ceiling. It is not a new price of 2 triệu."""
    match = re.search(
        r"(?:cố thêm|co them)\s+(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b",
        (text or "").casefold(),
    )
    if not match:
        return None
    return _million(match.group(1))


def _budget_phrase(folded):
    """tầm / khoảng là mức xoay quanh, không phải trần cứng như dưới.

    "25 triệu" đứng một mình cũng là mức xoay quanh. "dưới" và "trên" giữ nguyên
    là trần hoặc sàn. "20 đến 25 triệu" là một khoảng. "Cố thêm" không phải một giá mới.
    """
    if budget_stretch(folded):
        return None, None, None
    span = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:đến|den|tới|toi)\s*(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b",
        folded,
    )
    if span:
        low = _million(span.group(1))
        high = _million(span.group(2))
        if low > high:
            low, high = high, low
        return low, high, None
    price_min, price_max = _money_phrase(folded)
    price_target = None
    around = re.search(
        r"(?:tầm giá|tam gia|ngân sách|ngan sach|khoảng|khoang|tầm|tam)\s+(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b",
        folded,
    )
    if around:
        price_target = _million(around.group(1))
    if price_min is None and price_max is None and price_target is None:
        bare = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b", folded)
        if bare:
            price_target = _million(bare.group(1))
    return price_min, price_max, price_target


def _priority_phrase(folded):
    priorities = []
    if re.search(r"ưu tiên\s+ram|uu tien\s+ram|nhiều ram|nhieu ram|ram cao|ram lớn|ram lon", folded):
        priorities.append("ram")
    elif re.search(r"ưu tiên.{0,16}ram|uu tien.{0,16}ram", folded):
        priorities.append("ram")
    if re.search(r"ưu tiên\s+pin|uu tien\s+pin|pin trâu|pin trau|pin lâu|pin lau|pin tốt|pin tot", folded):
        priorities.append("battery")
    elif re.search(r"ưu tiên.{0,16}pin|uu tien.{0,16}pin", folded):
        priorities.append("battery")
    if re.search(r"ưu tiên.{0,16}(?:camera|chụp ảnh|chup anh)|(?:camera|chụp ảnh|chup anh).{0,16}là chính", folded):
        priorities.append("camera")
    return priorities


def _color_phrase(folded):
    for phrase in ("xô thơm", "xo thom", "xanh lá", "xanh la", "xanh dương", "xanh duong", "xanh", "đen", "den", "trắng", "trang", "hồng", "hong", "tím", "tim", "vàng", "vang", "bạc", "bac", "cam"):
        if (re.search(r"\bcam\b", folded) if phrase == "cam" else phrase in folded):
            return phrase
    return ""


_AI_STUDY_RE = re.compile(
    r"học\s*ai|hoc\s*ai|học(?:\s+\w+){0,4}\s+ai|hoc(?:\s+\w+){0,4}\s+ai|"
    r"trí tuệ|tri tue|machine learning|deep learning|học máy|hoc may|"
    r"\bcuda\b|\bgpu\b|"
    r"(?:lập trình|lap trinh|\bcoding\b|\bcode\b).{0,16}\bai\b|"
    r"\bai\b.{0,16}(?:lập trình|lap trinh|\bcoding\b|\bcode\b)"
)
_OFFICE_RE = re.compile(
    r"kế toán|ke toan|văn phòng|van phong|\bexcel\b|\bword\b|powerpoint|"
    r"hành chính|hanh chinh|soạn thảo|soan thao"
)


def demands_ai(text):
    """True when the shopper asked for AI, CUDA, or a GPU workload. Plain coding is not AI."""
    return _AI_STUDY_RE.search((text or "").casefold()) is not None


def office_work(text):
    """Accounting and office work are not the AI-laptop path."""
    folded = (text or "").casefold()
    return _OFFICE_RE.search(folded) is not None and not demands_ai(folded)


def _use_phrase(folded):
    if office_work(folded):
        if any(word in folded for word in ("chơi game", "choi game", "game tốt", "game tot", "cấu hình mạnh")):
            return "gaming"
        return ""
    if demands_ai(folded):
        return "study"
    if any(word in folded for word in ("chơi game", "choi game", "game tốt", "game tot", "cấu hình mạnh")):
        return "gaming"
    return ""


def _category_phrase(folded, use):
    if any(word in folded for word in ("máy tính bảng", "may tinh bang", "tablet", "ipad")) or "galaxy tab" in folded:
        return "tablet"
    if any(word in folded for word in ("laptop", "macbook", "máy tính", "may tinh")):
        return "laptop"
    if "tai nghe" in folded:
        return "headphones"
    if "đồng hồ" in folded or "dong ho" in folded or re.search(r"\bwatch\b", folded):
        return "smartwatch"
    if any(word in folded for word in ("điện thoại", "dien thoai", "điên thoại", "iphone")):
        return "phone"
    if use == "study":
        return "laptop"
    return ""


def _iphone_line(text):
    """'phone 16' and '16 pro max' become a line key. A bare budget does not."""
    folded = (text or "").casefold()
    folded = folded.replace("promax", "pro max")
    folded = re.sub(r"\b(?:iphone|phone|ip)\b", "iphone", folded)
    folded = re.sub(r"\s+", " ", folded)
    match = re.search(r"iphone\s*(1[0-9])\s*(pro max|pro|plus|e)?", folded)
    # "16 pro max cơ" still names that iPhone. A MacBook 16 Pro does not.
    if not match and not re.search(r"macbook|laptop|máy tính|may tinh", folded):
        match = re.search(r"(?:^|[^0-9])(1[0-9])\s*(pro max|plus|e)\b", folded)
        if not match:
            match = re.search(r"(?:^|[^0-9])(1[0-9])\s*(pro)\b", folded)
    if not match:
        return ""
    suffix = match.group(2) or ""
    return match.group(1) + ((" " + suffix) if suffix else "")


def _named_iphone(text):
    line = _iphone_line(text)
    if not line:
        return ""
    number, _, suffix = line.partition(" ")
    if suffix == "e":
        return "iPhone " + number + "e"
    if suffix == "pro max":
        return "iPhone " + number + " Pro Max"
    if suffix == "pro":
        return "iPhone " + number + " Pro"
    if suffix == "plus":
        return "iPhone " + number + " Plus"
    return "iPhone " + number


def _family_phrase(folded):
    if "macbook" in folded:
        return "MacBook"
    if "iphone" in folded:
        return "iPhone"
    if "ipad" in folded:
        return "iPad"
    return ""


_BRAND_NEEDLES = (
    ("macbook", "MacBook"),
    ("asus", "Asus"),
    ("dell", "Dell"),
    ("lenovo", "Lenovo"),
    ("acer", "Acer"),
    ("gigabyte", "GIGABYTE"),
    ("samsung", "Samsung"),
    ("xiaomi", "Xiaomi"),
    ("oppo", "OPPO"),
    ("vivo", "vivo"),
    ("honor", "HONOR"),
    ("realme", "realme"),
    ("sony", "Sony"),
    ("nokia", "Nokia"),
    ("apple", "Apple"),
    ("iphone", "Apple"),
    ("ipad", "Apple"),
)


def _negated_brand(folded, needle):
    brand = re.escape(needle) + r"\b"
    patterns = (
        r"(?:không|khong|đừng|dung|chẳng|chang)\s+(?:thích|thich|muốn|muon|cần|can|lấy|lay|chọn|chon|mua)\s+(?:(?:máy|may|hãng|hang|điện thoại|dien thoai)\s+)?" + brand,
        r"(?:miễn|mien)\s+(?:là\s+)?(?:không|khong)\s+phải\s+(?:(?:máy|may|hãng|hang)\s+)?" + brand,
        r"(?:trừ|tru)\s+(?:(?:hãng|hang|máy|may)\s+)?" + brand + r"(?:\s+ra)?",
        r"(?:ngoài|ngoai)\s+(?:(?:hãng|hang|máy|may)\s+)?" + brand,
    )
    return any(re.search(pattern, folded) for pattern in patterns)


def excluded_brands(text):
    """Brands the shopper rejected. A later positive mention is not an exclusion."""
    folded = (text or "").casefold()
    found = []
    for needle, label in _BRAND_NEEDLES:
        if _negated_brand(folded, needle) and label not in found:
            found.append(label)
    return found


def _brand_phrase(folded):
    rejected = {label.casefold() for label in excluded_brands(folded)}

    def allow(label):
        return label.casefold() not in rejected

    if "macbook" in folded and allow("MacBook"):
        return "MacBook"
    laptopish = "laptop" in folded or (
        ("máy tính" in folded or "may tinh" in folded)
        and "bảng" not in folded
        and "bang" not in folded
    )
    if "apple" in folded and "iphone" not in folded and "ipad" not in folded and laptopish and allow("MacBook"):
        return "MacBook"
    if ("iphone" in folded or "ipad" in folded or "apple" in folded) and allow("Apple"):
        return "Apple"
    for needle, label in _BRAND_NEEDLES:
        if needle in folded and allow(label):
            return label
    if re.search(r"\blg\b", folded):
        return "LG"
    if re.search(r"\bhp\b", folded):
        return "HP"
    if re.search(r"\bmsi\b", folded):
        return "MSI"
    return ""


def _span_hits(span, used):
    return any(span[0] < end and span[1] > start for start, end in used)


def _focus_phrase(folded):
    """RAM, storage and MacBook line. Pro on an iPhone is not a MacBook line."""
    family = _family_phrase(folded)
    mac_context = family == "MacBook"
    line = ""
    if mac_context and ("macbook air" in folded or re.search(r"\bair\b", folded)):
        line = "air"
    elif mac_context and ("macbook neo" in folded or re.search(r"\bneo\b", folded)):
        line = "neo"
    elif mac_context and ("macbook pro" in folded or re.search(r"\bpro\b", folded)):
        line = "pro"
    variant = ""
    if family in {"iPhone", "iPad"}:
        found = re.search(r"\b(pro max|pro|plus|air|mini)\b", folded)
        if found:
            variant = found.group(1)
    chip = ""
    chips = re.search(r"\bm(\d)\s*(pro|max|ultra)?\b", folded)
    if chips:
        chip = f"m{chips.group(1)}" + (f" {chips.group(2)}" if chips.group(2) else "")
    screen = None
    for size in re.finditer(r"\b(13|14|15|16)\b", folded):
        if re.match(r"\s*(?:triệu|trieu|tr)\b", folded[size.end():]):
            continue
        if "inch" in folded or "macbook" in folded or chip:
            screen = int(size.group(1))
            break
    ram = None
    min_ram = None
    storage = None
    used = []
    pair = re.search(r"(\d+)\s*gb\s*/\s*(\d+)\s*(gb|tb)\b", folded)
    if pair:
        ram = int(pair.group(1))
        storage = int(pair.group(2)) * (1024 if pair.group(3) == "tb" else 1)
        used.append(pair.span())
    minimum = re.search(
        r"ram\s*(?:ít nhất|it nhat|tối thiểu|toi thieu|từ|tu)\s*(\d+)\s*gb"
        r"|(?:ít nhất|it nhat|tối thiểu|toi thieu)\s*(\d+)\s*gb(?:\s*ram)?",
        folded,
    )
    if minimum and ram is None:
        min_ram = int(minimum.group(1) or minimum.group(2))
        used.append(minimum.span())
    if ram is None and min_ram is None:
        explicit = re.search(r"\bram\s*(\d+)\s*gb\b|\b(\d+)\s*gb\s*ram\b", folded)
        if explicit:
            ram = int(explicit.group(1) or explicit.group(2))
            used.append(explicit.span())
    for match in re.finditer(r"\b(\d+)\s*(gb|tb)\b", folded):
        if _span_hits(match.span(), used):
            continue
        number = int(match.group(1))
        if match.group(2) == "tb":
            storage = number * 1024
            used.append(match.span())
        elif number in {128, 256, 512, 1024}:
            storage = number
            used.append(match.span())
    if ram is None and min_ram is None:
        # "bản 16GB" is a RAM config even when the line does not repeat MacBook.
        edition = re.search(r"\bbản\s*(8|16|18|24|32|36|48|64|96)\s*gb\b", folded)
        if edition and not _span_hits(edition.span(), used):
            ram = int(edition.group(1))
            used.append(edition.span())
    if ram is None and min_ram is None and (mac_context or family == "iPad"):
        for match in re.finditer(r"\b(8|16|18|24|32|36|48|64|96)\s*gb\b", folded):
            if _span_hits(match.span(), used):
                continue
            ram = int(match.group(1))
            used.append(match.span())
            break
    return {
        "line": line,
        "variant": variant,
        "screen": screen,
        "ram_gb": ram,
        "min_ram": min_ram,
        "storage_gb": storage,
        "chip": chip,
        "specific": bool(ram or screen or chip),
        "family": family,
    }


def _signals(text):
    folded = (text or "").casefold()
    price_min, price_max, price_target = _budget_phrase(folded)
    use = _use_phrase(folded)
    named = re.search(r"iphone\s*\d+\s*(?:pro|plus|air|e)?|galaxy\s*[a-z]*\s*\d+|redmi\s*[a-z0-9]+|ipad\s*\w+|macbook\s*(?:air|pro|neo)?", folded)
    focus = _focus_phrase(folded)
    brand = _brand_phrase(folded)
    family = focus["family"]
    if not family and brand == "MacBook":
        family = "MacBook"
    category = _category_phrase(folded, use)
    if not category and brand in LAPTOP_BRANDS:
        category = "laptop"
    elif not category and brand in HEADPHONE_BRANDS:
        category = "headphones"
    query = "" if focus["specific"] else (named.group(0).strip() if named else "")
    if not query and not focus["specific"]:
        for token in ("vivobook", "inspiron", "ideapad", "pavilion", "legion", "katana", "nitro", "tuf"):
            if re.search(rf"\b{token}\b", folded):
                query = token
                break
    order_id = None
    order_match = re.search(r"đơn\s*#\s*(\d+)|xem đơn\s+(\d+)|đơn số\s+(\d+)", folded)
    if order_match:
        order_id = int(next(group for group in order_match.groups() if group))
    return {
        "category": category,
        "query": query,
        "color": _color_phrase(folded),
        "price_min": price_min,
        "price_max": price_max,
        "price_max_exclusive": bool(re.search(r"dưới\s+\d+(?:[.,]\d+)?\s*(?:triệu|tr)\b", folded)),
        "price_target": price_target,
        "priorities": _priority_phrase(folded),
        "brand": brand,
        "use": use,
        "ram_gb": focus["ram_gb"],
        "min_ram": focus["min_ram"],
        "storage_gb": focus["storage_gb"],
        "screen": focus["screen"],
        "line": focus["line"],
        "variant": focus["variant"],
        "chip": focus["chip"],
        "specific": focus["specific"],
        "family": family,
        "order_id": order_id,
        "excluded_brands": excluded_brands(folded),
    }


def _asks_cheapest(text):
    return _CHEAPEST_RE.search((text or "").casefold()) is not None


def _mark_cheapest(slots, question, current):
    """'Rẻ nhất' drops a budget inherited from the previous turn. A price in this sentence stays."""
    own_price = (
        current.get("price_min") is not None
        or current.get("price_max") is not None
        or current.get("price_target") is not None
    )
    if _asks_cheapest(question) and not own_price:
        slots["price_min"] = None
        slots["price_max"] = None
        slots["price_max_exclusive"] = False
        slots["price_target"] = None
        slots["cheapest"] = True
    else:
        slots["cheapest"] = False
    return slots


def _merge_request(current, prior, question):
    """Apply one user turn to the accumulated slots, newest values first."""
    if not prior:
        current["category"] = current["category"] or "phone"
        return _mark_cheapest(current, question, current)
    # A budget in this sentence replaces the old one. "Tầm 25 triệu" must not
    # keep an earlier "dưới 20 triệu", or the new band collapses.
    stated_budget = (
        current["price_min"] is not None
        or current["price_max"] is not None
        or current["price_target"] is not None
    )
    merged = {
        "category": current["category"] or prior["category"] or "phone",
        "query": current["query"] or ("" if current["specific"] else prior["query"]),
        "color": current["color"] or prior["color"],
        "brand": current["brand"] or prior["brand"],
        "use": current["use"] or prior["use"],
        "price_min": current["price_min"] if stated_budget else prior["price_min"],
        "price_max": current["price_max"] if stated_budget else prior["price_max"],
        "price_max_exclusive": current["price_max_exclusive"] if stated_budget else prior.get("price_max_exclusive", False),
        "price_target": current["price_target"] if stated_budget else prior["price_target"],
        "priorities": current["priorities"] or prior["priorities"],
        "ram_gb": current["ram_gb"] if current["specific"] else prior.get("ram_gb"),
        "min_ram": None if current["specific"] else (current["min_ram"] if current["min_ram"] is not None else prior.get("min_ram")),
        "storage_gb": None if current["specific"] else (current["storage_gb"] if current["storage_gb"] is not None else prior.get("storage_gb")),
        "screen": current["screen"] if current["specific"] else prior.get("screen"),
        "line": current["line"] if current["specific"] else (current["line"] or prior.get("line") or ""),
        "variant": current["variant"] or ("" if current["family"] and current["family"] != prior.get("family") else (prior.get("variant") or "")),
        "chip": current["chip"] if current["specific"] else (prior.get("chip") or ""),
        "specific": current["specific"],
        "family": current["family"] or prior.get("family") or "",
        "order_id": current.get("order_id"),
        "excluded_brands": [
            name for name in (prior.get("excluded_brands") or []) if name != current.get("brand")
        ] + [
            name for name in (current.get("excluded_brands") or [])
            if name not in (prior.get("excluded_brands") or [])
        ],
    }
    if current["category"] and current["category"] != prior.get("category"):
        for key in ("query", "brand", "family", "line", "variant", "chip"):
            merged[key] = current.get(key) or ""
        for key in ("ram_gb", "min_ram", "storage_gb", "screen"):
            merged[key] = current.get(key)
    if not current["category"] and current["brand"] in LAPTOP_BRANDS:
        merged["category"] = "laptop"
    elif not current["category"] and current["brand"] in HEADPHONE_BRANDS:
        merged["category"] = "headphones"
    if current["min_ram"] is not None and not current["specific"]:
        merged["ram_gb"] = None
    if current["family"] and current["family"] != (prior.get("family") or ""):
        merged["variant"] = current["variant"] or ""
        if not current["line"]:
            merged["line"] = ""
    if current["category"] in {"phone", "headphones", "smartwatch"} and not current["use"] and merged["use"] == "study":
        merged["use"] = ""
    if current["brand"] and prior.get("brand") and current["brand"] != prior["brand"]:
        merged["query"] = current["query"]
        merged["family"] = current["family"]
        merged["variant"] = current["variant"] or ""
        merged["line"] = current["line"] or ""
        if not current["specific"]:
            merged["chip"] = ""
            merged["screen"] = None
            merged["ram_gb"] = None
            merged["min_ram"] = current["min_ram"]
            merged["storage_gb"] = current["storage_gb"]
    if merged["use"] == "study" and merged["category"] == "phone":
        merged["category"] = "laptop"
    if merged.get("brand") in (merged.get("excluded_brands") or []):
        merged["brand"] = ""
    if current.get("excluded_brands"):
        rejected = {name.casefold() for name in merged["excluded_brands"]}
        if any(name in (merged.get("query") or "").casefold() for name in rejected):
            merged["query"] = ""
        family_brand = {"iPhone": "apple", "iPad": "apple", "MacBook": "macbook"}
        family = merged.get("family")
        if family and (family_brand.get(family) in rejected or (family == "MacBook" and "apple" in rejected)):
            if family.casefold() in (merged.get("query") or "").casefold():
                merged["query"] = ""
            merged["family"] = ""
    stretch = budget_stretch(question)
    if stretch:
        base = merged.get("price_max")
        if base is None:
            base = merged.get("price_target")
        if base is None:
            base = merged.get("price_min")
        if base is not None:
            merged["price_max"] = int(base) + stretch
            merged["price_max_exclusive"] = False
            merged["price_target"] = None
    if re.search(
        r"không cần gaming|khong can gaming|không chơi game nữa|khong choi game nua|bỏ gaming|bo gaming",
        (question or "").casefold(),
    ):
        if merged.get("use") == "gaming":
            merged["use"] = ""
    if "camera" in current["priorities"] and not current["use"] and merged.get("use") == "gaming":
        merged["use"] = ""
    return _mark_cheapest(merged, question, current)


def resolve_request(question, history=None):
    """Replay user turns in order so the latest budget, use and brand win."""
    prior = None
    for role, body in history or []:
        if role != "user":
            continue
        text = (body or "").strip()
        if text and text not in {"Đặt giúp tôi", "Đặt hàng"}:
            prior = _merge_request(_signals(text), prior, text)
    current = _signals(question)
    debug("STATE_BEFORE_EXTRACTION", user=question, state=prior or {})
    debug("EXTRACTED_SLOTS", slots=current)
    merged = _merge_request(current, prior, question)
    debug("STATE_AFTER_MERGE", state=merged)
    return merged


def interpret(text):
    return resolve_request(text, None)
