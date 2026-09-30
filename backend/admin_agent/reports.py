"""Read-only store reports. Cancelled orders stay out of revenue."""
from .format import (
    CATEGORIES,
    PERIODS,
    SLOT_LABEL,
    STATUS_LABEL,
    _clean,
    _clip,
    _money,
    _pay_label,
    _period_label,
    _period_start,
    _when,
)

def store_summary(conn):
    products = conn.execute("SELECT count(*) FROM products WHERE is_live_catalog").fetchone()[0]
    by_category = dict(conn.execute(
        "SELECT category, count(*) FROM products WHERE is_live_catalog GROUP BY category"
    ).fetchall())
    orders = conn.execute(
        """
        SELECT status, count(*), coalesce(sum(total_vnd), 0)
        FROM orders GROUP BY status
        """
    ).fetchall()
    users = conn.execute("SELECT count(*) FROM app_users").fetchone()[0]
    reviews = conn.execute(
        """
        SELECT count(*), round(avg(rating_value)::numeric, 1),
               count(*) FILTER (WHERE approved IS FALSE)
        FROM product_reviews
        """
    ).fetchone()
    support = conn.execute("SELECT count(*) FROM support_requests").fetchone()[0]
    stock = conn.execute(
        """
        SELECT count(*) FILTER (WHERE stock = 0),
               count(*) FILTER (WHERE stock > 0 AND stock < 10)
        FROM products WHERE is_live_catalog
        """
    ).fetchone()
    revenue = 0
    order_counts = []
    for status, count, total in orders:
        if status != "cancelled":
            revenue += int(total or 0)
        order_counts.append({
            "status": STATUS_LABEL.get(status, status),
            "count": int(count),
        })
    categories = [
        {"category": CATEGORIES.get(key, key), "count": int(by_category.get(key, 0))}
        for key in list(CATEGORIES) + [key for key in by_category if key not in CATEGORIES]
    ]
    return {
        "products": int(products),
        "categories": categories,
        "orders": order_counts,
        "revenue_excluding_cancelled": _money(revenue),
        "users": int(users),
        "reviews": int(reviews[0]),
        "rating_average": None if reviews[1] is None else float(reviews[1]),
        "reviews_pending": int(reviews[2] or 0),
        "support_requests": int(support),
        "out_of_stock": int(stock[0]),
        "low_stock": int(stock[1]),
    }


def sales_report(conn, period="all", category=""):
    period = period if period in PERIODS else "all"
    category = category if category in CATEGORIES else ""
    start = _period_start(period)
    totals = conn.execute(
        """
        SELECT count(DISTINCT o.id), coalesce(sum(i.qty), 0), coalesce(sum(i.unit_price * i.qty), 0)
        FROM orders o
        JOIN order_items i ON i.order_id = o.id
        LEFT JOIN products p ON p.source_product_id = i.product_id
        WHERE o.status <> 'cancelled'
          AND (%s::timestamptz IS NULL OR o.created_at >= %s)
          AND (%s = '' OR p.category = %s)
        """,
        (start, start, category, category),
    ).fetchone()
    rows = conn.execute(
        """
        SELECT i.name, sum(i.qty)::int, coalesce(sum(i.unit_price * i.qty), 0)
        FROM order_items i
        JOIN orders o ON o.id = i.order_id
        LEFT JOIN products p ON p.source_product_id = i.product_id
        WHERE o.status <> 'cancelled'
          AND (%s::timestamptz IS NULL OR o.created_at >= %s)
          AND (%s = '' OR p.category = %s)
        GROUP BY i.name
        ORDER BY sum(i.qty) DESC, sum(i.unit_price * i.qty) DESC
        LIMIT 5
        """,
        (start, start, category, category),
    ).fetchall()
    return {
        "period": _period_label(period),
        "category": CATEGORIES.get(category, "mọi danh mục"),
        "orders": int(totals[0] or 0),
        "units": int(totals[1] or 0),
        "revenue": _money(totals[2]),
        "best_sellers": [
            {"name": row[0], "qty": int(row[1]), "revenue": _money(row[2])}
            for row in rows
        ],
    }


def inventory_report(conn, mode="out", query="", category=""):
    mode = mode if mode in {"out", "low", "lookup"} else "out"
    query = _clean(query)
    category = category if category in CATEGORIES else ""
    scope = CATEGORIES.get(category, "")
    if mode == "lookup" and not query:
        return {"mode": "lookup", "note": "Cần tên sản phẩm hoặc hãng."}
    if mode == "out":
        where = "is_live_catalog AND stock = 0"
        params = ()
        title = "Hết hàng"
    elif mode == "low":
        where = "is_live_catalog AND stock > 0 AND stock < 10"
        params = ()
        title = "Còn dưới 10 máy"
    else:
        where = "is_live_catalog AND (name ILIKE %s OR coalesce(brand, '') ILIKE %s)"
        params = (f"%{query}%", f"%{query}%")
        title = f"Tồn kho khớp “{query}”"
    if category:
        where += " AND category = %s"
        params = params + (category,)
        title += f" trong {scope.lower()}"
    total = conn.execute(f"SELECT count(*) FROM products WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT name, coalesce(brand, ''), stock, price_vnd
        FROM products WHERE {where}
        ORDER BY stock, name
        LIMIT 8
        """,
        params,
    ).fetchall()
    return {
        "title": title,
        "count": int(total),
        "items": [
            {"name": row[0], "brand": row[1], "stock": int(row[2] or 0), "price": _money(row[3])}
            for row in rows
        ],
    }


def order_report(conn, mode="status", order_id=None):
    mode = mode if mode in {"status", "recent", "one"} else "status"
    if mode == "status":
        rows = conn.execute(
            "SELECT status, count(*), coalesce(sum(total_vnd), 0) FROM orders GROUP BY status"
        ).fetchall()
        found = {row[0]: row for row in rows}
        return {
            "orders": [
                {
                    "status": label,
                    "count": int(found.get(key, (key, 0, 0))[1] or 0),
                    "total": _money(found.get(key, (key, 0, 0))[2]),
                }
                for key, label in STATUS_LABEL.items()
            ]
        }
    if mode == "one":
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return {"found": False, "note": "Cần mã đơn."}
        return {"order": _order_detail(conn, order_id)}
    rows = conn.execute(
        """
        SELECT id FROM orders ORDER BY id DESC LIMIT 5
        """
    ).fetchall()
    return {"orders": [_order_detail(conn, row[0]) for row in rows]}


def _order_detail(conn, order_id):
    row = conn.execute(
        """
        SELECT id, status, total_vnd, ship_name, ship_phone, ship_address,
               deliver_on, deliver_slot, coalesce(pay_method, 'cod'), created_at
        FROM orders WHERE id=%s
        """,
        (order_id,),
    ).fetchone()
    if not row:
        return {"found": False, "order_id": order_id, "note": "Không có đơn này."}
    items = conn.execute(
        "SELECT name, qty, unit_price FROM order_items WHERE order_id=%s ORDER BY id",
        (order_id,),
    ).fetchall()
    slot = SLOT_LABEL.get(row[7], row[7] or "")
    return {
        "found": True,
        "order_id": int(row[0]),
        "status": STATUS_LABEL.get(row[1], row[1]),
        "total": _money(row[2]),
        "receiver": row[3] or "",
        "phone": row[4] or "",
        "address": row[5] or "",
        "delivery": " ".join(part for part in (_when(row[6]), slot) if part),
        "pay": _pay_label(row[8]),
        "created_at": _when(row[9]),
        "items": [
            {"name": item[0], "qty": int(item[1]), "line_total": _money(int(item[2] or 0) * int(item[1]))}
            for item in items
        ],
    }


def work_queue(conn):
    pending_count = conn.execute(
        "SELECT count(*) FROM product_reviews WHERE approved IS FALSE"
    ).fetchone()[0]
    reviews = conn.execute(
        """
        SELECT r.product_id, r.review_index, p.name, r.author_name, r.rating_value, r.review_body
        FROM product_reviews r
        JOIN products p ON p.source_product_id = r.product_id
        WHERE r.approved IS FALSE
        ORDER BY r.product_id DESC, r.review_index DESC
        LIMIT 8
        """
    ).fetchall()
    support_count = conn.execute("SELECT count(*) FROM support_requests").fetchone()[0]
    support = conn.execute(
        """
        SELECT id, name, email, body, created_at
        FROM support_requests ORDER BY id DESC LIMIT 8
        """
    ).fetchall()
    return {
        "reviews_pending": int(pending_count),
        "reviews": [
            {
                "product": row[2],
                "author": row[3] or "Ẩn danh",
                "rating": None if row[4] is None else float(row[4]),
                "body": _clip(row[5]),
            }
            for row in reviews
        ],
        "support_requests": int(support_count),
        "support": [
            {"id": int(row[0]), "name": row[1], "email": row[2], "body": _clip(row[3]), "at": _when(row[4])}
            for row in support
        ],
    }
