"""Tìm tên sản phẩm cho ô tìm kiếm trên thanh điều hướng.

Trình duyệt gọi GET /api/suggest?q=...
backend/server.py nhận kết quả rồi thêm giá và ảnh trước khi trả JSON.
"""


def search_names(conn, text, limit=8):
    text = (text or "").strip()[:60]
    if len(text) < 1:
        return []
    safe = text.replace("\\", "").replace("%", "").replace("_", "")
    return conn.execute(
        """
        SELECT source_product_id, name, price_vnd
        FROM products
        WHERE is_live_catalog AND name ILIKE %s
        ORDER BY price_vnd DESC NULLS LAST
        LIMIT %s
        """,
        (f"%{safe}%", limit),
    ).fetchall()
