"""Live admin assistant: one compiled LangGraph over the read-only reports.

Intent picks one report. Python keeps an explicit sentence on the offline
router and carries a period or order id through a follow-up. Explain writes
from the report JSON. There is no write tool.
"""
import contextvars
import json
import os
import re
import time
import warnings
from typing import TypedDict

import langchain_core  # noqa: F401

warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change",
    category=PendingDeprecationWarning,
)
from langgraph.graph import END, StateGraph

from .format import _fold
from .prompts.explain import EXPLAIN
from .prompts.intent import INTENT
from .route import _category_from_text, local_calls

_CONN = contextvars.ContextVar("octopus_admin_conn", default=None)
_TOOLS = {"store_summary", "sales_report", "inventory_report", "order_report", "work_queue", "none"}
_PERIODS = {"today", "7d", "30d", "all"}
_CATEGORIES = {"phone", "laptop", "tablet", "headphones", "smartwatch"}
_WRITE = re.compile(
    r"xoa|cap nhat|sua gia|dat hang|chuyen trang thai|them don|sua don|huy giup|xoa don"
)


class AdminState(TypedDict, total=False):
    question: str
    history: list
    started: float
    trace: list
    tool: str
    arguments: dict
    result: dict
    text: str
    text_from: str
    refuse: bool


def _stamp(state):
    started = state.get("started") or time.perf_counter()
    return round((time.perf_counter() - started) * 1000, 1)


def _pairs(history):
    pairs = []
    for item in history or []:
        if isinstance(item, dict):
            role = item.get("role") or ""
            body = item.get("content") or item.get("body") or ""
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            role, body = item[0], item[1]
        else:
            continue
        pairs.append((role, body or ""))
    return pairs


def _positive_order(value):
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _mentioned_period(folded):
    if "hom nay" in folded or "ngay nay" in folded:
        return "today"
    if "tuan" in folded or "7 ngay" in folded:
        return "7d"
    if "thang" in folded or "30 ngay" in folded:
        return "30d"
    if "toan bo" in folded or "tat ca" in folded:
        return "all"
    return ""


def _anaphoric(folded):
    if re.search(r"cua ai|o tren|vua roi|the con|con nua", folded):
        return True
    if re.search(r"\b(don|may|cai|san pham)\s+(do|nay|ay|kia)\b", folded):
        return True
    return re.search(r"\b(do|ay|kia)\b", folded) is not None


def _writes(folded):
    return _WRITE.search(folded or "") is not None


def _period_from_history(history):
    for role, body in reversed(_pairs(history)):
        if role not in ("bot", "assistant"):
            continue
        period = _mentioned_period(_fold(body))
        if period and period != "all":
            return period
    return ""


def _last_order_id(history):
    for role, body in reversed(_pairs(history)):
        if role not in ("bot", "assistant"):
            continue
        found = re.search(r"Đơn\s*#\s*(\d+)", body or "", re.I)
        if found:
            return int(found.group(1))
    return None


def _last_product_name(history):
    """Use the first bullet of the previous report when a follow-up names no product."""
    for role, body in reversed(_pairs(history)):
        if role not in ("bot", "assistant"):
            continue
        for line in (body or "").splitlines():
            line = line.strip()
            if not line.startswith("•"):
                continue
            name = re.split(r"\s*[:—–]\s", line.lstrip("•").strip(), maxsplit=1)[0].strip()
            if name:
                return name[:80]
    return ""


def _from_model(choice):
    if not isinstance(choice, dict):
        return "none", {}
    tool = choice.get("tool") if choice.get("tool") in _TOOLS else "none"
    period = choice.get("period") if choice.get("period") in _PERIODS else ""
    category = choice.get("category") if choice.get("category") in _CATEGORIES else ""
    inventory_mode = choice.get("inventory_mode") or ""
    if inventory_mode not in ("out", "low", "lookup") and choice.get("mode") in ("out", "low", "lookup"):
        inventory_mode = choice.get("mode")
    if inventory_mode not in ("out", "low", "lookup"):
        inventory_mode = ""
    order_mode = choice.get("order_mode") or ""
    if order_mode not in ("status", "recent", "one") and choice.get("mode") in ("status", "recent", "one"):
        order_mode = choice.get("mode")
    if order_mode not in ("status", "recent", "one"):
        order_mode = ""
    query = re.sub(r"\s+", " ", str(choice.get("query") or "")).strip()[:80]
    order_id = _positive_order(choice.get("order_id"))
    if tool == "sales_report":
        return tool, {"period": period or "all", "category": category}
    if tool == "inventory_report":
        return tool, {"mode": inventory_mode or "out", "query": query, "category": category}
    if tool == "order_report":
        arguments = {"mode": order_mode or "status"}
        if order_id:
            arguments["order_id"] = order_id
        return tool, arguments
    return tool, {}


def _carry(question, folded, history, tool, arguments):
    arguments = dict(arguments or {})
    category = _category_from_text(folded)
    if _anaphoric(folded) and re.search(r"\bdon\b", folded):
        mode = arguments.get("mode") or "recent"
        if re.search(r"\b(do|ay|kia)\b|cua ai|don nay", folded):
            mode = "one"
        arguments = {"mode": mode}
        tool = "order_report"
    elif _anaphoric(folded) and re.search(r"het hang|ton kho|con hang|con bao nhieu|sap het|duoi 10", folded):
        mode = "lookup"
        if "duoi 10" in folded or "sap het" in folded:
            mode = "low"
        elif "het hang" in folded:
            mode = "out"
        arguments = {
            "mode": mode,
            "query": arguments.get("query") or "",
            "category": category or arguments.get("category") or "",
        }
        tool = "inventory_report"
    elif _anaphoric(folded) and category:
        arguments = {"period": arguments.get("period") or "", "category": category}
        tool = "sales_report"

    if tool == "sales_report":
        said = _mentioned_period(folded)
        carried = _period_from_history(history)
        if said:
            arguments["period"] = said
        elif carried:
            arguments["period"] = carried
        else:
            arguments["period"] = arguments.get("period") or "all"
        if category:
            arguments["category"] = category
        elif "category" not in arguments:
            arguments["category"] = ""
        arguments["category"] = arguments.get("category") or ""
    elif tool == "inventory_report":
        if category:
            arguments["category"] = category
        arguments["mode"] = arguments.get("mode") or "out"
        if arguments["mode"] == "lookup" and not arguments.get("query"):
            arguments["query"] = _last_product_name(history)
        arguments["query"] = arguments.get("query") or ""
        arguments["category"] = arguments.get("category") or ""
    elif tool == "order_report":
        arguments["mode"] = arguments.get("mode") or "status"
        if arguments["mode"] == "one" and not arguments.get("order_id"):
            found = _last_order_id(history)
            if found:
                arguments["order_id"] = found
    return tool, arguments


def apply_admin_guards(question, history, choice):
    """Keep one explicit report, and carry period or order id across a follow-up."""
    folded = _fold(question)
    history = _pairs(history)
    if _writes(folded):
        return "none", {}
    calls = local_calls(question)
    specific = calls != [("store_summary", {})]
    tool, arguments = _from_model(choice)
    if specific and not _anaphoric(folded):
        if len(calls) == 1 or tool not in {name for name, _ in calls}:
            name, routed = calls[0]
            return name, dict(routed)
    return _carry(question, folded, history, tool, arguments)


def _history_messages(history):
    messages = []
    for role, body in _pairs(history)[-8:]:
        text = re.sub(r"\s+", " ", body or "").strip()[:500]
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role in ("bot", "assistant"):
            messages.append({"role": "assistant", "content": text})
    return messages


def _intent_choice(question, history):
    from agent.model import _complete

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for admin chat")
    base = os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "admin_turn",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "enum": sorted(_TOOLS)},
                    "period": {"type": "string", "enum": ["", "today", "7d", "30d", "all"]},
                    "category": {"type": "string", "enum": ["", *sorted(_CATEGORIES)]},
                    "inventory_mode": {"type": "string", "enum": ["", "out", "low", "lookup"]},
                    "query": {"type": "string"},
                    "order_mode": {"type": "string", "enum": ["", "status", "recent", "one"]},
                    "order_id": {"type": ["integer", "null"]},
                },
                "required": ["tool", "period", "category", "inventory_mode", "query", "order_mode", "order_id"],
                "additionalProperties": False,
            },
        },
    }
    messages = [
        {"role": "system", "content": INTENT},
        {"role": "user", "content": json.dumps({
            "history": _history_messages(history),
            "current_user_message": question[:500],
        }, ensure_ascii=False)},
    ]
    import urllib.error

    try:
        message = _complete(base, key, model_name, messages, temperature=0, response_format=schema)
    except urllib.error.HTTPError as exc:
        if exc.code not in (400, 422):
            raise
        message = _complete(
            base, key, model_name, messages, temperature=0, response_format={"type": "json_object"},
        )
    raw = json.loads(message.get("content") or "")
    if not isinstance(raw, dict):
        raise ValueError("Provider returned an invalid admin action")
    return raw


def intent_node(state):
    question = state.get("question") or ""
    history = _pairs(state.get("history"))
    t0 = _stamp(state)
    trace = list(state.get("trace") or [])
    if _writes(_fold(question)):
        trace.append({
            "kind": "intent", "name": "Chọn việc", "tool": "none", "arguments": {},
            "text": "Câu này muốn sửa dữ liệu. Bỏ qua tool.", "t0": t0, "t1": _stamp(state),
        })
        return {"tool": "none", "arguments": {}, "refuse": True, "trace": trace}
    choice = _intent_choice(question, history)
    tool, arguments = apply_admin_guards(question, history, choice)
    trace.append({
        "kind": "intent", "name": "Chọn việc", "tool": tool, "arguments": arguments,
        "model_tool": choice.get("tool") or "", "t0": t0, "t1": _stamp(state),
    })
    return {"tool": tool, "arguments": arguments, "refuse": False, "trace": trace}


def _after_intent(state):
    if (state.get("tool") or "none") in ("none", ""):
        return "explain"
    return "tool"


def tool_node(state):
    from .answer import _run_tool

    name = state.get("tool") or ""
    arguments = state.get("arguments") or {}
    t0 = _stamp(state)
    result = _run_tool(_CONN.get(), name, arguments)
    trace = list(state.get("trace") or [])
    trace.append({
        "kind": "tool", "name": name, "arguments": arguments, "t0": t0, "t1": _stamp(state),
    })
    return {"result": result, "trace": trace}


def _has_number(text, fact):
    fact = str(fact).strip()
    if not fact:
        return True
    if fact in (text or ""):
        return True
    if fact.isdigit():
        return re.search(r"(?<!\d)" + fact + r"(?!\d)", text or "") is not None
    digits = re.sub(r"\D", "", fact)
    if len(digits) >= 3 and digits in re.sub(r"\D", "", text or ""):
        return True
    return False


def _missing_facts(tool, result, text):
    result = result or {}
    if tool == "store_summary":
        return not (
            _has_number(text, result.get("products"))
            and _has_number(text, result.get("revenue_excluding_cancelled"))
        )
    if tool == "sales_report":
        if not _has_number(text, result.get("period")) or not _has_number(text, result.get("revenue")):
            return True
        sellers = result.get("best_sellers") or []
        if not sellers:
            return "chưa" not in (text or "").casefold() and not _has_number(text, result.get("units"))
        first = sellers[0]
        return not (_has_number(text, first.get("name")) and _has_number(text, first.get("qty")))
    if tool == "inventory_report":
        if result.get("note"):
            return result["note"] not in (text or "")
        if not _has_number(text, result.get("count")):
            return True
        items = result.get("items") or []
        if not items:
            return "không" not in (text or "").casefold()
        return not (_has_number(text, items[0].get("name")) and _has_number(text, items[0].get("stock")))
    if tool == "order_report":
        order = result.get("order")
        if isinstance(order, dict):
            if order.get("found") is False:
                return "không" not in (text or "").casefold()
            if not _has_number(text, order.get("order_id")):
                return True
            receiver = (order.get("receiver") or "").strip()
            return bool(receiver) and receiver not in (text or "")
        orders = result.get("orders") or []
        if orders and "order_id" in orders[0]:
            found = re.search(r"Đơn\s*#\s*(\d+)", text or "", re.I)
            return not found or int(found.group(1)) != int(orders[0].get("order_id"))
        if orders and "status" in orders[0]:
            return any(item.get("status") and item["status"] not in (text or "") for item in orders)
        return "chưa" not in (text or "").casefold()
    if tool == "work_queue":
        return not (
            _has_number(text, result.get("reviews_pending"))
            and _has_number(text, result.get("support_requests"))
        )
    return False


def explain_node(state):
    from .answer import _lines

    tool = state.get("tool") or "none"
    question = state.get("question") or ""
    result = state.get("result") or {}
    t0 = _stamp(state)
    if state.get("refuse"):
        text = "Mình chỉ đọc số liệu cửa hàng, không xóa hay sửa đơn."
        return _finish(state, text, "tool_note", t0)
    if tool in ("none", ""):
        text = "Bạn muốn xem doanh thu, kho, đơn hay việc đang chờ?"
        return _finish(state, text, "tool_note", t0)
    fallback = "\n".join(_lines(result, tool))
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    content = ""
    if key:
        try:
            content = _explain_text(question, tool, result)
        except Exception as exc:
            print("Admin explain failed: " + type(exc).__name__)
            content = ""
    if content and not _missing_facts(tool, result, content):
        return _finish(state, content, "model", t0)
    return _finish(state, fallback, "tool_note", t0)


def _explain_text(question, tool, result):
    from agent.model import _complete

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    base = os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    messages = [
        {"role": "system", "content": EXPLAIN},
        {"role": "user", "content": json.dumps({
            "question": question[:500],
            "tool": tool,
            "tool_result": result,
        }, ensure_ascii=False)},
    ]
    message = _complete(base, key, model_name, messages, temperature=0.2)
    return (message.get("content") or "").strip()


def _finish(state, text, text_from, t0):
    trace = list(state.get("trace") or [])
    trace.append({
        "kind": "explain", "name": "Trả lời", "text": (text or "")[:300],
        "text_from": text_from, "t0": t0, "t1": _stamp(state),
    })
    return {"text": text, "text_from": text_from, "trace": trace}


def _build():
    graph = StateGraph(AdminState)
    graph.add_node("intent", intent_node)
    graph.add_node("tool", tool_node)
    graph.add_node("explain", explain_node)
    graph.set_entry_point("intent")
    graph.add_conditional_edges("intent", _after_intent, {"tool": "tool", "explain": "explain"})
    graph.add_edge("tool", "explain")
    graph.add_edge("explain", END)
    return graph.compile()


ADMIN_GRAPH = _build()


def run_admin_graph(conn, question, history=None):
    """Run one admin turn. The report tools stay read-only."""
    token = _CONN.set(conn)
    try:
        final = ADMIN_GRAPH.invoke(
            {
                "question": question or "",
                "history": _pairs(history),
                "started": time.perf_counter(),
                "trace": [],
                "tool": "none",
                "arguments": {},
                "result": {},
                "text": "",
                "text_from": "",
                "refuse": False,
            },
            config={"callbacks": []},
        )
    finally:
        _CONN.reset(token)
    return {
        "text": final.get("text") or "",
        "text_from": final.get("text_from") or "",
        "tool": final.get("tool") or "none",
        "arguments": final.get("arguments") or {},
        "result": final.get("result") or {},
        "trace": final.get("trace") or [],
    }
