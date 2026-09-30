"""Detail, comparison, stock, orders, and checkout. place_order is the only write."""
import re

from .retrieve import _ai_score, _attach_specs, _media_url, _pick_color, _ram_gb, search_products
from .slots import resolve_request

_SIDE_PATTERNS = (
    re.compile(r"so sánh\s+(.+?)\s+(?:và|với)\s+(.+)$", re.I),
    re.compile(r"giữa\s+(.+?)\s+và\s+(.+?)\s+thì", re.I),
    re.compile(r"(.+?)\s+khác\s+(.+?)\s+chỗ nào", re.I),
    re.compile(r"(.+?)\s+hay\s+(.+)$", re.I),
)

def get_product(conn, product_id, color=""):
    row = conn.execute(
        """
        SELECT source_product_id, name, brand, price_vnd, stock, category
        FROM products WHERE source_product_id=%s AND is_live_catalog
        """,
        (int(product_id),),
    ).fetchone()
    if not row:
        return {"product": None, "note": "Không thấy sản phẩm."}
    if row[4] <= 0:
        return {"product": None, "note": "Sản phẩm đã hết hàng."}
    colors = conn.execute(
        """
        SELECT c.color_name, c.hex_color,
               (
                 SELECT i.image_url FROM product_color_images i
                 WHERE i.product_id = c.product_id AND i.color_name = c.color_name
                   AND coalesce(i.image_url, '') <> ''
                   AND i.image_url NOT ILIKE '%%/Kit/%%'
                   AND i.image_url NOT ILIKE '%%tem-%%'
                   AND i.image_url NOT ILIKE '%%-glr-%%'
                 ORDER BY i.display_order LIMIT 1
               )
        FROM product_colors c
        WHERE c.product_id=%s
        ORDER BY c.display_order, c.color_name
        """,
        (row[0],),
    ).fetchall()
    chosen = _pick_color(colors, color) or (colors[0] if colors else None)
    image_url = chosen[2] if chosen and chosen[2] else ""
    if not image_url:
        photo = conn.execute(
            """
            SELECT local_path FROM product_images
            WHERE product_id=%s AND local_path IS NOT NULL
            ORDER BY CASE image_role WHEN 'thumbnail' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
                     display_order
            LIMIT 1
            """,
            (row[0],),
        ).fetchone()
        image_url = _media_url(photo[0]) if photo else ""
    item = {
        "product_id": row[0],
        "name": row[1],
        "brand": row[2] or "",
        "price": int(row[3] or 0),
        "stock": int(row[4] or 0),
        "color_name": chosen[0] if chosen else "",
        "hex": chosen[1] if chosen else "",
        "image_url": image_url,
        "category": row[5],
        "specs": [],
        "reason": "",
    }
    _attach_specs(conn, [item])
    item["colors"] = [
        {"color_name": name, "hex": hex_color or "", "image_url": url or ""}
        for name, hex_color, url in colors
    ]
    return {"product": item, "note": ""}


def get_checkout_requirements(conn, user, product_id, color="", qty=1):
    found = get_product(conn, product_id, color)
    product = found.get("product")
    if not product:
        return {"ok": False, "note": found.get("note") or "Không đặt được máy này."}
    start_note = "Từ ngày mai, trong 14 ngày. Buổi sáng, chiều hoặc tối."
    return {
        "ok": True,
        "product": product,
        "qty": max(1, min(int(qty or 1), 5)),
        "fields": {
            "name": user["name"],
            "email": user["email"],
            "phone": user.get("phone") or "",
            "address": user.get("address") or "",
            "deliver_on": "",
            "deliver_slot": "afternoon",
        },
        "slots": [
            {"value": "morning", "label": "Sáng 8:00–12:00"},
            {"value": "afternoon", "label": "Chiều 13:00–17:00"},
            {"value": "evening", "label": "Tối 18:00–21:00"},
        ],
        "note": start_note,
    }


def place_order(conn, user, shipment, product_id, color="", qty=1):
    qty = max(1, min(int(qty or 1), 5))
    found = get_product(conn, product_id, color)
    product = found.get("product")
    if not product:
        return {"ok": False, "note": found.get("note") or "Không đặt được."}
    if product["stock"] < qty:
        return {"ok": False, "note": f"Chỉ còn {product['stock']} máy."}
    updated = conn.execute(
        """
        UPDATE products SET stock = stock - %s
        WHERE source_product_id=%s AND stock >= %s
        RETURNING stock
        """,
        (qty, product["product_id"], qty),
    ).fetchone()
    if not updated:
        return {"ok": False, "note": "Vừa hết hàng."}
    label = product["name"]
    if product["color_name"]:
        label = f"{label} ({product['color_name']})"
    total = product["price"] * qty
    order_id = conn.execute(
        """
        INSERT INTO orders(user_id, total_vnd, ship_name, ship_email, ship_phone, ship_address, deliver_on, deliver_slot, pay_method)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        (
            user["id"], total, shipment["name"], shipment["email"], shipment["phone"],
            shipment["address"], shipment["deliver_on"], shipment["deliver_slot"],
            shipment.get("pay_method") or "cod",
        ),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO order_items(order_id, product_id, name, unit_price, qty) VALUES (%s,%s,%s,%s,%s)",
        (order_id, product["product_id"], label, product["price"], qty),
    )
    return {
        "ok": True,
        "order_id": order_id,
        "name": product["name"],
        "color_name": product["color_name"],
        "qty": qty,
        "total": total,
        "stock_left": updated[0],
        "ship_name": shipment["name"],
        "deliver_on": shipment["deliver_on"].strftime("%d.%m.%Y"),
        "deliver_slot": shipment["deliver_slot"],
        "pay_method": shipment.get("pay_method") or "cod",
    }


def list_orders(conn, user):
    rows = conn.execute(
        """
        SELECT o.id, o.status, o.total_vnd, o.deliver_on, o.deliver_slot, coalesce(o.pay_method, 'cod'),
               string_agg(i.name || ' × ' || i.qty, ', ')
        FROM orders o
        LEFT JOIN order_items i ON i.order_id = o.id
        WHERE o.user_id=%s
        GROUP BY o.id
        ORDER BY o.id DESC
        LIMIT 5
        """,
        (user["id"],),
    ).fetchall()
    labels = {"placed": "Đã đặt", "packing": "Đang xử lý", "done": "Hoàn tất", "cancelled": "Đã hủy"}
    slots = {"morning": "sáng", "afternoon": "chiều", "evening": "tối"}
    orders = []
    for row in rows:
        orders.append({
            "order_id": row[0],
            "status": labels.get(row[1], row[1]),
            "total": int(row[2] or 0),
            "deliver_on": row[3].strftime("%d.%m.%Y") if row[3] else "",
            "deliver_slot": slots.get(row[4], row[4] or ""),
            "pay": "Khi nhận hàng" if row[5] != "qr" else "Chuyển khoản trên máy",
            "items": row[6] or "",
        })
    note = "Khách chưa có đơn." if not orders else f"{len(orders)} đơn gần nhất của khách này."
    return {"orders": orders, "note": note}



def _search_kwargs(resolved, limit=4, allow_more=False):
    keys = (
        "category", "query", "color", "price_min", "price_max", "brand", "use",
        "ram_gb", "min_ram", "storage_gb", "screen", "line", "chip", "specific",
        "price_target", "priorities", "family", "variant",
    )
    args = {key: resolved.get(key) for key in keys}
    args["limit"] = limit
    args["allow_more"] = allow_more
    return args


def find_product(conn, resolved):
    found = search_products(conn, **_search_kwargs(resolved or {}, limit=4))
    products = found.get("products") or []
    if not products:
        return {"product": None, "products": [], "note": found.get("note") or "Không thấy sản phẩm."}
    return {"product": products[0], "products": [products[0]], "note": ""}


def check_inventory(conn, resolved):
    found = find_product(conn, resolved)
    product = found.get("product")
    if not product:
        return {"products": [], "note": "Không thấy máy để xem tồn kho."}
    stock = int(product.get("stock") or 0)
    note = f"Còn {stock} máy." if stock else "Hết hàng."
    product["reason"] = note
    return {"products": [product], "stock": stock, "note": note}


def _compare_sides(question):
    text = (question or "").strip()
    for pattern in _SIDE_PATTERNS:
        found = pattern.search(text)
        if found:
            return found.group(1).strip(), found.group(2).strip()
    return "", ""


def _pick_side(products, side):
    if not products:
        return None
    folded = side.casefold()
    wants_pro = re.search(r"\bpro\b", folded) is not None
    wants_plus = "plus" in folded
    wants_air = re.search(r"\bair\b", folded) is not None
    wants_neo = re.search(r"\bneo\b", folded) is not None
    pool = list(products)
    if wants_air:
        airs = [item for item in pool if "air" in item["name"].casefold()]
        if airs:
            pool = airs
    elif wants_neo:
        neos = [item for item in pool if "neo" in item["name"].casefold()]
        if neos:
            pool = neos
    elif wants_pro:
        pros = [item for item in pool if re.search(r"\bpro\b", item["name"].casefold())]
        if pros:
            pool = pros
    elif wants_plus:
        plus = [item for item in pool if "plus" in item["name"].casefold()]
        if plus:
            pool = plus
    elif "iphone" in folded or "galaxy" in folded:
        plain = [
            item for item in pool
            if "pro" not in item["name"].casefold() and "plus" not in item["name"].casefold()
        ]
        if plain:
            pool = plain
    return pool[0]


def compare_products(conn, question):
    """Read two catalog rows and return them. The wording of the comparison is left to the model."""
    left, right = _compare_sides(question)
    if not left or not right:
        return {"products": [], "note": "Mình cần hai máy để so sánh."}
    picked = []
    for side in (left, right):
        resolved = resolve_request(side)
        if not resolved.get("query") and not resolved.get("brand"):
            words = [
                word for word in re.findall(r"[a-z0-9]+", side.casefold())
                if word not in {"tai", "nghe", "dong", "ho", "may", "va", "voi"}
            ]
            if words:
                resolved["query"] = words[-1]
        found = search_products(conn, **_search_kwargs(resolved, limit=4))
        choice = _pick_side(found.get("products") or [], side)
        if choice and all(choice["product_id"] != item["product_id"] for item in picked):
            picked.append(choice)
    if len(picked) < 2:
        return {"products": picked, "note": "Chưa đủ hai máy trong catalog để so."}
    return {
        "products": picked,
        "product_a": picked[0],
        "product_b": picked[1],
        "note": "Số liệu lấy từ catalog.",
    }


def _qty_in(text):
    match = re.search(r"(?:đặt|mua)\s+(\d+)", (text or "").casefold())
    if not match:
        return 1
    return int(match.group(1))


def prepare_checkout_request(conn, user, question, resolved):
    """Build the checkout form. This does not place an order and does not change stock."""
    found = find_product(conn, resolved)
    product = found.get("product")
    if not product:
        return {"ok": False, "products": [], "note": found.get("note") or "Chưa chọn được máy để đặt."}
    ready = get_checkout_requirements(
        conn,
        user,
        product["product_id"],
        (resolved or {}).get("color") or "",
        _qty_in(question),
    )
    ready["products"] = [product] if ready.get("ok") else []
    return ready


def refuse_request():
    return {"refused": True, "products": [], "note": "Mình không làm việc đó."}


def matches_request(products, request):
    if not products or not request:
        return False
    brand = (request.get("brand") or "").casefold()
    family = (request.get("family") or "").casefold()
    if brand == "macbook" or family == "macbook":
        needle = "macbook"
    elif family == "iphone":
        needle = "iphone"
    elif family == "ipad":
        needle = "ipad"
    else:
        needle = brand
    for item in products:
        if needle and needle not in f"{item.get('name', '')} {item.get('brand', '')}".casefold():
            return False
        if request.get("specific"):
            if request.get("ram_gb") and _ram_gb(item) != int(request["ram_gb"]):
                return False
            folded_name = (item.get("name") or "").casefold()
            if request.get("line") == "pro" and family != "iphone" and "macbook pro" not in folded_name:
                return False
            if request.get("screen") and f"{int(request['screen'])} inch" not in folded_name:
                return False
            continue
        if request.get("use") == "study" and item.get("category") not in ("laptop", "tablet", None, ""):
            return False
        if request.get("use") == "study" and _ai_score(item) < 5:
            return False
    return True


def follow_lead(request):
    use = (request or {}).get("use") or ""
    brand = (request or {}).get("brand") or ""
    if use == "study" and brand == "MacBook":
        return "MacBook Air không đủ để học AI vì RAM thấp và GPU tích hợp. Bản Pro, RAM từ 24 GB, mới chạy được bài."
    if brand == "MacBook":
        return "Một vài MacBook còn hàng."
    if use == "study" and brand:
        return f"Laptop {brand} để học AI cần GPU rời hoặc RAM từ 24 GB. Mấy máy này chạy được bài."
    if use == "study":
        return "Học AI cần GPU rời hoặc RAM từ 24 GB. MacBook Air RAM 16 GB không nằm trong nhóm này."
    if brand:
        return f"Một vài máy {brand} còn hàng."
    return "Mình thấy một vài máy còn hàng."


def lead_fits(lead, request):
    folded = (lead or "").casefold()
    brand = ((request or {}).get("brand") or "").casefold()
    if brand == "macbook" and "macbook" not in folded and "pro" not in folded and "16" not in folded:
        return False
    if brand and brand not in {"macbook", "apple"} and brand.casefold() not in folded:
        return False
    return True
