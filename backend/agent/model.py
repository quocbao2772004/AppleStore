"""Tool schema and the model loop. Returned prices and stock still come from the tools."""
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request

from .retrieve import list_category, search_products
from .debug import debug
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
                    "use": {"type": "string", "enum": ["", "gaming", "study"], "description": "gaming nếu chơi game. study chỉ khi học AI, code AI, machine learning hoặc cần GPU. Học code hay lập trình thường không phải study. Học kế toán, văn phòng, Excel không phải study. Câu nối tiếp như 'macbook thì sao' vẫn giữ use của câu trước."},
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
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Tìm đoạn điều khoản đã nhúng trong Qdrant. Dùng khi khách hỏi bảo hành, đổi trả, giao hàng hoặc chính sách hãng. Không dùng để tìm giá hay số máy còn lại.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Câu hỏi của khách, giữ nguyên ý bảo hành hoặc chính sách."},
                    "brand": {"type": "string", "description": "Hãng nếu khách nói, ví dụ Apple, Samsung, Xiaomi, OPPO. Để trống khi chưa rõ hãng."},
                    "doc_type": {
                        "type": "string",
                        "enum": ["warranty", "store_policy", "return", "privacy", "eula", "other"],
                        "description": "warranty khi hỏi bảo hành. Không lấy return, privacy hay eula để trả lời câu bảo hành.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def _model_product(item):
    specs = {spec.get("name"): spec.get("value") for spec in item.get("specs") or [] if isinstance(spec, dict)}
    return {
        "product_id": item.get("product_id"),
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
        "rear_camera": specs.get("Camera sau") or "",
        "front_camera": specs.get("Camera trước") or "",
        "camera_features": specs.get("Camera") or "",
        "video": specs.get("Quay phim") or "",
        "fit": item.get("fit") or "",
        "catalog_reason": item.get("reason") or "",
    }


def _public_payload(payload):
    """Facts the model may use. Prices and specs come from the catalog, not from the model."""
    data = json.loads(json.dumps(payload, default=str))
    if data.get("products"):
        data["products"] = [_model_product(item) for item in data["products"]]
        data["ui"] = "Mỗi sản phẩm cần một lời giải thích riêng theo product_id, dựa trên thông số và nhu cầu của khách."
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
        "price_max_exclusive": bool(hinted.get("price_max_exclusive")),
        "price_target": pick("price_target"),
        "ram_gb": pick("ram_gb"),
        "min_ram": pick("min_ram"),
        "storage_gb": pick("storage_gb"),
        "screen": pick("screen"),
        "line": pick("line", "") or "",
        "variant": pick("variant", "") or "",
        "chip": pick("chip", "") or "",
        "family": pick("family", "") or "",
        "excluded_brands": pick("excluded_brands") or [],
        "min_refresh": pick("min_refresh"),
    }
    # Local requirements are authoritative for hard constraints even when a
    # caller supplies an empty list or a looser ceiling.
    exclusions = list(hinted.get("excluded_brands") or [])
    for name in merged["excluded_brands"]:
        if name.casefold() not in {entry.casefold() for entry in exclusions}:
            exclusions.append(name)
    merged["excluded_brands"] = exclusions
    if hinted.get("price_max") is not None:
        if merged["price_max"] is None or int(merged["price_max"]) > int(hinted["price_max"]):
            merged["price_max"] = hinted["price_max"]
    if merged["brand"].casefold() in {name.casefold() for name in exclusions}:
        merged["brand"] = ""
    merged["specific"] = bool(merged["ram_gb"] or merged["screen"] or merged["chip"])
    hinted_priorities = hinted.get("priorities") or []
    chosen_priorities = chosen.get("priorities") if isinstance(chosen.get("priorities"), list) else None
    merged["priorities"] = chosen_priorities or hinted_priorities
    if hinted.get("cheapest"):
        merged["price_min"] = None
        merged["price_max"] = None
        merged["price_max_exclusive"] = False
        merged["price_target"] = None
        merged["cheapest"] = True
    else:
        merged["cheapest"] = False
    return merged


def _run_tool(conn, user, name, arguments, resolved=None):
    args = arguments or {}
    if name == "search_products":
        args = _merge_search(args, resolved)
        debug("SEARCH_INPUT", arguments=args)
        found = search_products(
            conn,
            category=args.get("category") or "phone",
            query=args.get("query") or "",
            color=args.get("color") or "",
            price_min=args.get("price_min"),
            price_max=args.get("price_max"),
            price_max_exclusive=bool(args.get("price_max_exclusive")),
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
            min_refresh=args.get("min_refresh"),
            excluded_brands=args.get("excluded_brands") or [],
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
        sentence = f"So sánh {left} và {right}" if left and right else (args.get("query") or "")
        found = compare_products(conn, sentence, sides=(left, right) if left and right else None, category=(resolved or {}).get("category"))
        return found, found.get("products") or [], None
    if name == "check_inventory":
        merged = _merge_search(args, resolved)
        found = check_inventory(conn, merged)
        return found, found.get("products") or [], None
    if name == "list_category":
        found = list_category(conn, (resolved or {}).get("category") or args.get("category") or "")
        return found, [], None
    if name == "list_orders":
        found = list_orders(conn, user)
        return found, [], None
    if name == "prepare_checkout":
        if args.get("product_id"):
            found = get_checkout_requirements(conn, user, args.get("product_id"), args.get("color") or "", args.get("qty") or 1)
        else:
            found = prepare_checkout_request(conn, user, args.get("query") or "", _merge_search(args, resolved), qty=args.get("qty"))
        return found, found.get("products") or [], found if found.get("ok") else None
    if name == "search_documents":
        from rag.search import search_documents

        doc_type = args.get("doc_type") or "warranty"
        found = search_documents(
            args.get("query") or "",
            brand=args.get("brand") or "",
            doc_type=doc_type,
        )
        return found, [], None
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


def _complete(base, key, model_name, messages, tools=None, temperature=0.2, response_format=None):
    body = {"model": model_name, "messages": messages, "temperature": temperature}
    if tools:
        body["tools"] = tools
    if response_format:
        body["response_format"] = response_format
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
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                payload = json.loads(response.read().decode())
            return payload["choices"][0]["message"]
        except urllib.error.HTTPError as exc:
            if attempt or exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            error = exc
        except (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError,
                BrokenPipeError, TimeoutError, socket.timeout) as exc:
            if attempt:
                raise
            error = exc
        debug("PROVIDER_RETRY", error=type(error).__name__, attempt=attempt + 2)
        time.sleep(0.4)


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
    passages = result.get("passages") or []
    if passages:
        data["passages"] = [
            {
                "title": item.get("title") or "",
                "brand": item.get("brand") or "",
                "score": item.get("score"),
                "text": (item.get("text") or "")[:180],
            }
            for item in passages[:4]
        ]
    brands = result.get("brands") or []
    if brands:
        data["category"] = result.get("category") or ""
        data["brands"] = [
            {"brand": item.get("brand") or "", "count": item.get("count")}
            for item in brands[:12]
        ]
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
    if name == "list_category":
        return {"category": (resolved or {}).get("category") or args.get("category") or ""}
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
        "price_max_exclusive", "excluded_brands", "priorities", "cheapest", "line", "family", "ram_gb", "min_ram", "storage_gb",
    )
    return {key: (resolved or {}).get(key) for key in keys}


def answer_with_openai(conn, user, question, history=None):
    """Live provider path. The server reports unavailability when no key is set."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    from .graph import run_shop_graph

    return run_shop_graph(conn, user, question, history)
