"""Requirement state and the follow-up policy for the live shop graph.

The prompt in prompts/requirements.py is the extraction contract. This module
fills the state from the sentence. It does not call the model. The next
question is chosen here, not inside a system prompt. route() is untouched.
"""
import re

from .constants import HEADPHONE_BRANDS, LAPTOP_BRANDS
from .debug import debug
from .prompts.requirements import PROMPT
from .slots import _category_phrase, resolve_request

# Assumed once the use is known. These are not questions for the shopper.
DEFAULT_RULES = {
    "ai": {"ram_min": 16, "storage_gb": 512, "gpu": "nvidia"},
    "gaming_laptop": {"gpu": "discrete"},
}

_CLOSE_RE = re.compile(
    r"\bđặt\b|\bdat\b|chốt đơn|chot don|thêm vào giỏ|them vao gio|"
    r"mua giúp|mua giup|ok đặt|ok dat|đặt hàng|dat hang",
    re.I,
)
_SWITCH_RE = re.compile(r"thôi|cho tôi|cái đó|máy này", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_OUR_QUESTION_RE = re.compile(
    r"ngân sách của bạn|bạn đang cần điện thoại, laptop|"
    r"bạn chủ yếu dùng|ưu tiên gpu mạnh hơn",
    re.I,
)
_GPU_CHOICE_RE = re.compile(r"gpu|hiệu năng|hieu nang|mạnh hơn|manh hon", re.I)
_CARRY_CHOICE_RE = re.compile(r"\bpin\b|nhẹ|nhe|mang đi|trọng lượng|trong luong", re.I)
_STOP_RE = re.compile(r"không muốn|thôi đừng|không mua|không đặt|chẳng muốn", re.I)

_KIND = {
    "phone": "điện thoại",
    "laptop": "laptop",
    "tablet": "máy tính bảng",
    "headphones": "tai nghe",
    "smartwatch": "đồng hồ",
}


def _user_lines(question, history):
    lines = []
    for role, body in history or []:
        if role == "user" and (body or "").strip():
            lines.append(body.strip())
    if (question or "").strip():
        lines.append(question.strip())
    return lines


def _folded_lines(question, history):
    lines = []
    for line in _user_lines(question, history):
        folded = line.casefold().replace("điên thoại", "điện thoại")
        lines.append(folded)
    return lines


def explicit_close(question, history=None):
    """A real order, not a wish such as 'muốn mua'."""
    if _CLOSE_RE.search(question or ""):
        return True
    if not _SWITCH_RE.search(question or ""):
        return False
    for line in _user_lines("", history):
        if _CLOSE_RE.search(line):
            return True
    return False


def _high(pattern, blob):
    return "high" if re.search(pattern, blob) else None


def extract_requirements(question, history=None):
    """Structured need. Unstated fields stay empty. Defaults are not written here."""
    resolved = resolve_request(question, history)
    folded_lines = _folded_lines(question, history)
    blob = "\n".join(folded_lines)
    category = ""
    for line in folded_lines:
        category = _category_phrase(line, "") or category
    family = resolved.get("family") or ""
    if not category and family == "iPhone":
        category = "phone"
    elif not category and family == "iPad":
        category = "tablet"
    elif not category and family == "MacBook":
        category = "laptop"
    elif not category and resolved.get("brand") in LAPTOP_BRANDS:
        category = "laptop"
    elif not category and resolved.get("brand") in HEADPHONE_BRANDS:
        category = "headphones"
    use = resolved.get("use") or ""
    use_cases = []
    if use == "gaming":
        use_cases.append("gaming")
    elif use == "study":
        if "ai" in blob or "trí tuệ" in blob or "tri tue" in blob:
            use_cases.extend(["coding", "ai"])
        elif re.search(r"\bcode\b|coding|lập trình|lap trinh", blob):
            use_cases.append("coding")
        else:
            use_cases.append("study")
    elif re.search(r"\bcode\b|coding|lập trình|lap trinh", blob):
        use_cases.append("coding")
    priorities = list(resolved.get("priorities") or [])
    if re.search(r"gpu.{0,20}(?:mạnh hơn|manh hon).{0,16}pin", blob) and "gpu" not in priorities:
        priorities.append("gpu")
    battery = "high" if (
        "battery" in priorities
        or re.search(r"pin (?:phải |phai )?trâu|pin trâu|pin trau|pin lâu|pin lau|pin tốt|pin tot|pin dùng lâu|pin dung lau", blob)
    ) else None
    portability = "high" if re.search(r"mang đi|mang di|mang theo|mỗi ngày|moi ngay", blob) else None
    weight = _high(r"đừng nặng|dung nang|máy nhẹ|may nhe|gọn nhẹ|gon nhe|trọng lượng|trong luong", blob)
    gpu_required = True if category == "laptop" and ("ai" in use_cases or "gaming" in use_cases) else None
    gpu_preferences = []
    if "nvidia" in blob or re.search(r"\brtx\b", blob):
        gpu_preferences.append("nvidia")
    brand = resolved.get("brand") or ""
    operating_system = None
    if "windows" in blob:
        operating_system = "windows"
    elif "macos" in blob or "mac os" in blob:
        operating_system = "macos"
    elif re.search(r"\bios\b", blob):
        operating_system = "ios"
    elif "android" in blob:
        operating_system = "android"
    ssd_min = None
    ssd_match = re.search(
        r"(?:ssd|ổ cứng|o cung).{0,16}(?:ít nhất|it nhat|tối thiểu|toi thieu)\s*(\d+)\s*gb"
        r"|(?:ít nhất|it nhat|tối thiểu|toi thieu)\s*(\d+)\s*gb\s*(?:ssd|ổ cứng|o cung)",
        blob,
    )
    if ssd_match:
        ssd_min = int(ssd_match.group(1) or ssd_match.group(2))
    phone = category == "phone"
    headphones = category == "headphones"
    watch = category == "smartwatch"
    extracted = {
        "category": category,
        "budget_min": resolved.get("price_min"),
        "budget_max": resolved.get("price_max"),
        "budget_target": resolved.get("price_target"),
        "use_cases": use_cases,
        "brand_preferences": [brand] if brand else [],
        "brand_exclusions": list(resolved.get("excluded_brands") or []),
        "priorities": priorities,
        "portability": portability,
        "operating_system": operating_system,
        "ram_min": resolved.get("min_ram"),
        "ssd_min": ssd_min,
        "gpu_required": gpu_required,
        "gpu_preferences": gpu_preferences,
        "battery_priority": battery,
        "weight_priority": weight,
        "screen_size": resolved.get("screen"),
        "screen_priority": _high(r"ưu tiên màn|uu tien man|màn hình lớn|man hinh lon|màn đẹp|man dep", blob),
        "upgradeability_priority": _high(r"nâng cấp|nang cap|nâng ram|nang ram|tháo ram|thao ram", blob) if not re.search(r"được không|duoc khong|con này|con nay", blob) else None,
        "camera_priority": _high(r"chụp ảnh|chup anh|camera", blob) if phone else None,
        "gaming_priority": "high" if phone and "gaming" in use_cases else None,
        "storage_min": None,
        "performance_priority": _high(r"cấu hình mạnh|cau hinh manh|hiệu năng|hieu nang", blob) if phone else None,
        "form_factor": (
            "in-ear" if headphones and re.search(r"nhét tai|nhet tai|in-ear|inear", blob)
            else "over-ear" if headphones and re.search(r"chụp tai|chup tai|over-ear|overear", blob)
            else None
        ),
        "anc_priority": _high(r"chống ồn|chong on|\banc\b", blob) if headphones else None,
        "sound_priority": _high(r"âm thanh|am thanh|\bbass\b", blob) if headphones else None,
        "microphone_priority": _high(r"micro|mic\b|họp online|hop online", blob) if headphones else None,
        "comfort_priority": _high(r"đeo lâu|deo lau|êm|em tai", blob) if headphones else None,
        "multipoint_required": True if headphones and re.search(r"hai máy|hai may|multipoint", blob) else None,
        "compatible_phone": None,
        "fitness_priority": _high(r"tập luyện|tap luyen|thể thao|the thao", blob) if watch else None,
        "health_tracking_priority": _high(r"nhịp tim|nhip tim|sức khỏe|suc khoe", blob) if watch else None,
        "gps_required": True if watch and re.search(r"\bgps\b", blob) else None,
        "calling_required": True if watch and re.search(r"nghe gọi|nghe goi|gọi điện|goi dien", blob) else None,
        "style_priority": _high(r"đẹp|dep|thời trang|thoi trang", blob) if watch else None,
        "specific": bool(resolved.get("specific") or resolved.get("query")),
        "cheapest": bool(resolved.get("cheapest")),
    }
    debug("EXTRACTED_REQUIREMENTS", user=question, requirements=extracted)
    return extracted


def missing_question(state):
    """One next question, or an empty string when the shop can search."""
    state = state or {}
    if state.get("specific") or state.get("cheapest"):
        return ""
    category = state.get("category") or ""
    if not category:
        return "Bạn đang cần điện thoại, laptop, tai nghe, máy tính bảng hay đồng hồ?"
    has_budget = any(state.get(key) is not None for key in ("budget_min", "budget_max", "budget_target"))
    if not has_budget:
        kind = _KIND.get(category, "máy")
        purpose = ""
        uses = state.get("use_cases") or []
        if "gaming" in uses:
            purpose = " để chơi game"
        elif "ai" in uses:
            purpose = " để học AI"
        elif "study" in uses:
            purpose = " để học và làm việc"
        return "Ngân sách của bạn cho {0}{1} khoảng bao nhiêu?".format(kind, purpose)
    uses = state.get("use_cases") or []
    if category == "laptop" and not uses and not state.get("brand_preferences"):
        return "Bạn chủ yếu dùng laptop để học, làm việc, chơi game hay đồ họa?"
    if category == "phone" and not uses and not state.get("brand_preferences") and not state.get("camera_priority"):
        return "Bạn chủ yếu dùng điện thoại để chụp ảnh, chơi game hay dùng hàng ngày?"
    if (
        category == "laptop"
        and state.get("gpu_required")
        and (state.get("portability") == "high" or state.get("weight_priority") == "high")
        and not state.get("priorities")
        and not state.get("tradeoff_answered")
    ):
        return "Bạn ưu tiên GPU mạnh hơn, hay pin và máy nhẹ để mang đi?"
    return ""


def _plain(body):
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", body or "")).strip()


def _last_bot(history):
    for role, body in reversed(list(history or [])):
        if role in ("bot", "assistant") and (body or "").strip():
            return body
    return ""


def _asked_tradeoff(history):
    return "ưu tiên gpu mạnh hơn" in _plain(_last_bot(history)).casefold()


def _continues(question, history):
    """A short reply to the shop's own question, not thanks or a new greeting."""
    from .policy import _SMALLTALK_RE

    if _SMALLTALK_RE.search(question or "") or _STOP_RE.search(question or ""):
        return False
    return _OUR_QUESTION_RE.search(_plain(_last_bot(history))) is not None


def follow_up_arguments(question, history):
    """A pin/weight answer becomes a battery priority. A GPU answer keeps the study default."""
    if not _asked_tradeoff(history):
        return {}
    folded = (question or "").casefold()
    if _CARRY_CHOICE_RE.search(folded) and not _GPU_CHOICE_RE.search(folded):
        return {"priorities": ["battery"]}
    return {}


def consultation(question, history, decision):
    """Live gate in front of search and checkout. None keeps the offline router choice.

    Returns (tool, intent, question) when the shopper should be asked one thing,
    or when a wish was misread as an order and should search instead.
    """
    tool = (decision or {}).get("tool") or "none"
    if tool not in ("search_products", "prepare_checkout", "none"):
        return None
    if explicit_close(question, history):
        return None
    if tool == "none" and not _continues(question, history):
        return None
    state = extract_requirements(question, history)
    if _asked_tradeoff(history):
        state = dict(state)
        state["tradeoff_answered"] = True
    ask = missing_question(state)
    debug("MISSING_REQUIREMENTS", question=ask, state=state)
    if ask:
        return ("ask", "advise", ask)
    if tool in ("prepare_checkout", "none"):
        return ("search_products", "product_search", "")
    return None
