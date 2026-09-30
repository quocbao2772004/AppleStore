"""Structured product search. SQL stays in this module; the model only passes slots."""
import re

from .constants import CATEGORIES, GAMING_CPU, LAPTOP_GAMING, SPEC_NAMES, STUDY_CPU_SQL

def _money(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _media_url(local_path):
    prefix = "data/images/"
    if not local_path or not str(local_path).startswith(prefix):
        return ""
    return "/media/" + str(local_path)[len(prefix):]


def _name_query(query):
    text = (query or "").replace("%", "").replace("_", "").strip()
    folded = text.casefold()
    if not text or len(text.split()) > 3:
        return ""
    if folded in {"ai", "học", "hoc", "laptop", "máy tính", "may tinh", "điện thoại"}:
        return ""
    if any(word in folded for word in ("phù hợp", "phu hop", "học", "hoc", "nào", "nao", "gợi ý", "goi y", "tư vấn", "tu van", "cho việc")):
        return ""
    return text


def search_products(conn, category="phone", query="", color="", price_min=None, price_max=None, brand="", use="", limit=3, ram_gb=None, min_ram=None, storage_gb=None, screen=None, line="", chip="", specific=False, price_target=None, priorities=None, family="", variant="", allow_more=False, cheapest=False, **_extra):
    limit = max(1, min(int(limit or 3), 20 if allow_more else 4))
    if category not in CATEGORIES:
        category = "phone"
    # Pro/Air/Neo is a MacBook line. On a phone it is a variant, and 128–1024 GB is storage.
    if (family or "").casefold() in {"iphone", "ipad"}:
        line = ""
    elif (line or "") in {"air", "pro", "neo"} and category != "laptop":
        line = ""
    if category == "phone" and ram_gb and int(ram_gb) in {128, 256, 512, 1024} and not storage_gb:
        storage_gb = int(ram_gb)
        ram_gb = None
        if not screen and not chip:
            specific = False
    if use == "study" and category == "phone" and not specific:
        category = "laptop"
    price_min = _money(price_min)
    price_max = _money(price_max)
    price_target = _money(price_target)
    # "Tầm X" stays near X. A lower cap still wins. A looser model cap does not.
    strict_max = price_max
    if price_target:
        soft = int(price_target * 1.15)
        strict_max = soft if strict_max is None else min(strict_max, soft)
    focus = {
        "ram_gb": ram_gb,
        "min_ram": min_ram,
        "storage_gb": storage_gb,
        "screen": screen,
        "line": line or "",
        "chip": chip or "",
        "specific": bool(specific),
        "family": family or "",
        "variant": variant or "",
        "cheapest": bool(cheapest),
    }
    text = "" if specific else _name_query(query)
    picked = _search_rows(conn, category, text, color, price_min, strict_max, brand, use, limit, focus)
    if not picked and text and not specific:
        picked = _search_rows(conn, category, "", color, price_min, strict_max, brand, use, limit, focus)
    if not picked and use == "study" and not specific:
        picked = _search_rows(conn, category, "", color, price_min, strict_max, brand, "study-ram", limit, focus)
    if not picked and use == "study" and not specific and (price_target or price_max):
        advice = _near_study(conn, brand, price_min, price_max, price_target, priorities or [])
        if advice:
            return advice
    if not picked:
        if specific:
            note = "Không thấy đúng cấu hình khách hỏi."
        elif color:
            note = "Không còn máy đúng màu, đúng giá và còn hàng."
        elif use == "study":
            note = "Không thấy laptop còn hàng đủ GPU hoặc RAM để học AI."
        else:
            note = "Không thấy sản phẩm còn hàng đúng nhu cầu."
        return {"products": [], "note": note}
    if specific:
        note = "Đây đúng cấu hình khách hỏi. Hãy nhận xét chip, RAM và GPU của máy này. Đừng trả lời bằng câu về MacBook Air nếu khách không hỏi Air."
    elif use == "study" and _brand_like(brand) == "%macbook%":
        note = "Khách chưa chỉ một cấu hình. Các máy này là MacBook Pro từ 24 GB. Air không nằm trong danh sách."
    elif use == "study" and cheapest:
        note = "Các máy này là laptop rẻ nhất còn hàng đủ GPU rời hoặc RAM từ 32 GB để học AI."
    elif use == "study":
        note = "Các máy này có GPU rời hoặc RAM từ 32 GB."
    elif cheapest:
        note = "Các máy này là mẫu còn hàng rẻ nhất đúng nhóm khách hỏi."
    else:
        note = ""
    if (
        not specific
        and use != "study"
        and _brand_like(brand) == "%apple%"
        and category == "phone"
        and (family or "").casefold() != "iphone"
        and "iphone" not in (query or "").casefold()
    ):
        note = "Mình đang xem iPhone. MacBook là máy tính, bạn nói thêm nếu muốn xem nhóm đó."
        return {"products": picked, "note": note, "lead": note}
    return {"products": picked, "note": note}


def _search_rows(conn, category, text, color, price_min, price_max, brand, use, limit, focus=None):
    color_like = _color_like(color)
    like = f"%{text}%" if text else ""
    brand_like = _brand_like(brand)
    study_sql = ""
    params = [
        category, price_min, price_min, price_max, price_max,
        color_like, color_like, like, like, like, brand_like, brand_like, brand_like,
    ]
    if use in ("study", "study-ram"):
        study_sql = """
          AND EXISTS (
            SELECT 1 FROM product_specifications s
            WHERE s.product_id = p.source_product_id AND s.spec_name = 'RAM'
              AND substring(s.spec_value from '([0-9]+)')::int >= 16
          )
        """
    # Cheapest keeps every discrete-GPU laptop. The CPU regex would hide an i5 with an RTX.
    if use == "study" and not (focus or {}).get("cheapest"):
        study_sql += """
          AND EXISTS (
            SELECT 1 FROM product_specifications s
            WHERE s.product_id = p.source_product_id
              AND s.spec_name IN ('Công nghệ CPU', 'Chip xử lý (CPU)', 'Chip xử lý')
              AND s.spec_value ~* %s
          )
        """
        params.append(STUDY_CPU_SQL)
    focus = focus or {}
    focus_sql = ""
    line = focus.get("line") or ""
    if line == "pro":
        focus_sql += " AND p.name ILIKE '%%macbook pro%%'"
    elif line == "air":
        focus_sql += " AND p.name ILIKE '%%macbook air%%'"
    elif line == "neo":
        focus_sql += " AND p.name ILIKE '%%macbook neo%%'"
    screen = focus.get("screen")
    if screen:
        focus_sql += " AND p.name ILIKE %s"
        params.append(f"%{int(screen)} inch%")
    chip = (focus.get("chip") or "").casefold()
    if chip == "m5":
        focus_sql += " AND p.name ILIKE '%%m5%%' AND p.name NOT ILIKE '%%m5 pro%%' AND p.name NOT ILIKE '%%m5 max%%' AND p.name NOT ILIKE '%%m5 ultra%%'"
    elif chip:
        focus_sql += " AND p.name ILIKE %s"
        params.append(f"%{chip}%")
    ram_gb = focus.get("ram_gb")
    if ram_gb:
        focus_sql += """
          AND EXISTS (
            SELECT 1 FROM product_specifications s
            WHERE s.product_id = p.source_product_id AND s.spec_name = 'RAM'
              AND substring(s.spec_value from '([0-9]+)')::int = %s
          )
        """
        params.append(int(ram_gb))
    elif focus.get("min_ram"):
        focus_sql += """
          AND EXISTS (
            SELECT 1 FROM product_specifications s
            WHERE s.product_id = p.source_product_id AND s.spec_name = 'RAM'
              AND substring(s.spec_value from '([0-9]+)')::int >= %s
          )
        """
        params.append(int(focus["min_ram"]))
    storage_gb = focus.get("storage_gb")
    if storage_gb:
        storage_gb = int(storage_gb)
        name_sql = ["p.name ILIKE %s", "p.name ILIKE %s"]
        params.append(f"%{storage_gb}gb%")
        params.append(f"%{storage_gb} gb%")
        if storage_gb % 1024 == 0:
            tb = storage_gb // 1024
            name_sql.extend(["p.name ILIKE %s", "p.name ILIKE %s"])
            params.append(f"%{tb}tb%")
            params.append(f"%{tb} tb%")
        focus_sql += f"""
          AND (
            {" OR ".join(name_sql)}
            OR EXISTS (
              SELECT 1 FROM product_specifications s
              WHERE s.product_id = p.source_product_id
                AND s.spec_name IN ('Dung lượng lưu trữ', 'Ổ cứng', 'Bộ nhớ trong')
                AND substring(s.spec_value from '([0-9]+)')::int = %s
            )
          )
        """
        params.append(storage_gb)
    variant = (focus.get("variant") or "").casefold()
    if variant in {"pro", "pro max", "plus", "air", "mini"} and not focus.get("line"):
        focus_sql += " AND p.name ILIKE %s AND p.name NOT ILIKE '%%macbook%%'"
        params.append(f"%{variant}%")
    family_name = (focus.get("family") or "").casefold()
    if family_name == "iphone" and category == "phone":
        focus_sql += " AND p.name ILIKE '%%iphone%%'"
    elif family_name == "ipad" and category == "tablet":
        focus_sql += " AND p.name ILIKE '%%ipad%%'"
    elif family_name == "macbook" and category == "laptop":
        focus_sql += " AND p.name ILIKE '%%macbook%%'"
    params.extend((color_like, color_like))
    price_order = "ASC" if use in ("study", "study-ram") or focus.get("cheapest") else "DESC"
    row_limit = 400 if use in ("study", "study-ram") or focus.get("cheapest") else 160
    rows = conn.execute(
        f"""
        SELECT p.source_product_id, p.name, p.brand, p.price_vnd, p.stock,
               c.color_name, c.hex_color,
               (
                 SELECT i.image_url FROM product_color_images i
                 WHERE i.product_id = p.source_product_id AND i.color_name = c.color_name
                   AND coalesce(i.image_url, '') <> ''
                   AND i.image_url NOT ILIKE '%%/Kit/%%'
                   AND i.image_url NOT ILIKE '%%tem-%%'
                   AND i.image_url NOT ILIKE '%%-glr-%%'
                 ORDER BY i.display_order LIMIT 1
               ) AS image_url,
               (
                 SELECT i.local_path FROM product_images i
                 WHERE i.product_id = p.source_product_id AND i.local_path IS NOT NULL
                 ORDER BY CASE i.image_role WHEN 'thumbnail' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
                          i.display_order
                 LIMIT 1
               ) AS local_path,
               p.category
        FROM products p
        LEFT JOIN product_colors c ON c.product_id = p.source_product_id
        WHERE p.is_live_catalog AND p.category = %s AND p.stock > 0 AND coalesce(p.price_vnd, 0) > 0
          AND (%s::bigint IS NULL OR p.price_vnd >= %s)
          AND (%s::bigint IS NULL OR p.price_vnd <= %s)
          AND (%s = '' OR c.color_name ILIKE %s)
          AND (%s = '' OR p.name ILIKE %s OR coalesce(p.brand, '') ILIKE %s)
          AND (%s = '' OR coalesce(p.brand, '') ILIKE %s OR p.name ILIKE %s)
          {study_sql}
          {focus_sql}
        ORDER BY
          CASE WHEN %s <> '' AND c.color_name ILIKE %s THEN 0 ELSE 1 END,
          p.price_vnd {price_order}
        LIMIT {row_limit}
        """,
        params,
    ).fetchall()
    picked = _best_colors(rows, color)
    _attach_specs(conn, picked)
    if use == "gaming":
        picked = [item for item in picked if _is_gaming_item(item)]
    if focus.get("specific"):
        for item in picked:
            item["fit"], item["reason"] = _judge(item)
        return picked[:limit]
    if use in ("study", "study-ram"):
        picked = [item for item in picked if _ai_score(item) >= 5]
        if focus.get("cheapest"):
            picked.sort(key=lambda item: (item["price"], -_ai_score(item)))
        else:
            picked.sort(key=lambda item: (-_ai_score(item), item["price"]))
        for item in picked:
            item["fit"] = "strong"
            item["reason"] = _study_reason(item)
        return _spread(picked, collapse_storage=True)[:limit]
    if focus.get("cheapest") and not focus.get("specific"):
        picked.sort(key=lambda item: item["price"])
    return _spread(picked)[:limit]



def _color_like(color):
    text = (color or "").casefold().strip()
    if not text:
        return ""
    if "xô thơm" in text or "xo thom" in text or "xanh lá" in text or "xanh la" in text:
        return "%xanh lá%"
    if text in ("xanh", "xanh dương", "xanh duong"):
        return "%xanh%"
    return f"%{text}%"


def _best_colors(rows, color):
    grouped = {}
    asked = _color_like(color).strip("%")
    for row in rows:
        rank = 0 if asked and asked.casefold() in (row[5] or "").casefold() else 1
        current = grouped.get(row[0])
        if current is None or rank < current[0]:
            grouped[row[0]] = (rank, row)
    items = []
    for _, row in sorted(grouped.values(), key=lambda item: (item[0], -(item[1][3] or 0))):
        items.append({
            "product_id": row[0],
            "name": row[1],
            "brand": row[2] or "",
            "price": int(row[3] or 0),
            "stock": int(row[4] or 0),
            "color_name": row[5] or "",
            "hex": row[6] or "",
            "image_url": row[7] or _media_url(row[8]),
            "category": row[9] or "",
            "specs": [],
            "reason": "",
        })
    return items


def _specs_for(conn, product_ids):
    if not product_ids:
        return {}
    rows = conn.execute(
        """
        SELECT product_id, spec_name, spec_value
        FROM product_specifications
        WHERE product_id = ANY(%s) AND spec_name = ANY(%s)
        """,
        (list(product_ids), list(SPEC_NAMES)),
    ).fetchall()
    grouped = {}
    for product_id, name, value in rows:
        grouped.setdefault(product_id, {}).setdefault(name, value)
    return grouped


def _attach_specs(conn, items):
    grouped = _specs_for(conn, [item["product_id"] for item in items])
    for item in items:
        raw = grouped.get(item["product_id"], {})
        cpu = raw.get("Chip xử lý (CPU)") or raw.get("Chip xử lý") or raw.get("Công nghệ CPU") or ""
        storage = raw.get("Dung lượng lưu trữ") or raw.get("Ổ cứng") or ""
        battery = raw.get("Dung lượng pin") or raw.get("Thông tin Pin") or ""
        screen = raw.get("Màn hình rộng") or raw.get("Kích thước màn hình") or ""
        max_charge = raw.get("Hỗ trợ sạc tối đa") or ""
        included = raw.get("Sạc kèm theo máy") or ""
        if max_charge and included:
            charging = f"tối đa {max_charge}, kèm theo máy {included}"
        else:
            charging = max_charge or (f"kèm theo máy {included}" if included else "")
        wanted = [
            ("Chip", cpu),
            ("RAM", raw.get("RAM", "")),
            ("Bộ nhớ", storage),
            ("Pin", battery),
            ("Sạc", charging),
            ("Màn hình", screen),
            ("Card", raw.get("Card màn hình", "")),
        ]
        item["specs"] = [{"name": name, "value": value} for name, value in wanted if value]
        item["reason"] = item.get("reason") or ""


def _is_gaming_item(item):
    if item.get("category") == "laptop":
        card = next((spec["value"] for spec in item["specs"] if spec["name"] == "Card"), "")
        return LAPTOP_GAMING.search(f"{item.get('name') or ''} {card}") is not None
    cpu = next((spec["value"] for spec in item["specs"] if spec["name"] == "Chip"), "")
    ram = next((spec["value"] for spec in item["specs"] if spec["name"] == "RAM"), "")
    match = re.search(r"\d+", ram)
    ram_n = int(match.group()) if match else 0
    return bool(GAMING_CPU.search(cpu)) and ram_n >= 8


def _pick_color(colors, asked):
    if not colors:
        return None
    like = _color_like(asked).strip("%").casefold()
    if not like:
        return colors[0]
    for color in colors:
        if like in (color[0] or "").casefold():
            return color
    return colors[0]


def _brand_like(brand):
    text = (brand or "").strip().casefold()
    if text in {"mac", "macbook"}:
        text = "macbook"
    return f"%{text}%" if text else ""


def _spread(items, collapse_storage=False):
    kept = []
    seen = set()
    for item in items:
        key = re.sub(r"\b\d+\s*w\b", "", (item.get("name") or "").casefold())
        if collapse_storage:
            key = re.sub(r"\b\d+\s*tb\b", "", key)
        key = re.sub(r"\s+", " ", key).strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _spec_value(item, name):
    return next((spec["value"] for spec in item.get("specs") or [] if spec["name"] == name), "")


def _ram_gb(item):
    match = re.search(r"\d+", _spec_value(item, "RAM"))
    return int(match.group()) if match else 0


def _ai_score(item):
    """Học AI cần GPU rời hoặc MacBook Pro từ 24 GB. Air và máy 16 GB GPU tích hợp không tính."""
    name = (item.get("name") or "").casefold()
    if "macbook air" in name or "macbook neo" in name:
        return 0
    ram = _ram_gb(item)
    cpu = _spec_value(item, "Chip").casefold()
    gpu = _spec_value(item, "Card").casefold()
    rtx = bool(re.search(r"rtx\s*(?:30|40|50)\d{2}", gpu))
    apple_pro = bool(re.search(r"\bm\d\s*(?:pro|max|ultra)\b", cpu))
    if rtx and ram >= 32:
        return 9
    if apple_pro and ram >= 48:
        return 9
    if apple_pro and ram >= 24:
        return 8
    if rtx and ram >= 16:
        return 7
    if ram >= 32:
        return 5
    return 0


def _judge(item):
    ram = _ram_gb(item)
    cpu = _spec_value(item, "Chip")
    gpu = _spec_value(item, "Card")
    cpu_folded = cpu.casefold()
    name = (item.get("name") or "").casefold()
    base_m = "macbook pro" in name and not re.search(r"\bm\d\s*(?:pro|max|ultra)\b", cpu_folded)
    if base_m and ram <= 16:
        return "tight", f"Chip {cpu}, RAM {ram} GB, GPU tích hợp. Khung Pro nhưng 16 GB chỉ đủ bài nhỏ, học AI thì chật."
    if "macbook air" in name or "macbook neo" in name:
        return "weak", f"RAM {ram} GB, GPU tích hợp. Không hợp học AI."
    if _ai_score(item) >= 5:
        return "strong", _study_reason(item)
    return "tight", f"Chip {cpu}, RAM {ram} GB, {gpu}. Hơi chật để học AI."


def _study_reason(item):
    ram = _ram_gb(item)
    cpu = _spec_value(item, "Chip")
    gpu = _spec_value(item, "Card")
    name = (item.get("name") or "").casefold()
    if "macbook pro" in name:
        return f"Bản Pro, {ram} GB RAM thống nhất, chip {cpu}. Đủ để học AI và chạy model nhỏ."
    if "rtx" in gpu.casefold():
        short = gpu.split("-", 1)[-1].strip()
        return f"GPU rời {short}, RAM {ram} GB. Đủ để học AI và chạy model nhỏ."
    return f"RAM {ram} GB, chip {cpu}. Đủ bộ nhớ để học và chạy bài."


def _battery_wh(item):
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*wh", _spec_value(item, "Pin"), re.I)
    if not match:
        return 0.0
    return float(match.group(1).replace(",", "."))


def _money_label(amount):
    amount = int(amount or 0)
    if amount and amount % 1_000_000 == 0:
        return f"{amount // 1_000_000} triệu"
    text = f"{amount:,}".replace(",", ".")
    return text + "₫"


def _budget_band(price_min, price_max, price_target):
    if price_target:
        low, high = int(price_target * 0.8), int(price_target * 1.2)
    elif price_max:
        low, high = int(price_max * 0.75), int(price_max)
    else:
        return None, None
    if price_min:
        low = max(low, int(price_min))
    if price_max and int(price_max) < high and (not price_target or int(price_max) < int(price_target)):
        high = int(price_max)
    if low > high:
        low = int(high * 0.75)
    return low, high


def _line_key(item):
    """Gộp các mã SKU của cùng một dòng, để tư vấn không đưa hai biến thể y hệt."""
    name = re.sub(r"\([^)]*\)", " ", (item.get("name") or "").casefold())
    words = [word for word in re.split(r"[^a-z0-9]+", name) if word and word != "laptop"]
    kept = []
    for word in words:
        if re.fullmatch(r"[a-z]{0,3}\d{3,}[a-z0-9]*", word):
            continue
        if word in {"core", "intel", "amd", "ryzen"} or re.fullmatch(r"\d+", word):
            continue
        kept.append(word)
    return " ".join(kept[:4])


def _one_per_line(items):
    kept = []
    seen = set()
    for item in items:
        key = _line_key(item)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _rank_near(items, anchor, priorities):
    """Capable machines stay first. RAM and pin only reorder inside that group."""
    priorities = priorities or []

    def key(item):
        ram = _ram_gb(item)
        wh = _battery_wh(item)
        price = item.get("price") or 0
        distance = abs(price - anchor) if anchor else price
        capable = 1 if _ai_score(item) >= 5 else 0
        ram_rank = ram if "ram" in priorities else 0
        bat_rank = wh if "battery" in priorities else 0
        return (capable, _ai_score(item), ram_rank, bat_rank, ram, wh, -distance)

    return sorted(items, key=key, reverse=True)


def _split_budget(items, anchor, priorities, stretch_ratio=1.12):
    """Under the budget first. A little over is a separate step, not the opener."""
    ranked = _one_per_line(_spread(_rank_near(items, anchor, priorities), collapse_storage=True))
    under = [item for item in ranked if (item.get("price") or 0) <= anchor]
    stretch_high = int(anchor * stretch_ratio)
    taken = {_line_key(item) for item in under}
    stretch = [
        item for item in ranked
        if anchor < (item.get("price") or 0) <= stretch_high and _line_key(item) not in taken
    ]
    return under, stretch


def _near_laptop_reason(item, anchor, tier):
    ram = _ram_gb(item)
    pin = _spec_value(item, "Pin")
    pin_bit = f", pin {pin}" if pin else ""
    label = _money_label(anchor)
    if tier == "stretch":
        where = f"Nhỉnh hơn {label} một chút"
    else:
        where = f"Dưới {label}"
    if _ai_score(item) >= 5:
        return _study_reason(item) + f" {where}."
    return f"{where}, RAM {ram} GB{pin_bit}. Chạy code được, học AI thì chật vì GPU tích hợp."


def _air_reason(item, anchor):
    ram = _ram_gb(item)
    pin = _spec_value(item, "Pin")
    pin_bit = f", pin {pin}" if pin else ""
    over = ""
    if anchor and (item.get("price") or 0) > anchor * 1.05:
        over = f"Đắt hơn tầm {_money_label(anchor)} khá nhiều. "
    return f"{over}RAM {ram} GB{pin_bit}, GPU tích hợp. Không quá phù hợp để học AI."


def _priced_laptops(conn, price_low, price_high, name_like=""):
    like = name_like or ""
    rows = conn.execute(
        """
        SELECT p.source_product_id, p.name, p.brand, p.price_vnd, p.stock,
               c.color_name, c.hex_color,
               (
                 SELECT i.image_url FROM product_color_images i
                 WHERE i.product_id = p.source_product_id AND i.color_name = c.color_name
                   AND coalesce(i.image_url, '') <> ''
                   AND i.image_url NOT ILIKE '%%/Kit/%%'
                   AND i.image_url NOT ILIKE '%%tem-%%'
                   AND i.image_url NOT ILIKE '%%-glr-%%'
                 ORDER BY i.display_order LIMIT 1
               ) AS image_url,
               (
                 SELECT i.local_path FROM product_images i
                 WHERE i.product_id = p.source_product_id AND i.local_path IS NOT NULL
                 ORDER BY CASE i.image_role WHEN 'thumbnail' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
                          i.display_order
                 LIMIT 1
               ) AS local_path,
               p.category
        FROM products p
        LEFT JOIN product_colors c ON c.product_id = p.source_product_id
        WHERE p.is_live_catalog AND p.category = 'laptop' AND p.stock > 0 AND coalesce(p.price_vnd, 0) > 0
          AND p.price_vnd >= %s AND p.price_vnd <= %s
          AND (%s = '' OR p.name ILIKE %s OR coalesce(p.brand, '') ILIKE %s)
        ORDER BY p.price_vnd ASC
        LIMIT 240
        """,
        (int(price_low), int(price_high), like, like, like),
    ).fetchall()
    picked = _best_colors(rows, "")
    _attach_specs(conn, picked)
    return picked


def _pick_airs(airs, anchor, priorities, count=2):
    if not airs:
        return []
    pool = _spread(airs, collapse_storage=True)
    by_price = sorted(pool, key=lambda item: (abs((item.get("price") or 0) - anchor), item.get("price") or 0))
    chosen = [by_price[0]]
    if "ram" in (priorities or []):
        richer = sorted(pool, key=lambda item: (-_ram_gb(item), abs((item.get("price") or 0) - anchor)))
        for item in richer:
            if item["product_id"] not in {one["product_id"] for one in chosen} and _ram_gb(item) > _ram_gb(chosen[0]):
                chosen.append(item)
                break
    elif "battery" in (priorities or []):
        longer = sorted(pool, key=lambda item: (-_battery_wh(item), abs((item.get("price") or 0) - anchor)))
        for item in longer:
            if item["product_id"] not in {one["product_id"] for one in chosen} and _battery_wh(item) > _battery_wh(chosen[0]):
                chosen.append(item)
                break
    for item in by_price:
        if len(chosen) >= count:
            break
        if item["product_id"] not in {one["product_id"] for one in chosen}:
            chosen.append(item)
    return chosen[:count]


def _near_study(conn, brand, price_min, price_max, price_target, priorities):
    """When nothing in budget can learn AI, show nearby laptops and, if they asked for Mac, a few Airs."""
    low, high = _budget_band(price_min, price_max, price_target)
    if low is None:
        return None
    anchor = price_target or price_max or high
    wants_mac = _brand_like(brand) == "%macbook%"
    pool = [
        item for item in _priced_laptops(conn, low, high)
        if "macbook" not in (item.get("name") or "").casefold()
    ]
    # A hard "dưới X" does not step past the cap. "Tầm X" may step about 12%.
    ratio = 1.12 if price_target else 1.0
    under, stretch = _split_budget(pool, anchor, priorities, ratio)
    laptops = under[:2] + stretch[:1]
    airs = []
    neo_note = ""
    if wants_mac:
        air_high = max(int(anchor * 1.8), high)
        airs = _pick_airs(_priced_laptops(conn, 1, air_high, "%macbook air%"), anchor, priorities, count=1)
        if not airs:
            ceiling = conn.execute(
                """
                SELECT max(price_vnd) FROM products
                WHERE is_live_catalog AND category = 'laptop' AND stock > 0
                  AND name ILIKE '%%macbook air%%'
                """
            ).fetchone()[0]
            if ceiling:
                airs = _pick_airs(_priced_laptops(conn, 1, int(ceiling), "%macbook air%"), anchor, priorities, count=1)
        neos = _priced_laptops(conn, low, high, "%macbook neo%")
        if neos:
            neo = neos[0]
            neo_note = f" MacBook Neo nằm trong tầm giá nhưng RAM {_ram_gb(neo)} GB, không dùng để học AI."
    if not laptops and not airs:
        return None
    tiers = {id(item): "under" for item in under[:2]}
    tiers.update({id(item): "stretch" for item in stretch[:1]})
    for item in laptops:
        item["fit"] = "strong" if _ai_score(item) >= 5 else "tight"
        item["reason"] = _near_laptop_reason(item, anchor, tiers.get(id(item), "under"))
    for item in airs:
        item["fit"] = "weak"
        item["reason"] = _air_reason(item, anchor)
    label = _money_label(anchor)
    capable = any(_ai_score(item) >= 5 for item in laptops)
    if "ram" in priorities and "battery" in priorities:
        rank_note = " Trong từng mức giá, mình xếp theo RAM rồi tới pin."
    elif "ram" in priorities:
        rank_note = " Mình ưu tiên RAM."
    elif "battery" in priorities:
        rank_note = " Mình ưu tiên pin."
    else:
        rank_note = ""
    if wants_mac:
        opening = f"Không có MacBook trong tầm {label} đủ để học AI."
    elif capable:
        opening = f"Trong tầm {label} có laptop GPU rời chạy được bài nhỏ."
    else:
        opening = f"Không có laptop đủ GPU trong tầm {label}."
    under_shown = [item for item in laptops if tiers.get(id(item)) == "under"]
    stretch_shown = [item for item in laptops if tiers.get(id(item)) == "stretch"]
    if under_shown and any(_ai_score(item) >= 5 for item in under_shown):
        middle = f" Mình đưa laptop dưới {label} trước. Bản GPU rời trong mức này chạy được bài nhỏ."
    elif under_shown:
        middle = f" Mình đưa laptop dưới {label} trước. Mức này chủ yếu GPU tích hợp, học AI thì chật."
    elif laptops and capable:
        middle = f" Laptop nhỉnh hơn {label} một chút có GPU rời thì chạy bài nhỏ được."
    elif laptops:
        middle = f" Laptop quanh {label} chủ yếu GPU tích hợp, học AI thì chật."
    else:
        middle = ""
    if stretch_shown and under_shown:
        middle += f" Nhích hơn {label} một chút thì có cấu hình khá hơn."
    air_note = " MacBook Air để so thì đắt hơn nhiều, pin ổn nhưng không quá phù hợp để học AI." if airs else ""
    lead = f"{opening}{middle}{rank_note}{neo_note}{air_note}".strip()
    return {"products": laptops + airs, "note": lead, "lead": lead, "near_miss": True}
