"""Live customer assistant: one compiled LangGraph in front of the existing tools.

The provider interprets intent and requirements once per turn. One tool step
queries the catalog; ranking and hard filters stay in Python. The explain step
writes prose from tool results.
"""
import contextvars
import json
import os
import re
import socket
import time
import urllib.error
import warnings
from typing import Any, TypedDict

from .prompts.chat import CHAT as _CHAT_SYSTEM
from .prompts.explain import EXPLAIN as _EXPLAIN_SYSTEM, recommendation_format
from .debug import debug

# langchain_core shows this pending warning by default. Register the ignore
# after that import and before LangGraph builds Reviver() with no allow-list.
# The constructor then uses "core", which is the same fallback it already takes.
import langchain_core  # noqa: F401

warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change",
    category=PendingDeprecationWarning,
)
from langgraph.graph import END, StateGraph


class ShopState(TypedDict, total=False):
    question: str
    history: list
    user: dict
    started: float
    trace: list
    products: list
    product_reasons: dict
    checkout: Any
    orders: Any
    result: dict
    advice_lead: str
    text: str
    text_from: str
    resolved: dict
    intent: str
    tool: str
    arguments: dict
    ask: str

_CONN = contextvars.ContextVar("octopus_shop_conn", default=None)

def _stamp(state):
    return round((time.perf_counter() - state["started"]) * 1000, 1)


def _warranty_text(result):
    """Quote the retrieval note and passages. Do not add a brand that was not retrieved."""
    result = result or {}
    note = (result.get("note") or "").strip()
    lines = []
    if note:
        lines.append(note)
    for item in (result.get("passages") or [])[:3]:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        title = (item.get("title") or "").strip()
        if title:
            lines.append(title + ": " + text)
        else:
            lines.append(text)
    if lines:
        return "\n".join(lines)
    return "Không có điều khoản của hãng này trong kho. Đừng lấy điều khoản hãng khác."


def intent_node(state):
    import agent.model as model
    from .understand import understand_turn

    question = state.get("question") or ""
    history = state.get("history") or []
    understood = understand_turn(question, history)
    resolved = understood["resolved"]
    # "study" is the AI search. Coding, school, and accounting must not inherit it.
    apply_turn_guards(question, history, resolved)
    slot_done = _stamp(state)
    trace = list(state.get("trace") or [])
    trace.append({
        "kind": "slots",
        "type": "SPAN",
        "name": "Đọc câu hỏi",
        "text": "Provider suy luận yêu cầu từ hội thoại.",
        "arguments": model._slot_snapshot(resolved),
        "input": {"question": question[:240]},
        "t0": 0,
        "t1": slot_done,
    })
    tool = understood["action"]
    # A provider classification cannot open checkout from free text. The
    # product card's explicit checkout action is handled separately by server.
    if tool == "prepare_checkout":
        tool = "search_products" if resolved.get("category") else "ask"
        if tool == "ask":
            understood["ask"] = "Bạn muốn xem loại sản phẩm nào trước khi chọn máy để đặt?"
    # A broad consultation needs a budget before recommending cards. The
    # provider infers the meaning; this guard enforces the conversation step
    # if its action choice varies between calls.
    # "tầm giá này" points at the card already on screen. The model history
    # is shortened before that price, so the binding is done here.
    named_from_sentence = pin_named_model(question, resolved)
    # "asus" in query is a brand column filter, not a product-name search.
    _brand_query_to_column(resolved)
    # "Có điện thoại Asus không" is a catalog lookup. A stock count of one
    # named unit, such as "còn hàng không", stays on check_inventory.
    if tool == "check_inventory" and not re.search(
        r"còn hàng|con hang|còn máy|con may|còn không|con khong|tồn kho|ton kho|còn mấy|con may",
        question or "",
        re.I,
    ):
        tool = "search_products"
        understood["ask"] = ""
    carry_discussed_price(question, history, resolved, named_from_sentence)
    has_budget = any(resolved.get(key) is not None for key in ("price_min", "price_max", "price_target"))
    # A free-form query can describe a game or use case, so it cannot by
    # itself prove the shopper named a device to inspect without a budget.
    named_product = named_from_sentence or bool(
        resolved.get("specific") or resolved.get("variant") or resolved.get("chip")
        or resolved.get("family") or resolved.get("brand")
    )
    # A named model, or a category plus a budget, is ready to search. Asking
    # again would hide the product the shopper already named.
    if tool == "ask" and (named_product or (resolved.get("category") and (has_budget or resolved.get("cheapest")))):
        tool = "search_products"
    if _category_overview(resolved) and tool in ("ask", "search_products", "list_category"):
        tool = "list_category"
        understood["ask"] = ""
    elif tool == "list_category" and not resolved.get("category"):
        tool = "ask"
        understood["ask"] = ""
    elif tool == "search_products" and not has_budget and not named_product and not resolved.get("cheapest"):
        tool = "ask"
        understood["ask"] = ""
    bargain = bargain_turn(question, history, resolved, _CONN.get())
    if bargain and bargain["mode"] == "ask":
        tool = "ask"
        understood["ask"] = bargain["ask"]
    elif bargain and bargain["mode"] == "quote":
        tool = "search_products"
        understood["ask"] = ""
    elif stick_to_shown_cards(question, history, resolved):
        # "mấy máy này" means the cards already on screen, not a new name search.
        tool = "search_products"
        understood["ask"] = ""
    intent = {"ask": "advise", "search_documents": "warranty", "refuse": "safety"}.get(tool, tool)
    ask = understood["ask"] if tool == "ask" else ""
    arguments = {}
    if tool == "search_documents":
        arguments = {"query": question, "brand": resolved.get("brand") or "", "doc_type": understood["doc_type"]}
    elif tool == "compare_products":
        arguments = {"product_a": understood["compare_left"], "product_b": understood["compare_right"], "query": question}
    elif tool in ("get_product", "check_inventory", "prepare_checkout"):
        arguments = {"query": resolved.get("query") or question}
        if tool == "prepare_checkout":
            arguments["qty"] = understood["qty"]
    intent_done = _stamp(state)
    trace.append({
        "kind": "intent",
        "type": "SPAN",
        "name": "Chọn việc",
        "text": "Ý định " + intent + ". Tool " + tool + ".",
        "tool": tool,
        "model_action": understood["action"],
        "arguments": arguments,
        "input": {"question": question[:240]},
        "t0": slot_done,
        "t1": intent_done,
    })
    return {
        "resolved": resolved,
        "intent": intent,
        "tool": tool,
        "arguments": arguments,
        "ask": ask,
        "trace": trace,
    }


def apply_turn_guards(question, history, resolved):
    """Keep plain coding and accounting off the AI search."""
    from .slots import demands_ai, office_work

    earlier = " ".join((body or "") for role, body in (history or []) if role == "user")
    blob = ((question or "") + " " + earlier).casefold()
    # A budget follow-up keeps study only when someone actually asked for AI.
    if resolved.get("use") == "study" and (office_work(question) or not demands_ai(blob)):
        resolved["use"] = ""
        if not office_work(question) and re.search(
            r"chơi game|choi game|game tốt|game tot|cấu hình mạnh", blob
        ):
            resolved["use"] = "gaming"
        priorities = list(resolved.get("priorities") or [])
        have = {item.casefold() for item in priorities}
        if re.search(r"nhẹ|nhe|gọn|gon|mang đi|mang di|mang theo", blob) and "weight" not in have:
            priorities.append("weight")
            have.add("weight")
        if re.search(r"\bpin\b|cả ngày|ca ngay|pin trâu|pin trau", blob) and "battery" not in have:
            priorities.append("battery")
        resolved["priorities"] = priorities
    if resolved.get("use") == "study":
        return resolved
    priorities = list(resolved.get("priorities") or [])
    folded = (question or "").casefold()
    have = {item.casefold() for item in priorities}
    if re.search(r"nhẹ|nhe|gọn|gon|mang đi|mang di|mang theo", folded) and "weight" not in have:
        priorities.append("weight")
        have.add("weight")
    if re.search(r"\bpin\b|cả ngày|ca ngay|pin trâu|pin trau", folded) and "battery" not in have:
        priorities.append("battery")
    resolved["priorities"] = priorities
    return resolved


_BARGAIN_RE = re.compile(r"bớt|giảm giá|giam gia|mặc cả|mac ca|hạ giá|ha gia|thương lượng|thuong luong")


def _attr(value):
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _brand_chips(result):
    """Clickable brand chips. The model writes the lead; the chips are the catalog."""
    kind = {
        "phone": "điện thoại",
        "laptop": "laptop",
        "tablet": "máy tính bảng",
        "headphones": "tai nghe",
        "smartwatch": "đồng hồ",
    }.get((result or {}).get("category") or "", "sản phẩm")
    parts = []
    for item in (result or {}).get("brands") or []:
        name = (item.get("brand") or "").strip()
        if not name:
            continue
        ask = "cho mình xem " + kind + " " + name
        parts.append(
            '<button type="button" class="brand-chip" data-q="'
            + _attr(ask) + '">' + _attr(name) + "</button>"
        )
    if not parts:
        return ""
    return '<div class="brand-chips">' + "".join(parts) + "</div>"


def _category_overview(resolved):
    """A category with no brand, model, budget, or use is a catalog listing."""
    if not (resolved or {}).get("category"):
        return False
    if any((resolved.get(key) or "") for key in ("brand", "query", "line", "variant", "chip", "family", "use", "color")):
        return False
    if resolved.get("specific") or resolved.get("cheapest") or (resolved.get("priorities") or []):
        return False
    if any(resolved.get(key) is not None for key in ("price_min", "price_max", "price_target", "ram_gb", "min_ram", "storage_gb")):
        return False
    if resolved.get("excluded_brands"):
        return False
    return True


def _brand_query_to_column(resolved):
    from .slots import _BRAND_NEEDLES

    query = (resolved.get("query") or "").strip()
    folded = query.casefold()
    if not folded:
        return
    for needle, label in _BRAND_NEEDLES:
        if folded == needle or folded == label.casefold():
            if not resolved.get("brand"):
                resolved["brand"] = label
            resolved["query"] = ""
            return


def pin_named_model(question, resolved):
    """A named model is enough to search. A missing budget must not hide that model."""
    from .slots import _iphone_line, _named_iphone, _signals

    signals = _signals(question)
    label = _named_iphone(question)
    if label:
        resolved["query"] = label
        resolved["family"] = "iPhone"
        resolved["brand"] = "Apple"
        resolved["category"] = "phone"
        suffix = _iphone_line(question).partition(" ")[2]
        resolved["variant"] = suffix if suffix in {"pro", "pro max", "plus", "air"} else ""
        return True
    concrete = bool(signals.get("query") or signals.get("line") or signals.get("variant") or signals.get("chip"))
    if not concrete:
        return False
    if signals.get("query"):
        resolved["query"] = signals["query"]
    for key in ("family", "brand", "variant", "line", "chip", "category"):
        if signals.get(key) and not resolved.get(key):
            resolved[key] = signals[key]
    query = (resolved.get("query") or "").casefold()
    if not resolved.get("category"):
        if any(word in query for word in ("galaxy", "iphone", "redmi")):
            resolved["category"] = "phone"
        elif "ipad" in query:
            resolved["category"] = "tablet"
        elif "macbook" in query or resolved.get("family") == "MacBook":
            resolved["category"] = "laptop"
    if resolved.get("family") == "iPhone" and not resolved.get("brand"):
        resolved["brand"] = "Apple"
    if resolved.get("family") == "MacBook" and not resolved.get("brand"):
        resolved["brand"] = "MacBook"
    return True


_DEICTIC_PRICE = re.compile(
    r"tầm giá này|tam gia nay|giá này|gia nay|giá đó|gia do|giá máy này|gia may nay|"
    r"tầm này|tam nay|cùng tầm|cung tam|quanh giá|cùng giá|cung gia|tầm giá đó|tam gia do|"
    r"mức giá này|muc gia nay|khoảng giá này|khoang gia nay"
)
_OTHER_MACHINES = re.compile(
    r"mấy máy|may may|máy khác|may khac|máy nào khác|may nao khac|"
    r"tần số quét|tan so quet|tần số cao|tan so cao|quét cao|quet cao"
)
_HIGHER_REFRESH = re.compile(
    r"tần số quét|tan so quet|tần số cao|tan so cao|\bhz\b|quét cao|quet cao|mượt hơn|muot hon"
)
_SHOWN_PRICE = re.compile(r"(\d{1,3}(?:\.\d{3})+)\s*₫")


def _latest_shown_prices(history):
    """Prices printed on the latest advice card. User text is not a list price."""
    for role, body in reversed(history or []):
        if role == "user":
            continue
        text = re.sub(r"<[^>]+>", " ", body or "")
        amounts = [int(match.group(1).replace(".", "")) for match in _SHOWN_PRICE.finditer(text)]
        if amounts:
            return text, amounts
    return "", []


def _first_hz(text):
    match = re.search(r"(\d+)\s*hz", text or "", re.I)
    return int(match.group(1)) if match else None


def _category_from_advice(text):
    folded = (text or "").casefold()
    if any(word in folded for word in ("iphone", "điện thoại", "dien thoai", "galaxy")):
        return "phone"
    if any(word in folded for word in ("macbook", "laptop", "máy tính", "may tinh")):
        return "laptop"
    return ""


def carry_discussed_price(question, history, resolved, named_in_sentence):
    """Bind 'this price' to the card on screen, and drop that model when another is requested."""
    from .slots import _budget_phrase, _signals

    folded = (question or "").casefold()
    own_min, own_max, own_target = _budget_phrase(folded)
    has_own_number = own_min is not None or own_max is not None or own_target is not None
    anchor_text, prices = _latest_shown_prices(history)
    if _DEICTIC_PRICE.search(folded) and not has_own_number and prices:
        resolved["price_target"] = max(prices)
        resolved["price_min"] = None
        resolved["price_max"] = None
        resolved["price_max_exclusive"] = False
        if not resolved.get("category"):
            resolved["category"] = _category_from_advice(anchor_text)
    if _OTHER_MACHINES.search(folded) and not named_in_sentence:
        signals = _signals(question)
        if not signals.get("query") and not signals.get("variant") and not signals.get("chip") and not signals.get("line"):
            resolved["query"] = ""
            resolved["family"] = ""
            resolved["variant"] = ""
            resolved["line"] = ""
            resolved["chip"] = ""
            resolved["specific"] = False
            resolved["ram_gb"] = None
            resolved["min_ram"] = None
            resolved["storage_gb"] = None
            resolved["screen"] = None
            if not signals.get("brand"):
                resolved["brand"] = ""
    if _HIGHER_REFRESH.search(folded):
        priorities = list(resolved.get("priorities") or [])
        if "refresh" not in {item.casefold() for item in priorities}:
            priorities.append("refresh")
        resolved["priorities"] = priorities
        discussed = _first_hz(anchor_text)
        if discussed:
            resolved["min_refresh"] = discussed
        if resolved.get("use") == "gaming":
            resolved["use"] = ""


_THESE_CARDS = re.compile(
    r"mấy máy này|may may nay|mấy cái này|may cai nay|"
    r"máy vừa xem|may vua xem|vừa gợi ý|vua goi y|trước đó|truoc do|"
    r"cậu bảo|cau bao|vừa bảo|vua bao|chỗ nào|cho nao|khác đơn vị|khac don vi"
)
_EARLIER_CARDS = re.compile(r"trước đó|truoc do|gợi ý trước|goi y truoc")


def shown_card_ids(history, skip_latest=False):
    """Product ids printed on advice cards, newest group first."""
    groups = []
    for role, body in reversed(history or []):
        if role == "user":
            continue
        found = re.findall(r'name="product_id" value="(\d+)"', body or "")
        if not found:
            continue
        groups.append([int(value) for value in dict.fromkeys(found)])
        if len(groups) >= (2 if skip_latest else 1):
            break
    if not groups:
        return []
    if skip_latest and len(groups) > 1:
        return groups[1]
    return groups[0]


def stick_to_shown_cards(question, history, resolved):
    """A follow-up about these phones stays on the cards just shown."""
    folded = (question or "").casefold()
    if not _THESE_CARDS.search(folded):
        return False
    ids = shown_card_ids(history, skip_latest=_EARLIER_CARDS.search(folded) is not None)
    if not ids:
        return False
    resolved["shown_ids"] = ids[:4]
    resolved["query"] = ""
    resolved["family"] = ""
    resolved["variant"] = ""
    resolved["line"] = ""
    resolved["chip"] = ""
    resolved["brand"] = ""
    resolved["specific"] = False
    if not resolved.get("category"):
        resolved["category"] = "phone"
    if re.search(r"\bpin\b|trâu|trau", folded):
        priorities = list(resolved.get("priorities") or [])
        if "battery" not in {item.casefold() for item in priorities}:
            priorities.append("battery")
        resolved["priorities"] = priorities
    return True


def _shown_result(conn, resolved, question):
    """Load the cards the shopper is pointing at, plus a model named in this sentence."""
    from .retrieve import search_products
    from .slots import _iphone_line, _named_iphone
    from .tools import get_product

    products = []
    for ident in resolved.get("shown_ids") or []:
        item = (get_product(conn, ident) or {}).get("product")
        if item and all(item["product_id"] != have["product_id"] for have in products):
            products.append(item)
    label = _named_iphone(question)
    if label:
        wanted = _iphone_line(label)
        if not any(_iphone_line(item.get("name") or "") == wanted for item in products):
            extra = search_products(
                conn, category="phone", query=label, brand="Apple", family="iPhone", limit=4,
            )
            for item in extra.get("products") or []:
                if _iphone_line(item.get("name") or "") == wanted:
                    products.append(item)
                    break
    note = (
        "Đây là các máy vừa đưa và máy khách vừa nhắc. "
        "Chỉ nêu đúng số pin trong catalog. Số mAh và số giờ là hai cách ghi khác nhau, "
        "không kết luận máy nào dùng lâu hơn."
    )
    return {"products": products[:4], "note": note}


def _bargain_product(question, history):
    from .slots import _named_iphone
    named = _named_iphone(question)
    if named:
        return named
    for role, body in reversed(history or []):
        if role == "user":
            named = _named_iphone(body)
            if named:
                return named
    for role, body in reversed(history or []):
        if role != "user":
            named = _named_iphone(re.sub(r"<[^>]+>", " ", body or ""))
            if named:
                return named
    return ""


def _bargain_context(question, history):
    if _BARGAIN_RE.search((question or "").casefold()):
        return True
    for role, body in history or []:
        if _BARGAIN_RE.search((body or "").casefold()):
            return True
    return False


def _offer_amount(question):
    from .slots import _budget_phrase

    price_min, price_max, price_target = _budget_phrase((question or "").casefold())
    return price_target or price_max or price_min


def _listed_iphone(conn, label):
    from .retrieve import search_products
    from .slots import _iphone_line

    found = search_products(
        conn, category="phone", query=label, brand="Apple", family="iPhone", limit=4,
    )
    wanted = _iphone_line(label)
    return [
        item for item in (found.get("products") or [])
        if _iphone_line(item.get("name") or "") == wanted
    ]


def bargain_turn(question, history, resolved, conn=None):
    """A price after a discount talk is an offer on that phone, not a new search."""
    if not _bargain_context(question, history):
        return None
    from .slots import _brand_phrase

    if _brand_phrase((question or "").casefold()) not in ("", "Apple"):
        return None
    if re.search(r"laptop|máy tính|may tinh|máy nào|may nao|cho xem|gợi ý|goi y|\btìm\b|\btim\b", (question or "").casefold()):
        return None
    label = _bargain_product(question, history)
    if not label:
        return None
    offer = _offer_amount(question)
    if not offer:
        ask = "Bạn muốn lấy " + label + " khoảng bao nhiêu?"
        if conn is not None:
            listed = _listed_iphone(conn, label)
            if listed:
                price = min(item.get("price") or 0 for item in listed)
                ask = label + " đang để giá " + _vnd_phrase(price) + ". Bạn muốn lấy khoảng bao nhiêu?"
        return {"mode": "ask", "ask": ask}
    resolved["query"] = label
    resolved["category"] = "phone"
    resolved["brand"] = "Apple"
    resolved["family"] = "iPhone"
    resolved["variant"] = ""
    resolved["line"] = ""
    resolved["chip"] = ""
    resolved["screen"] = None
    resolved["ram_gb"] = None
    resolved["storage_gb"] = None
    resolved["specific"] = False
    resolved["use"] = ""
    resolved["cheapest"] = False
    resolved["price_min"] = None
    resolved["price_max"] = None
    resolved["price_target"] = None
    resolved["price_max_exclusive"] = False
    resolved["bargain_offer"] = offer
    return {"mode": "quote", "ask": ""}


def _bargain_note(products, resolved):
    label = resolved.get("query") or "Máy này"
    offer = int(resolved.get("bargain_offer") or 0)
    if not products:
        return "Mình không thấy " + label + " còn hàng để mặc cả."
    price = min(item.get("price") or 0 for item in products)
    listed = _vnd_phrase(price)
    if offer and offer < price:
        return (
            label + " đang bán " + listed + ". " + _vnd_phrase(offer)
            + " thấp hơn giá niêm yết, bên mình không bớt xuống mức đó."
        )
    if offer and offer == price:
        return "Đúng giá " + label + " đang bán, " + listed + "."
    if offer and offer > price:
        return label + " đang bán " + listed + ", không cần trả cao hơn giá niêm yết."
    return label + " đang bán " + listed + "."


def _after_intent(state):
    tool = state.get("tool") or "none"
    if tool in ("none", "refuse", "ask", ""):
        return "explain"
    return "tool"


def tool_node(state):
    import agent.model as model

    name = state.get("tool") or ""
    arguments = state.get("arguments") or {}
    resolved = state.get("resolved") or {}
    user = state.get("user") or {}
    t0 = _stamp(state)
    if name == "search_products" and resolved.get("shown_ids"):
        result = _shown_result(_CONN.get(), resolved, state.get("question") or "")
        found = result.get("products") or []
        ready = None
        ran = {"shown_ids": list(resolved.get("shown_ids") or [])}
    else:
        ran = model._executed_arguments(name, arguments, resolved)
        result, found, ready = model._run_tool(_CONN.get(), user, name, arguments, resolved)
    t1 = _stamp(state)
    advice = state.get("advice_lead") or ""
    if result.get("near_miss"):
        advice = result.get("lead") or result.get("note") or advice
    products = list(state.get("products") or [])
    orders = state.get("orders")
    checkout = state.get("checkout")
    if name == "list_orders":
        orders = result.get("orders") or []
        products = []
    elif name in ("search_products", "get_product", "compare_products", "check_inventory"):
        products = found
    if name == "search_products" and resolved.get("bargain_offer"):
        from .slots import _iphone_line
        wanted = _iphone_line(resolved.get("query") or "")
        products = [item for item in products if _iphone_line(item.get("name") or "") == wanted]
        result = dict(result)
        result["products"] = products
        result["bargain"] = True
        result["note"] = _bargain_note(products, resolved)
        result["lead"] = result["note"]
    debug("FINAL_PRODUCT_IDS_TO_EXPLAIN", ids=[item.get("product_id") for item in products])
    if ready:
        checkout = ready
    note = ""
    if name == "search_products" and resolved.get("cheapest"):
        note = "Câu này hỏi mẫu rẻ nhất. Python không giữ price_max hay price_target của câu trước."
    trace = list(state.get("trace") or [])
    trace.append({
        "kind": "tool",
        "type": "TOOL",
        "name": name,
        "sent": model._trace_value(arguments),
        "ran": model._trace_value(ran),
        "note": note,
        "result": model._trace_result(result),
        "t0": t0,
        "t1": t1,
    })
    return {
        "result": result,
        "products": products,
        "orders": orders,
        "checkout": checkout,
        "advice_lead": advice,
        "trace": trace,
    }


def _history_messages(history):
    import agent.model as model

    messages = []
    for role, body in (history or [])[-8:]:
        if role == "user":
            messages.append({"role": "user", "content": (body or "")[:500]})
            continue
        text = model._history_text(body)
        if text:
            messages.append({"role": "assistant", "content": text})
    return messages


def _finish(state, text, text_from, step, product_reasons=None):
    trace = list(state.get("trace") or [])
    trace.append(step)
    answer = {"text": text, "text_from": text_from, "trace": trace}
    if product_reasons is not None:
        answer["product_reasons"] = product_reasons
    return answer


def _catalog_reason(product, resolved):
    """Use only catalog facts if a provider omits a required card explanation."""
    existing = (product.get("reason") or "").strip()
    if existing:
        return existing
    specs = {item.get("name"): item.get("value") for item in product.get("specs") or []}
    if "refresh" in {item.casefold() for item in (resolved.get("priorities") or [])}:
        match = re.search(r"(\d+)\s*hz", specs.get("Màn hình") or "", re.I)
        if match:
            return "Màn hình của máy này quét " + match.group(1) + " Hz."
    if "camera" in (resolved.get("priorities") or []):
        facts = [specs.get("Camera sau"), specs.get("Camera trước")]
        label = "nhu cầu chụp ảnh"
    elif resolved.get("use") == "gaming":
        facts = [specs.get("Chip"), specs.get("RAM"), specs.get("Màn hình")]
        label = "nhu cầu chơi game"
    else:
        facts = [specs.get("Chip"), specs.get("RAM"), specs.get("Pin")]
        label = "nhu cầu bạn nêu"
    details = [str(value).strip() for value in facts if value]
    if details:
        return "Mẫu này đáp ứng bộ lọc cho " + label + "; thông số đáng cân nhắc là " + ", ".join(details[:2]) + "."
    return "Mẫu này đúng nhóm sản phẩm và giới hạn giá bạn đã chọn; catalog chưa đủ thông số để nhận xét sâu hơn."


_OVERCLAIM = re.compile(
    r"cả ngày|pin tốt|dùng lâu|sử dụng lâu|làm việc lâu|thời gian dài|thời gian sử dụng|"
    r"không cần sạc|sạc thường xuyên|gọn nhẹ|máy nhẹ|nhẹ nhàng|trọng lượng|tính di động|độ gọn|"
    r"trong suốt|lâu hơn|lâu dài|trâu hơn|trau hon|\bnhẹ\b|\bgọn\b",
    re.I,
)


def _vnd_phrase(amount):
    amount = int(amount or 0)
    if amount and amount % 1_000_000 == 0:
        return str(amount // 1_000_000) + " triệu"
    return f"{amount:,}".replace(",", ".") + "₫"


def _budget_clause(resolved, question):
    resolved = resolved or {}
    amount = resolved.get("price_target") or resolved.get("price_max")
    if not amount:
        return ""
    phrase = _vnd_phrase(amount)
    folded = (question or "").casefold()
    if re.search(r"tầm|khoảng|khoang|\btam\b", folded):
        return " Trong tầm " + phrase + "."
    if resolved.get("price_target"):
        return " Các máy không vượt " + phrase + "."
    if resolved.get("price_max_exclusive"):
        return " Mức giá là dưới " + phrase + "."
    return " Mức giá là tối đa " + phrase + "."


def _ground_intro(intro, products, resolved, question=""):
    """Replace a lead that invents weight or battery hours with the catalog limit."""
    if not intro or not _OVERCLAIM.search(intro):
        return intro
    from .retrieve import _screen_inches

    folded = (question or "").casefold()
    about_size = re.search(r"nhẹ|nhe|gọn|gon|mang đi|mang di|trọng lượng|trong luong", folded) is not None
    screens = [_screen_inches(item) for item in products or []]
    compact = [size for size in screens if size < 15]
    if about_size and compact and len(compact) == len(screens):
        text = "Các máy dưới đây có màn hình dưới 15 inch, nhỏ hơn các mẫu 15.6 inch cùng tầm giá. Mình chưa có cân nặng và chưa có số giờ pin, chỉ có số Wh."
    elif about_size and compact:
        text = "Mình xếp màn hình nhỏ hơn lên trước. Chưa có cân nặng và chưa có số giờ pin, chỉ có số Wh."
    elif about_size:
        text = "Mình chỉ nêu đúng thông số trong catalog. Chưa có số giờ pin và chưa có cân nặng."
    else:
        text = "Mình chỉ nêu đúng pin ghi trong catalog. Số mAh và số giờ không đổi được cho nhau, nên không kết luận máy nào dùng lâu hơn."
    return text + _budget_clause(resolved, question)


def _measured(product):
    specs = {item.get("name"): (item.get("value") or "").strip() for item in product.get("specs") or []}
    screen = ""
    match = re.search(r"(\d+(?:[.,]\d+)?)", specs.get("Màn hình") or "")
    if match:
        screen = match.group(1).replace(",", ".") + " inch"
    raw_pin = specs.get("Pin") or ""
    pin = ""
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*wh", raw_pin, re.I)
    if match:
        pin = match.group(1).replace(",", ".") + " Wh"
    else:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*mah", raw_pin, re.I)
        if match:
            pin = match.group(1).replace(",", ".") + " mAh"
    return specs.get("Chip") or "", specs.get("RAM") or "", screen, pin


def _bad_sentence(sentence):
    if re.search(
        r"không (?:kết luận|so được|đổi được|đoán|thấp hơn|cao hơn)|khác đơn vị|hai đơn vị|không cùng",
        sentence or "",
        re.I,
    ):
        return False
    if _OVERCLAIM.search(sentence):
        return True
    # mAh and Wh are capacities. A higher number is not a longer day, and it
    # cannot be ranked against a spec that is already written in hours.
    has_capacity = re.search(r"\d+(?:[.,]\d+)?\s*(?:wh|mah)", sentence or "", re.I)
    claims_duration = re.search(
        r"đáp ứng|đủ dùng|thoải mái|suốt|lâu|cả ngày|hàng ngày|thấp hơn|cao hơn|trâu",
        sentence or "",
        re.I,
    )
    return bool(has_capacity and claims_duration)


def _fact_sentence(product):
    chip, ram, screen, pin = _measured(product)
    bits = []
    if chip:
        bits.append("chip " + chip)
    if ram:
        bits.append("RAM " + ram)
    if screen:
        bits.append("màn hình " + screen)
    text = ("Máy này có " + ", ".join(bits) + ".") if bits else ""
    if pin:
        text += " Pin trong catalog là " + pin + ". Shop chưa ghi số giờ, nên mình không đoán dùng được bao lâu."
    return text.strip()


def _ground_reason(reason, product):
    """Drop only the sentence that invents hours or weight. Keep the rest."""
    if not reason:
        return reason
    sentences = [part for part in re.split(r"(?<=[\.\!\?])\s+", reason.strip()) if part]
    if not any(_bad_sentence(part) for part in sentences):
        return reason
    kept = [part for part in sentences if not _bad_sentence(part)]
    chip, ram, screen, pin = _measured(product)
    if not kept:
        return _fact_sentence(product) or reason
    extra = []
    if screen and not any(screen.split()[0] in part for part in kept):
        extra.append("Màn hình " + screen + ".")
    if pin and not any(re.search(r"wh|số giờ", part, re.I) for part in kept):
        extra.append("Pin trong catalog là " + pin + ". Shop chưa ghi số giờ, nên mình không đoán dùng được bao lâu.")
    return " ".join(kept + extra).strip()


def _recommendation_reply(content, products, resolved, note, question=""):
    """Match provider explanations to the exact returned product IDs."""
    import agent.model as model

    parsed = None
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        pass
    if isinstance(parsed, dict):
        intro = str(parsed.get("intro") or "").strip()
        supplied = parsed.get("reasons") if isinstance(parsed.get("reasons"), dict) else {}
    else:
        intro, supplied = model.split_advice(content, products)
    reasons = {}
    fallback_ids = []
    for product in products:
        product_id = product.get("product_id")
        reason = supplied.get(str(product_id)) or supplied.get(product_id)
        if isinstance(reason, str) and reason.strip():
            reasons[product_id] = _ground_reason(reason.strip(), product)
        else:
            reasons[product_id] = _catalog_reason(product, resolved)
            fallback_ids.append(product_id)
    debug("PRODUCT_EXPLANATIONS", product_ids=list(reasons), fallback_ids=fallback_ids)
    intro = _ground_intro(intro, products, resolved, question)
    return intro or note or "Mình đã tìm được các mẫu phù hợp với yêu cầu của bạn.", reasons


def explain_node(state):
    import agent.model as model

    tool = state.get("tool") or "none"
    intent = state.get("intent") or ""
    result = state.get("result") or {}
    question = state.get("question") or ""
    advice = state.get("advice_lead") or ""
    t0 = _stamp(state)
    if tool == "search_documents" or intent == "warranty":
        text = _warranty_text(result)
        t1 = _stamp(state)
        return _finish(state, text, "tool_note", {
            "kind": "explain",
            "type": "SPAN",
            "name": "Trích điều khoản",
            "text": text[:300],
            "tool": "search_documents",
            "input": {"tool": "search_documents"},
            "calls": [],
            "t0": t0,
            "t1": t1,
        })
    if tool == "refuse" or intent == "safety":
        text = "Mình không làm việc đó."
        t1 = _stamp(state)
        return _finish(state, text, "tool_note", {
            "kind": "explain",
            "type": "SPAN",
            "name": "Từ chối",
            "text": text,
            "tool": "refuse",
            "input": {"question": question[:240]},
            "calls": [],
            "t0": t0,
            "t1": t1,
        })
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    note = (result.get("note") or result.get("lead") or advice or "").strip()
    if result.get("bargain"):
        reasons = {
            product["product_id"]: "Giá niêm yết của máy này là " + _vnd_phrase(product.get("price")) + "."
            for product in (state.get("products") or [])
        }
        t1 = _stamp(state)
        return _finish(state, note or "Giá niêm yết là giá bán.", "tool_note", {
            "kind": "explain",
            "type": "SPAN",
            "name": "Giá niêm yết",
            "text": (note or "")[:300],
            "tool": tool,
            "input": {"tool": tool},
            "calls": [],
            "t0": t0,
            "t1": t1,
        }, product_reasons=reasons or None)
    if not key:
        if tool == "list_category":
            text = _brand_chips(result)
        elif tool == "ask" or intent == "advise":
            text = (state.get("ask") or "").strip()
        else:
            text = ""
        text = text or note or "Mình chưa gọi được model. Bạn nói rõ máy hoặc hãng mình cần tìm giúp."
        reasons = None
        if tool == "search_products" and state.get("products"):
            reasons = {product["product_id"]: _catalog_reason(product, state.get("resolved") or {})
                       for product in state["products"]}
        t1 = _stamp(state)
        return _finish(state, text, "tool_note", {
            "kind": "explain",
            "type": "SPAN",
            "name": "Ghi chú tool",
            "text": text[:300],
            "tool": tool,
            "input": {"tool": tool} if tool not in ("none", "") else {"question": question[:240]},
            "calls": [],
            "t0": t0,
            "t1": t1,
        }, product_reasons=reasons)
    base = os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    system = _EXPLAIN_SYSTEM if tool not in ("none", "") else _CHAT_SYSTEM
    messages = [{"role": "system", "content": system}]
    messages.extend(_history_messages(state.get("history")))
    if tool in ("none", ""):
        user_text = question
    else:
        payload = model._public_payload(result or {"note": note})
        if tool == "ask":
            payload = {
                "need": "một câu hỏi tự nhiên trước khi chọn máy",
                "criteria": state.get("resolved") or {},
            }
        if tool == "search_products":
            resolved = state.get("resolved") or {}
            criteria = {
                key: resolved.get(key) for key in (
                    "category", "brand", "query", "use", "priorities", "price_target",
                    "price_max", "price_max_exclusive", "excluded_brands",
                )
            }
            payload = {"criteria": criteria, "tool_result": payload}
        user_text = question + "\n" + json.dumps(payload, ensure_ascii=False)
    messages.append({"role": "user", "content": user_text})
    products = state.get("products") or []
    if tool == "ask":
        messages.insert(1, {"role": "system", "content": (
            "Chưa đủ thông tin để chọn máy. Hỏi đúng một câu bằng lời của bạn. "
            "Nếu thiếu ngân sách, hỏi ngân sách. Không dùng câu mẫu cố định và không liệt kê sản phẩm."
        )})
    elif tool == "list_category":
        messages.insert(1, {"role": "system", "content": (
            "Giao diện đã hiện chip các hãng còn hàng. Viết một hoặc hai câu dẫn ngắn. "
            "Không liệt kê lại tên hãng, không bịa hãng, không kể từng máy, không hỏi thêm."
        )})
    elif tool == "compare_products" and products:
        messages.insert(1, {"role": "system", "content": (
            "Giao diện đã hiện bảng so sánh các máy trong tool, gồm giá, tồn và thông số. "
            "Viết một hoặc hai câu về khác biệt đáng kể. Không chép lại từng dòng của bảng. "
            "Không bịa thông số, giá hay số lượng ngoài tool."
        )})
    if tool == "search_products" and products:
        messages.insert(1, {"role": "system", "content": (
            "Trả JSON theo schema: intro là một câu dẫn ngắn; reasons có đúng một lời giải thích "
            "cho MỖI product_id trong tool_result.products. Mỗi lời gồm một hoặc hai câu, "
            "nêu thông số của chính máy đó và vì sao liên quan đến nhu cầu hiện tại. "
            "Không lặp cùng một nhận xét cho các máy, không bịa tính năng, không đưa máy khác vào. "
            "Khi tool chỉ có số Wh: nêu đúng số đó và nói chưa có số giờ. "
            "Khi criteria có refresh: chỉ nêu số Hz ghi trong thông số màn hình của chính máy đó. "
            "Số mAh và số giờ là hai cách ghi khác nhau, không kết luận máy nào dùng lâu hơn. "
            "Cấm các ý pin tốt, dùng lâu, lâu hơn, thời gian dài, không cần sạc, dùng cả ngày, máy nhẹ, gọn nhẹ, trọng lượng. "
            "Nói về độ gọn thì chỉ so sánh số inch của màn hình, ví dụ 14 inch nhỏ hơn 15.6 inch."
        )})
        try:
            try:
                message = model._complete(
                    base, key, model_name, messages, tools=None, temperature=0.2,
                    response_format=recommendation_format([product["product_id"] for product in products]),
                )
            except urllib.error.HTTPError as exc:
                if exc.code not in (400, 422):
                    raise
                message = model._complete(base, key, model_name, messages, tools=None, temperature=0.2)
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            debug("PRODUCT_EXPLANATION_PROVIDER_UNAVAILABLE", error=f"HTTP {exc.code}")
            message = {"content": ""}
        except (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError,
                BrokenPipeError, TimeoutError, socket.timeout) as exc:
            debug("PRODUCT_EXPLANATION_PROVIDER_UNAVAILABLE", error=type(exc).__name__)
            message = {"content": ""}
    elif tool == "search_products":
        messages.insert(1, {"role": "system", "content": (
            "Tool đã lọc category và brand trong catalog và không trả về sản phẩm. "
            "Viết câu trả lời tự nhiên: cửa hàng chưa có đúng loại hàng đó. "
            "Không nói đây là lượt kiểm tra tồn kho, không chép nguyên văn note, "
            "không hỏi một câu hỏi soạn sẵn. Không bịa tên máy, giá, số lượng. "
            "Nếu note nêu dòng còn hàng, chỉ nhắc trong câu nói."
        )})
        try:
            message = model._complete(base, key, model_name, messages, tools=None, temperature=0.2)
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            debug("PRODUCT_EXPLANATION_PROVIDER_UNAVAILABLE", error=f"HTTP {exc.code}")
            message = {"content": ""}
        except (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError,
                BrokenPipeError, TimeoutError, socket.timeout) as exc:
            debug("PRODUCT_EXPLANATION_PROVIDER_UNAVAILABLE", error=type(exc).__name__)
            message = {"content": ""}
    else:
        message = model._complete(base, key, model_name, messages, tools=None, temperature=0.2)
    content = (message.get("content") or "").strip()
    generated = bool(content)
    reasons = None
    if tool == "search_products" and products:
        content, reasons = _recommendation_reply(
            content, products, state.get("resolved") or {}, note, question,
        )
        if result.get("near_miss") and note:
            # Catalog assessment is authoritative when every in-budget option
            # has a capability tradeoff. Keep the model's per-product reasons.
            content = note
    text = content or note
    if tool == "list_category":
        chips = _brand_chips(result)
        if chips and "brand-chips" not in text:
            text = (text + chips).strip() if text else chips
    t1 = _stamp(state)
    model_input = {"tool": tool} if tool not in ("none", "") else {"question": question[:240]}
    return _finish(state, text, "model" if generated else "tool_note", {
        "kind": "model",
        "type": "GENERATION",
        "name": model_name,
        "text": text,
        "calls": [],
        "input": model_input,
        "t0": t0,
        "t1": t1,
    }, product_reasons=reasons)


def _build():
    graph = StateGraph(ShopState)
    graph.add_node("intent", intent_node)
    graph.add_node("tool", tool_node)
    graph.add_node("explain", explain_node)
    graph.set_entry_point("intent")
    graph.add_conditional_edges("intent", _after_intent, {"tool": "tool", "explain": "explain"})
    graph.add_edge("tool", "explain")
    graph.add_edge("explain", END)
    return graph.compile()


SHOP_GRAPH = _build()


def _shown_passages(final):
    """Citations for the shopper. The trace keeps its own shortened copy."""
    if (final.get("tool") or "") != "search_documents":
        return []
    shown = []
    for item in ((final.get("result") or {}).get("passages") or [])[:3]:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        shown.append({
            "title": item.get("title") or "",
            "brand": item.get("brand") or "",
            "source_url": item.get("source_url") or "",
            "text": text,
        })
    return shown


def run_shop_graph(conn, user, question, history=None):
    """Run the compiled graph once. Products stay in the tool's order."""
    token = _CONN.set(conn)
    try:
        final = SHOP_GRAPH.invoke(
            {
                "question": question or "",
                "history": list(history or []),
                "user": user or {},
                "started": time.perf_counter(),
                "trace": [],
                "products": [],
                "product_reasons": {},
                "checkout": None,
                "orders": None,
                "result": {},
                "advice_lead": "",
                "text": "",
                "text_from": "",
                "resolved": {},
                "intent": "",
                "tool": "none",
                "arguments": {},
                "ask": "",
            },
            config={"callbacks": []},
        )
    finally:
        _CONN.reset(token)
    spoken = {
        "text": final.get("text") or "",
        "text_from": final.get("text_from") or "tool_note",
        "tool": final.get("tool") or "",
        "products": final.get("products") or [],
        "product_reasons": final.get("product_reasons") or {},
        "checkout": final.get("checkout"),
        "orders": final.get("orders"),
        "passages": _shown_passages(final),
        "trace": final.get("trace") or [],
    }
    try:
        from .langfuse_log import publish_turn
        publish_turn(question, spoken, user)
    except Exception:
        pass
    return spoken
