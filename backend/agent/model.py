"""Tool schema and the model loop. Returned prices and stock still come from the tools."""
import json
import os
import re
import time
import urllib.request

from .retrieve import search_products
from .slots import resolve_request
from .tools import (
    check_inventory,
    compare_products,
    find_product,
    get_checkout_requirements,
    get_product,
    list_orders,
    prepare_checkout_request,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Tìm sản phẩm còn hàng theo nhóm, màu, hãng, giá và nhu cầu. Luôn gọi tool này khi khách hỏi gợi ý máy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["phone", "laptop", "tablet", "headphones", "smartwatch"]},
                    "query": {"type": "string", "description": "Chỉ tên dòng máy nếu khách nêu tên, ví dụ MacBook Pro. Để trống khi khách hỏi nhu cầu chung như học AI, chơi game, dưới X triệu. Không ghi cả câu hỏi vào query."},
                    "color": {"type": "string", "description": "Chỉ điền khi khách đã nói màu. Để trống khi đang gợi ý. Không hỏi màu trong lúc tư vấn."},
                    "price_min": {"type": "integer", "description": "Giá tối thiểu, đơn vị đồng."},
                    "price_max": {"type": "integer", "description": "Giá tối đa, đơn vị đồng. Dưới 50 triệu là 50000000."},
                    "brand": {"type": "string", "description": "Hãng. iPhone và iPad dùng Apple. MacBook dùng MacBook. Đừng đổi điện thoại Apple thành MacBook."},
                    "family": {"type": "string", "description": "Nhóm máy: iPhone, iPad hoặc MacBook. Không ghi hãng vào đây."},
                    "use": {"type": "string", "enum": ["", "gaming", "study"], "description": "gaming nếu chơi game. study nếu học, học AI, lập trình hoặc sinh viên. Câu nối tiếp như 'macbook thì sao' vẫn giữ use của câu trước."},
                    "line": {"type": "string", "enum": ["", "air", "pro", "neo"], "description": "Chỉ dòng MacBook Air, Pro hoặc Neo. iPhone Pro và iPad Pro để trống."},
                    "variant": {"type": "string", "description": "Biến thể điện thoại hoặc máy tính bảng, ví dụ pro, plus. Không dùng cho MacBook."},
                    "screen": {"type": "integer", "description": "Cỡ màn hình inch nếu khách nói, ví dụ 14. iPhone 16 không phải màn 16 inch."},
                    "chip": {"type": "string", "description": "Chip nếu khách nói, ví dụ m5 hoặc m5 pro. Chip M5 thường không phải m5 pro."},
                    "ram_gb": {"type": "integer", "description": "Đúng một mức RAM, ví dụ RAM 16GB. 256GB của điện thoại không phải RAM."},
                    "min_ram": {"type": "integer", "description": "RAM tối thiểu khi khách nói ít nhất hoặc từ N GB. Không điền ram_gb."},
                    "storage_gb": {"type": "integer", "description": "Bộ nhớ trong, ví dụ 128, 256, 512. Không điền vào ram_gb."},
                    "limit": {"type": "integer"},
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Lấy một sản phẩm còn hàng, kèm màu và cấu hình, khi khách chỉ định một máy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "Điền khi đã biết mã máy. Nếu chưa biết, điền query."},
                    "query": {"type": "string", "description": "Tên máy khi khách xem thông số hoặc một cấu hình."},
                    "color": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "So sánh hai máy còn hàng. Lấy thông số từ catalog, không bịa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_a": {"type": "string", "description": "Tên máy thứ nhất, ví dụ MacBook Air."},
                    "product_b": {"type": "string", "description": "Tên máy thứ hai, ví dụ MacBook Pro."},
                },
                "required": ["product_a", "product_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Xem còn hàng một máy. Không dùng search_products để suy ra tồn kho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Tên máy khách hỏi còn hàng."},
                    "category": {"type": "string"},
                    "brand": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_orders",
            "description": "Liệt kê đơn hàng của chính khách đang đăng nhập. Gọi khi khách hỏi đơn của mình hoặc theo dõi đơn. Không dùng để tìm sản phẩm.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_checkout",
            "description": "Chuẩn bị form đặt hàng. Chỉ gọi khi khách muốn mình đặt giúp một máy đã xác định.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "color": {"type": "string"},
                    "qty": {"type": "integer"},
                },
                "required": ["product_id"],
            },
        },
    },
]


def _model_product(item):
    specs = {spec.get("name"): spec.get("value") for spec in item.get("specs") or [] if isinstance(spec, dict)}
    return {
        "name": item.get("name") or "",
        "price_vnd": item.get("price"),
        "stock": item.get("stock"),
        "chip": specs.get("Chip") or "",
        "ram": specs.get("RAM") or "",
        "storage": specs.get("Bộ nhớ") or "",
        "battery": specs.get("Pin") or "",
        "charging": specs.get("Sạc") or "",
        "screen": specs.get("Màn hình") or "",
        "gpu": specs.get("Card") or "",
    }


def _public_payload(payload):
    """Facts the model may use. Prices and specs come from the catalog, not from the model."""
    data = json.loads(json.dumps(payload, default=str))
    if data.get("products"):
        data["products"] = [_model_product(item) for item in data["products"]]
        data["ui"] = (
            "Mỗi máy kèm chip, pin, sạc và kích thước màn hình. "
            "Viết một đoạn cho từng máy, dùng đúng các số này, rồi giải thích vì sao hợp nhu cầu khách. "
            "Viết thành câu. Không viết nhãn Chip:, RAM:, Giá:."
        )
    product = data.get("product")
    if isinstance(product, dict):
        data["product"] = _model_product(product)
    for key in ("product_a", "product_b"):
        if isinstance(data.get(key), dict):
            data[key] = _model_product(data[key])
    return data


def _given(arguments, key):
    if key not in (arguments or {}):
        return False
    value = arguments.get(key)
    return value is not None and value != ""


def _merge_search(arguments, resolved):
    """API điền thì giữ. Chỗ API bỏ trống thì lấy gợi ý local từ câu và hội thoại."""
    chosen = dict(arguments or {})
    hinted = resolved or {}

    def pick(key, default=None):
        if _given(chosen, key):
            return chosen.get(key)
        if hinted.get(key) not in (None, ""):
            return hinted.get(key)
        return default

    merged = {
        "category": pick("category", "phone"),
        "brand": pick("brand", "") or "",
        "use": pick("use", "") or "",
        "query": pick("query", "") or "",
        "color": pick("color", "") or "",
        "price_min": pick("price_min"),
        "price_max": pick("price_max"),
        "price_target": pick("price_target"),
        "ram_gb": pick("ram_gb"),
        "min_ram": pick("min_ram"),
        "storage_gb": pick("storage_gb"),
        "screen": pick("screen"),
        "line": pick("line", "") or "",
        "variant": pick("variant", "") or "",
        "chip": pick("chip", "") or "",
        "family": pick("family", "") or "",
    }
    merged["specific"] = bool(merged["ram_gb"] or merged["screen"] or merged["chip"])
    hinted_priorities = hinted.get("priorities") or []
    chosen_priorities = chosen.get("priorities") if isinstance(chosen.get("priorities"), list) else None
    merged["priorities"] = chosen_priorities or hinted_priorities
    if hinted.get("cheapest"):
        merged["price_min"] = None
        merged["price_max"] = None
        merged["price_target"] = None
        merged["cheapest"] = True
    else:
        merged["cheapest"] = False
    return merged


def _run_tool(conn, user, name, arguments, resolved=None):
    args = arguments or {}
    if name == "search_products":
        args = _merge_search(args, resolved)
        found = search_products(
            conn,
            category=args.get("category") or "phone",
            query=args.get("query") or "",
            color=args.get("color") or "",
            price_min=args.get("price_min"),
            price_max=args.get("price_max"),
            brand=args.get("brand") or "",
            use=args.get("use") or "",
            ram_gb=args.get("ram_gb"),
            min_ram=args.get("min_ram"),
            storage_gb=args.get("storage_gb"),
            screen=args.get("screen"),
            line=args.get("line") or "",
            variant=args.get("variant") or "",
            chip=args.get("chip") or "",
            specific=bool(args.get("specific")),
            price_target=args.get("price_target"),
            priorities=args.get("priorities") or [],
            family=args.get("family") or "",
            cheapest=bool(args.get("cheapest")),
            limit=args.get("limit") or (4 if args.get("cheapest") else 3),
        )
        return found, found.get("products") or [], None
    if name == "get_product":
        if args.get("product_id"):
            found = get_product(conn, args.get("product_id"), args.get("color") or "")
            products = [found["product"]] if found.get("product") else []
            return found, products, None
        merged = _merge_search(args, resolved)
        found = find_product(conn, merged)
        return found, found.get("products") or [], None
    if name == "compare_products":
        left = args.get("product_a") or ""
        right = args.get("product_b") or ""
        found = compare_products(conn, f"So sánh {left} và {right}" if left and right else "")
        return found, found.get("products") or [], None
    if name == "check_inventory":
        merged = _merge_search(args, resolved)
        found = check_inventory(conn, merged)
        return found, found.get("products") or [], None
    if name == "list_orders":
        found = list_orders(conn, user)
        return found, [], None
    if name == "prepare_checkout":
        if args.get("product_id"):
            found = get_checkout_requirements(conn, user, args.get("product_id"), args.get("color") or "", args.get("qty") or 1)
        else:
            found = prepare_checkout_request(conn, user, "", _merge_search(args, resolved))
        return found, found.get("products") or [], found if found.get("ok") else None
    return {"note": "Không có tool này."}, [], None


def _name_keys(name):
    text = re.sub(r"\d+\s*gb", " ", (name or "").casefold())
    text = re.sub(r"điện thoại|dien thoai|laptop|tai nghe|đồng hồ|dong ho", " ", text)
    skip = {"5g", "4g", "rtx", "nvidia", "geforce", "intel", "amd", "core", "ryzen", "card"}
    return [
        word for word in re.findall(r"[a-z0-9]+", text)
        if word not in skip and not word.isdigit()
    ]


def _best_start(line, products, claimed):
    head = line.casefold()[:80]
    best = None
    best_score = 1
    for item in products or []:
        if item.get("product_id") in claimed:
            continue
        keys = _name_keys(item.get("name") or "")
        score = sum(1 for key in keys if key and key in head)
        if score > best_score:
            best = item
            best_score = score
    return best


def split_advice(text, products):
    """Split a reply into an intro and a paragraph of advice under each product."""
    lines = []
    for raw in re.split(r"[\n\r]+|(?<=[.!?])\s+", text or ""):
        line = re.sub(r"^\d+[\.\)]\s*", "", raw.strip(" -")).strip().replace("**", "")
        if not line or re.fullmatch(r"\d+", line):
            continue
        if re.match(r"(nếu bạn|bạn có muốn|bạn cần thêm|các sản phẩm|những máy này|tất cả máy)\b", line.casefold()):
            continue
        lines.append(line)
    notes = {}
    intro = []
    current = None
    claimed = set()
    for line in lines:
        match = _best_start(line, products, claimed)
        if match is not None:
            current = match
            claimed.add(match.get("product_id"))
            body = re.sub(r"^[^:]{0,90}:\s*", "", line).strip() or line
            notes[match.get("product_id")] = body
            continue
        if current is not None:
            notes[current.get("product_id")] = (notes[current.get("product_id")] + " " + line).strip()
            continue
        intro.append(line)
    return " ".join(intro).strip(), notes


def _history_text(body):
    text = re.sub(r"<[^>]+>", " ", body or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def _complete(base, key, model_name, messages, tools=None, temperature=0.2):
    body = {"model": model_name, "messages": messages, "temperature": temperature}
    if tools:
        body["tools"] = tools
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.loads(response.read().decode())
    return payload["choices"][0]["message"]


def _trace_value(value, depth=0):
    if depth > 3:
        return "…"
    if isinstance(value, dict):
        kept = {}
        for key, item in value.items():
            folded = str(key).casefold()
            if folded in {"phone", "address", "email", "password"} or "phone" in folded or "address" in folded:
                continue
            kept[key] = _trace_value(item, depth + 1)
        return kept
    if isinstance(value, list):
        return [_trace_value(item, depth + 1) for item in value[:6]]
    if isinstance(value, str):
        return value[:240]
    return value


def _trace_result(result):
    data = {}
    if result.get("note"):
        data["note"] = (result.get("note") or "")[:300]
    if result.get("lead"):
        data["lead"] = (result.get("lead") or "")[:300]
    if result.get("near_miss"):
        data["near_miss"] = True
    if "ok" in result:
        data["ok"] = bool(result.get("ok"))
    products = result.get("products") or []
    if products:
        data["count"] = len(products)
        data["products"] = [_model_product(item) for item in products[:4]]
    elif isinstance(result.get("product"), dict):
        data["product"] = _model_product(result["product"])
    if "orders" in result:
        data["orders"] = [
            {
                "order_id": item.get("order_id"),
                "status": item.get("status"),
                "total": item.get("total"),
                "items": (item.get("items") or "")[:120],
            }
            for item in (result.get("orders") or [])[:5]
        ]
    return data


def _executed_arguments(name, arguments, resolved):
    args = arguments or {}
    if name == "search_products":
        return _merge_search(args, resolved)
    if name == "check_inventory":
        return _merge_search(args, resolved)
    if name == "get_product" and not args.get("product_id"):
        return _merge_search(args, resolved)
    if name == "prepare_checkout" and not args.get("product_id"):
        return _merge_search(args, resolved)
    return args


def _slot_snapshot(resolved):
    keys = (
        "category", "brand", "use", "query", "price_min", "price_max", "price_target",
        "cheapest", "line", "family", "ram_gb", "min_ram", "storage_gb",
    )
    return {key: (resolved or {}).get(key) for key in keys}


def answer_with_openai(conn, user, question, history=None):
    """One loop: the model chooses a tool, Python runs it, the model decides again."""
    started = time.perf_counter()

    def stamp():
        return round((time.perf_counter() - started) * 1000, 1)

    resolved = resolve_request(question, history)
    slot_done = stamp()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý bán hàng của Octopus Store. Trả lời tiếng Việt. "
                "Mỗi lượt bạn tự chọn: gọi một tool, hoặc viết câu trả lời cuối. "
                "Python chạy tool và gửi kết quả lại. Đọc kết quả rồi gọi tool tiếp hoặc dừng. "
                "Không bịa tên máy, giá, chip, RAM hay số tồn. Những số đó chỉ lấy từ kết quả tool. "
                "Không gọi tool khi câu không cần dữ liệu catalog hay đơn hàng. "
                "prepare_checkout chỉ khi khách đang yêu cầu đặt một máy đã chọn. Câu hỏi và câu từ chối thì trả lời bằng chữ. "
                "Khi đang tư vấn, không hỏi màu sắc. Chỉ hỏi màu khi khách đã chọn một máy và muốn đặt. "
                "Khi khách hỏi sản phẩm, gọi search_products. query chỉ là tên máy nếu khách nêu tên; "
                "câu hỏi chung như học AI thì query để trống. "
                "Học, học AI, lập trình, sinh viên: category=laptop và use=study. "
                "256GB và 512GB là storage_gb, không phải ram_gb. "
                "iPhone Pro không phải dòng MacBook. Apple trên điện thoại là brand Apple. "
                "Laptop Apple trong catalog là brand MacBook. "
                "Khi khách hỏi một cấu hình cụ thể, nhận xét đúng máy đó theo chip, RAM và GPU trong tool. "
                "MacBook Pro 14 chip M5 thường, RAM 16 GB, GPU tích hợp: làm bài nhỏ được, học AI thì chật. "
                "Đừng trả lời bằng câu về MacBook Air nếu khách không hỏi Air và kết quả không kèm Air. "
                "Khi khách chưa chỉ cấu hình, học AI nên là MacBook Pro từ 24 GB hoặc laptop có GPU rời. "
                "Nếu tool không trả sản phẩm và note nói không có máy khớp, nói lại đúng note. "
                "Nếu tool trả về sản phẩm, viết về từng máy. Đừng lặp câu từ chối của lượt trước. "
                "Laptop quanh tầm giá là hướng thực tế. MacBook Air trong kết quả không quá phù hợp để học AI và có thể vượt tầm giá. "
                "Không khen Air là máy học AI. "
                "Câu nối tiếp chỉ đổi hãng hoặc dòng máy thì giữ nguyên nhu cầu câu trước. "
                "Khi gợi ý local có cheapest=true, khách muốn mẫu rẻ nhất và đã bỏ tầm giá cũ. "
                "Gọi search_products, để trống price_max và price_target, giữ use và category của nhu cầu. "
                "Đừng viết lại câu không có máy dưới ngân sách cũ. "
                "Chơi game: use=gaming. Máy tính trong tiếng Việt là laptop, trừ khi là máy tính bảng. "
                "Bạn tự chọn tham số tool. Chỗ bạn điền được giữ. Chỗ bạn bỏ trống thì hệ thống lấy từ gợi ý local bên dưới. "
                "Không bịa tên máy, giá, chip, RAM hay số tồn kho. "
                "Khi tool đã trả sản phẩm, viết một câu mở về tầm giá, rồi mỗi máy một đoạn riêng bắt đầu bằng tên máy. "
                "Trong đoạn đó nói chip nào, pin bao nhiêu, sạc tối đa bao nhiêu, màn hình rộng bao nhiêu, "
                "rồi giải thích vì sao từng số đó hợp người khách đang hỏi. "
                "Người lớn tuổi thì nói màn hình có dễ đọc không, pin có đỡ phải sạc nhiều lần không, sạc có nhanh khi cắm không. "
                "Chỉ nhắc người lớn tuổi khi khách nói phụ huynh hoặc người lớn tuổi. "
                "Khách hỏi học AI thì nói GPU và RAM có chạy bài được không. "
                "Dùng đúng số trong tool, không bịa. Viết thành câu. Không viết nhãn Chip:, RAM:, Giá:. "
                "Không thêm câu chung cho mọi máy ở cuối. "
                "Nếu note của tool nói máy nào bị loại, câu mở nói lại ý đó. "
                "Đòi xóa dữ liệu, xem đơn người khác hoặc chạy SQL: từ chối bằng chữ, không gọi tool. "
                "Không tự điền số điện thoại, địa chỉ hay lịch nhận. "
                "Gợi ý local, không bắt buộc: "
                f"category={resolved.get('category') or ''}, brand={resolved.get('brand') or ''}, "
                f"family={resolved.get('family') or ''}, "
                f"use={resolved.get('use') or ''}, line={resolved.get('line') or ''}, "
                f"screen={resolved.get('screen') or ''}, chip={resolved.get('chip') or ''}, "
                f"ram_gb={resolved.get('ram_gb') or ''}, min_ram={resolved.get('min_ram') or ''}, "
                f"storage_gb={resolved.get('storage_gb') or ''}, "
                f"price_max={resolved.get('price_max') if resolved.get('price_max') is not None else ''}, "
                f"price_min={resolved.get('price_min') if resolved.get('price_min') is not None else ''}, "
                f"price_target={resolved.get('price_target') if resolved.get('price_target') is not None else ''}, "
                f"cheapest={bool(resolved.get('cheapest'))}, "
                f"priorities={','.join(resolved.get('priorities') or [])}."
            ),
        },
    ]
    for role, body in (history or [])[-8:]:
        if role == "user":
            messages.append({"role": "user", "content": (body or "")[:500]})
        else:
            text = _history_text(body)
            if text:
                messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": question})
    products = []
    checkout = None
    orders = None
    advice_lead = ""
    pending_input = {"question": (question or "")[:240]}
    trace = [{
        "kind": "slots",
        "type": "SPAN",
        "name": "Đọc câu hỏi",
        "text": "Gợi ý local từ câu này và hội thoại. Đây chưa phải model. Chỗ model bỏ trống thì Python điền từ gợi ý này.",
        "arguments": _slot_snapshot(resolved),
        "input": pending_input,
        "t0": 0,
        "t1": slot_done,
    }]
    for _ in range(4):
        t0 = stamp()
        message = _complete(base, key, model, messages, TOOLS, temperature=0.2)
        t1 = stamp()
        calls = message.get("tool_calls") or []
        parsed = []
        call_rows = []
        for call in calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            parsed.append((call, name, arguments))
            call_rows.append({"name": name, "arguments": _trace_value(arguments)})
        content = (message.get("content") or "").strip()
        trace.append({
            "kind": "model",
            "type": "GENERATION",
            "name": model,
            "text": content,
            "calls": call_rows,
            "input": pending_input,
            "t0": t0,
            "t1": t1,
        })
        if not calls:
            text = content or advice_lead
            return {
                "text": text,
                "text_from": "model" if content else "tool_note",
                "products": products,
                "checkout": checkout,
                "orders": orders,
                "trace": trace,
            }
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        round_tools = []
        for call, name, arguments in parsed:
            ran = _executed_arguments(name, arguments, resolved)
            tool_t0 = stamp()
            result, found, ready = _run_tool(conn, user, name, arguments, resolved)
            tool_t1 = stamp()
            if result.get("near_miss"):
                advice_lead = result.get("lead") or result.get("note") or advice_lead
            if name == "list_orders":
                orders = result.get("orders") or []
                products = []
            elif found:
                products = found
            if ready:
                checkout = ready
            note = ""
            if name == "search_products" and resolved.get("cheapest"):
                note = "Câu này hỏi mẫu rẻ nhất. Python không giữ price_max hay price_target của câu trước."
            public_result = _trace_result(result)
            trace.append({
                "kind": "tool",
                "type": "TOOL",
                "name": name,
                "sent": _trace_value(arguments),
                "ran": _trace_value(ran),
                "note": note,
                "result": public_result,
                "t0": tool_t0,
                "t1": tool_t1,
            })
            round_tools.append({"tool": name, "result": public_result})
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(_public_payload(result), ensure_ascii=False),
            })
        pending_input = round_tools[0] if len(round_tools) == 1 else {"tools": round_tools}
    return {
        "text": advice_lead,
        "text_from": "tool_note",
        "products": products,
        "checkout": checkout,
        "orders": orders,
        "trace": trace,
    }
