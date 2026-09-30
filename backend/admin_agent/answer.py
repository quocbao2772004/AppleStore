"""Admin tool schema and the answer loop. Every number comes from reports.py."""
import json
import os
import urllib.request

from .format import _clip
from .reports import inventory_report, order_report, sales_report, store_summary, work_queue
from .route import local_calls

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "store_summary",
            "description": "Tổng quan: số sản phẩm theo danh mục, đơn, doanh thu đơn chưa hủy, tài khoản, đánh giá, số bài chờ duyệt, yêu cầu hỗ trợ, máy hết hàng và còn dưới 10.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sales_report",
            "description": "Sản phẩm bán chạy theo số lượng và doanh thu. Bỏ đơn đã hủy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "7d", "30d", "all"],
                        "description": "today là hôm nay, 7d là 7 ngày, 30d là 30 ngày, all là toàn bộ.",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["", "phone", "laptop", "tablet", "headphones", "smartwatch"],
                        "description": "Để trống nếu không lọc danh mục.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_report",
            "description": "Tồn kho. out là hết hàng. low là còn dưới 10 máy. lookup là tìm theo tên sản phẩm hoặc hãng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["out", "low", "lookup"]},
                    "query": {"type": "string", "description": "Tên sản phẩm hoặc hãng khi mode=lookup."},
                    "category": {
                        "type": "string",
                        "enum": ["", "phone", "laptop", "tablet", "headphones", "smartwatch"],
                        "description": "Lọc một danh mục. Để trống nếu hỏi cả cửa hàng.",
                    },
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "order_report",
            "description": "Đơn hàng. status đếm theo trạng thái. recent lấy 5 đơn mới. one xem một đơn theo mã.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["status", "recent", "one"]},
                    "order_id": {"type": "integer", "description": "Mã đơn khi mode=one."},
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "work_queue",
            "description": "Việc cần xử lý: đánh giá chờ duyệt và yêu cầu hỗ trợ mới.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _run_tool(conn, name, arguments):
    args = arguments or {}
    if name == "store_summary":
        return store_summary(conn)
    if name == "sales_report":
        return sales_report(conn, args.get("period") or "all", args.get("category") or "")
    if name == "inventory_report":
        return inventory_report(conn, args.get("mode") or "out", args.get("query") or "", args.get("category") or "")
    if name == "order_report":
        return order_report(conn, args.get("mode") or "status", args.get("order_id"))
    if name == "work_queue":
        return work_queue(conn)
    return {"note": "Không có tool này."}


def _lines(result, name):
    if name == "store_summary":
        categories = ", ".join(f"{item['count']} {item['category'].lower()}" for item in result["categories"] if item["count"])
        orders = ", ".join(f"{item['count']} {item['status'].lower()}" for item in result["orders"])
        average = result["rating_average"] if result["rating_average"] is not None else "chưa có"
        return [
            f"Đang bán {result['products']} sản phẩm: {categories}.",
            f"Đơn: {orders}. Doanh thu đơn chưa hủy: {result['revenue_excluding_cancelled']}.",
            f"Tài khoản: {result['users']}. Đánh giá: {result['reviews']} bài, điểm trung bình {average}. Chờ duyệt: {result['reviews_pending']}.",
            f"Hỗ trợ: {result['support_requests']} yêu cầu. Hết hàng: {result['out_of_stock']}. Còn dưới 10 máy: {result['low_stock']}.",
        ]
    if name == "sales_report":
        lines = [
            f"Bán chạy {result['period']}, {result['category'].lower()}: {result['orders']} đơn, {result['units']} máy, doanh thu {result['revenue']}. Đơn đã hủy không tính."
        ]
        if not result["best_sellers"]:
            lines.append("Chưa có sản phẩm bán trong khoảng này.")
        for item in result["best_sellers"]:
            lines.append(f"• {item['name']}: {item['qty']} máy, {item['revenue']}")
        return lines
    if name == "inventory_report":
        if result.get("note"):
            return [result["note"]]
        lines = [f"{result['title']}: {result['count']} sản phẩm."]
        if not result["items"]:
            lines.append("Không có sản phẩm trong nhóm này.")
        for item in result["items"]:
            brand = f", {item['brand']}" if item["brand"] else ""
            lines.append(f"• {item['name']}{brand}: còn {item['stock']}, {item['price']}")
        if result["count"] > len(result["items"]):
            lines.append(f"Đang hiện {len(result['items'])} dòng đầu.")
        return lines
    if name == "order_report":
        if "order" in result:
            return _order_lines(result["order"])
        if result.get("orders") and "status" in result["orders"][0] and "items" not in result["orders"][0]:
            return [f"{item['status']}: {item['count']} đơn, {item['total']}" for item in result["orders"]]
        lines = []
        for order in result.get("orders") or []:
            lines.extend(_order_lines(order))
        return lines or ["Chưa có đơn."]
    if name == "work_queue":
        lines = [f"Đánh giá chờ duyệt: {result['reviews_pending']}."]
        for item in result["reviews"]:
            score = "" if item["rating"] is None else f"{item['rating']:g}/5, "
            lines.append(f"• {item['product']} — {item['author']}, {score}{item['body']}")
        lines.append(f"Hỗ trợ: {result['support_requests']} yêu cầu.")
        for item in result["support"]:
            lines.append(f"• #{item['id']} {item['name']} ({item['email']}), {item['at']}: {item['body']}")
        return lines
    return [result.get("note") or "Chưa có số liệu."]


def _order_lines(order):
    if not order.get("found", True):
        return [order.get("note") or "Không có đơn này."]
    items = "; ".join(f"{item['name']} × {item['qty']} ({item['line_total']})" for item in order["items"])
    who = " ".join(part for part in (order["receiver"], order["phone"], order["address"]) if part)
    lines = [f"Đơn #{order['order_id']} · {order['status']} · {order['total']} · {order['pay']}."]
    if who:
        lines.append(who)
    lines.append(f"Đặt {order['created_at']}. Nhận {order['delivery']}. {items}".strip())
    return lines


def speak_local(conn, question):
    blocks = []
    for name, arguments in local_calls(question):
        blocks.extend(_lines(_run_tool(conn, name, arguments), name))
    return "\n".join(blocks)


def _ask_model(conn, question, key):
    base = os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý quản trị cửa hàng Octopus Store. Trả lời tiếng Việt, ngắn, đủ số. "
                "Chỉ dùng số liệu từ tool. Không bịa. Không sửa dữ liệu và không đặt hàng. "
                "Tổng quan: store_summary. Bán chạy hoặc doanh thu: sales_report. "
                "Đơn đã hủy không tính vào bán chạy. period là today, 7d, 30d hoặc all. "
                "Tồn kho: inventory_report, mode out, low hoặc lookup. Có thể kèm category. "
                "Đơn: order_report, mode status, recent hoặc one. "
                "Đánh giá chờ duyệt và hỗ trợ: work_queue. "
                "Nếu tool trả về rỗng, nói chưa có."
            ),
        },
        {"role": "user", "content": question[:500]},
    ]
    last = None
    for _ in range(3):
        request = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps({
                "model": model,
                "messages": messages,
                "tools": TOOLS,
                "temperature": 0.1,
            }).encode(),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.loads(response.read().decode())
        message = payload["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return (message.get("content") or "").strip()
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            result = _run_tool(conn, name, arguments)
            last = (name, result)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })
    if last:
        return "\n".join(_lines(last[1], last[0]))
    return ""


def answer_admin(conn, question):
    question = (question or "").strip()[:500]
    if not question:
        return "Nhập một câu hỏi.", ""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return speak_local(conn, question), "Đang trả lời từ số liệu trong máy."
    try:
        text = _ask_model(conn, question, key)
    except Exception as exc:
        print(f"Admin agent failed: {type(exc).__name__}")
        text = ""
    if text:
        return text, ""
    return speak_local(conn, question), "Không kết nối được trợ lý từ xa, nên đây là số liệu trong máy."
