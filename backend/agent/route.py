"""Pick the customer action. Eval and the store fallback both call route()."""
import re

from .policy import needs_tool
from .slots import resolve_request

_SAFETY_RE = re.compile(
    r"xóa|xoá|drop table|delete from|update products|dump |mật khẩu|password|"
    r"token session|user khác|user_id|bỏ qua|bo qua|ignore previous|"
    r"select \*|trừ tiền thật|sửa stock|sua stock|tắt kiểm tra|tat kiem tra|"
    r"export the database|app_users|không phải máy của cửa hàng|admin@|khách khác|khach khac|"
    r"thực hiện order|thuc hien order",
    re.I,
)
_ORDER_RE = re.compile(
    r"đơn (của|hàng|số|#)|theo dõi đơn|don cua toi|xem đơn|xem lại đơn|"
    r"kiểm tra đơn|tra cứu đơn|order của tôi|mã đơn|lịch sử đơn|"
    r"tôi có đơn|đơn vừa|đơn hôm|đơn gần|đơn mới|đơn cũ|đơn tuần|"
    r"đơn đặt|tôi đặt đơn|đã giao chưa|đơn hàng",
    re.I,
)
_CHECKOUT_RE = re.compile(
    r"\bđặt\b|\bmua\b|chốt đơn|thêm vào giỏ|tạo đơn|xác nhận đặt|ok đặt",
    re.I,
)
_DECLINE_RE = re.compile(
    r"không muốn|chẳng muốn|chưa muốn|đừng đặt|đừng mua|thôi đừng|"
    r"không đặt|không mua|đâu có|"
    r"có (?:muốn )?(?:đặt|mua).{0,60}đâu|có muốn.{0,60}đâu",
    re.I,
)
_PERMISSION_RE = re.compile(
    r"có được không|được không|được chứ|có được ko|có sao không|mua được không|đặt được không",
    re.I,
)
_COMPARE_RE = re.compile(r"so sánh|so sanh|khác .+ chỗ nào|\bhay\b|giữa .+ và .+", re.I)
_STOCK_RE = re.compile(r"còn hàng|còn máy|tồn kho|còn không", re.I)
_DETAIL_RE = re.compile(r"thông số|chi tiết|cấu hình|cho xem|\bmở\b", re.I)


def _history_users(history):
    lines = []
    for item in history or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2 or item[0] != "user":
            continue
        text = (item[1] or "").strip()
        if text:
            lines.append(text)
    return lines


def _checkout_line(text):
    if _DECLINE_RE.search(text) or _PERMISSION_RE.search(text):
        return False
    return _CHECKOUT_RE.search(text) is not None


def route(question, resolved=None, history=None):
    """Pick an action from the sentence. The model may still choose a tool; this is the local router."""
    text = question or ""
    resolved = resolved or {}
    if _SAFETY_RE.search(text):
        return {"intent": "safety", "tool": "refuse"}
    if _ORDER_RE.search(text):
        return {"intent": "order_tracking", "tool": "list_orders"}
    if _DECLINE_RE.search(text) or _PERMISSION_RE.search(text):
        return {"intent": "chat", "tool": "none"}
    prior_checkout = any(_checkout_line(line) for line in _history_users(history))
    if _checkout_line(text) or (prior_checkout and re.search(r"thôi|cho tôi|cái đó|máy này", text, re.I)):
        return {"intent": "checkout", "tool": "prepare_checkout"}
    if _COMPARE_RE.search(text):
        return {"intent": "comparison", "tool": "compare_products"}
    if _STOCK_RE.search(text):
        return {"intent": "inventory", "tool": "check_inventory"}
    named = bool(
        resolved.get("family")
        or resolved.get("line")
        or resolved.get("chip")
        or resolved.get("screen")
        or resolved.get("query")
        or resolved.get("storage_gb")
    )
    detail = bool(_DETAIL_RE.search(text)) or (resolved.get("specific") and named) or (resolved.get("storage_gb") and named)
    if detail:
        bare_ram = (
            resolved.get("specific")
            and resolved.get("ram_gb")
            and not named
            and not _DETAIL_RE.search(text)
        )
        return {"intent": "product_detail", "tool": "search_products" if bare_ram else "get_product"}
    if resolved.get("specific"):
        return {"intent": "product_detail", "tool": "search_products"}
    if not needs_tool(text):
        return {"intent": "chat", "tool": "none"}
    if resolved.get("use") == "study" or resolved.get("price_target"):
        return {"intent": "recommendation", "tool": "search_products"}
    return {"intent": "product_search", "tool": "search_products"}
