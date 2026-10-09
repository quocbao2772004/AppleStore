"""One provider call interprets the customer's intent and complete requirements."""
import json
import os
import urllib.error

from .constants import CATEGORIES
from .debug import debug
from .prompts.understand import PROMPT


def _nullable(kind):
    return {"type": [kind, "null"]}


_FIELDS = {
    "category": {"type": "string", "enum": ["", *sorted(CATEGORIES)]},
    "query": {"type": "string"},
    "color": {"type": "string"},
    "price_min": _nullable("integer"),
    "price_max": _nullable("integer"),
    "price_max_exclusive": {"type": "boolean"},
    "price_target": _nullable("integer"),
    "budget_mode": {"type": "string", "enum": ["none", "target", "max_exclusive", "max_inclusive", "min", "range"]},
    "brand": {"type": "string"},
    "excluded_brands": {"type": "array", "items": {"type": "string"}},
    "use": {"type": "string", "enum": ["", "gaming", "study"]},
    "priorities": {"type": "array", "items": {"type": "string"}},
    "ram_gb": _nullable("integer"),
    "min_ram": _nullable("integer"),
    "storage_gb": _nullable("integer"),
    "screen": _nullable("integer"),
    "line": {"type": "string"},
    "variant": {"type": "string"},
    "chip": {"type": "string"},
    "family": {"type": "string"},
    "cheapest": {"type": "boolean"},
}

_ACTIONS = (
    "ask", "search_products", "list_category", "get_product", "compare_products", "check_inventory",
    "prepare_checkout", "list_orders", "search_documents", "none", "refuse",
)

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "shop_turn",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": list(_ACTIONS)},
                "question_to_ask": {"type": "string"},
                "compare_left": {"type": "string"},
                "compare_right": {"type": "string"},
                "qty": _nullable("integer"),
                "doc_type": {"type": "string", "enum": ["warranty", "store_policy", "return", "privacy", "eula", "other"]},
                "latest_excluded_brands": {"type": "array", "items": {"type": "string"}},
                "latest_budget": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": ["unchanged", "none", "target", "max_exclusive", "max_inclusive", "min", "range"]},
                        "price_min": _nullable("integer"),
                        "price_max": _nullable("integer"),
                        "price_target": _nullable("integer"),
                    },
                    "required": ["mode", "price_min", "price_max", "price_target"],
                    "additionalProperties": False,
                },
                "latest_use": {"type": "string", "enum": ["unchanged", "gaming", "study", "other"]},
                "latest_priorities": {"type": "array", "items": {"type": "string"}},
                "requirements": {
                    "type": "object", "properties": _FIELDS,
                    "required": list(_FIELDS), "additionalProperties": False,
                },
            },
            "required": ["action", "question_to_ask", "compare_left", "compare_right", "qty", "doc_type", "latest_excluded_brands", "latest_budget", "latest_use", "latest_priorities", "requirements"],
            "additionalProperties": False,
        },
    },
}


def _turns(history):
    from .model import _history_text

    turns = []
    for role, body in (history or [])[-40:]:
        if role == "user":
            turns.append({"role": "user", "content": (body or "")[:1000]})
        elif role in ("bot", "assistant"):
            content = _history_text(body)
            if content:
                turns.append({"role": "assistant", "content": content})
    return turns


def _positive_int(value):
    return value if type(value) is int and value > 0 else None


def _clean_requirements(raw):
    if not isinstance(raw, dict):
        raise ValueError("Provider returned no requirements")
    resolved = {}
    for key in ("price_min", "price_max", "price_target", "ram_gb", "min_ram", "storage_gb", "screen"):
        resolved[key] = _positive_int(raw.get(key))
    for key in ("query", "color", "brand", "line", "variant", "chip", "family"):
        resolved[key] = str(raw.get(key) or "").strip()[:120]
    resolved["category"] = raw.get("category") if raw.get("category") in CATEGORIES else ""
    resolved["use"] = raw.get("use") if raw.get("use") in ("gaming", "study") else ""
    resolved["price_max_exclusive"] = bool(raw.get("price_max_exclusive") and resolved["price_max"] is not None)
    budget_mode = raw.get("budget_mode")
    if budget_mode == "target":
        resolved["price_target"] = resolved["price_target"] or resolved["price_max"] or resolved["price_min"]
        resolved["price_min"] = resolved["price_max"] = None
        resolved["price_max_exclusive"] = False
    elif budget_mode in ("max_exclusive", "max_inclusive"):
        resolved["price_max"] = resolved["price_max"] or resolved["price_target"]
        resolved["price_min"] = resolved["price_target"] = None
        resolved["price_max_exclusive"] = budget_mode == "max_exclusive"
    elif budget_mode == "min":
        resolved["price_min"] = resolved["price_min"] or resolved["price_target"]
        resolved["price_max"] = resolved["price_target"] = None
        resolved["price_max_exclusive"] = False
    elif budget_mode == "range":
        resolved["price_target"] = None
        resolved["price_max_exclusive"] = False
    elif budget_mode == "none":
        resolved["price_min"] = resolved["price_max"] = resolved["price_target"] = None
        resolved["price_max_exclusive"] = False
    if resolved["price_target"] is not None and resolved["price_target"] == resolved["price_max"] and not resolved["price_max_exclusive"]:
        resolved["price_max"] = None
    if resolved["price_target"] is not None and resolved["price_target"] == resolved["price_min"]:
        resolved["price_min"] = None
    resolved["cheapest"] = bool(raw.get("cheapest"))
    resolved["excluded_brands"] = list(dict.fromkeys(
        str(name).strip()[:80] for name in (raw.get("excluded_brands") or [])
        if isinstance(name, str) and name.strip()
    ))
    resolved["priorities"] = list(dict.fromkeys(
        str(name).strip()[:40] for name in (raw.get("priorities") or [])
        if isinstance(name, str) and name.strip()
    ))
    if resolved["brand"].casefold() in {name.casefold() for name in resolved["excluded_brands"]}:
        resolved["brand"] = ""
    resolved["specific"] = bool(resolved["ram_gb"] or resolved["screen"] or resolved["chip"])
    return resolved


def understand_turn(question, history=None):
    """Use the configured provider to infer semantics; never fall back to regex parsing."""
    from .model import _complete

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for customer chat")
    base = os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps({
            "history": _turns(history), "current_user_message": question,
        }, ensure_ascii=False)},
    ]
    try:
        message = _complete(base, key, model_name, messages, temperature=0, response_format=RESPONSE_FORMAT)
    except urllib.error.HTTPError as exc:
        if exc.code not in (400, 422):
            raise
        # Some OpenAI-compatible providers implement JSON mode but not strict schemas.
        message = _complete(base, key, model_name, messages, temperature=0, response_format={"type": "json_object"})
    if message.get("refusal"):
        raise ValueError("Provider refused requirements extraction")
    raw = json.loads(message.get("content") or "")
    if not isinstance(raw, dict) or raw.get("action") not in _ACTIONS:
        raise ValueError("Provider returned an invalid shop action")
    resolved = _clean_requirements(raw.get("requirements"))
    # The full conversation summary can accidentally lose a budget when the
    # shopper changes category. A separately interpreted current-turn budget
    # always takes precedence over that summary; no price text is parsed here.
    latest_budget = raw.get("latest_budget") or {}
    if latest_budget.get("mode") in ("none", "target", "max_exclusive", "max_inclusive", "min", "range"):
        current = _clean_requirements({
            "budget_mode": latest_budget["mode"],
            "price_min": latest_budget.get("price_min"),
            "price_max": latest_budget.get("price_max"),
            "price_target": latest_budget.get("price_target"),
        })
        for key in ("price_min", "price_max", "price_target", "price_max_exclusive"):
            resolved[key] = current[key]
    # Keep an explicit rejection from the newest message even if the model's
    # full-state summary accidentally drops it while merging old preferences.
    latest_excluded = raw.get("latest_excluded_brands") or []
    for name in latest_excluded:
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()[:80]
        if name.casefold() not in {item.casefold() for item in resolved["excluded_brands"]}:
            resolved["excluded_brands"].append(name)
    if resolved["brand"].casefold() in {item.casefold() for item in resolved["excluded_brands"]}:
        resolved["brand"] = ""
    latest_use = raw.get("latest_use")
    if latest_use in ("gaming", "study", "other"):
        resolved["use"] = "" if latest_use == "other" else latest_use
    for name in raw.get("latest_priorities") or []:
        if isinstance(name, str) and name.strip() and name.casefold() not in {item.casefold() for item in resolved["priorities"]}:
            resolved["priorities"].append(name.strip()[:40])
    action = raw["action"]
    ask = str(raw.get("question_to_ask") or "").strip()[:500]
    if action == "ask" and not ask:
        raise ValueError("Provider requested clarification without a question")
    if action == "search_products" and not resolved["category"]:
        raise ValueError("Provider requested product search without a category")
    if action == "list_category" and not resolved["category"]:
        raise ValueError("Provider requested a category list without a category")
    result = {
        "action": action,
        "ask": ask,
        "resolved": resolved,
        "compare_left": str(raw.get("compare_left") or "").strip()[:120],
        "compare_right": str(raw.get("compare_right") or "").strip()[:120],
        "qty": _positive_int(raw.get("qty")) or 1,
        "doc_type": raw.get("doc_type") or "warranty",
    }
    debug("PROVIDER_REQUIREMENTS", user=question, result=result)
    return result
