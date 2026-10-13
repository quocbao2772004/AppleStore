#!/usr/bin/env python3
"""Cửa hàng Octopus Store.

Chạy: .venv/bin/python backend/server.py
Giao diện người dùng nằm ở frontend/. Trang, đăng nhập và đơn hàng nằm ở file này.
Trợ lý khách nằm ở backend/agent/. Trợ lý quản trị nằm ở backend/admin_agent/. Ô tìm kiếm gọi api/suggest.py. Bảng nằm ở database/schema.sql.
"""

import hashlib
import html
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import urllib.request
import urllib.error
from contextvars import ContextVar
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import psycopg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from api.suggest import search_names


def load_dotenv(path):
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")
import invoice
import payment
MEDIA_ROOT = (ROOT / "data" / "images").resolve()
STATIC = ROOT / "frontend"
DSN = os.environ.get("DATABASE_URL", "dbname=tgdd_products")
HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8765"))
DEMO_MODE = os.environ.get("APP_DEMO_MODE", "1") == "1"
SHOW_DEMO_LOGIN = os.environ.get("APP_SHOW_DEMO_LOGIN", "0") == "1"
PUBLIC_ORIGINS = frozenset(
    origin.strip().rstrip("/")
    for origin in os.environ.get("APP_PUBLIC_ORIGIN", "").split(",")
    if origin.strip()
)
COOKIE_SECURE = "; Secure" if any(origin.startswith("https://") for origin in PUBLIC_ORIGINS) else ""
CURRENT_USER = ContextVar("current_user", default=None)
CUTOUT_ROOT = (ROOT / "data" / "cutouts").resolve()

CATEGORIES = (
    ("phone", "Điện thoại"),
    ("laptop", "Laptop"),
    ("tablet", "Máy tính bảng"),
    ("headphones", "Tai nghe"),
    ("smartwatch", "Đồng hồ"),
)
LABEL = dict(CATEGORIES)
LIVE_CATEGORIES = ContextVar("live_categories", default=None)


def category_pairs():
    live = LIVE_CATEGORIES.get()
    return live if live else CATEGORIES


def category_map():
    return dict(category_pairs())
LINES = {
    "phone": "Pro hơn hẳn.",
    "laptop": "Mỏng. Nhẹ. Làm được việc dài.",
    "tablet": "Màn hình lớn, mang theo được.",
    "headphones": "Nghe rõ. Phần còn lại im.",
    "smartwatch": "Đeo cả ngày. Nhìn đã thấy giờ.",
}
THEMES = {
    "phone": "light",
    "laptop": "dark",
    "tablet": "soft",
    "headphones": "ink",
    "smartwatch": "light",
}
PREFIXES = (
    "Điện thoại ",
    "Máy tính bảng ",
    "Tai nghe Bluetooth ",
    "Tai nghe Có dây ",
    "Tai nghe Có Dây ",
    "Tai nghe ",
    "Laptop ",
    "Đồng hồ thông minh ",
    "Đồng hồ ",
)


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def current_attr(active, value="page"):
    return f' aria-current="{value}"' if active else ""


def money(value):
    if not value:
        return "Chưa niêm yết"
    return f"{int(value):,}".replace(",", ".") + "₫"


def short_name(name):
    text = name or "Sản phẩm"
    for prefix in PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return re.sub(r"\s*-\s*imei\s*$", "", text, flags=re.I).strip()


def display_name(name):
    text = short_name(name)
    text = re.sub(r"\s*\([^)]*\)", "", text)
    text = re.sub(r"\s+-\s+.*$", "", text)
    text = re.sub(r"\s+\d+\s*GB(?:\s*/\s*\d+\s*(?:GB|TB))?", "", text, flags=re.I)
    text = re.sub(r"\s+5G\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text or short_name(name)


def media_url(local_path):
    if not local_path or not local_path.startswith("data/images/"):
        return None
    return "/media/" + quote(local_path[len("data/images/"):])


def connect():
    return psycopg.connect(DSN, autocommit=True)


def brand_slug(name):
    text = unicodedata.normalize("NFKD", name or "Khác")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "khac"


def brand_directory(conn, category):
    rows = conn.execute(
        """
        SELECT coalesce(nullif(brand, ''), 'Khác') AS brand, count(*)
        FROM products
        WHERE is_live_catalog AND category = %s
        GROUP BY 1
        ORDER BY count(*) DESC, brand
        """,
        (category,),
    ).fetchall()
    seen = {}
    brands = []
    for name, count in rows:
        base = brand_slug(name)
        seen[base] = seen.get(base, 0) + 1
        slug = base if seen[base] == 1 else f"{base}-{seen[base]}"
        brands.append({"name": name, "slug": slug, "count": int(count)})
    return brands


def covers(conn, product_ids):
    if not product_ids:
        return {}
    rows = conn.execute(
        """
        SELECT DISTINCT ON (product_id) product_id, local_path, coalesce(alt_text, '')
        FROM product_images
        WHERE product_id = ANY(%s) AND local_path IS NOT NULL
        ORDER BY product_id,
                 CASE image_role WHEN 'thumbnail' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
                 display_order, image_url
        """,
        (list(product_ids),),
    ).fetchall()
    found = {}
    for product_id, path, alt in rows:
        url = media_url(path)
        if url:
            found[product_id] = (url, alt)
    return found


def product_images(conn, product_id):
    rows = conn.execute(
        """
        SELECT local_path, coalesce(alt_text, '')
        FROM product_images
        WHERE product_id = %s AND local_path IS NOT NULL
        ORDER BY CASE image_role WHEN 'thumbnail' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
                 display_order, image_url
        """,
        (product_id,),
    ).fetchall()
    return [(media_url(path), alt) for path, alt in rows if media_url(path)]


def product_row(conn, row, headline=None, line=None):
    if not row:
        return None
    images = product_images(conn, row[0])
    if not images:
        return None
    return {
        "id": row[0], "category": row[1], "name": row[2], "brand": row[3],
        "price": row[4], "short": short_name(row[2]), "images": images,
        "image": images[0][0],
        "alt": images[0][1] or display_name(row[2]),
        "title": display_name(row[2]),
        "headline": headline or display_name(row[2]),
        "line": line,
    }


def spotlight(conn, include, exclude=None, headline=None, line=None, category=None):
    sql = """
        SELECT source_product_id, category, name, brand, price_vnd
        FROM products
        WHERE is_live_catalog AND price_vnd > 0 AND name ILIKE %s
          AND EXISTS (
            SELECT 1 FROM product_images i
            WHERE i.product_id = products.source_product_id AND i.local_path IS NOT NULL
          )
    """
    params = [include]
    if category:
        sql += " AND category = %s"
        params.append(category)
    if exclude:
        sql += " AND name NOT ILIKE %s"
        params.append(exclude)
    sql += " ORDER BY price_vnd ASC LIMIT 1"
    item = product_row(conn, conn.execute(sql, params).fetchone(), headline, line)
    if not item:
        return None
    item["note"] = f"Từ {money(item['price'])}. Đang có tại cửa hàng."
    return ready_cutout(item)


def local_from_media(url):
    if url and url.startswith("/media/"):
        return ROOT / "data" / "images" / url[len("/media/"):]
    return None


COLOR_SOURCES = {}
COLOR_SOURCE_LOCK = threading.Lock()


def banner_cutout(image):
    from PIL import Image
    image = image.convert("RGBA")
    if max(image.size) > 900:
        image.thumbnail((900, 900), Image.LANCZOS)
    image = cut_edges(image)
    box = image.getbbox()
    if not box:
        return image
    pad = 18
    left, top, right, bottom = box
    return image.crop((
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad),
        min(image.height, bottom + pad),
    ))


def cut_edges(image):
    from PIL import ImageDraw
    image = image.convert("RGBA")
    width, height = image.size
    pixels = image.load()
    seeds = [
        (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
        (width // 2, 0), (width // 2, height - 1), (0, height // 2), (width - 1, height // 2),
    ]
    for x, y in seeds:
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0 or min(red, green, blue) < 236:
            continue
        ImageDraw.floodfill(image, (x, y), (red, green, blue, 0), thresh=16)
    return _drop_white_fringe(image)


def _drop_white_fringe(image):
    # Chỉ xóa pixel gần trắng đang chạm vùng trong suốt. Thân máy trắng ở bên trong được giữ.
    pixels = image.load()
    width, height = image.size
    neighbors = (
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    )
    for _pass in range(2):
        clear = []
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = pixels[x, y]
                if alpha == 0:
                    continue
                darkest = min(red, green, blue)
                if darkest < 176 or max(red, green, blue) - darkest > 36:
                    continue
                for dx, dy in neighbors:
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < width and 0 <= ny < height and pixels[nx, ny][3] == 0:
                        clear.append((x, y))
                        break
        if not clear:
            break
        for x, y in clear:
            red, green, blue, _alpha = pixels[x, y]
            pixels[x, y] = (red, green, blue, 0)
    return image


def make_cutout(source, dest):
    from PIL import Image
    image = Image.open(source)
    if max(image.size) > 900:
        image.thumbnail((900, 900), Image.LANCZOS)
    image = cut_edges(image)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, "PNG")


def remember_color_source(name, url):
    with COLOR_SOURCE_LOCK:
        if COLOR_SOURCES.get(name) == url:
            return
        COLOR_SOURCES[name] = url
        CUTOUT_ROOT.mkdir(parents=True, exist_ok=True)
        (CUTOUT_ROOT / "sources.json").write_text(json.dumps(COLOR_SOURCES))


def load_color_sources():
    path = CUTOUT_ROOT / "sources.json"
    if not path.is_file():
        return
    try:
        COLOR_SOURCES.update(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return


def remote_cutout_name(url):
    return hashlib.sha1(b"banner2\n" + url.encode()).hexdigest()[:12] + ".png"


def cached_cutout_url(url):
    if not url or not str(url).startswith("https://"):
        return url or ""
    name = remote_cutout_name(url)
    path = CUTOUT_ROOT / name
    if path.is_file() and path.stat().st_size > 32:
        return f"/cutout/{name}"
    return url


def shown_image(url):
    if not url:
        return ""
    if str(url).startswith("https://"):
        return cached_cutout_url(url)
    if str(url).startswith("/media/"):
        return ready_cutout({"image": url}).get("image") or url
    return url


def remote_cutout_url(url):
    if not url or not url.startswith("https://"):
        return url
    name = remote_cutout_name(url)
    remember_color_source(name, url)
    return f"/cutout/{name}"


def ensure_remote_cutout(name):
    dest = CUTOUT_ROOT / name
    if dest.is_file() and dest.stat().st_size > 32:
        return True
    with COLOR_SOURCE_LOCK:
        lock = BUILD_LOCKS.get(name)
        if lock is None:
            lock = threading.Lock()
            BUILD_LOCKS[name] = lock
    with lock:
        if dest.is_file() and dest.stat().st_size > 32:
            return True
        return write_remote_cutout(name, dest)


BUILD_LOCKS = {}


def write_remote_cutout(name, dest):
    url = COLOR_SOURCES.get(name)
    if not url or not url.startswith("https://"):
        return False
    from io import BytesIO
    from PIL import Image
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        blob = response.read(8_000_000)
    image = banner_cutout(Image.open(BytesIO(blob)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(".part")
    image.save(temporary, "PNG")
    temporary.replace(dest)
    return dest.is_file()


def cutout_name(source):
    return hashlib.sha1(str(source).encode()).hexdigest()[:12] + ".png"


def ready_cutout(item):
    source = local_from_media(item.get("image"))
    if not source:
        return item
    name = cutout_name(source)
    path = CUTOUT_ROOT / name
    if path.is_file():
        item["image"] = f"/cutout/{name}?v={int(path.stat().st_mtime)}"
    return item


def with_cutout(item):
    source = local_from_media(item.get("image"))
    if not source or not source.is_file():
        return item
    name = cutout_name(source)
    dest = CUTOUT_ROOT / name
    try:
        if not dest.exists() or dest.stat().st_mtime < source.stat().st_mtime:
            make_cutout(source, dest)
        item["image"] = f"/cutout/{name}"
    except Exception:
        pass
    return item


def flagship(conn, category):
    row = conn.execute(
        """
        SELECT source_product_id, category, name, brand, price_vnd
        FROM products
        WHERE is_live_catalog AND category = %s AND price_vnd > 0
          AND name NOT ILIKE '%%duo%%'
          AND name NOT ILIKE '%%imei%%'
          AND EXISTS (
            SELECT 1 FROM product_images i
            WHERE i.product_id = products.source_product_id AND i.local_path IS NOT NULL
          )
        ORDER BY (
            SELECT count(*) FROM product_images i
            WHERE i.product_id = products.source_product_id
              AND i.local_path IS NOT NULL AND i.image_role = 'thumbnail'
        ) DESC, price_vnd DESC
        LIMIT 1
        """,
        (category,),
    ).fetchone()
    return product_row(conn, row)


def catalog(conn, category=None, query="", sort="featured", offset=0, limit=24, brand=None):
    where = ["p.is_live_catalog"]
    params = []
    if category in category_map():
        where.append("p.category = %s")
        params.append(category)
    if brand:
        where.append("coalesce(nullif(p.brand, ''), 'Khác') = %s")
        params.append(brand)
    if query:
        where.append("p.search_vector @@ plainto_tsquery('simple', %s)")
        params.append(query)
    order = "random()" if sort == "shuffle" else {
        "price-asc": "p.price_vnd ASC NULLS LAST, p.name",
        "price-desc": "p.price_vnd DESC NULLS LAST, p.name",
    }.get(sort, "p.price_vnd DESC NULLS LAST, p.name")
    sql = f"""
        SELECT p.source_product_id, p.category, p.name, p.brand, p.price_vnd, count(*) OVER ()
        FROM products p
        WHERE {' AND '.join(where)}
        ORDER BY {order}
        LIMIT %s OFFSET %s
    """
    rows = conn.execute(sql, [*params, limit, offset]).fetchall()
    return rows_to_items(conn, rows), (rows[0][5] if rows else 0)


def rows_to_items(conn, rows):
    images = covers(conn, [row[0] for row in rows])
    items = []
    for row in rows:
        image = images.get(row[0])
        items.append({
            "id": row[0], "category": row[1], "name": row[2], "brand": row[3] or "Khác",
            "price": row[4], "short": short_name(row[2]),
            "image": image[0] if image else None,
            "alt": (image[1] if image else None) or display_name(row[2]),
            "title": display_name(row[2]),
        })
    return items


def load_product(conn, product_id):
    row = conn.execute(
        """
        SELECT source_product_id, category, name, brand, price_vnd, stock, description,
               rating_value, rating_count, url
        FROM products
        WHERE source_product_id = %s AND is_live_catalog
        """,
        (product_id,),
    ).fetchone()
    if not row:
        return None
    images = product_images(conn, row[0])
    specs = conn.execute(
        """
        SELECT group_name, spec_name, spec_value
        FROM product_specifications
        WHERE product_id = %s
        ORDER BY display_order, spec_name
        LIMIT 40
        """,
        (product_id,),
    ).fetchall()
    related, _ = catalog(conn, category=row[1], brand=row[3] or "Khác", sort="featured", limit=5)
    related = [item for item in related if item["id"] != product_id][:4]
    return {
        "id": row[0], "category": row[1], "name": row[2], "brand": row[3],
        "price": row[4], "stock": int(row[5] or 0), "description": row[6], "rating": row[7], "rating_count": row[8],
        "source": row[9], "short": short_name(row[2]), "title": display_name(row[2]),
        "images": images, "specs": specs,
        "related": related,
    }


def parse_bag(cookie_header):
    jar = SimpleCookie(cookie_header or "")
    raw = jar["bag"].value if "bag" in jar else ""
    bag = []
    for part in raw.split(","):
        if ":" not in part:
            continue
        ident, qty = part.split(":", 1)
        if ident.isdigit() and qty.isdigit():
            amount = max(0, min(int(qty), 5))
            if amount:
                bag.append((int(ident), amount))
    return bag[:30]


def dump_bag(bag):
    return ",".join(f"{ident}:{qty}" for ident, qty in bag if qty > 0)


BAG_ICON = (
    '<svg class="bag-icon" viewBox="0 0 16 20" aria-hidden="true">'
    '<path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" '
    'd="M3.2 6.2h9.6c.66 0 1.2.54 1.2 1.2v9.3c0 .66-.54 1.2-1.2 1.2H3.2c-.66 0-1.2-.54-1.2-1.2V7.4c0-.66.54-1.2 1.2-1.2z"/>'
    '<path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
    'd="M5.3 6.1V4.7a2.7 2.7 0 0 1 5.4 0V6.1"/>'
    '</svg>'
)
def robot_tag(size, extra=""):
    attrs = (
        'class="robot-face" color="#1d1d1f" auto-sleep="0" '
        'press-squeeze="false" antenna-drag="false" aria-hidden="true"'
    )
    suffix = (" " + extra) if extra else ""
    # Light-DOM face stays visible until the custom element attaches its shadow.
    face = (
        '<svg class="robot-fallback" viewBox="0 0 64 64" aria-hidden="true">'
        '<rect x="8" y="8" width="48" height="48" rx="16" fill="#1d1d1f"/>'
        '<ellipse cx="24" cy="34" rx="6" ry="7" fill="#fff"/>'
        '<ellipse cx="40" cy="34" rx="6" ry="7" fill="#fff"/>'
        "</svg>"
    )
    return f'<agent-robot-avatar {attrs} size="{int(size)}"{suffix}>{face}</agent-robot-avatar>'


OCTOPUS_MASCOT = robot_tag(46, 'id="octopus-mascot" data-state="idle"')
BOT_MARK = (
    f'<span class="av av-bot" aria-hidden="true">{robot_tag(32)}</span>'
)


def layout(title, body, bag_count, current=None, home=False, admin=False, show_reasons=False):
    count = f'<span class="bag-count">{bag_count}</span>' if bag_count else ""
    nav_items = [("/", "Trang chủ", current == "home")]
    nav_items.extend((f"/c/{key}", label, key == current) for key, label in category_pairs())
    nav_items.extend((
        ("/gioi-thieu", "Giới thiệu", current == "about"),
        ("/lien-he", "Liên hệ", current == "contact"),
    ))
    links = "".join(
        f'<a href="{esc(href)}"{current_attr(active)}>{esc(label)}</a>'
        for href, label, active in nav_items
    )
    home_attr = ' data-home="1"' if home else ""
    if admin:
        home_attr = ' class="is-admin"'
    user = CURRENT_USER.get()
    if user:
        admin_link = '<a class="nav-chip" href="/admin">Quản trị</a>' if user["role"] == "admin" else ""
        account = (
            f'<a class="nav-chip" href="/account">Tài khoản</a>'
            f'<a class="nav-chip" href="/orders">Đơn hàng</a>'
            f'{admin_link}'
            '<form class="inline-form" method="post" action="/logout"><button class="nav-chip" type="submit">Thoát</button></form>'
        )
    else:
        account = '<a class="icon-btn" href="/login">Đăng nhập</a><a class="icon-btn" href="/register">Đăng ký</a>'
    shop_search = "" if admin else """
    <form class="nav-search" action="/shop" method="get" role="search">
      <input id="nav-search" type="search" name="q" placeholder="Tìm sản phẩm" autocomplete="off" aria-label="Tìm theo tên sản phẩm" aria-autocomplete="list" aria-controls="nav-suggest">
      <div id="nav-suggest" class="suggest" hidden></div>
    </form>"""
    shop_actions = "" if admin else f"""
    <div class="gn-actions">
      <span class="account">{account}</span>
      <a class="icon-btn bag-link" href="/bag" aria-label="Túi hàng, {bag_count} sản phẩm">{BAG_ICON}{count}</a>
    </div>"""
    bot_avatar = BOT_MARK
    if user:
        initial = esc((user["name"] or "B").strip()[:1].upper())
        history = chat_history_markup(user, bot_avatar)
        assistant_body = f"""
    <div id="assistant-log" class="assistant-log" data-initial="{initial}">
      <div class="msg bot">{bot_avatar}<div class="bubble bot">Xin chào {esc(user["name"])}. Mình có thể giúp gì cho bạn?</div></div>
      {history}
    </div>
    <form id="assistant-compose" class="assistant-compose" action="/tro-ly" method="post">
      <button type="button" id="assistant-mic" aria-label="Nói">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z"/><path d="M6 11a6 6 0 0 0 12 0"/><path d="M12 17v4"/></svg>
      </button>
      <input id="assistant-q" name="q" type="text" placeholder="Nhắn trợ lý…" autocomplete="off" aria-label="Nhắn trợ lý">
      <button class="send" type="submit" aria-label="Gửi">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12l16-8-6 16-2-6z"/></svg>
      </button>
    </form>"""
    else:
        assistant_body = f"""
    <div class="assistant-log">
      <div class="msg bot">{bot_avatar}<div class="bubble bot">Đăng nhập để hỏi trợ lý và đặt hàng.</div></div>
      <a class="buy" href="/login">Đăng nhập</a>
    </div>"""
    clear_button = (
        '<button type="button" id="assistant-clear" aria-label="Xóa lịch sử chat">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M7 7l1 13h8l1-13"/></svg>'
        "</button>"
    ) if user else ""
    assistant_pop = f"""
<template id="bot-avatar">{bot_avatar}</template>
<div class="assistant-launch">
  {quick_contact_markup()}
  <div class="assistant-row">
    <span class="assistant-caption" aria-hidden="true">Trợ lý AI</span>
    <span class="assistant-fab-wrap">
      <button class="assistant-fab" id="open-assistant" type="button" aria-label="Mở trợ lý AI, đang trực tuyến" aria-expanded="false" aria-controls="assistant">
        {robot_tag(64)}
      </button>
      <span class="online-dot" aria-hidden="true"></span>
    </span>
  </div>
</div>
<aside id="assistant" class="assistant-pop" hidden aria-labelledby="assistant-title">
  <div class="assistant-bar">
    <div class="assistant-who">{OCTOPUS_MASCOT}<div><h2 id="assistant-title">Octopus Store</h2><p id="assistant-status">Trợ lý AI</p></div></div>
    <div class="assistant-tools">{clear_button}<button type="button" id="assistant-close" aria-label="Đóng">×</button></div>
  </div>
  {assistant_body}
</aside>
<dialog id="assistant-clear-dialog" class="admin-modal admin-modal-confirm">
  <div class="admin-modal-card">
    <h2 id="assistant-clear-title">Xóa lịch sử chat?</h2>
    <p class="note">Các tin trong phiên này sẽ mất. Lời chào vẫn giữ lại.</p>
    <p id="assistant-clear-error" class="assistant-confirm-error" hidden>Chưa xóa được. Thử lại.</p>
    <div class="admin-modal-actions">
      <button type="button" class="quiet" id="assistant-clear-cancel">Hủy</button>
      <button type="button" class="danger" id="assistant-clear-confirm">Xóa</button>
    </div>
  </div>
</dialog>"""
    shop_categories = "" if admin else f"""
  <nav class="sub" aria-label="Nhóm sản phẩm">
    <div class="sub-links">{links}</div>
  </nav>"""
    brand_href = "/admin" if admin else "/"
    header_label = "Quản trị" if admin else "Cửa hàng"
    header_class = "top admin-top" if admin else "top"
    account_link = '<li><a href="/account">Thông tin cá nhân</a></li>' if user else ""
    reasons = store_reasons() if show_reasons and not admin else ""
    footer = "" if admin else f"""
<footer class="footer">
  <nav class="footer-nav" aria-label="Chân trang">
    <div>
      <h2>Cửa hàng</h2>
      <ul><li><a href="/">Trang chủ</a></li>{''.join(f'<li><a href="/c/{esc(key)}">{esc(label)}</a></li>' for key, label in category_pairs())}<li><a href="/gioi-thieu">Giới thiệu</a></li><li><a href="/lien-he">Liên hệ</a></li></ul>
    </div>
    <div>
      <h2>Túi</h2>
      <ul><li><a href="/bag">Xem túi hàng</a></li><li><a href="/shop">Tất cả sản phẩm</a></li>{account_link}</ul>
    </div>
    <div>
      <h2>Giá</h2>
      <ul><li><a href="/shop?sort=price-asc">Giá thấp trước</a></li><li><a href="/shop?sort=price-desc">Giá cao trước</a></li></ul>
    </div>
    <div>
      <h2>Nguồn</h2>
      <ul><li><span>Giá niêm yết tham chiếu tại Hà Nội.</span></li></ul>
    </div>
  </nav>
  <p class="legal">© 2026 Octopus store. All rights reserved.</p>
</footer>"""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{esc(title)}</title>
<link rel="icon" href="/frontend/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/frontend/store.css?v=105">
</head>
<body{home_attr}>
<a class="skip" href="#content">Tới nội dung</a>
<header class="{header_class}">
  <nav class="gn" aria-label="{header_label}">
    <a class="brand" href="{brand_href}" aria-label="Octopus Store"><img class="logo" src="/frontend/logo.png" alt=""><span class="brand-name">Octopus Store</span></a>{shop_search}{shop_actions}
  </nav>{shop_categories}
</header>
{body}
{"" if admin else '''<aside class="compare-dock" id="compare-dock" hidden aria-label="So sánh">
  <p class="compare-note" id="compare-note" hidden></p>
  <div class="compare-slots" id="compare-slots"></div>
  <div class="compare-actions">
    <a class="buy" id="compare-go" href="/so-sanh">Xem cấu hình</a>
    <button type="button" class="quiet" id="compare-clear">Xóa</button>
  </div>
</aside>'''}
{assistant_pop}
{reasons}
{footer}
<script type="module" src="/frontend/agent-robot-avatar/agent-robot-avatar.js?v=105"></script>
<script src="/frontend/store.js?v=105" defer></script>
</body>
</html>"""


CARD_TONES = ("sand", "dusk", "mist", "sky", "lilac", "blush", "cloud", "paper", "white", "ink")


def color_preview_images(conn, product_ids):
    if not product_ids:
        return {}
    rows = conn.execute(
        """
        SELECT DISTINCT ON (product_id, color_name) product_id, color_name, image_url
        FROM product_color_images
        WHERE product_id = ANY(%s) AND coalesce(image_url, '') <> ''
        ORDER BY product_id, color_name,
                 CASE
                   WHEN image_url ILIKE '%%/Kit/%%' OR image_url ILIKE '%%tem-%%' OR image_url ILIKE '%%-glr-%%' THEN 1
                   ELSE 0
                 END,
                 display_order
        """,
        (list(product_ids),),
    ).fetchall()
    grouped = {}
    for product_id, name, url in rows:
        grouped.setdefault(product_id, {})[name] = url
    return grouped


def color_banner_markup(item, colors, thumbs):
    thumbs = thumbs or {}
    usable = [color for color in (colors or []) if thumbs.get(color[0])]
    if not usable:
        image = (
            f'<img src="{esc(item["image"])}" alt="{esc(item["alt"])}" loading="lazy">'
            if item.get("image") else '<div class="missing">Chưa có ảnh</div>'
        )
        return image, ""
    chosen = next((name for name, _, selected in usable if selected), usable[0][0])
    image = (
        f'<img data-color="{esc(chosen)}" src="{esc(cached_cutout_url(thumbs[chosen]))}" '
        f'alt="{esc(chosen)}" loading="lazy">'
    )
    dots = []
    for name, hex_color, _selected in usable:
        style = f"background:{hex_color}" if hex_color else "background:#d2d2d7"
        current = " on" if name == chosen else ""
        dots.append(
            f'<button type="button" class="swatch{current}" data-color-name="{esc(name)}" '
            f'data-cutout="{esc(cached_cutout_url(thumbs[name]))}" style="{style}" '
            f'aria-label="{esc(name)}"></button>'
        )
    swatches = (
        f'<div class="swatches" aria-label="Màu sắc">{"".join(dots)}'
        f'<span class="color-label">{esc(chosen)}</span></div>'
    )
    return image, swatches


def phone_tiles(conn, items, show_brand=True):
    ids = [item["id"] for item in items]
    colors = product_colors(conn, ids)
    thumbs = color_preview_images(conn, ids)
    return "".join(
        tile(item, show_brand, colors.get(item["id"]), thumbs.get(item["id"]))
        for item in items
    )


def tile(item, show_brand=True, colors=None, thumbs=None):
    item = ready_cutout(dict(item))
    tone = CARD_TONES[int(item["id"]) % len(CARD_TONES)]
    image, swatches = color_banner_markup(item, colors, thumbs)
    kicker = item.get("brand") if show_brand and item.get("brand") else category_map().get(item.get("category"), "")
    marker = " data-color-card" if swatches else ""
    return f"""<article class="family-card"{marker}>
      <a class="family-photo tone-{tone}" href="/p/{item["id"]}">{image}</a>
      {swatches}
      <p class="family-kicker">{esc(kicker)}</p>
      <h3>{esc(item.get("title") or item["short"])}</h3>
      <p class="family-price">{esc(money(item["price"]))}</p>
      <div class="ctas">
        <a class="pill solid" href="/p/{item["id"]}">Tìm hiểu thêm</a>
        {buy_link(item["id"], "Mua")}
      </div>
    </article>"""


def buy_link(product_id, label="Mua"):
    return f'<a class="buy" href="/p/{int(product_id)}">{esc(label)}</a>'


def buy_form(product_id, label="Mua"):
    return f"""<form method="post" action="/bag/add">
      <input type="hidden" name="id" value="{int(product_id)}">
      <button class="buy" type="submit">{esc(label)}</button>
    </form>"""


def line_banner(item, eyebrow):
    if not item:
        return ""
    title = item.get("headline") or item.get("title") or ""
    return f"""<div class="line-slide"><a class="line-banner" href="/p/{int(item["id"])}">
      <div>
        <p class="eyebrow">{esc(eyebrow)}</p>
        <h2>{esc(title)}</h2>
        <p>{esc(item.get("line") or "")}</p>
        <span class="more">Tìm hiểu thêm ›</span>
      </div>
      <img src="{esc(item["image"])}" alt="{esc(item["alt"])}">
    </a></div>"""


CATEGORY_BANNERS = {
    "phone": (
        ("%iphone 18 pro%", "%max%", "iPhone 18 Pro", "Pro hơn hẳn.", "iPhone"),
        ("%iphone 18 pro max%", None, "iPhone 18 Pro Max", "Cùng Pro. Màn hình lớn hơn.", "iPhone"),
        ("%iphone duo%", None, "iPhone Duo", "Mở ra một màn hình.", "iPhone"),
        ("%iphone air%", None, "iPhone Air", "Mỏng nhẹ.", "iPhone"),
    ),
    "laptop": (
        ("%macbook air 15 inch m5%35w%", "%24gb%", "MacBook Air 15 inch M5 35W", "Mỏng. Nhẹ. Làm được việc dài.", "MacBook"),
        ("%macbook pro 14 inch m5 16gb%", None, "MacBook Pro 14 inch M5", "Mỏng. Đủ cho một ngày dài.", "MacBook"),
        ("%zenbook duo%", None, "Asus Zenbook DUO", "Hai màn hình.", "Asus"),
        ("%thinkpad x1 carbon%", None, "ThinkPad X1 Carbon", "Mỏng cho công việc.", "Lenovo"),
    ),
    "tablet": (
        ("%ipad pro m5 13%", None, "iPad Pro M5 13 inch", "Màn hình lớn, mang theo được.", "iPad"),
        ("%ipad air m4 13%", None, "iPad Air M4 13 inch", "Mỏng. Màn hình lớn.", "iPad"),
        ("%tab s11 ultra%", None, "Galaxy Tab S11 Ultra", "Màn hình rộng.", "Samsung"),
        ("%xiaomi pad 8 pro%", None, "Xiaomi Pad 8 Pro", "Dòng Pro của Xiaomi.", "Xiaomi"),
    ),
    "headphones": (
        ("%airpods max 2%", None, "AirPods Max 2", "Nghe rõ. Đeo cả ngày.", "AirPods"),
        ("%wh1000xm6%", "%imei%", "Sony WH-1000XM6", "Chụp tai. Nghe rõ.", "Sony"),
        ("%airpods pro 3%", None, "AirPods Pro 3", "Nhét tai. Gọn.", "AirPods"),
        ("%momentum 5%", None, "Sennheiser Momentum 5", "Chụp tai.", "Sennheiser"),
    ),
    "smartwatch": (
        ("%apple watch ultra 4%", None, "Apple Watch Ultra 4", "Đeo cả ngày.", "Apple Watch"),
        ("%galaxy watch ultra 2%", None, "Galaxy Watch Ultra 2", "Nhịp trên cổ tay.", "Samsung"),
        ("%apple watch series 12 gps 46mm%", "%cellular%", "Apple Watch Series 12", "Nhìn đã thấy giờ.", "Apple Watch"),
        ("%apple watch se 3 gps 44mm%", "%cellular%", "Apple Watch SE 3", "Gọn trên cổ tay.", "Apple Watch"),
    ),
}


def line_rail_markup(slides):
    if not slides:
        return ""
    arrows = ""
    if len(slides) > 1:
        arrows = """<div class="line-arrows">
        <button type="button" data-loop-for="line-rail" data-loop-dir="-1" aria-label="Banner trước">‹</button>
        <button type="button" data-loop-for="line-rail" data-loop-dir="1" aria-label="Banner sau">›</button>
      </div>"""
    return f'<div class="line-rail-wrap"><div class="line-rail" id="line-rail" data-loop data-auto>{"".join(slides)}</div>{arrows}</div>'


def category_line_rail(conn, category):
    slides = []
    for include, exclude, headline, line, eyebrow in CATEGORY_BANNERS.get(category, ()):
        item = spotlight(conn, include, exclude, headline, line, category)
        if item:
            slides.append(line_banner(item, eyebrow))
    return line_rail_markup(slides)


STORE_REASONS = (
    {
        "kicker": "Bảo hành",
        "title": "Đọc đúng điều khoản hãng.",
        "body": "Hỏi bảo hành, trợ lý lấy điều khoản của đúng hãng đó.",
        "detail": "Cửa hàng lưu điều khoản bảo hành theo từng hãng. Trợ lý chỉ đọc đoạn của hãng bạn hỏi, không lấy điều khoản hãng khác. Thời hạn tùy hãng và từng loại máy.",
        "href": "",
        "link": "Hỏi trợ lý ›",
        "action": "assistant",
        "image": "/frontend/reasons/warranty.png",
        "alt": "Khiên bảo hành",
    },
    {
        "kicker": "Giao hàng",
        "title": "Giao trên cả nước.",
        "body": "Hẹn buổi nhận khi đặt.",
        "detail": "Ghi địa chỉ lúc chốt. Giao trên cả nước. Buổi nhận sớm nhất là ngày hôm sau: sáng 8–12, chiều 13–17, tối 18–21.",
        "href": "/lien-he",
        "link": "Hỏi cửa hàng ›",
        "action": "",
        "image": "/frontend/reasons/ship.png",
        "alt": "Thùng giao hàng",
    },
    {
        "kicker": "Giá",
        "title": "Giá niêm yết phải chăng.",
        "body": "Tham chiếu tại Hà Nội, ghi trên từng máy.",
        "detail": "Mỗi sản phẩm có giá của chính nó, niêm yết tham chiếu tại Hà Nội. Có thể xếp giá thấp hoặc cao để chọn, và so sánh tối đa 4 máy cùng nhóm.",
        "href": "/shop",
        "link": "Xem sản phẩm ›",
        "action": "",
        "image": "/frontend/reasons/price.png",
        "alt": "Thẻ giá để trống",
    },
    {
        "kicker": "Trợ lý AI",
        "title": "Mua có trợ lý đi cùng.",
        "body": "Nói nhu cầu, trợ lý tìm máy đang có.",
        "detail": "Trợ lý AI nghe nhu cầu và tầm giá, rồi tìm trong kho đang bán. Màu chỉ hỏi khi đặt.",
        "href": "",
        "link": "Mở trợ lý ›",
        "action": "assistant",
        "image": "/frontend/reasons/assistant.png",
        "alt": "Robot trợ lý",
    },
    {
        "kicker": "Thanh toán",
        "title": "Thanh toán gọn lúc chốt.",
        "body": "Trả khi nhận, hoặc chuyển khoản.",
        "detail": "Lúc đặt, chọn thanh toán khi nhận hàng, hoặc chuyển khoản và xem mã trên máy. Hoá đơn gửi tới email nhận hàng.",
        "href": "/bag",
        "link": "Đến túi hàng ›",
        "action": "",
        "image": "/frontend/reasons/pay.png",
        "alt": "Điện thoại và xu",
    },
)


def store_reasons():
    cards = []
    for card in STORE_REASONS:
        cards.append(
            f'<button type="button" class="reason-card" data-reason-open'
            f' data-kicker="{esc(card["kicker"])}" data-title="{esc(card["title"])}"'
            f' data-detail="{esc(card["detail"])}" data-href="{esc(card["href"])}"'
            f' data-link="{esc(card["link"])}" data-action="{esc(card["action"])}">'
            f'<span class="reason-kicker">{esc(card["kicker"])}</span>'
            f'<strong>{esc(card["title"])}</strong>'
            f'<span class="reason-body">{esc(card["body"])}</span>'
            f'<img class="reason-photo" src="{esc(card["image"])}" alt="{esc(card["alt"])}">'
            f'<span class="reason-plus" aria-hidden="true">'
            f'<svg viewBox="0 0 16 16"><path fill="currentColor" d="M7 2h2v12H7zM2 7h12v2H2z"/></svg>'
            f'</span>'
            f'</button>'
        )
    return (
        '<section class="reason-band" aria-label="Vì sao mua tại Octopus Store">'
        '<div class="reason-head"><h2>Vì sao mua tại Octopus Store.</h2>'
        '<div class="reason-tools">'
        '<div class="reason-arrows">'
        '<button type="button" data-reason-dir="-1" aria-label="Thẻ trước">‹</button>'
        '<button type="button" data-reason-dir="1" aria-label="Thẻ sau">›</button>'
        '</div>'
        '<a href="/lien-he">Liên hệ ›</a></div></div>'
        f'<div class="reason-rail" id="reason-rail" data-reason-rail>{"".join(cards)}</div>'
        '</section>'
        '<dialog id="reason-dialog" class="reason-dialog" aria-labelledby="reason-title">'
        '<div class="reason-modal">'
        '<button type="button" class="reason-close" data-reason-close aria-label="Đóng">×</button>'
        '<p class="reason-kicker" id="reason-kicker"></p>'
        '<h2 id="reason-title"></h2>'
        '<p class="reason-copy" id="reason-copy"></p>'
        '<a class="reason-more-link" id="reason-link" href="/lien-he">Tìm hiểu thêm ›</a>'
        '</div></dialog>'
    )



def banner(item, primary=False, tone="ink", brand=""):
    heading = "h1" if primary else "h2"
    line = item.get("line") or LINES.get(item["category"], "")
    name = item.get("headline") or item["title"]
    hero = " home-hero" if brand else ""
    brand_html = (
        f'<p class="hero-brand"><img class="hero-logo" src="/frontend/logo.png" alt="">{esc(brand)}</p>'
        if brand else ""
    )
    return f"""<section class="banner stage-wide tone-{esc(tone)}{hero}">
      {brand_html}
      <div class="banner-photo"><img src="{esc(item["image"])}" alt="{esc(item["alt"])}"></div>
      <div class="banner-lockup">
        <div>
          <p class="eyebrow">{esc(name)}</p>
          <{heading}>{esc(line)}</{heading}>
          <p class="banner-note">{esc(item.get("note") or "")}</p>
        </div>
        <div class="buy-cluster">
          <p>Từ {esc(money(item["price"]))}</p>
          <div class="ctas">{buy_link(item["id"])}<a class="more" href="/p/{item["id"]}">Khám phá</a></div>
        </div>
      </div>
    </section>"""


def split_tile(item, tone):
    line = item.get("line") or ""
    name = item.get("headline") or item["title"]
    return f"""<section class="split tone-{esc(tone)}">
      <h2>{esc(name)}</h2>
      <p class="lead">{esc(line)}</p>
      <p class="fine">{esc(item.get("note") or "")}</p>
      <div class="ctas">
        <a class="pill solid" href="/p/{item["id"]}">Tìm hiểu thêm</a>
        {buy_link(item["id"], "Mua")}
      </div>
      <a class="split-photo" href="/p/{item["id"]}"><img src="{esc(item["image"])}" alt="{esc(item["alt"])}"></a>
    </section>"""


def product_colors(conn, product_ids):
    if not product_ids:
        return {}
    rows = conn.execute(
        """
        SELECT product_id, color_name, hex_color, is_selected
        FROM product_colors
        WHERE product_id = ANY(%s)
        ORDER BY display_order, color_name
        """,
        (list(product_ids),),
    ).fetchall()
    grouped = {}
    for product_id, name, hex_color, selected in rows:
        grouped.setdefault(product_id, []).append((name, hex_color, selected))
    return grouped


def color_galleries(conn, product_id):
    rows = conn.execute(
        """
        SELECT c.color_name, c.hex_color, c.is_selected, i.image_url
        FROM product_colors c
        LEFT JOIN product_color_images i
          ON i.product_id = c.product_id AND i.color_name = c.color_name
        WHERE c.product_id = %s
        ORDER BY c.display_order, i.display_order
        """,
        (product_id,),
    ).fetchall()
    colors = []
    images = {}
    for name, hex_color, selected, image_url in rows:
        if not colors or colors[-1][0] != name:
            colors.append((name, hex_color, selected))
        if image_url:
            images.setdefault(name, []).append(image_url)
    return colors, images


def color_swatches(colors, names=False, clickable=False):
    if not colors:
        return ""
    chosen = next((name for name, _, selected in colors if selected), colors[0][0])
    dots = []
    for name, hex_color, selected in colors:
        style = f"background:{esc(hex_color or '#d2d2d7')}"
        current = " on" if name == chosen else ""
        if clickable:
            dots.append(
                f'<button type="button" class="swatch{current}" data-color-name="{esc(name)}" style="{style}" title="{esc(name)}" aria-label="{esc(name)}"></button>'
            )
        else:
            dots.append(f'<i class="swatch{current}" style="{style}" title="{esc(name)}"></i>')
    label = f'<span class="color-label">{esc(chosen)}</span>' if names else ""
    return f'<div class="swatches" aria-label="Màu sắc">{"".join(dots)}{label}</div>'


def family_card(item, tone, colors=None, thumbs=None):
    name = item.get("headline") or item["title"]
    line = item.get("line") or ""
    image, swatches = color_banner_markup(item, colors, thumbs)
    if not swatches:
        swatches = color_swatches(colors or [])
    marker = " data-color-card" if "data-color-name" in swatches else ""
    return f"""<article class="family-card"{marker}>
      <a class="family-photo tone-{esc(tone)}" href="/p/{item["id"]}">{image}</a>
      {swatches}
      <p class="family-kicker">Mới</p>
      <h3>{esc(name)}</h3>
      <p>{esc(line)}</p>
      <p class="family-price">Từ {esc(money(item["price"]))}</p>
      <div class="ctas">
        <a class="pill solid" href="/p/{item["id"]}">Tìm hiểu thêm</a>
        {buy_link(item["id"], "Mua")}
      </div>
    </article>"""


FAMILY_CACHE = {}


def phone_family(conn, brand_name=None):
    cached = FAMILY_CACHE.get(brand_name)
    if cached and time.time() - cached[0] < 120:
        return cached[1]
    html = build_phone_family(conn, brand_name)
    FAMILY_CACHE[brand_name] = (time.time(), html)
    return html


def build_phone_family(conn, brand_name=None):
    specs = [
        ("%iphone duo%", None, "iPhone Duo", "Màn hình lớn khi mở ra. Gập được.", "sand", "iPhone (Apple)"),
        ("%iphone 18 pro%", "%max%", "iPhone 18 Pro", "Hiệu năng và camera của dòng Pro.", "dusk", "iPhone (Apple)"),
        ("%iphone 18 pro max%", None, "iPhone 18 Pro Max", "Màn hình lớn hơn trong dòng Pro.", "mist", "iPhone (Apple)"),
        ("%iphone air%", None, "iPhone Air", "Mỏng nhẹ.", "sky", "iPhone (Apple)"),
        ("%iphone 17 %", None, "iPhone 17", "Đủ dùng. Bền.", "lilac", "iPhone (Apple)"),
        ("%iphone 17e%", None, "iPhone 17e", "Đủ tính năng. Dễ chọn.", "blush", "iPhone (Apple)"),
        ("%fold8 ultra%", None, "Galaxy Z Fold8 Ultra", "Mở rộng. Mỏng hơn thế hệ trước.", "ink", "Samsung"),
        ("%galaxy s26 ultra%", None, "Galaxy S26 Ultra", "Sáng. Sắc. Một tấm kính.", "paper", "Samsung"),
        ("%fold7%", None, "Galaxy Z Fold7", "Gập lại. Mở thành màn hình.", "mist", "Samsung"),
        ("%xiaomi 17 ultra%", None, "Xiaomi 17 Ultra", "Ống kính lớn. Thân máy gọn.", "cloud", "Xiaomi"),
        ("%find n6%", None, "OPPO Find N6", "Gập được. Màn hình rộng.", "paper", "OPPO"),
        ("%x300 ultra%", None, "vivo X300 Ultra", "Camera cao cấp của vivo.", "sky", "vivo"),
        ("%magic v5%", None, "HONOR Magic V5", "Mỏng khi gập. Rộng khi mở.", "lilac", "HONOR"),
        ("%realme p4 power%", None, "realme P4 Power", "Pin lớn. Giá dễ vào.", "sand", "realme"),
    ]
    cards = []
    for include, exclude, headline, line, tone, brand in specs:
        if brand_name and brand != brand_name:
            continue
        item = spotlight(conn, include, exclude, headline, line)
        if item:
            cards.append((item, tone))
    if brand_name and len(cards) < 4:
        extra, _ = catalog(conn, "phone", brand=brand_name, limit=8)
        seen = {item["id"] for item, _ in cards}
        names = {(item.get("headline") or item["title"]).split(" 5G")[0].lower() for item, _ in cards}
        tones = ["sand", "sky", "lilac", "blush", "mist", "cloud", "paper"]
        for item in extra:
            label = item["title"].split(" 5G")[0].lower()
            if item["id"] in seen or any(name in label or label in name for name in names):
                continue
            names.add(label)
            item["headline"] = item["title"]
            item["line"] = "Đang có tại cửa hàng."
            cards.append((ready_cutout(item), tones[len(cards) % len(tones)]))
            if len(cards) >= 6:
                break
    if not cards:
        return ""
    ids = [item["id"] for item, _ in cards]
    color_map = product_colors(conn, ids)
    thumbs = color_preview_images(conn, ids)
    title = f"Khám phá {brand_name}." if brand_name else "Khám phá dòng sản phẩm."
    side = '<a class="more" href="/c/phone">Tất cả điện thoại</a>' if brand_name else ""
    return f"""<section class="family" aria-label="Dòng điện thoại">
      <div class="family-head">
        <h2>{esc(title)}</h2>
        {side}
      </div>
      <div class="family-row" id="family-row" data-loop>{''.join(family_card(item, tone, color_map.get(item["id"]), thumbs.get(item["id"])) for item, tone in cards)}</div>
      <div class="family-arrows">
        <button type="button" data-loop-for="family-row" data-loop-dir="-1" aria-label="Xem máy phía trước">‹</button>
        <button type="button" data-loop-for="family-row" data-loop-dir="1" aria-label="Xem máy phía sau">›</button>
      </div>
    </section>"""


def render_home(conn, bag_count):
    wide = [
        (spotlight(conn, "%iphone duo%", None, "iPhone Duo", "Mở ra một màn hình."), "ink"),
        (spotlight(conn, "%iphone 18 pro max%", None, "iPhone 18 Pro Max", "Cùng Pro. Màn hình lớn hơn."), "white"),
        (spotlight(conn, "%iphone 18 pro%", "%max%", "iPhone 18 Pro", "Pro hơn hẳn."), "sky"),
        (spotlight(conn, "%fold7%", None, "Galaxy Z Fold7", "Gập lại. Mở thành màn hình."), "paper"),
    ]
    halves = [
        (spotlight(conn, "%apple watch ultra 4%", None, "Apple Watch Ultra", "Đeo cả ngày.", "smartwatch"), "ink"),
        (spotlight(conn, "%macbook pro 14 inch m5 16gb%", None, "MacBook Pro", "Mỏng. Đủ cho một ngày dài.", "laptop"), "white"),
        (spotlight(conn, "%airpods max 2%", None, "AirPods Max", "Nghe rõ. Đeo cả ngày.", "headphones"), "cloud"),
        (spotlight(conn, "%xiaomi 17 ultra%", None, "Xiaomi 17 Ultra", "Ống kính lớn. Thân máy gọn."), "sand"),
        (spotlight(conn, "%galaxy s26 ultra%", None, "Galaxy S26 Ultra", "Sáng. Sắc. Một tấm kính."), "paper"),
        (spotlight(conn, "%ipad pro m5 13%", None, "iPad Pro", "Màn hình lớn. Mang theo được.", "tablet"), "sky"),
        (spotlight(conn, "%galaxy watch ultra 2%", None, "Galaxy Watch Ultra", "Nhịp trên cổ tay.", "smartwatch"), "dusk"),
        (spotlight(conn, "%fold8 ultra%", None, "Galaxy Z Fold8 Ultra", "Mỏng hơn. Mở rộng hơn."), "mist"),
    ]
    wide = [(item, tone) for item, tone in wide if item]
    halves = [(item, tone) for item, tone in halves if item]
    if not wide and not halves:
        empty = '<main id="content" class="page"><h1>Danh mục đang trống.</h1></main>'
        return layout("Octopus Store", empty, bag_count, current="home", home=True)
    chapters = "".join(
        banner(
            item,
            primary=(index == 0),
            tone=tone,
            brand="Octopus Store" if item.get("headline") == "iPhone Duo" else "",
        )
        for index, (item, tone) in enumerate(wide)
    )
    mosaic = "".join(split_tile(item, tone) for item, tone in halves)
    body = f"""<main id="content">
      <div id="nav-sentinel" aria-hidden="true"></div>
      {chapters}
      <section class="mosaic" id="mosaic">{mosaic}</section>
    </main>"""
    return layout("Octopus Store", body, bag_count, current="home", home=True)


def brand_nav(category, brands, selected_slug=None):
    all_current = current_attr(selected_slug is None)
    chips = [f'<a href="/c/{esc(category)}"{all_current}>Tất cả</a>']
    for brand in brands:
        chips.append(
            f'<a href="/c/{esc(category)}/{esc(brand["slug"])}"{current_attr(brand["slug"] == selected_slug)}>'
            f'{esc(brand["name"])} <span>{brand["count"]}</span></a>'
        )
    return f'<nav class="brand-nav" aria-label="Hãng">{"".join(chips)}</nav>'


def render_directory(conn, bag_count):
    blocks = []
    for key, label in category_pairs():
        brands = brand_directory(conn, key)
        chips = "".join(
            f'<a href="/c/{esc(key)}/{esc(brand["slug"])}">{esc(brand["name"])} <span>{brand["count"]}</span></a>'
            for brand in brands
        )
        blocks.append(
            f'<section class="directory"><h2><a href="/c/{esc(key)}">{esc(label)}</a></h2>'
            f'<nav class="brand-nav" aria-label="{esc(label)}">{chips}</nav></section>'
        )
    body = f"""<main id="content" class="page shop-page">
      <div id="nav-sentinel" aria-hidden="true"></div>
      <header class="page-head"><h1>Cửa hàng</h1><p class="note">Chọn danh mục, rồi chọn hãng.</p></header>
      {''.join(blocks)}
    </main>"""
    return layout("Cửa hàng", body, bag_count)


def render_shop(conn, bag_count, category, query, sort, page, brand_slug_value=None, show_all=False):
    brands = brand_directory(conn, category)
    selected = None
    if brand_slug_value:
        selected = next((brand for brand in brands if brand["slug"] == brand_slug_value), None)
        if not selected:
            return None
    page = max(page, 1)
    limit = 24
    chips = brand_nav(category, brands, selected["slug"] if selected else None)
    hero = None
    if not selected and not query:
        if category == "phone":
            hero = spotlight(conn, "%iphone 18 pro%", "%max%", "iPhone 18 Pro", "Pro hơn hẳn.")
        hero = hero or flagship(conn, category)
    family_html = phone_family(conn, selected["name"] if selected else None) if category == "phone" and not query else ""
    line_html = category_line_rail(conn, category) if not selected and not query else ""
    hero_html = ""
    if line_html or family_html:
        hero = None
    if hero and hero.get("image"):
        hero_html = f"""<a class="cat-banner" href="/p/{hero["id"]}">
          <div>
            <p class="eyebrow">{esc(hero["brand"] or category_map()[category])}</p>
            <h2>{esc(hero.get("headline") or hero["title"])}</h2>
            <p>{esc(hero.get("line") or LINES[category])}</p>
            <span class="more">Tìm hiểu thêm</span>
          </div>
          <img src="{esc(hero["image"])}" alt="{esc(hero["alt"])}">
        </a>"""
    if selected:
        items, total = catalog(conn, category, query, sort, (page - 1) * limit, limit, selected["name"])
        title = selected["name"]
        note = f'{category_map()[category]} · {total} sản phẩm'
        grid = phone_tiles(conn, items, False) if category == "phone" else "".join(tile(item, show_brand=False) for item in items)
        grid = grid or '<div class="empty"><p>Không có sản phẩm khớp.</p></div>'
        last = max(1, (total + limit - 1) // limit)
        prev_link = f'<a href="{esc(shop_href(category, query, sort, page - 1, selected["slug"]))}">Trước</a>' if page > 1 else "<span></span>"
        next_link = f'<a href="{esc(shop_href(category, query, sort, page + 1, selected["slug"]))}">Sau</a>' if page < last else "<span></span>"
        listing = f'<div class="product-banners" id="danh-sach">{grid}</div><nav class="pager" aria-label="Trang">{prev_link}<span>{page}/{last}</span>{next_link}</nav>'
    else:
        preview = 24
        if show_all:
            items, total = catalog(conn, category, query, sort if sort != "featured" else "price-desc", (page - 1) * limit, limit)
        else:
            use_shuffle = sort == "featured" and not query
            items, total = catalog(conn, category, query, "shuffle" if use_shuffle else sort, 0, preview)
        title = category_map()[category]
        shown = len(items)
        if show_all:
            note = f"{total} sản phẩm · trang {page}"
            last = max(1, (total + limit - 1) // limit)
            prev_link = f'<a href="{esc(shop_href(category, query, sort, page - 1, show_all=True))}">Trước</a>' if page > 1 else "<span></span>"
            next_link = f'<a href="{esc(shop_href(category, query, sort, page + 1, show_all=True))}">Sau</a>' if page < last else "<span></span>"
            pager = f'<nav class="pager" aria-label="Trang">{prev_link}<span>{page}/{last}</span>{next_link}</nav>'
        else:
            note = f"Xem trước {shown} / {total} sản phẩm" if total > shown else f"{total} sản phẩm"
            pager = ""
            if total > shown:
                href = shop_href(category, query, sort, 1, show_all=True)
                pager = f'<p class="see-all"><a class="pill solid" href="{esc(href)}">Xem tất cả {total} sản phẩm</a></p>'
        grid = phone_tiles(conn, items) if category == "phone" else "".join(tile(item) for item in items)
        grid = grid or '<div class="empty"><p>Không có sản phẩm khớp.</p></div>'
        listing = f'<div class="product-banners" id="danh-sach">{grid}</div>{pager}'
    action = shop_href(category, "", "featured", 1, selected["slug"] if selected else None)
    body = f"""<main id="content" class="page shop-page">
      <div id="nav-sentinel" aria-hidden="true"></div>
      <div class="banner-bleed">{line_html}{hero_html}</div>
      {family_html}
      <div class="catalog-center">
      <header class="page-head"><p class="kicker">{esc(category_map()[category] if selected else "Danh mục")}</p><h1>{esc(title)}</h1><p class="note">{esc(note)}</p></header>
      {chips}
      <form class="tools" method="get" action="{esc(action)}" role="search">
        <input type="search" name="q" value="{esc(query)}" placeholder="Tìm trong {esc(title)}" aria-label="Tìm sản phẩm">
        <input type="hidden" name="sort" value="{esc(sort)}">
        <button type="submit">Tìm</button>
      </form>
      <p class="sort">
        <a href="{esc(shop_href(category, query, "featured", 1, selected["slug"] if selected else None))}"{current_attr(sort == "featured", "true")}>Nổi bật</a>
        <a href="{esc(shop_href(category, query, "price-asc", 1, selected["slug"] if selected else None))}"{current_attr(sort == "price-asc", "true")}>Giá tăng</a>
        <a href="{esc(shop_href(category, query, "price-desc", 1, selected["slug"] if selected else None))}"{current_attr(sort == "price-desc", "true")}>Giá giảm</a>
      </p>
      {listing}
      </div>
    </main>"""
    return layout(f"{title} · {category_map()[category]}" if selected else title, body, bag_count, current=category, show_reasons=True)


def suggest_products(conn, text):
    rows = search_names(conn, text)
    images = covers(conn, [row[0] for row in rows])
    return [
        {
            "id": row[0],
            "name": display_name(row[1]),
            "price": money(row[2]),
            "image": (images.get(row[0]) or [None])[0],
        }
        for row in rows
    ]


def shop_href(category, query, sort, page, brand_slug_value=None, show_all=False):
    if category and brand_slug_value:
        base = f"/c/{category}/{brand_slug_value}"
    elif category:
        base = f"/c/{category}"
    else:
        base = "/shop"
    parts = []
    if query:
        parts.append("q=" + quote(query))
    if show_all:
        parts.append("all=1")
    if sort and sort != "featured":
        parts.append("sort=" + quote(sort))
    if page > 1:
        parts.append(f"page={page}")
    return base + (("?" + "&".join(parts)) if parts else "")


def pick_compare(found):
    kept = []
    category = None
    mixed = False
    for ident, cat in found:
        if category is None:
            category = cat
        elif cat != category:
            mixed = True
            continue
        if ident in kept:
            continue
        if len(kept) >= 4:
            continue
        kept.append(ident)
    return kept, category, mixed


def compare_href(ids):
    clean = [int(ident) for ident in ids]
    if not clean:
        return "/so-sanh"
    return "/so-sanh?" + "&".join(f"id={ident}" for ident in clean)


def compare_markup(products, category_label, note=""):
    if not products:
        return """<main id="content" class="page compare-page"><div id="nav-sentinel"></div>
          <h1>So sánh</h1>
          <p class="note">Chưa chọn máy. Mở một sản phẩm rồi bấm So sánh.</p>
          <p><a class="more" href="/c/phone">Xem điện thoại</a></p>
        </main>"""
    head = []
    for product in products:
        others = [item["id"] for item in products if item["id"] != product["id"]]
        image = f'<img src="{esc(product["image"])}" alt="">' if product.get("image") else ""
        head.append(
            f'<th scope="col"><a class="compare-card" href="/p/{int(product["id"])}"'
            f' data-compare-id="{int(product["id"])}" data-compare-title="{esc(product["title"])}"'
            f' data-compare-price="{esc(product["price_label"])}" data-compare-image="{esc(product.get("image") or "")}">'
            f'{image}<strong>{esc(product["title"])}</strong><span>{esc(product["price_label"])}</span></a>'
            f'<a class="compare-remove" href="{esc(compare_href(others))}">Bỏ</a></th>'
        )
    order = []
    seen = set()
    values = []
    groups_for_name = {}
    for product in products:
        bag = {}
        for group, name, value in product["specs"]:
            if name not in bag:
                bag[name] = value
            if name not in seen:
                seen.add(name)
                order.append(name)
            if group and name not in groups_for_name:
                groups_for_name[name] = group
        values.append(bag)
    rows = []
    last_group = None
    span = len(products) + 1
    blank = "—"
    for name in order:
        group = groups_for_name.get(name, "")
        if group != last_group:
            rows.append(f'<tr class="compare-group"><th colspan="{span}">{esc(group or "Thông số")}</th></tr>')
            last_group = group
        cells = "".join(f"<td>{esc(bag.get(name) or blank)}</td>" for bag in values)
        rows.append(f'<tr><th scope="row">{esc(name)}</th>{cells}</tr>')
    more = ""
    if len(products) < 4 and products[0].get("category"):
        more = f'<p class="note"><a class="more" href="/c/{esc(products[0]["category"])}">Thêm máy cùng nhóm</a></p>'
    status = f'<p class="note">{esc(note)}</p>' if note else ""
    label = category_label or "máy"
    return f"""<main id="content" class="page compare-page" data-compare-category="{esc(products[0].get("category") or "")}" data-compare-label="{esc(label)}">
      <div id="nav-sentinel"></div>
      <h1>So sánh {esc(label.lower())}</h1>
      <p class="note">Cấu hình chi tiết, tối đa 4 máy cùng nhóm.</p>
      {status}{more}
      <div class="compare-wrap"><table class="compare">
        <thead><tr><th></th>{"".join(head)}</tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table></div>
    </main>"""


def load_compare(conn, ids):
    clean = []
    for ident in ids:
        if isinstance(ident, int) or str(ident).isdigit():
            value = int(ident)
            if value not in clean:
                clean.append(value)
        if len(clean) == 8:
            break
    if not clean:
        return [], "", False
    rows = conn.execute(
        """
        SELECT source_product_id, category, name, price_vnd
        FROM products
        WHERE source_product_id = ANY(%s) AND is_live_catalog
        """,
        (clean,),
    ).fetchall()
    by_id = {row[0]: row for row in rows}
    found = [(ident, by_id[ident][1]) for ident in clean if ident in by_id]
    kept, category, mixed = pick_compare(found)
    if not kept:
        return [], "", mixed
    photos = covers(conn, kept)
    spec_rows = conn.execute(
        """
        SELECT product_id, coalesce(group_name, ''), spec_name, spec_value
        FROM product_specifications
        WHERE product_id = ANY(%s)
        ORDER BY display_order, spec_name
        """,
        (kept,),
    ).fetchall()
    grouped = {ident: [] for ident in kept}
    for product_id, group, name, value in spec_rows:
        if not name:
            continue
        grouped[product_id].append((group or "", name, re.sub(r"\s+", " ", value or "").strip()))
    products = []
    for ident in kept:
        row = by_id[ident]
        photo = photos.get(ident)
        products.append({
            "id": ident,
            "category": row[1],
            "title": display_name(row[2]),
            "price_label": money(row[3]),
            "image": photo[0] if photo else "",
            "specs": grouped.get(ident) or [],
        })
    return products, category_map().get(category, ""), mixed


def render_compare(conn, bag_count, ids):
    products, label, mixed = load_compare(conn, ids)
    note = "Chỉ so sánh được máy cùng nhóm." if mixed else ""
    current = products[0]["category"] if products else ""
    return layout("So sánh", compare_markup(products, label, note), bag_count, current=current)


def quick_contact_markup():
    links = (
        ("qc-zalo", "Zalo", '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v6A3.5 3.5 0 0 1 15.5 16H12l-4 3.2V16H8.5A3.5 3.5 0 0 1 5 12.5z"/></svg>'),
        ("qc-facebook", "Facebook", '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M14.5 8H17V5h-2.5A3.5 3.5 0 0 0 11 8.5V11H8.5v3H11v7h3v-7h2.2l.5-3H14v-2.2c0-.4.4-.8.8-.8z"/></svg>'),
        ("qc-call", "Gọi ngay", '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M8 3.5h2.2l1.2 3.2-1.6 1a12 12 0 0 0 5.5 5.5l1-1.6 3.2 1.2V15a2 2 0 0 1-2.2 2A15.5 15.5 0 0 1 6 6.7 2 2 0 0 1 8 3.5z"/></svg>'),
        ("qc-mail", "Email", '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5z"/><path fill="none" stroke="currentColor" stroke-width="1.8" d="M5 7l7 5 7-5"/></svg>'),
    )
    items = "".join(
        f'<a class="qc-link {klass}" href="/lien-he">{icon}<span>{label}</span></a>'
        for klass, label, icon in links
    )
    return f"""<div class="quick-contact">
      <div class="quick-menu" id="quick-menu" hidden>{items}</div>
      <div class="qc-row">
        <span class="assistant-caption" aria-hidden="true">Liên hệ nhanh</span>
        <button type="button" class="qc-toggle" aria-expanded="false" aria-controls="quick-menu" aria-label="Mở liên hệ nhanh">
          <svg class="qc-icon qc-icon-open" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M8 3.5h2.2l1.2 3.2-1.6 1a12 12 0 0 0 5.5 5.5l1-1.6 3.2 1.2V15a2 2 0 0 1-2.2 2A15.5 15.5 0 0 1 6 6.7 2 2 0 0 1 8 3.5z"/></svg>
          <svg class="qc-icon qc-icon-close" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>
    </div>"""


def render_product(conn, bag_count, product_id, notice=""):
    product = load_product(conn, product_id)
    if not product:
        body = """<main id="content" class="page"><div id="nav-sentinel"></div>
          <div class="empty"><h1>Không thấy sản phẩm.</h1><p><a class="more" href="/shop">Về cửa hàng</a></p></div></main>"""
        return layout("Không thấy", body, bag_count), 404
    colors, galleries = color_galleries(conn, product["id"])
    chosen = next((name for name, _, selected in colors if selected), colors[0][0] if colors else "")
    slides = ""
    if galleries:
        for name, urls in galleries.items():
            for src in urls:
                hidden = "" if name == chosen else " hidden"
                slides += f'<figure class="wide-slide" data-color="{esc(name)}"{hidden}><img src="{esc(src)}" alt="{esc(name)}"></figure>'
    if not slides:
        images = product["images"] or [("", product["short"])]
        slides = "".join(
            f'<figure class="wide-slide"><img src="{esc(src)}" alt="{esc(alt or product["short"])}"></figure>'
            for src, alt in images[:12] if src
        ) or '<figure class="wide-slide"><div class="missing">Chưa có ảnh</div></figure>'
    rating = ""
    if product["rating"]:
        rating = f'<p class="note">{esc(product["rating"])} / 5'
        if product["rating_count"]:
            rating += f' · {int(product["rating_count"])} đánh giá'
        rating += "</p>"
    groups = []
    last = None
    for group, name, value in product["specs"]:
        if group != last:
            groups.append(f'<p class="spec-group">{esc(group or "Thông số")}</p>')
            last = group
        groups.append(f'<div class="spec-row"><span>{esc(name)}</span><span>{esc(value)}</span></div>')
    specs = "".join(groups) or '<p class="note">Thông số chi tiết chưa có trong danh mục này.</p>'
    brand_name = product["brand"] or "Khác"
    slug = next((item["slug"] for item in brand_directory(conn, product["category"]) if item["name"] == brand_name), "")
    brand_href = f'/c/{product["category"]}/{slug}' if slug else f'/c/{product["category"]}'
    related = "".join(tile(item, show_brand=False) for item in product["related"])
    photo = product["images"][0][0] if product["images"] else ""
    group_label = category_map().get(product["category"], "máy")
    compare_button = (
        f'<button type="button" class="compare-btn" id="compare-add"'
        f' data-id="{int(product["id"])}" data-category="{esc(product["category"])}"'
        f' data-label="{esc(group_label)}" data-title="{esc(product["title"])}"'
        f' data-price="{esc(money(product["price"]))}" data-image="{esc(photo)}">So sánh</button>'
    )
    body = f"""<main id="content" class="page buy-page">
      <div id="nav-sentinel" aria-hidden="true"></div>
      <article>
        <header class="buy-copy">
          <p class="family-kicker">Mới</p>
          <h1>Mua {esc(product["title"])}</h1>
          {rating}
          <p class="price">Từ {esc(money(product["price"]))}</p>
          <p class="note">{"Hết hàng" if product["stock"] <= 0 else f"Còn {product['stock']} máy"}</p>
          {color_swatches(colors, names=True, clickable=True)}
          <div class="ctas">{buy_form(product["id"], "Thêm vào túi") if product["stock"] > 0 else ""}{compare_button}<a class="more" href="{esc(brand_href)}">Xem {esc(brand_name)}</a></div>
          <p class="note">Giá tham chiếu, chưa gồm phí.</p>
        </header>
        <div class="wide-wrap">
          <div class="wide-gallery" id="wide-gallery">{slides}</div>
          <button class="wide-arrow" type="button" data-wide-dir="1" aria-label="Ảnh tiếp theo">›</button>
        </div>
      </article>
      <section class="specs"><h2>Thông số</h2>{specs}</section>
      {review_section(conn, product["id"], notice)}
      <section class="related"><h2>Cùng hãng</h2><div class="product-banners">{related}</div></section>
    </main>"""
    return layout(product["title"], body, bag_count, current=product["category"]), 200


def pay_fields(values):
    chosen = (values or {}).get("pay_method") or "cod"
    radios = []
    for key, label in (("cod", "Thanh toán khi nhận hàng"), ("qr", "Chuyển khoản, xem mã trên máy")):
        checked = " checked" if key == chosen else ""
        radios.append(
            f'<label><input type="radio" name="pay_method" value="{key}"{checked}>{label}</label>'
        )
    return (
        '<fieldset class="pay-choices"><legend>Thanh toán</legend>'
        + "".join(radios)
        + '<p class="note">Chưa trừ tiền thật. Hoá đơn gửi tới email nhận hàng sau khi đặt.</p></fieldset>'
    )


def review_section(conn, product_id, notice=""):
    rows = conn.execute(
        """
        SELECT author_name, rating_value, review_body, published_at_text
        FROM product_reviews
        WHERE product_id=%s AND approved IS NOT FALSE
        ORDER BY review_index DESC
        LIMIT 5
        """,
        (product_id,),
    ).fetchall()
    items = []
    for author, score, body, when in rows:
        mark = f"{float(score):.0f}/5" if score is not None else ""
        items.append(
            f'<article class="review-card"><p><strong>{esc(author or "Ẩn danh")}</strong>'
            f' <span class="note">{esc(mark)} {esc(when or "")}</span></p><p>{esc(body or "")}</p></article>'
        )
    user = CURRENT_USER.get()
    note = f'<p class="note">{esc(notice)}</p>' if notice else ""
    if user:
        form = f"""<form class="auth-form review-form" method="post" action="/p/{product_id}/review">
          <label>Điểm <select name="rating"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select></label>
          <label>Nhận xét <textarea name="body" required></textarea></label>
          <button class="buy" type="submit">Gửi đánh giá</button>
          <p class="note">Bài viết hiện sau khi quản trị duyệt.</p>
        </form>"""
    else:
        form = '<p class="note"><a href="/login">Đăng nhập</a> để gửi đánh giá.</p>'
    listing = "".join(items) or '<p class="note">Chưa có đánh giá đã duyệt.</p>'
    return f'<section class="specs"><h2>Đánh giá</h2>{note}{listing}{form}</section>'


def local_pay_mark(order_id, total):
    digest = hashlib.sha256(f"form-{order_id}-{total}".encode()).digest()
    cells = []
    for index in range(21 * 21):
        if digest[index % len(digest)] & (1 << (index % 8)):
            cells.append(f'<rect x="{index % 21}" y="{index // 21}" width="1" height="1"/>')
    return (
        '<svg class="pay-mark" viewBox="0 0 21 21" role="img" aria-label="Mã xem trên máy này">'
        + "".join(cells)
        + "</svg>"
    )


def render_receipt(conn, user, order_id, notice=""):
    row = conn.execute(
        """
        SELECT id, user_id, total_vnd, status, ship_name, ship_email, ship_phone, ship_address,
               deliver_on, deliver_slot, coalesce(pay_method, 'cod'), created_at,
               invoice_sent_at, invoice_error, paid_at, payment_email_sent_at, payment_email_error
        FROM orders WHERE id=%s
        """,
        (order_id,),
    ).fetchone()
    if not row or not user or (row[1] != user["id"] and user.get("role") != "admin"):
        return None
    items = conn.execute(
        "SELECT name, qty, unit_price FROM order_items WHERE order_id=%s ORDER BY id",
        (order_id,),
    ).fetchall()
    lines = "".join(
        f'<li><span>{esc(short_name(name))}</span><span>× {qty}</span><span>{esc(money(int(price or 0) * qty))}</span></li>'
        for name, qty, price in items
    )
    state = ORDER_LABEL.get(row[3], row[3])
    when = delivery_when(row[8], row[9])
    pay = "Thanh toán khi nhận hàng" if row[10] != "qr" else "Chuyển khoản trên máy này"
    if row[10] != "qr":
        mark = ""
    elif row[14]:
        mark = f'<p class="note">{esc(payment.paid_note({"payment_email_sent_at": row[15], "payment_email_error": row[16] or ""}))}</p>'
    elif payment.bank_ready():
        ref = payment.transfer_reference(row[0])
        mark = (
            f'<img class="pay-qr" src="/orders/{int(row[0])}/pay-qr" alt="Mã chuyển khoản">'
            f'<p class="note">Nội dung chuyển khoản: {esc(ref)}. Đúng số tiền trên phiếu.</p>'
            f'<form method="post" action="/orders/{int(row[0])}/pay-check">'
            f'<button class="buy" type="submit">Đối soát chuyển khoản</button></form>'
        )
    else:
        mark = local_pay_mark(row[0], row[2])
    extra = f'<p class="note">{esc(notice)}</p>' if notice else ""
    info = f"""<div class="receipt-info">
          <h1>Phiếu đơn #{row[0]}</h1>
          <p class="note">{esc(state)} · {esc(pay)}</p>
          {extra}
          <ul class="order-card receipt-lines">{lines}</ul>
          <p class="total"><span>Tổng</span><strong>{esc(money(row[2]))}</strong></p>
          <p>{esc(row[4] or "")}<br>{esc(row[6] or "")}<br>{esc(row[7] or "")}</p>
          <p class="note">Nhận {esc(when)}</p>
          <p class="note">{esc(invoice.invoice_status_note(row[12], row[13]))}</p>
          <p><a class="buy" href="/orders">Về đơn hàng</a></p>
        </div>"""
    if row[10] == "qr" and not row[14]:
        sheet = f'<div class="order-sheet receipt-pay"><div class="receipt-grid"><aside class="pay-pane">{mark}</aside>{info}</div></div>'
    else:
        sheet = f'<div class="order-sheet">{info}{mark}</div>'
    body = f'<main id="content" class="page"><div id="nav-sentinel"></div>{sheet}</main>'
    return layout(f"Đơn #{row[0]}", body, 0)


def about_feature(item, tone):
    if not item:
        return ""
    return (
        f'<a class="about-feature tone-{esc(tone)}" href="/p/{int(item["id"])}">'
        f'<p class="eyebrow">{esc(item["headline"])}</p>'
        f'<h2>{esc(item.get("line") or item["headline"])}</h2>'
        f'<p class="about-feature-price">Từ {esc(money(item["price"]))}</p>'
        f'<img src="{esc(item["image"])}" alt="{esc(item["alt"])}">'
        f"</a>"
    )


def about_groups(conn):
    groups = []
    for key, label in category_pairs():
        picks = []
        for include, exclude, headline, line, _eyebrow in CATEGORY_BANNERS.get(key, ()):
            item = spotlight(conn, include, exclude, headline, line, key)
            if item:
                picks.append(item)
        groups.append((key, label, picks))
    return groups


def render_about(bag_count=0):
    lead = about_feature(None, "ink")
    mosaic = ""
    groups_html = "".join(
        f'<a class="about-cat" href="/c/{esc(key)}">{esc(label)}</a>'
        for key, label in category_pairs()
    )
    try:
        with connect() as conn:
            duo = spotlight(conn, "%iphone duo%", None, "iPhone Duo", "Mở ra một màn hình.", "phone")
            tiles = (
                spotlight(conn, "%iphone 18 pro%", "%max%", "iPhone 18 Pro", "Pro hơn hẳn.", "phone"),
                spotlight(conn, "%macbook air 15 inch m5%35w%", "%24gb%", "MacBook Air 15 inch M5", "Mỏng. Nhẹ. Làm được việc dài.", "laptop"),
                spotlight(conn, "%ipad pro m5 13%", None, "iPad Pro M5 13 inch", "Màn hình lớn, mang theo được.", "tablet"),
                spotlight(conn, "%airpods max 2%", None, "AirPods Max 2", "Nghe rõ. Đeo cả ngày.", "headphones"),
            )
            lead = about_feature(duo, "ink")
            mosaic = "".join(
                about_feature(item, tone)
                for item, tone in zip(tiles, ("paper", "white", "sky", "sand"))
                if item
            )
            blocks = []
            for key, label, picks in about_groups(conn):
                if picks:
                    cards = "".join(
                        f'<a class="about-pick" href="/p/{int(item["id"])}">'
                        f'<img src="{esc(item["image"])}" alt="{esc(item["alt"])}">'
                        f"<strong>{esc(item['headline'])}</strong>"
                        f"<span>{esc(money(item['price']))}</span></a>"
                        for item in picks
                    )
                else:
                    cards = f'<a class="about-cat" href="/c/{esc(key)}">{esc(label)}</a>'
                blocks.append(
                    f'<section class="about-group">'
                    f'<div class="about-group-head"><h3>{esc(label)}</h3>'
                    f'<a href="/c/{esc(key)}">Xem tất cả</a></div>'
                    f'<div class="about-picks">{cards}</div></section>'
                )
            groups_html = "".join(blocks)
    except Exception:
        pass
    mosaic_html = f'<div class="about-mosaic">{mosaic}</div>' if mosaic else ""
    body = f"""<main id="content" class="about-page">
      <div id="nav-sentinel"></div>
      <section class="about-hero">
        <p class="eyebrow">Giới thiệu</p>
        <h1>Octopus Store</h1>
        <p class="about-lead">Cửa hàng điện thoại, laptop, máy tính bảng, tai nghe và đồng hồ. Ảnh dưới đây là máy đang có trong kho.</p>
        <p class="note">Giá niêm yết tham chiếu tại Hà Nội.</p>
        <div class="ctas">
          <a class="buy" href="/c/phone">Xem điện thoại</a>
          <a class="more" href="/lien-he">Liên hệ cửa hàng</a>
        </div>
      </section>
      {lead}
      {mosaic_html}
      <section class="about-block">
        <p class="eyebrow">Cửa hàng có gì</p>
        <h2>Các nhóm máy đang bán.</h2>
        <p class="about-copy">Mỗi nhóm lấy vài máy đặc trưng đang còn hàng. Bấm vào máy để xem cấu hình và giá, hoặc mở cả nhóm.</p>
        {groups_html}
      </section>
      <section class="about-block">
        <p class="eyebrow">Định hướng</p>
        <h2>Bốn điều cửa hàng giữ.</h2>
        <div class="about-pillars">
          <article>
            <h3>Sản phẩm</h3>
            <p>Điện thoại, laptop, máy tính bảng, tai nghe và đồng hồ. Mỗi nhóm có trang riêng, chỉ hiện máy đang bán.</p>
          </article>
          <article>
            <h3>Giá</h3>
            <p>Giá niêm yết tham chiếu tại Hà Nội, ghi trên từng sản phẩm.</p>
          </article>
          <article>
            <h3>Đặt hàng</h3>
            <p>Thêm máy vào túi. Khi chốt, cửa hàng hỏi tên, email, số điện thoại, địa chỉ, buổi nhận và cách thanh toán. Buổi nhận sớm nhất là ngày hôm sau.</p>
          </article>
          <article>
            <h3>Trợ lý AI</h3>
            <p>Nút Trợ lý AI ở góc màn hình. Nói nhu cầu, trợ lý tìm trong kho đang có.</p>
          </article>
        </div>
      </section>
      <section class="about-cta">
        <h2>Cần hỏi cửa hàng?</h2>
        <p>Gửi lời nhắn. Quản trị đọc trong mục hỗ&nbsp;trợ.</p>
        <a class="buy" href="/lien-he">Liên hệ</a>
      </section>
    </main>"""
    return layout("Giới thiệu", body, bag_count, current="about")


def render_contact(user=None, values=None, message="", error="", bag_count=0):
    values = values or {}
    if user and not values:
        values = {"name": user.get("name") or "", "email": user.get("email") or "", "phone": user.get("phone") or "", "body": ""}
    status = message or error
    status_class = "contact-status is-error" if error else "contact-status"
    note = f'<p class="{status_class}" role="status">{esc(status)}</p>' if status else ""
    form = (
        f'<form class="auth-form" method="post" action="/lien-he">'
        f'<div class="contact-fields">'
        f'<label>Tên <input name="name" value="{esc(values.get("name") or "")}" required autocomplete="name"></label>'
        f'<label>Email <input name="email" type="email" value="{esc(values.get("email") or "")}" required autocomplete="email"></label>'
        f'</div>'
        f'<label>Số điện thoại <input name="phone" inputmode="tel" value="{esc(values.get("phone") or "")}" placeholder="10 hoặc 11 số, bắt đầu bằng 0" autocomplete="tel"></label>'
        f'<label>Nội dung <textarea name="body" required placeholder="Máy bạn muốn hỏi, hoặc việc cần cửa hàng xem.">{esc(values.get("body") or "")}</textarea></label>'
        f'<button class="buy" type="submit">Gửi liên hệ</button>'
        f'</form>'
    )
    body = f"""<main id="content" class="contact-page">
      <div id="nav-sentinel"></div>
      <section class="contact-hero">
        <p class="eyebrow">Liên hệ</p>
        <h1>Gửi lời nhắn cho cửa hàng.</h1>
        <p class="contact-lead">Form trên trang này là cách gửi tin.<br>Quản trị đọc trong mục Hỗ trợ.</p>
      </section>
      <section class="contact-grid">
        <div class="contact-info">
          <h2>Thông tin liên hệ</h2>
          <p class="contact-copy">Cửa hàng nhận lời nhắn qua form trên trang này.</p>
          <div class="contact-cards">
            <article class="contact-card">
              <span>Kênh nhận tin</span>
              <strong>Form trên trang này</strong>
              <p>Quản trị đọc trong mục Hỗ trợ.</p>
            </article>
            <article class="contact-card">
              <span>Hỏi máy đang có</span>
              <strong>Trợ lý AI</strong>
              <p>Nút Trợ lý AI ở góc màn hình. Nói nhu cầu, trợ lý tìm trong kho đang bán.</p>
            </article>
            <article class="contact-card">
              <span>Giá</span>
              <strong>Giá niêm yết tham chiếu tại Hà Nội.</strong>
              <p>Giá ghi trên từng sản phẩm.</p>
            </article>
          </div>
        </div>
        <div class="contact-form-card">
          <h2>Gửi yêu cầu</h2>
          <p class="contact-copy">Điền tên, email và nội dung. Số điện thoại để trống cũng gửi được.</p>
          {note}
          {form}
        </div>
      </section>
      <section class="contact-steps">
        <p class="eyebrow">Cách một lời nhắn đi</p>
        <h2>Ba bước.</h2>
        <ol class="contact-step-list">
          <li><strong>Điền form</strong><span>Tên, email, số điện thoại nếu có, và việc cần hỏi.</span></li>
          <li><strong>Gửi</strong><span>Yêu cầu vào mục Hỗ trợ để quản trị đọc.</span></li>
          <li><strong>Hỏi máy</strong><span>Trợ lý AI tìm trong kho đang bán. Màu chỉ hỏi khi đặt.</span></li>
        </ol>
      </section>
      <section class="contact-faq">
        <p class="eyebrow">Hỗ trợ</p>
        <h2>Câu hay gặp.</h2>
        <div class="contact-faq-list">
          <details>
            <summary>Số điện thoại có phải điền không?</summary>
            <p>Để trống cũng gửi được. Khi điền, dùng 10 hoặc 11 số, bắt đầu bằng 0.</p>
          </details>
          <details>
            <summary>Quản trị xem tin ở đâu?</summary>
            <p>Trong mục Hỗ trợ của trang quản trị.</p>
          </details>
          <details>
            <summary>Muốn hỏi máy đang bán thì làm gì?</summary>
            <p>Mở Trợ lý AI và nói nhu cầu. Cửa hàng hỏi màu khi đặt.</p>
          </details>
        </div>
      </section>
    </main>"""
    return layout("Liên hệ", body, bag_count, current="contact")


def save_support(conn, user, fields):
    name = (fields.get("name") or [""])[0].strip()
    email = (fields.get("email") or [""])[0].strip().lower()
    phone = clean_phone((fields.get("phone") or [""])[0])
    body = re.sub(r"\s+", " ", (fields.get("body") or [""])[0]).strip()
    posted = {"name": name, "email": email, "phone": phone, "body": body}
    if len(name) < 2:
        return posted, "Tên cần ít nhất 2 ký tự."
    if "@" not in email or "." not in email.split("@")[-1]:
        return posted, "Email chưa đúng."
    if phone and not re.fullmatch(r"0\d{9,10}", phone):
        return posted, "Số điện thoại cần 10 hoặc 11 số, bắt đầu bằng 0."
    if len(body) < 8:
        return posted, "Nội dung cần ít nhất 8 ký tự."
    conn.execute(
        "INSERT INTO support_requests(user_id, name, email, phone, body) VALUES (%s,%s,%s,%s,%s)",
        (user["id"] if user else None, name, email, phone or None, body[:2000]),
    )
    return posted, ""


def save_customer_review(conn, user, product_id, fields):
    body = re.sub(r"\s+", " ", (fields.get("body") or [""])[0]).strip()
    raw = (fields.get("rating") or ["5"])[0]
    if len(body) < 8:
        return "Nội dung cần ít nhất 8 ký tự."
    if raw not in {"1", "2", "3", "4", "5"}:
        return "Chọn điểm từ 1 đến 5."
    exists = conn.execute(
        "SELECT 1 FROM products WHERE source_product_id=%s AND is_live_catalog",
        (product_id,),
    ).fetchone()
    if not exists:
        return "Không thấy sản phẩm."
    index = conn.execute(
        "SELECT coalesce(max(review_index), -1) + 1 FROM product_reviews WHERE product_id=%s",
        (product_id,),
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO product_reviews(product_id, review_index, author_name, rating_value, review_body, published_at_text, approved)
        VALUES (%s,%s,%s,%s,%s,'Chờ duyệt',false)
        """,
        (product_id, index, user["name"], int(raw), body[:2000]),
    )
    return ""


def render_admin_support(conn):
    rows = conn.execute(
        """
        SELECT id, name, email, phone, body, created_at
        FROM support_requests
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()
    items = []
    for row in rows:
        stamp = row[5].strftime("%d.%m.%Y %H:%M") if row[5] else ""
        items.append(
            f'<tr><td>#{row[0]}</td><td>{esc(row[1])}<p class="note">{esc(row[2])}'
            f'{(" · " + esc(row[3])) if row[3] else ""}</p></td>'
            f'<td>{esc(row[4])}</td><td>{esc(stamp)}</td></tr>'
        )
    body_rows = "".join(items) or '<tr><td colspan="4">Chưa có yêu cầu.</td></tr>'
    inner = f"""<p class="note">{len(rows)} yêu cầu gần nhất</p>
    <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>Mã</th><th>Người gửi</th><th>Nội dung</th><th>Lúc</th></tr></thead>
    <tbody>{body_rows}</tbody></table></div>"""
    return admin_page("Hỗ trợ", "Hỗ trợ", inner, "support")


def render_bag(conn, bag):
    if not bag:
        body = """<main id="content" class="page"><div id="nav-sentinel"></div>
          <div class="empty"><h1>Túi đang trống.</h1><p>Chọn một máy ở cửa hàng, rồi thêm vào túi trên máy này.</p>
          <p><a class="more" href="/shop">Tới cửa hàng</a></p></div></main>"""
        return layout("Túi hàng", body, 0)
    ids = [ident for ident, _ in bag]
    rows = conn.execute(
        """
        SELECT source_product_id, name, brand, price_vnd
        FROM products WHERE source_product_id = ANY(%s)
        """,
        (ids,),
    ).fetchall()
    found = {row[0]: row for row in rows}
    lines = []
    total = 0
    count = 0
    for ident, qty in bag:
        row = found.get(ident)
        if not row:
            continue
        images = product_images(conn, ident)
        src = images[0][0] if images else ""
        price = row[3] or 0
        total += price * qty
        count += qty
        image = f'<img src="{esc(src)}" alt="">' if src else ""
        lines.append(f"""<div class="bag-row">
          {image}
          <div><a href="/p/{ident}">{esc(display_name(row[1]))}</a><p class="note">{esc(money(price))}</p></div>
          <form class="qty" method="post" action="/bag/set">
            <input type="hidden" name="id" value="{ident}">
            <label>Số lượng <input name="qty" type="number" min="0" max="5" value="{qty}"></label>
            <button class="quiet" type="submit">Cập nhật</button>
          </form>
        </div>""")
    body = f"""<main id="content" class="page">
      <div id="nav-sentinel" aria-hidden="true"></div>
      <h1>Túi hàng</h1>
      {''.join(lines)}
      <p class="total"><span>Tạm tính</span><strong>{esc(money(total))}</strong></p>
      <p><a class="buy" href="/checkout">Đặt hàng</a></p>
      <p class="note">Cần đăng nhập trước khi đặt. Đơn được lưu trên máy này, chưa thanh toán thật.</p>
    </main>"""
    return layout("Túi hàng", body, count)


COMMERCE_SQL = """
CREATE TABLE IF NOT EXISTS app_users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app_sessions (
    token TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_users(id),
    status TEXT NOT NULL DEFAULT 'placed',
    total_vnd BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app_categories (
    slug TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT,
    name TEXT NOT NULL,
    unit_price BIGINT NOT NULL,
    qty INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS app_chat_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""
COMMERCE_READY = False


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"


def check_password(password, stored):
    salt, digest = stored.split("$", 1)
    return hash_password(password, salt).split("$", 1)[1] == digest


def ensure_commerce(conn):
    global COMMERCE_READY
    if COMMERCE_READY:
        return
    conn.execute(COMMERCE_SQL)
    exists = conn.execute("SELECT 1 FROM app_users WHERE role='admin' LIMIT 1").fetchone()
    admin_email = "admin@form.local" if DEMO_MODE else os.environ.get("APP_ADMIN_EMAIL", "").strip().lower()
    admin_password = "form-admin" if DEMO_MODE else os.environ.get("APP_ADMIN_PASSWORD", "")
    if not exists and admin_email and admin_password:
        conn.execute(
            "INSERT INTO app_users(email, name, password_hash, role) VALUES (%s,%s,%s,'admin')",
            (admin_email, "Quản trị", hash_password(admin_password)),
        )
    customer = conn.execute("SELECT 1 FROM app_users WHERE email='khach@form.local'").fetchone() if DEMO_MODE else None
    if DEMO_MODE and not customer:
        conn.execute(
            "INSERT INTO app_users(email, name, password_hash, role) VALUES (%s,%s,%s,'customer')",
            ("khach@form.local", "Khách", hash_password("form-khach")),
        )
    for index, (slug, label) in enumerate(CATEGORIES):
        conn.execute(
            "INSERT INTO app_categories(slug, label, sort_order) VALUES (%s,%s,%s) ON CONFLICT (slug) DO NOTHING",
            (slug, label, index),
        )
    sync_category_check(conn)
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ship_name TEXT")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ship_email TEXT")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ship_phone TEXT")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS ship_address TEXT")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS deliver_on DATE")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS deliver_slot TEXT")
    conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INTEGER")
    pending = conn.execute("SELECT count(*) FROM products WHERE is_live_catalog AND stock IS NULL").fetchone()[0]
    if pending:
        conn.execute(
            """
            UPDATE products
            SET stock = 50 + floor(random() * 251)::int
            WHERE is_live_catalog AND stock IS NULL
            """
        )
    conn.execute("UPDATE products SET stock = 0 WHERE stock IS NULL")
    conn.execute("ALTER TABLE products ALTER COLUMN stock SET DEFAULT 0")
    conn.execute("ALTER TABLE products ALTER COLUMN stock SET NOT NULL")
    conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS phone TEXT")
    conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS address TEXT")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pay_method TEXT DEFAULT 'cod'")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_sent_at TIMESTAMPTZ")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_error TEXT")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_email_sent_at TIMESTAMPTZ")
    conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_email_error TEXT")
    conn.execute("ALTER TABLE product_reviews ADD COLUMN IF NOT EXISTS approved BOOLEAN DEFAULT true")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_requests (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    conn.execute("ALTER TABLE app_chat_messages ADD COLUMN IF NOT EXISTS session_token TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS app_chat_messages_user_idx ON app_chat_messages(user_id, id DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS app_chat_messages_session_idx ON app_chat_messages(user_id, session_token, id DESC)")
    from rag.documents import ensure_table
    ensure_table(conn)
    from agent.ordersql import ensure_order_sql
    ensure_order_sql(conn)
    COMMERCE_READY = True


def bind_categories(conn):
    rows = conn.execute("SELECT slug, label FROM app_categories ORDER BY sort_order, slug").fetchall()
    LIVE_CATEGORIES.set(tuple((row[0], row[1]) for row in rows) or CATEGORIES)


def sync_category_check(conn):
    slugs = [
        row[0] for row in conn.execute("SELECT slug FROM app_categories ORDER BY sort_order, slug").fetchall()
        if re.fullmatch(r"[a-z0-9-]{2,32}", row[0] or "")
    ]
    if not slugs:
        return
    quoted = ",".join("'" + slug + "'" for slug in slugs)
    conn.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_category_check")
    conn.execute(f"ALTER TABLE products ADD CONSTRAINT products_category_check CHECK (category IN ({quoted}))")


def session_token_from_cookie(header):
    """Read the session token directly. SimpleCookie drops every cookie when one value is odd."""
    match = re.search(r"(?:^|;\s*)session=([^;\s]+)", header or "")
    if not match:
        return ""
    return match.group(1).strip().strip('"')


def user_from_cookie(conn, header):
    token = session_token_from_cookie(header)
    if not token:
        return None
    row = conn.execute(
        """
        SELECT u.id, u.email, u.name, u.role, s.token, u.phone, u.address
        FROM app_sessions s JOIN app_users u ON u.id=s.user_id
        WHERE s.token=%s
        """,
        (token,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "email": row[1], "name": row[2], "role": row[3], "token": row[4],
        "phone": row[5] or "", "address": row[6] or "",
    }


def save_chat(conn, user_id, session_token, role, body):
    text = (body or "").strip()
    if not text or not user_id or not session_token:
        return
    conn.execute(
        "INSERT INTO app_chat_messages(user_id, session_token, role, body) VALUES (%s,%s,%s,%s)",
        (user_id, session_token, role, text[:24000]),
    )
    conn.execute(
        """
        DELETE FROM app_chat_messages
        WHERE user_id=%s AND session_token=%s AND id < (
            SELECT id FROM app_chat_messages
            WHERE user_id=%s AND session_token=%s
            ORDER BY id DESC
            OFFSET 59
            LIMIT 1
        )
        """,
        (user_id, session_token, user_id, session_token),
    )


def load_chat(conn, user_id, session_token, limit=40):
    if not session_token:
        return []
    rows = conn.execute(
        """
        SELECT role, body FROM app_chat_messages
        WHERE user_id=%s AND session_token=%s
        ORDER BY id DESC
        LIMIT %s
        """,
        (user_id, session_token, limit),
    ).fetchall()
    rows.reverse()
    return rows


def clear_chat(conn, user_id, session_token):
    if not user_id or not session_token:
        return
    conn.execute(
        "DELETE FROM app_chat_messages WHERE user_id=%s AND session_token=%s",
        (user_id, session_token),
    )
    TRACES.pop(session_token, None)


TRACES = {}
TRACE_LIMIT = 12


def remember_trace(token, turn):
    if not token or not turn:
        return
    turn = dict(turn)
    turn.setdefault("at", datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M:%S"))
    end = 0.0
    for step in turn.get("steps") or []:
        try:
            end = max(end, float(step.get("t1") or 0))
        except (TypeError, ValueError):
            continue
    turn["latency_ms"] = end
    turns = TRACES.setdefault(token, [])
    turns.append(turn)
    del turns[:-TRACE_LIMIT]


def trace_revision(token):
    turns = TRACES.get(token or "") or []
    parts = [str(len(turns))]
    for turn in turns:
        try:
            latency = float(turn.get("latency_ms") or 0)
        except (TypeError, ValueError):
            latency = 0
        parts.append(str(len(turn.get("steps") or [])))
        parts.append(str(round(latency, 1)))
    return ":".join(parts)


def _trace_pre(value):
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return f"<pre>{esc(text)}</pre>"


def _fmt_latency(ms):
    try:
        value = float(ms)
    except (TypeError, ValueError):
        value = 0
    if value < 0:
        value = 0
    if value < 1000:
        shown = round(value, 1)
        if shown.is_integer():
            shown = int(shown)
        return f"{shown} ms"
    return f"{value / 1000:.2f} s"


def _trace_query_int(query, key, default):
    try:
        return int((query.get(key) or [str(default)])[0])
    except (TypeError, ValueError):
        return default


def _trace_observations(turn):
    """One customer turn is one trace. Steps become SPAN, GENERATION, and TOOL rows."""
    steps = list(turn.get("steps") or [])
    rows = []
    next_id = 0

    def add(**fields):
        nonlocal next_id
        fields["id"] = next_id
        next_id += 1
        rows.append(fields)
        return fields["id"]

    end = 0.0
    for step in steps:
        try:
            end = max(end, float(step.get("t1") or 0))
        except (TypeError, ValueError):
            continue
    try:
        end = max(end, float(turn.get("latency_ms") or 0))
    except (TypeError, ValueError):
        pass
    origin = turn.get("text_from") or ""
    if origin == "model":
        origin_line = "Câu trên chat là câu model viết."
    elif origin == "tool_note":
        origin_line = "Model không viết câu cuối. Trang trợ lý dùng ghi chú của tool."
    else:
        origin_line = "Câu trên chat do đường offline viết."
    add(
        depth=0,
        type="SPAN",
        name="Lượt hỏi",
        t0=0.0,
        t1=end,
        note=origin_line,
        blocks=[
            ("Input", {"question": turn.get("question") or ""}),
            ("Output", {"answer": turn.get("answer") or "", "text_from": origin}),
        ],
    )
    for step in steps:
        try:
            t0 = float(step.get("t0") or 0)
            t1 = float(step.get("t1") if step.get("t1") is not None else t0)
        except (TypeError, ValueError):
            t0, t1 = 0.0, 0.0
        if t1 < t0:
            t1 = t0
        kind = step.get("kind") or ""
        obs_type = step.get("type") or {
            "slots": "SPAN", "model": "GENERATION", "tool": "TOOL", "fallback": "SPAN",
        }.get(kind, "SPAN")
        if kind == "model":
            calls = step.get("calls") or []
            output = {"text": step.get("text") or ""}
            if calls:
                output["tool_calls"] = calls
            add(
                depth=1,
                type="GENERATION",
                name=step.get("name") or "model",
                t0=t0,
                t1=t1,
                note="Một lượt gọi model. Model chọn tool hoặc viết câu trả lời.",
                blocks=[
                    ("Input", step.get("input") if isinstance(step.get("input"), dict) else {"text": step.get("text") or ""}),
                    ("Output", output),
                ],
            )
            continue
        if kind == "tool":
            sent = step.get("sent") or {}
            ran = step.get("ran") or {}
            note = step.get("note") or ""
            if sent != ran and not note:
                note = "Python đã điền hoặc sửa tham số trước khi chạy."
            blocks = [("Input · model gửi", sent), ("Input · Python chạy", ran), ("Output", step.get("result") or {})]
            add(
                depth=2,
                type="TOOL",
                name=step.get("name") or "tool",
                t0=t0,
                t1=t1,
                note=note or "Python chạy tool và trả kết quả cho model.",
                blocks=blocks,
            )
            continue
        if kind == "slots":
            add(
                depth=1,
                type="SPAN",
                name=step.get("name") or "Đọc câu hỏi",
                t0=t0,
                t1=t1,
                note="Python đọc câu này và câu trước. Chưa gọi model.",
                blocks=[
                    ("Input", step.get("input") if isinstance(step.get("input"), dict) else {"question": turn.get("question") or ""}),
                    ("Output", step.get("arguments") or {}),
                ],
            )
            continue
        add(
            depth=1,
            type=obs_type if obs_type in {"SPAN", "GENERATION", "TOOL"} else "SPAN",
            name=step.get("name") or "Đường offline",
            t0=t0,
            t1=t1,
            note=step.get("text") or "Không gọi được model. Đây là đường offline.",
            blocks=[
                ("Input", {"text": step.get("text") or ""}),
                ("Output", {"tool": step.get("tool") or "", "arguments": step.get("arguments") or {}}),
            ],
        )
    return rows


def _trace_bar(t0, t1, total):
    if total <= 0:
        return "left:0%;width:8px"
    left = max(0.0, min(100.0, (t0 / total) * 100))
    width = max(1.5, (t1 - t0) / total * 100)
    width = min(width, 100 - left)
    return f"left:{left:.2f}%;width:{width:.2f}%"


def render_trace(user, query=None, bag_count=0):
    query = query or {}
    turns = list(TRACES.get(user.get("token") or "", []))
    view = (query.get("view") or ["timeline"])[0]
    if view not in ("tree", "timeline"):
        view = "timeline"
    selected = _trace_query_int(query, "t", len(turns) or 1)
    if turns:
        selected = min(max(selected, 1), len(turns))
    else:
        selected = 0
    turn = turns[selected - 1] if selected else None
    rows = _trace_observations(turn) if turn else []
    picked = _trace_query_int(query, "o", 0)
    if rows and not any(row["id"] == picked for row in rows):
        picked = 0
    focus = next((row for row in rows if row["id"] == picked), None)

    def href(trace_index, obs_id, mode):
        return f"/admin/tracing?t={trace_index}&o={obs_id}&view={mode}"

    session_links = []
    for index, item in enumerate(turns, start=1):
        question = item.get("question") or "(không có chữ)"
        source = "Model" if item.get("source") == "model" else "Offline"
        count = len(item.get("steps") or [])
        meta = f"{source} · {count} observations · {_fmt_latency(item.get('latency_ms'))}"
        if item.get("at"):
            meta = f"{item['at']} · {meta}"
        on = " on" if index == selected else ""
        session_links.append(
            f'<a class="lf-session{on}" href="{href(index, 0, view)}">'
            f'<span class="lf-session-q">{esc(question)}</span>'
            f'<span class="lf-session-meta">{esc(meta)}</span></a>'
        )
    if not session_links:
        session_links.append('<p class="note">Chưa có lượt nào. Hỏi trợ lý một câu, rồi mở lại trang.</p>')

    if not turn:
        main = '<p class="note">Phiên này chưa có trace.</p>'
        detail = '<p class="note">Chọn một trace sau khi chat.</p>'
    else:
        total = 0.0
        for row in rows:
            total = max(total, float(row["t1"]))
        ticks = []
        for part in (0, 0.5, 1):
            ticks.append(f"<span>{esc(_fmt_latency(total * part))}</span>")
        tree_on = "on" if view == "tree" else ""
        time_on = "on" if view == "timeline" else ""
        tree_href = href(selected, picked, "tree")
        time_href = href(selected, picked, "timeline")
        source = "Model chọn tool, Python chạy, model viết câu trả lời." if turn.get("source") == "model" else "Đường offline. Không phải suy luận của model."
        obs_rows = []
        for row in rows:
            on = " on" if row["id"] == picked else ""
            kind = (row["type"] or "SPAN").lower()
            obs_rows.append(
                f'<a class="lf-row type-{kind}{on}" style="--depth:{int(row["depth"])}" href="{href(selected, row["id"], view)}">'
                f'<span class="lf-name"><span class="lf-badge {kind}">{esc(row["type"])}</span> {esc(row["name"])}</span>'
                f'<span class="lf-track"><span class="lf-bar {kind}" style="{_trace_bar(row["t0"], row["t1"], total)}"></span></span>'
                f'<span class="lf-lat">{esc(_fmt_latency(row["t1"] - row["t0"]))}</span></a>'
            )
        main = f"""
        <div class="lf-toolbar">
          <div>
            <p class="lf-q">{esc(turn.get("question") or "")}</p>
            <p class="lf-sub">{esc(_fmt_latency(turn.get("latency_ms")))} · {len(turn.get("steps") or [])} observations · {esc(source)}</p>
          </div>
          <div class="lf-switch" role="tablist">
            <a role="tab" href="{tree_href}" class="{tree_on}">Cây</a>
            <a role="tab" href="{time_href}" class="{time_on}">Timeline</a>
          </div>
        </div>
        <div class="lf-axis" aria-hidden="true"><span></span><span class="lf-ruler">{"".join(ticks)}</span><span></span></div>
        <div class="lf-tree">{"".join(obs_rows)}</div>"""
        blocks = []
        for label, value in (focus or {}).get("blocks") or []:
            blocks.append(f'<div class="lf-io"><h3>{esc(label)}</h3>{_trace_pre(value)}</div>')
        note = f'<p class="lf-note">{esc(focus.get("note") or "")}</p>' if focus and focus.get("note") else ""
        if focus:
            kind = (focus["type"] or "SPAN").lower()
            detail = (
                f'<span class="lf-badge {kind}">{esc(focus["type"])}</span>'
                f'<h2>{esc(focus["name"])}</h2>'
                f'<p class="lf-sub">{esc(_fmt_latency(focus["t1"] - focus["t0"]))} · bắt đầu {esc(_fmt_latency(focus["t0"]))}</p>'
                f"{note}{''.join(blocks)}"
            )
        else:
            detail = '<p class="note">Chọn một observation.</p>'
    revision = trace_revision(user.get("token") or "")
    inner = f"""<div class="lf-title-row">
      <p class="lf-live">Tự cập nhật khi có lượt mới.</p>
      <button type="button" id="trace-reload" class="lf-reload">Tải lại</button>
    </div>
    <p class="note">Mỗi câu hỏi là một trace. Trong trace có observation: SPAN là Python đọc câu, GENERATION là một lượt model, TOOL là Python chạy tool. Cây và timeline dùng thời gian thật. Không lưu số điện thoại, địa chỉ hay khóa API.</p>
    <div class="lf lf-view-{esc(view)}">
      <aside class="lf-sessions" aria-label="Traces trong phiên">
        <p class="lf-side-label">Traces</p>
        {"".join(session_links)}
      </aside>
      <section class="lf-main" aria-label="Trace">{main}</section>
      <aside class="lf-detail" aria-label="Observation">{detail}</aside>
    </div>"""
    return admin_page(
        "Tracing",
        "Tracing",
        inner,
        "tracing",
        main_class=" trace-page",
        main_attrs=f' data-rev="{esc(revision)}" data-count="{len(turns)}"',
    )


def render_tracing_denied():
    body = """<main id="content" class="page"><div id="nav-sentinel"></div>
      <h1>Tracing</h1>
      <p class="note">Chỉ quản trị xem được trang này.</p>
      <p><a class="more" href="/">Về đầu</a></p>
    </main>"""
    return layout("Tracing", body, 0)


def chat_history_markup(user, bot_avatar):
    if not user:
        return ""
    try:
        with connect() as conn:
            rows = load_chat(conn, user["id"], user.get("token") or "")
    except Exception:
        return ""
    initial = esc((user["name"] or "B").strip()[:1].upper())
    user_avatar = f'<span class="av av-user" aria-hidden="true">{initial}</span>'
    parts = []
    for role, body in rows:
        if role == "user":
            parts.append(
                f'<div class="msg user"><div class="bubble user"><span>{esc(body)}</span></div>{user_avatar}</div>'
            )
            continue
        kind = "bubble bot cards" if body and (
            "advice-card" in body or "chat-compare" in body or "chat-invoice" in body
            or "citation" in body or "<form" in body
        ) else "bubble bot"
        parts.append(f'<div class="msg bot">{bot_avatar}<div class="{kind}">{body}</div></div>')
    return "".join(parts)


if DEMO_MODE:
    LOGIN_NOTE = "Khách: khach@form.local / form-khach<br>Quản trị: admin@form.local / form-admin"
elif SHOW_DEMO_LOGIN:
    LOGIN_NOTE = "Khách demo: khach@form.local / form-khach<br>Quản trị: admin@form.local (mật khẩu quản trị riêng)"
else:
    LOGIN_NOTE = "Đăng nhập vào tài khoản của bạn."


def auth_page(title, heading, action, note, error=""):
    message = f'<p class="note">{esc(error)}</p>' if error else ""
    body = f"""<main id="content" class="page auth-page">
      <div id="nav-sentinel"></div>
      <h1>{esc(heading)}</h1>
      {message}
      <form class="auth-form" method="post" action="{esc(action)}">
        <label>Tên <input name="name" required></label>
        <label>Email <input name="email" type="email" required></label>
        <label>Mật khẩu <input name="password" type="password" minlength="6" required></label>
        <button class="buy" type="submit">{esc(heading)}</button>
      </form>
      <p class="note">{note}</p>
    </main>"""
    if action == "/login":
        body = body.replace("<label>Tên <input name=\"name\" required></label>", "")
    return layout(title, body, 0)


DELIVER_SLOTS = (
    ("morning", "Sáng 8:00–12:00"),
    ("afternoon", "Chiều 13:00–17:00"),
    ("evening", "Tối 18:00–21:00"),
)


def saigon_today():
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def delivery_bounds():
    today = saigon_today()
    return today + timedelta(days=1), today + timedelta(days=14)


def clean_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits


def delivery_when(day, slot):
    if not day:
        return ""
    stamp = day.strftime("%d.%m.%Y") if hasattr(day, "strftime") else str(day)
    label = dict(DELIVER_SLOTS).get(slot, "")
    return f"{stamp} · {label}" if label else stamp


def delivery_line(name, phone, address, day, slot):
    when = delivery_when(day, slot)
    bits = []
    who = " · ".join(part for part in (name, phone) if part)
    if who:
        bits.append(esc(who))
    if address:
        bits.append(esc(address))
    if when:
        bits.append("Nhận " + esc(when))
    if not bits:
        return ""
    return '<p class="note">' + "<br>".join(bits) + "</p>"


def read_shipment(fields, user):
    name = (fields.get("name") or [""])[0].strip()
    email = (fields.get("email") or [""])[0].strip().lower()
    phone = clean_phone((fields.get("phone") or [""])[0])
    address = re.sub(r"\s+", " ", (fields.get("address") or [""])[0]).strip()
    day_raw = (fields.get("deliver_on") or [""])[0]
    slot = (fields.get("deliver_slot") or [""])[0]
    pay = (fields.get("pay_method") or ["cod"])[0]
    if pay not in ("cod", "qr"):
        pay = "cod"
    data = {
        "name": name, "email": email, "phone": phone, "address": address,
        "deliver_on": day_raw, "deliver_slot": slot, "pay_method": pay,
        "color": (fields.get("color") or [""])[0],
    }
    if len(name) < 2:
        return data, "Nhập tên người nhận."
    if "@" not in email or "." not in email.split("@")[-1]:
        return data, "Email chưa đúng."
    if not re.fullmatch(r"0\d{9,10}", phone):
        return data, "Số điện thoại cần 10 hoặc 11 số, bắt đầu bằng 0."
    if len(address) < 8:
        return data, "Nhập địa chỉ nhận hàng."
    if slot not in dict(DELIVER_SLOTS):
        return data, "Chọn buổi nhận hàng."
    try:
        day = datetime.strptime(day_raw, "%Y-%m-%d").date()
    except ValueError:
        return data, "Chọn ngày nhận hàng."
    start, end = delivery_bounds()
    if day < start:
        return data, "Chọn từ ngày mai. Không giao trong hôm nay."
    if day > end:
        return data, "Chỉ đặt lịch trong 14 ngày tới."
    data["deliver_on"] = day
    return data, ""


def render_checkout(conn, user, bag, values=None, error=""):
    start, end = delivery_bounds()
    values = values or {
        "name": user["name"], "email": user["email"],
        "phone": user.get("phone") or "", "address": user.get("address") or "",
        "deliver_on": start.isoformat(), "deliver_slot": "afternoon",
    }
    ids = [ident for ident, _ in bag]
    rows = conn.execute(
        "SELECT source_product_id, name, price_vnd FROM products WHERE source_product_id = ANY(%s)",
        (ids,),
    ).fetchall() if ids else []
    found = {row[0]: row for row in rows}
    photos = covers(conn, ids)
    lines = []
    total = 0
    for ident, qty in bag:
        row = found.get(ident)
        if not row or not row[2]:
            continue
        total += int(row[2]) * qty
        photo = photos.get(ident)
        image = f'<img src="{esc(photo[0])}" alt="">' if photo else '<span class="order-thumb"></span>'
        lines.append(
            f'<li><span class="order-photo">{image}</span><span>{esc(short_name(row[1]))}</span>'
            f'<span>× {qty}</span><span>{esc(money(int(row[2]) * qty))}</span></li>'
        )
    if not lines:
        body = """<main id="content" class="page"><div id="nav-sentinel"></div>
          <div class="empty"><h1>Túi đang trống.</h1><p><a class="more" href="/shop">Tới cửa hàng</a></p></div></main>"""
        return layout("Đặt hàng", body, 0)
    options = "".join(
        f'<option value="{esc(key)}"{" selected" if key == values.get("deliver_slot") else ""}>{esc(label)}</option>'
        for key, label in DELIVER_SLOTS
    )
    body = f"""<main id="content" class="page"><div id="nav-sentinel"></div>
      <div class="checkout-sheet">
        <h1>Đặt hàng</h1>
        {admin_note(error)}
        <ul class="order-card">{"".join(lines)}</ul>
        <p class="total"><span>Tạm tính</span><strong>{esc(money(total))}</strong></p>
        <form class="auth-form" method="post" action="/checkout">
          <label>Tên người nhận <input name="name" value="{esc(values.get("name", ""))}" required></label>
          <label>Email <input name="email" type="email" value="{esc(values.get("email", ""))}" required></label>
          <label>Số điện thoại <input name="phone" inputmode="tel" value="{esc(values.get("phone", ""))}" placeholder="0901234567" required></label>
          <label>Địa chỉ <textarea name="address" required>{esc(values.get("address", ""))}</textarea></label>
          <label>Ngày nhận <input name="deliver_on" type="date" min="{start.isoformat()}" max="{end.isoformat()}" value="{esc(values.get("deliver_on") if isinstance(values.get("deliver_on"), str) else (values.get("deliver_on").isoformat() if values.get("deliver_on") else ""))}" required></label>
          <label>Buổi nhận <select name="deliver_slot">{options}</select></label>
          {pay_fields(values)}
          <p class="note">Giao từ ngày mai, trong buổi đã chọn. Không giao trong hôm nay.</p>
          <button class="buy" type="submit">Xác nhận đặt hàng</button>
        </form>
      </div>
    </main>"""
    return layout("Đặt hàng", body, sum(qty for _, qty in bag))


def render_account(user, message="", error=""):
    status = message or error
    note = f'<p class="note">{esc(status)}</p>' if status else ""
    body = f"""<main id="content" class="page"><div id="nav-sentinel"></div>
      <div class="account-sheet">
        <h1>Thông tin cá nhân</h1>
        {note}
        <form class="auth-form" method="post" action="/account">
          <label>Tên <input name="name" value="{esc(user.get("name") or "")}" required autocomplete="name"></label>
          <label>Email <input name="email" type="email" value="{esc(user.get("email") or "")}" required autocomplete="email"></label>
          <label>Số điện thoại <input name="phone" inputmode="tel" value="{esc(user.get("phone") or "")}" placeholder="0901234567" autocomplete="tel"></label>
          <label>Địa chỉ <textarea name="address" autocomplete="street-address">{esc(user.get("address") or "")}</textarea></label>
          <label>Mật khẩu hiện tại <input name="current" type="password" autocomplete="current-password"></label>
          <label>Mật khẩu mới <input name="password" type="password" autocomplete="new-password"></label>
          <p class="note">Số điện thoại và địa chỉ được điền sẵn khi đặt hàng. Để trống mật khẩu mới nếu không đổi. Đổi email hoặc mật khẩu thì cần mật khẩu hiện tại.</p>
          <button class="buy" type="submit">Lưu</button>
        </form>
      </div>
    </main>"""
    return layout("Thông tin cá nhân", body, 0)


def save_customer_account(conn, user, fields):
    name = (fields.get("name") or [""])[0].strip()
    email = (fields.get("email") or [""])[0].strip().lower()
    phone = clean_phone((fields.get("phone") or [""])[0])
    address = re.sub(r"\s+", " ", (fields.get("address") or [""])[0]).strip()
    current = (fields.get("current") or [""])[0]
    new = (fields.get("password") or [""])[0]
    posted = {
        "id": user["id"], "name": name, "email": email, "phone": phone, "address": address,
        "role": user.get("role") or "customer", "token": user.get("token") or "",
    }
    if len(name) < 2:
        return posted, "Tên cần ít nhất 2 ký tự."
    if "@" not in email or "." not in email.split("@")[-1]:
        return posted, "Email chưa đúng."
    if phone and not re.fullmatch(r"0\d{9,10}", phone):
        return posted, "Số điện thoại cần 10 hoặc 11 số, bắt đầu bằng 0."
    if address and len(address) < 8:
        return posted, "Địa chỉ cần ít nhất 8 ký tự."
    taken = conn.execute(
        "SELECT id FROM app_users WHERE lower(email)=%s AND id<>%s",
        (email, user["id"]),
    ).fetchone()
    if taken:
        return posted, "Email này đã có tài khoản."
    email_changed = email != (user.get("email") or "").lower()
    if new or email_changed:
        stored = conn.execute("SELECT password_hash FROM app_users WHERE id=%s", (user["id"],)).fetchone()
        if not current or not stored or not check_password(current, stored[0]):
            return posted, "Nhập đúng mật khẩu hiện tại để đổi email hoặc mật khẩu."
        if new and len(new) < 6:
            return posted, "Mật khẩu mới cần ít nhất 6 ký tự."
    if new:
        conn.execute(
            "UPDATE app_users SET name=%s, email=%s, phone=%s, address=%s, password_hash=%s WHERE id=%s",
            (name, email, phone or None, address or None, hash_password(new), user["id"]),
        )
    else:
        conn.execute(
            "UPDATE app_users SET name=%s, email=%s, phone=%s, address=%s WHERE id=%s",
            (name, email, phone or None, address or None, user["id"]),
        )
    return posted, ""


def render_orders(conn, user):
    rows = conn.execute(
        """
        SELECT id, total_vnd, created_at, status, ship_name, ship_phone, ship_address, deliver_on, deliver_slot
        FROM orders WHERE user_id=%s ORDER BY id DESC
        """,
        (user["id"],),
    ).fetchall()
    grouped = {}
    if rows:
        item_rows = conn.execute(
            """
            SELECT order_id, product_id, name, qty, unit_price
            FROM order_items WHERE order_id = ANY(%s) ORDER BY id
            """,
            ([row[0] for row in rows],),
        ).fetchall()
        for order_id, product_id, name, qty, unit_price in item_rows:
            grouped.setdefault(order_id, []).append((product_id, name, qty, unit_price))
        photos = covers(conn, [row[1] for row in item_rows if row[1]])
    else:
        photos = {}
    cards = []
    for order_id, total, created_at, status, ship_name, ship_phone, ship_address, deliver_on, deliver_slot in rows:
        stamp = created_at.strftime("%d.%m.%Y") if created_at else ""
        state = ORDER_LABEL.get(status, status)
        receive = delivery_line(ship_name, ship_phone, ship_address, deliver_on, deliver_slot)
        lines = []
        for product_id, name, qty, unit_price in grouped.get(order_id, []):
            photo = photos.get(product_id)
            href = f'/p/{product_id}' if product_id else ""
            image = (
                f'<img src="{esc(photo[0])}" alt="">'
                if photo else '<span class="order-thumb"></span>'
            )
            thumb = f'<a class="order-photo" href="{href}">{image}</a>' if href else f'<span class="order-photo">{image}</span>'
            title = esc(short_name(name))
            label = f'<a href="{href}">{title}</a>' if href else f'<span>{title}</span>'
            lines.append(
                f'<li>{thumb}{label}<span>× {qty}</span><span>{esc(money((unit_price or 0) * qty))}</span></li>'
            )
        cards.append(
            f'<article class="order-card"><header><div><strong>Đơn #{order_id}</strong>'
            f'<p class="note">{esc(stamp)} · {esc(state)}</p>{receive}</div>'
            f'<p class="order-total">{esc(money(total))}</p></header><ul>{"".join(lines)}</ul></article>'
        )
    body = (
        '<main id="content" class="page"><div id="nav-sentinel"></div>'
        f'<div class="order-sheet"><h1>Đơn hàng</h1>{"".join(cards) or "<p>Chưa có đơn nào.</p>"}</div></main>'
    )
    return layout("Đơn hàng", body, 0)


def nav_icon(name):
    paths = {
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        "box": '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/>',
        "folder": '<path d="M3 7h6l2 2h10v10H3z"/>',
        "bag": '<path d="M6 8h12l-1 12H7z"/><path d="M9 8V7a3 3 0 0 1 6 0v1"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="3"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        "star": '<path d="M12 3l2.2 5 5.3.6-4 3.7 1.1 5.4L12 15.8 7.4 17.7 8.5 12.3 4.5 8.6 9.8 8z"/>',
        "chart": '<path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16v-5"/><path d="M12 16V8"/><path d="M16 16v-3"/>',
        "spark": '<path d="M12 3l1.4 4.6L18 9l-4.6 1.4L12 15l-1.4-4.6L6 9l4.6-1.4z"/><path d="M18 14l.5 1.6L20 16l-1.5.4L18 18l-.5-1.6L16 16l1.5-.4z"/>',
        "user": '<circle cx="12" cy="8" r="3"/><path d="M5 19a7 7 0 0 1 14 0"/>',
        "store": '<path d="M3 10l2-6h14l2 6"/><path d="M4 10h16v9H4z"/><path d="M10 19v-5h4v5"/>',
        "out": '<path d="M9 6H5v12h4"/><path d="M10 12h9"/><path d="M16 8l4 4-4 4"/>',
        "mail": '<path d="M4 6h16v12H4z"/><path d="M4 7l8 6 8-6"/>',
        "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
        "trace": '<path d="M4 15l4-6 4 8 3-4h5"/>',
    }
    return (
        '<svg class="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'{paths[name]}</svg>'
    )


def admin_page(title, heading, inner, current, main_class="", main_attrs=""):
    items = (
        ("home", "Quản trị", "/admin", "grid"),
        ("products", "Sản phẩm", "/admin/products", "box"),
        ("categories", "Danh mục", "/admin/categories", "folder"),
        ("orders", "Đơn hàng", "/admin/orders", "bag"),
        ("users", "Người dùng", "/admin/users", "users"),
        ("reviews", "Đánh giá", "/admin/reviews", "star"),
        ("stats", "Thống kê", "/admin/stats", "chart"),
        ("support", "Hỗ trợ", "/admin/support", "mail"),
        ("documents", "Tài liệu", "/admin/documents", "file"),
        ("assistant", "Trợ lý Ảo", "/admin/assistant", "spark"),
        ("tracing", "Tracing", "/admin/tracing", "trace"),
    )
    nav = "".join(
        f'<a href="{href}"{current_attr(key == current)}>{nav_icon(icon)}{esc(label)}</a>'
        for key, label, href, icon in items
    )
    profile_current = current_attr(current == "profile")
    body = f"""<main id="content" class="page admin-page{main_class}"{main_attrs}>
      <div id="nav-sentinel"></div>
      <div class="admin-layout">
        <aside class="admin-nav" aria-label="Quản trị">
          {nav}
          <p class="admin-section">Hệ thống</p>
          <a href="/admin/profile"{profile_current}>{nav_icon("user")}Trang cá nhân</a>
          <a href="/">{nav_icon("store")}Xem cửa hàng</a>
          <form method="post" action="/logout"><button type="submit">{nav_icon("out")}Đăng xuất</button></form>
        </aside>
        <section>
          <h1>{esc(heading)}</h1>
          {inner}
        </section>
      </div>
    </main>"""
    return layout(title, body, 0, admin=True)


def render_admin_documents(conn, note=""):
    from rag.documents import broker_status, list_documents
    from rag.settings import DOC_TYPES

    labels = dict(DOC_TYPES)
    status_label = {
        "queued": "Đang chờ",
        "processing": "Đang nhúng",
        "ready": "Sẵn sàng",
        "failed": "Lỗi",
    }
    options = "".join(
        '<option value="{0}">{1}</option>'.format(esc(key), esc(label))
        for key, label in DOC_TYPES
    )
    rows = []
    for item in list_documents(conn):
        stamp = item["created_at"].strftime("%d.%m.%Y %H:%M") if item["created_at"] else ""
        state = status_label.get(item["status"], item["status"])
        detail = esc(item["error"][:180]) if item["error"] else "{0} đoạn".format(item["chunk_count"])
        rows.append(
            "<tr><td>{title}<p class=\"note\">{brand} · {kind}</p></td>"
            "<td>{state}<p class=\"note\">{detail}</p></td>"
            "<td>{stamp}</td>"
            "<td class=\"admin-actions\">"
            "<form method=\"post\" action=\"/admin/documents\">"
            "<input type=\"hidden\" name=\"action\" value=\"reindex\">"
            "<input type=\"hidden\" name=\"id\" value=\"{id}\">"
            "<button class=\"quiet\" type=\"submit\">Nhúng lại</button></form>"
            "<form method=\"post\" action=\"/admin/documents\">"
            "<input type=\"hidden\" name=\"action\" value=\"delete\">"
            "<input type=\"hidden\" name=\"id\" value=\"{id}\">"
            "<button class=\"quiet\" type=\"submit\">Xóa</button></form>"
            "</td></tr>".format(
                title=esc(item["title"]),
                brand=esc(item["brand"] or "Chưa ghi hãng"),
                kind=esc(labels.get(item["doc_type"], item["doc_type"])),
                state=esc(state),
                detail=detail,
                stamp=esc(stamp),
                id=item["id"],
            )
        )
    body_rows = "".join(rows) or '<tr><td colspan="4">Chưa có tài liệu.</td></tr>'
    inner = """{note}
    <p class="note">{status}</p>
    <p class="note">Tệp txt, md hoặc html, tối đa 2 MB. Trang này lưu file gốc rồi gửi mã tài liệu vào RabbitMQ. Worker cắt đoạn, nhúng bằng text-embedding-3-small và ghi Qdrant. Câu hỏi bảo hành chỉ đọc loại Bảo hành.</p>
    <form class="auth-form" method="post" action="/admin/documents" enctype="multipart/form-data">
      <label>Tiêu đề <input name="title" required maxlength="160"></label>
      <label>Hãng <input name="brand" maxlength="40" placeholder="Apple, Samsung, OPPO"></label>
      <label>Loại <select name="doc_type">{options}</select></label>
      <label>Ngôn ngữ <select name="lang"><option value="vi">Tiếng Việt</option><option value="en">Tiếng Anh</option></select></label>
      <label>Phạm vi <input name="scope" maxlength="200" placeholder="Ví dụ: chỉ phụ kiện, không phải laptop"></label>
      <label>URL nguồn <input name="source_url" maxlength="300" placeholder="https://"></label>
      <label>Tệp <input type="file" name="file" accept=".txt,.md,.html,.htm" required></label>
      <button class="buy" type="submit">Đưa vào hàng đợi</button>
    </form>
    <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>Tài liệu</th><th>Trạng thái</th><th>Lúc</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table></div>""".format(
        note=admin_note(note),
        status=esc(broker_status()),
        options=options,
        rows=body_rows,
    )
    return admin_page("Tài liệu", "Tài liệu cho trợ lý", inner, "documents")


def render_admin(conn):
    products = conn.execute("SELECT count(*) FROM products WHERE is_live_catalog").fetchone()[0]
    orders = conn.execute("SELECT count(*), coalesce(sum(total_vnd),0) FROM orders").fetchone()
    users = conn.execute("SELECT count(*) FROM app_users").fetchone()[0]
    reviews = conn.execute("SELECT count(*) FROM product_reviews").fetchone()[0]
    cards = f"""<div class="stats">
      <a href="/admin/products"><strong>{products}</strong><span>Sản phẩm đang bán</span></a>
      <a href="/admin/orders"><strong>{orders[0]}</strong><span>Đơn hàng · {esc(money(orders[1]))}</span></a>
      <a href="/admin/users"><strong>{users}</strong><span>Người dùng</span></a>
      <a href="/admin/reviews"><strong>{reviews}</strong><span>Đánh giá</span></a>
      <a href="/admin/tracing"><strong>Tracing</strong><span>Lượt hỏi trong phiên này</span></a>
    </div>
    <p><a class="buy" href="/admin/products">Quản lý sản phẩm</a></p>"""
    return admin_page("Quản trị", "Quản trị", cards, "home")


def admin_list_href(group="", text="", page=1):
    params = []
    if group in category_map():
        params.append(f"group={quote(group)}")
    if text:
        params.append(f"q={quote(text)}")
    if page > 1:
        params.append(f"page={page}")
    return "/admin/products" + (("?" + "&".join(params)) if params else "")


def render_admin_products(conn, text, page, group):
    page = max(page, 1)
    if group not in category_map():
        group = ""
    counts = dict(conn.execute(
        "SELECT category, count(*) FROM products WHERE is_live_catalog GROUP BY category"
    ).fetchall())
    hidden = f'<input type="hidden" name="group" value="{esc(group)}">' if group else ""
    chips = "".join(
        f'<a href="{admin_list_href(key)}"{current_attr(key == group)}>{esc(label)} <span>{counts.get(key, 0)}</span></a>'
        for key, label in category_pairs()
    )
    search = f"""<form class="tools" method="get" action="/admin/products" role="search">
      {hidden}
      <input type="search" name="q" value="{esc(text)}" placeholder="Tên hoặc hãng" aria-label="Tìm sản phẩm">
      <button type="submit">Tìm</button>
      <a class="buy" href="/admin/new">Thêm sản phẩm</a>
    </form>"""
    if not group and not text:
        sample_rows = conn.execute(
            """
            SELECT category, source_product_id FROM (
                SELECT category, source_product_id,
                       row_number() OVER (
                           PARTITION BY category
                           ORDER BY price_vnd DESC NULLS LAST, source_product_id DESC
                       ) AS n
                FROM products
                WHERE is_live_catalog AND category = ANY(%s)
            ) ranked
            WHERE n <= 3
            """,
            ([key for key, _ in category_pairs()],),
        ).fetchall()
        by_group = {}
        for category, product_id in sample_rows:
            by_group.setdefault(category, []).append(product_id)
        pics = covers(conn, [product_id for _, product_id in sample_rows])
        cards = []
        for key, label in category_pairs():
            thumbs = "".join(
                f'<img src="{esc(pics[product_id][0])}" alt="">'
                for product_id in by_group.get(key, [])
                if product_id in pics
            )
            cards.append(
                f'<a class="admin-group" href="{admin_list_href(key)}">'
                f'<span class="admin-group-photos">{thumbs}</span>'
                f'<strong>{esc(label)}</strong><span>{counts.get(key, 0)} sản phẩm</span></a>'
            )
        inner = search + f'<div class="admin-groups">{"".join(cards)}</div>'
        return admin_page("Sản phẩm", "Quản lý sản phẩm", inner, "products")

    limit = 20
    like = f"%{text.replace('%', '').replace('_', '')}%" if text else "%"
    rows = conn.execute(
        """
        SELECT source_product_id, category, brand, name, price_vnd, stock, coalesce(description, ''), count(*) OVER ()
        FROM products
        WHERE is_live_catalog
          AND (%s = '' OR category = %s)
          AND (%s = '' OR name ILIKE %s OR coalesce(brand, '') ILIKE %s)
        ORDER BY price_vnd DESC NULLS LAST, source_product_id DESC
        LIMIT %s OFFSET %s
        """,
        (group, group, text, like, like, limit, (page - 1) * limit),
    ).fetchall()
    total = rows[0][7] if rows else 0
    pics = covers(conn, [row[0] for row in rows])
    items = []
    for row in rows:
        photo = pics.get(row[0])
        thumb = (
            f'<img class="admin-thumb" src="{esc(photo[0])}" alt="">'
            if photo else '<span class="admin-thumb"></span>'
        )
        meta = esc(row[2] or "")
        if not group:
            label = esc(category_map().get(row[1], row[1]))
            meta = f"{label} · {meta}" if meta else label
        items.append(
            f'<li>{thumb}'
            f'<div class="admin-product"><a href="/p/{row[0]}">{esc(display_name(row[3]))}</a>'
            f'<p class="note">{meta}</p></div>'
            f'<p class="admin-price">{esc(money(row[4]))}<span class="note">Còn {int(row[5] or 0)}</span></p>'
            f'<div class="admin-actions"><button type="button" class="admin-edit"'
            f' data-id="{row[0]}" data-name="{esc(row[3])}" data-brand="{esc(row[2] or "")}"'
            f' data-category="{esc(row[1])}" data-price="{esc(row[4] or "")}" data-stock="{int(row[5] or 0)}"'
            f' data-description="{esc(row[6] or "")}" data-image="{esc(photo[0]) if photo else ""}">Sửa</button>'
            f'<form method="post" action="/admin/{row[0]}/delete">'
            f'<input type="hidden" name="group" value="{esc(group or row[1])}">'
            f'<button class="quiet" type="submit">Xóa</button></form></div></li>'
        )
    body_rows = "".join(items) or "<li>Không có sản phẩm trong nhóm này.</li>"
    last = max(1, (total + limit - 1) // limit)
    prev_link = f'<a href="{admin_list_href(group, text, page - 1)}">Trước</a>' if page > 1 else "<span></span>"
    next_link = f'<a href="{admin_list_href(group, text, page + 1)}">Sau</a>' if page < last else "<span></span>"
    heading = category_map()[group] if group else "Kết quả tìm"
    options = "".join(
        f'<option value="{esc(key)}">{esc(label)}</option>' for key, label in category_pairs()
    )
    modal = f"""<dialog id="product-edit" class="admin-modal">
      <div class="admin-modal-card">
        <h2>Sửa sản phẩm</h2>
        <img id="product-edit-photo" class="admin-modal-photo" alt="" hidden>
        <form class="auth-form" id="product-edit-form" method="post" action="/admin/0">
          <label>Tên <input name="name" required></label>
          <label>Hãng <input name="brand"></label>
          <label>Nhóm <select name="category">{options}</select></label>
          <label>Giá (đồng) <input name="price" inputmode="numeric" required></label>
          <label>Tồn kho <input name="stock" inputmode="numeric" required></label>
          <label>Mô tả <input name="description"></label>
          <div class="admin-modal-actions">
            <button type="button" class="quiet" id="product-edit-cancel">Hủy</button>
            <button class="buy" type="submit">Lưu</button>
          </div>
        </form>
      </div>
    </dialog>"""
    inner = f"""{search}
    <nav class="admin-filters" aria-label="Nhóm sản phẩm">{chips}</nav>
    <p class="note">{total} sản phẩm</p>
    <ul class="admin-list">{body_rows}</ul>
    <nav class="pager" aria-label="Trang">{prev_link}<span>{page}/{last}</span>{next_link}</nav>
    {modal}"""
    return admin_page(heading, heading, inner, "products")


ORDER_STATES = (
    ("placed", "Đã đặt"),
    ("packing", "Đang xử lý"),
    ("done", "Hoàn tất"),
    ("cancelled", "Đã hủy"),
)
ORDER_LABEL = dict(ORDER_STATES)


def admin_note(text):
    return f'<p class="note">{esc(text)}</p>' if text else ""


def render_admin_orders(conn, note=""):
    users = conn.execute("SELECT id, name, email FROM app_users ORDER BY name, id").fetchall()
    user_options = "".join(
        f'<option value="{row[0]}">{esc(row[1])} · {esc(row[2])}</option>' for row in users
    )
    rows = conn.execute(
        """
        SELECT o.id, u.name, o.total_vnd, o.status, o.created_at,
               string_agg(i.name || ' × ' || i.qty, ', '),
               o.ship_name, o.ship_phone, o.deliver_on, o.deliver_slot
        FROM orders o
        JOIN app_users u ON u.id = o.user_id
        LEFT JOIN order_items i ON i.order_id = o.id
        GROUP BY o.id, u.name, o.total_vnd, o.status, o.created_at,
                 o.ship_name, o.ship_phone, o.deliver_on, o.deliver_slot
        ORDER BY o.id DESC
        LIMIT 50
        """
    ).fetchall()
    items = []
    for row in rows:
        options = "".join(
            f'<option value="{esc(key)}"{" selected" if key == row[3] else ""}>{esc(label)}</option>'
            for key, label in ORDER_STATES
        )
        when = delivery_when(row[8], row[9])
        who = " · ".join(part for part in (row[6], row[7], when) if part)
        guest = f'<p class="note">{esc(who)}</p>' if who else ""
        items.append(
            f'<tr><td>#{row[0]}</td><td>{esc(row[1])}{guest}</td><td>{esc(money(row[2]))}</td>'
            f'<td><form class="admin-actions" method="post" action="/admin/orders/{row[0]}">'
            f'<select name="status" aria-label="Trạng thái đơn {row[0]}">{options}</select>'
            f'<button class="quiet" type="submit">Lưu</button></form></td>'
            f'<td>{esc(row[5] or "")}</td>'
            f'<td class="admin-actions"><form method="post" action="/admin/orders/{row[0]}/delete">'
            f'<button class="quiet" type="submit">Xóa</button></form></td></tr>'
        )
    body_rows = "".join(items) or '<tr><td colspan="6">Chưa có đơn.</td></tr>'
    inner = f"""{admin_note(note)}
    <form class="admin-compact" method="post" action="/admin/orders/new">
      <label>Khách <select name="user_id">{user_options}</select></label>
      <label>Mã hoặc tên sản phẩm <input name="product" required placeholder="370977 hoặc iPhone 18 Pro"></label>
      <label>Số lượng <input name="qty" inputmode="numeric" value="1" required></label>
      <button class="buy" type="submit">Thêm đơn</button>
    </form>
    <table class="admin-table"><thead><tr><th>Đơn</th><th>Khách</th><th>Tổng</th><th>Trạng thái</th><th>Sản phẩm</th><th></th></tr></thead>
    <tbody>{body_rows}</tbody></table>"""
    return admin_page("Đơn hàng", "Đơn hàng", inner, "orders")


def render_admin_categories(conn, note=""):
    totals = {
        row[0]: row
        for row in conn.execute(
            """
            SELECT category, count(*), min(price_vnd), max(price_vnd)
            FROM products WHERE is_live_catalog GROUP BY category
            """
        ).fetchall()
    }
    brands = {}
    for category, brand, count in conn.execute(
        """
        SELECT category, coalesce(nullif(brand, ''), 'Khác'), count(*)
        FROM products WHERE is_live_catalog
        GROUP BY 1, 2
        ORDER BY count(*) DESC, 2
        """
    ).fetchall():
        bucket = brands.setdefault(category, [])
        if len(bucket) < 6:
            bucket.append((brand, count))
    cards = []
    for key, label in category_pairs():
        row = totals.get(key)
        count = row[1] if row else 0
        span = f"{money(row[2])} – {money(row[3])}" if row and row[2] and row[3] else ""
        brand_links = "".join(
            f'<a href="{admin_list_href(key, name)}">{esc(name)} <span>{amount}</span></a>'
            for name, amount in brands.get(key, [])
        )
        cards.append(
            f'<article class="admin-cat">'
            f'<a class="admin-cat-title" href="{admin_list_href(key)}"><strong>{esc(label)}</strong>'
            f'<span>{count} sản phẩm</span></a>'
            f'<p class="note">{esc(span)}</p>'
            f'<div class="admin-brands">{brand_links}</div>'
            f'<div class="admin-actions"><a href="/admin/categories/{esc(key)}">Sửa</a>'
            f'<form method="post" action="/admin/categories/{esc(key)}/delete">'
            f'<button class="quiet" type="submit">Xóa</button></form></div></article>'
        )
    inner = f"""{admin_note(note)}
    <p><a class="buy" href="/admin/categories/new">Thêm danh mục</a></p>
    <div class="admin-cats">{"".join(cards)}</div>"""
    return admin_page("Danh mục", "Danh mục", inner, "categories")


def render_category_form(category=None, error=""):
    category = category or {"slug": "", "label": ""}
    message = admin_note(error)
    if category["slug"]:
        inner = f"""{message}
        <form class="auth-form" method="post" action="/admin/categories/{esc(category["slug"])}">
          <label>Mã <input value="{esc(category["slug"])}" disabled></label>
          <label>Tên hiển thị <input name="label" value="{esc(category["label"])}" required></label>
          <button class="buy" type="submit">Lưu</button>
        </form>
        <p><a class="more" href="/admin/categories">Về danh mục</a></p>"""
        return admin_page("Sửa danh mục", "Sửa danh mục", inner, "categories")
    inner = f"""{message}
    <form class="auth-form" method="post" action="/admin/categories/new">
      <label>Mã <input name="slug" placeholder="phu-kien" required></label>
      <label>Tên hiển thị <input name="label" required></label>
      <button class="buy" type="submit">Lưu</button>
    </form>
    <p class="note">Mã viết thường, không dấu, dùng trong đường dẫn. Ví dụ phu-kien.</p>
    <p><a class="more" href="/admin/categories">Về danh mục</a></p>"""
    return admin_page("Thêm danh mục", "Thêm danh mục", inner, "categories")


def save_category(conn, fields, slug=None):
    label = (fields.get("label") or [""])[0].strip()
    if len(label) < 2:
        return "Tên danh mục cần ít nhất 2 ký tự."
    if slug:
        conn.execute("UPDATE app_categories SET label=%s WHERE slug=%s", (label, slug))
        bind_categories(conn)
        return ""
    raw = (fields.get("slug") or [""])[0].strip().lower()
    if not re.fullmatch(r"[a-z0-9-]{2,32}", raw):
        return "Mã chỉ gồm chữ thường, số và dấu gạch, từ 2 đến 32 ký tự."
    exists = conn.execute("SELECT 1 FROM app_categories WHERE slug=%s", (raw,)).fetchone()
    if exists:
        return "Mã này đã có."
    sort_order = conn.execute("SELECT coalesce(max(sort_order), 0) + 1 FROM app_categories").fetchone()[0]
    conn.execute(
        "INSERT INTO app_categories(slug, label, sort_order) VALUES (%s,%s,%s)",
        (raw, label, sort_order),
    )
    sync_category_check(conn)
    bind_categories(conn)
    return ""


def delete_category(conn, slug):
    count = conn.execute("SELECT count(*) FROM products WHERE category=%s", (slug,)).fetchone()[0]
    if count:
        return "Danh mục còn sản phẩm, chưa xóa."
    conn.execute("DELETE FROM app_categories WHERE slug=%s", (slug,))
    sync_category_check(conn)
    bind_categories(conn)
    return ""


def render_admin_users(conn, note=""):
    rows = conn.execute(
        """
        SELECT u.id, u.name, u.email, u.role, u.created_at::date, count(o.id)
        FROM app_users u
        LEFT JOIN orders o ON o.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id
        """
    ).fetchall()
    items = []
    for row in rows:
        items.append(
            f'<tr><td>{esc(row[1])}</td><td>{esc(row[2])}</td>'
            f'<td>{"Quản trị" if row[3] == "admin" else "Khách"}</td>'
            f'<td>{row[5]}</td><td>{esc(row[4])}</td>'
            f'<td class="admin-actions"><a href="/admin/users/{row[0]}">Sửa</a>'
            f'<form method="post" action="/admin/users/{row[0]}/delete">'
            f'<button class="quiet" type="submit">Xóa</button></form></td></tr>'
        )
    body_rows = "".join(items) or '<tr><td colspan="6">Chưa có tài khoản.</td></tr>'
    inner = f"""{admin_note(note)}
    <p><a class="buy" href="/admin/users/new">Thêm tài khoản</a></p>
    <table class="admin-table"><thead><tr><th>Tên</th><th>Email</th><th>Vai trò</th><th>Đơn</th><th>Ngày tạo</th><th></th></tr></thead>
    <tbody>{body_rows}</tbody></table>"""
    return admin_page("Người dùng", "Người dùng", inner, "users")


def render_account_form(account=None, error=""):
    account = account or {"id": "", "name": "", "email": "", "role": "customer"}
    options = "".join(
        f'<option value="{esc(key)}"{" selected" if key == account["role"] else ""}>{esc(label)}</option>'
        for key, label in (("admin", "Quản trị"), ("customer", "Khách"))
    )
    action = f'/admin/users/{account["id"]}' if account["id"] else "/admin/users/new"
    password_label = "Mật khẩu mới" if account["id"] else "Mật khẩu"
    hint = '<p class="note">Để trống mật khẩu nếu không đổi.</p>' if account["id"] else ""
    inner = f"""{admin_note(error)}
    <form class="auth-form" method="post" action="{action}">
      <label>Tên <input name="name" value="{esc(account["name"])}" required></label>
      <label>Email <input name="email" type="email" value="{esc(account["email"])}" required></label>
      <label>Vai trò <select name="role">{options}</select></label>
      <label>{password_label} <input name="password" type="password" autocomplete="new-password"{" required" if not account["id"] else ""}></label>
      {hint}
      <button class="buy" type="submit">Lưu</button>
    </form>
    <p><a class="more" href="/admin/users">Về người dùng</a></p>"""
    heading = "Sửa tài khoản" if account["id"] else "Thêm tài khoản"
    return admin_page(heading, heading, inner, "users")


def reviews_href(text="", page=1):
    params = []
    if text:
        params.append(f"q={quote(text)}")
    if page > 1:
        params.append(f"page={page}")
    return "/admin/reviews" + (("?" + "&".join(params)) if params else "")


def render_admin_reviews(conn, text, page, note=""):
    page = max(page, 1)
    limit = 20
    like = f"%{text.replace('%', '').replace('_', '')}%" if text else "%"
    rows = conn.execute(
        """
        SELECT p.source_product_id, p.name, r.author_name, r.rating_value, r.review_body,
               r.published_at_text, r.review_index, r.approved, count(*) OVER ()
        FROM product_reviews r
        JOIN products p ON p.source_product_id = r.product_id
        WHERE p.is_live_catalog
          AND (%s = '' OR p.name ILIKE %s OR coalesce(r.author_name, '') ILIKE %s)
        ORDER BY r.product_id DESC, r.review_index DESC
        LIMIT %s OFFSET %s
        """,
        (text, like, like, limit, (page - 1) * limit),
    ).fetchall()
    total = rows[0][8] if rows else 0
    items = []
    for row in rows:
        body = (row[4] or "").strip()
        if len(body) > 180:
            body = body[:177].rstrip() + "…"
        score = f"{float(row[3]):.1f}" if row[3] is not None else "—"
        state = "Đã hiện" if row[7] is not False else "Chờ duyệt"
        approve = ""
        if row[7] is False:
            approve = (
                f'<form method="post" action="/admin/reviews/{row[0]}/{row[6]}/approve">'
                f'<button class="quiet" type="submit">Duyệt</button></form>'
            )
        items.append(
            f'<tr><td><a href="/p/{row[0]}">{esc(display_name(row[1]))}</a></td>'
            f'<td>{esc(row[2] or "Ẩn danh")}</td><td>{esc(score)}</td>'
            f'<td>{esc(body)}</td><td>{esc(row[5] or "")} · {state}</td>'
            f'<td class="admin-actions">{approve}<a href="/admin/reviews/{row[0]}/{row[6]}">Sửa</a>'
            f'<form method="post" action="/admin/reviews/{row[0]}/{row[6]}/delete">'
            f'<button class="quiet" type="submit">Xóa</button></form></td></tr>'
        )
    body_rows = "".join(items) or '<tr><td colspan="6">Không có đánh giá.</td></tr>'
    last = max(1, (total + limit - 1) // limit)
    prev_link = f'<a href="{reviews_href(text, page - 1)}">Trước</a>' if page > 1 else "<span></span>"
    next_link = f'<a href="{reviews_href(text, page + 1)}">Sau</a>' if page < last else "<span></span>"
    inner = f"""{admin_note(note)}
    <form class="tools" method="get" action="/admin/reviews" role="search">
      <input type="search" name="q" value="{esc(text)}" placeholder="Sản phẩm hoặc người viết" aria-label="Tìm đánh giá">
      <button type="submit">Tìm</button>
      <a class="buy" href="/admin/reviews/new">Thêm đánh giá</a>
    </form>
    <p class="note">{total} đánh giá</p>
    <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>Sản phẩm</th><th>Người viết</th><th>Điểm</th><th>Nội dung</th><th>Thời điểm</th><th></th></tr></thead>
    <tbody>{body_rows}</tbody></table></div>
    <nav class="pager" aria-label="Trang">{prev_link}<span>{page}/{last}</span>{next_link}</nav>"""
    return admin_page("Đánh giá", "Đánh giá", inner, "reviews")


def render_admin_stats(conn):
    products = conn.execute("SELECT count(*) FROM products WHERE is_live_catalog").fetchone()[0]
    orders = conn.execute("SELECT count(*), coalesce(sum(total_vnd),0) FROM orders").fetchone()
    users = conn.execute("SELECT count(*) FROM app_users").fetchone()[0]
    reviews = conn.execute(
        "SELECT count(*), round(avg(rating_value)::numeric, 1) FROM product_reviews"
    ).fetchone()
    counts = dict(conn.execute(
        "SELECT category, count(*) FROM products WHERE is_live_catalog GROUP BY category"
    ).fetchall())
    widest = max(counts.values(), default=1) or 1
    bars = "".join(
        f'<div class="bar-row"><span>{esc(label)}</span>'
        f'<span class="bar"><span style="width:{(counts.get(key, 0) * 100 // widest)}%"></span></span>'
        f'<span>{counts.get(key, 0)}</span></div>'
        for key, label in category_pairs()
    )
    brand_rows = conn.execute(
        """
        SELECT coalesce(nullif(brand, ''), 'Khác'), count(*)
        FROM products WHERE is_live_catalog
        GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 8
        """
    ).fetchall()
    brand_items = "".join(
        f'<tr><td>{esc(row[0])}</td><td>{row[1]}</td></tr>' for row in brand_rows
    ) or '<tr><td colspan="2">Chưa có hãng.</td></tr>'
    sellers = conn.execute(
        """
        SELECT i.name, sum(i.qty)::int, sum(i.unit_price * i.qty)
        FROM order_items i
        JOIN orders o ON o.id = i.order_id
        WHERE o.status <> 'cancelled'
        GROUP BY i.name
        ORDER BY sum(i.qty) DESC, sum(i.unit_price * i.qty) DESC
        LIMIT 5
        """
    ).fetchall()
    seller_items = "".join(
        f'<tr><td>{esc(short_name(row[0]))}</td><td>{row[1]}</td><td>{esc(money(row[2] or 0))}</td></tr>'
        for row in sellers
    ) or '<tr><td colspan="3">Chưa có đơn.</td></tr>'
    stock = conn.execute(
        """
        SELECT count(*) FILTER (WHERE stock = 0), count(*) FILTER (WHERE stock > 0 AND stock < 10)
        FROM products WHERE is_live_catalog
        """
    ).fetchone()
    average = reviews[1] if reviews[1] is not None else "—"
    cards = f"""<div class="stats">
      <a href="/admin/products"><strong>{products}</strong><span>Sản phẩm</span></a>
      <a href="/admin/orders"><strong>{orders[0]}</strong><span>Đơn · {esc(money(orders[1]))}</span></a>
      <a href="/admin/users"><strong>{users}</strong><span>Người dùng</span></a>
      <a href="/admin/reviews"><strong>{reviews[0]}</strong><span>Đánh giá · {esc(average)}</span></a>
    </div>
    <h2>Theo danh mục</h2>
    <div class="bars">{bars}</div>
    <h2>Bán chạy</h2>
    <table class="admin-table"><thead><tr><th>Sản phẩm</th><th>Số lượng</th><th>Doanh thu</th></tr></thead><tbody>{seller_items}</tbody></table>
    <h2>Tồn kho</h2>
    <p class="note">Hết hàng: {stock[0]}. Còn dưới 10 máy: {stock[1]}.</p>
    <h2>Hãng có nhiều sản phẩm</h2>
    <table class="admin-table"><thead><tr><th>Hãng</th><th>Số lượng</th></tr></thead><tbody>{brand_items}</tbody></table>"""
    return admin_page("Thống kê", "Thống kê", cards, "stats")


def admin_chat_token(user):
    """Keep admin turns off the shopper transcript. The shopper token is unchanged."""
    token = (user or {}).get("token") or ""
    if not token:
        return ""
    return "admin:" + token


def ask_assistant(conn, question, history=None):
    import admin_agent
    return admin_agent.answer_admin(conn, question, history)


def render_admin_assistant(messages=None, note=""):
    user = CURRENT_USER.get() or {}
    initial = esc((user.get("name") or "Q").strip()[:1].upper())
    user_avatar = '<span class="av av-user" aria-hidden="true">' + initial + "</span>"
    rows = list(messages or [])
    if rows:
        last_bot = -1
        for index, row in enumerate(rows):
            if row[0] in ("bot", "assistant"):
                last_bot = index
        parts = []
        for index, row in enumerate(rows):
            body = esc(row[1] or "")
            if row[0] == "user":
                parts.append(
                    '<div class="msg user"><div class="bubble user"><span>'
                    + body + "</span></div>" + user_avatar + "</div>"
                )
            else:
                aside = '<p class="chat-note">' + esc(note) + "</p>" if index == last_bot and note else ""
                parts.append(
                    '<div class="msg bot">' + BOT_MARK + '<div class="bubble bot">'
                    + body + "</div>" + aside + "</div>"
                )
        thread = "".join(parts)
    else:
        name = esc(user.get("name") or "bạn")
        thread = (
            '<div class="msg bot">' + BOT_MARK
            + '<div class="bubble bot">Xin chào ' + name
            + ". Bạn muốn xem doanh thu, máy bán chạy, kho hay đơn mới?</div></div>"
        )
    inner = (
        '<div class="admin-chat">'
        '<div class="assistant-bar"><div class="assistant-who">' + BOT_MARK
        + "<div><h2>Trợ lý</h2><p>Số liệu cửa hàng, chỉ đọc</p></div></div></div>"
        '<form class="admin-chat-clear" method="post" action="/admin/assistant">'
        '<input type="hidden" name="action" value="clear">'
        '<button type="submit">Cuộc mới</button></form>'
        '<div class="admin-chat-log">' + thread + "</div>"
        '<form class="assistant-compose" method="post" action="/admin/assistant">'
        '<input name="q" type="text" placeholder="Hỏi số liệu cửa hàng" required aria-label="Câu hỏi">'
        '<button class="send" type="submit" aria-label="Gửi">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12l16-8-6 16-2-6z"/></svg>'
        "</button></form></div>"
    )
    return admin_page("Trợ lý Ảo", "Trợ lý Ảo", inner, "assistant")


def render_admin_profile(user, message="", error=""):
    status = message or error
    note = f'<p class="note">{esc(status)}</p>' if status else ""
    role = "Quản trị" if user["role"] == "admin" else "Khách"
    inner = f"""{note}
      <form class="auth-form" method="post" action="/admin/profile">
        <label>Tên <input name="name" value="{esc(user["name"])}" required></label>
        <label>Email <input value="{esc(user["email"])}" disabled></label>
        <p class="note">Vai trò: {role}</p>
        <label>Mật khẩu hiện tại <input name="current" type="password" autocomplete="current-password"></label>
        <label>Mật khẩu mới <input name="password" type="password" autocomplete="new-password"></label>
        <button class="buy" type="submit">Lưu</button>
      </form>
      <p class="note">Để trống mật khẩu mới nếu chỉ đổi tên.</p>"""
    return admin_page("Trang cá nhân", "Trang cá nhân", inner, "profile")


def save_profile(conn, user, fields):
    name = (fields.get("name") or [""])[0].strip()
    current = (fields.get("current") or [""])[0]
    new = (fields.get("password") or [""])[0]
    if len(name) < 2:
        return "Tên cần ít nhất 2 ký tự."
    if new:
        stored = conn.execute("SELECT password_hash FROM app_users WHERE id=%s", (user["id"],)).fetchone()
        if not current or not stored or not check_password(current, stored[0]):
            return "Mật khẩu hiện tại chưa đúng."
        if len(new) < 6:
            return "Mật khẩu mới cần ít nhất 6 ký tự."
        conn.execute(
            "UPDATE app_users SET name=%s, password_hash=%s WHERE id=%s",
            (name, hash_password(new), user["id"]),
        )
    else:
        conn.execute("UPDATE app_users SET name=%s WHERE id=%s", (name, user["id"]))
    return ""


def render_admin_form(product=None, error=""):
    product = product or {
        "id": "", "name": "", "brand": "", "category": "phone", "price": "",
        "stock": 0, "description": "", "images": [],
    }
    options = "".join(
        f'<option value="{esc(key)}"{" selected" if key == product["category"] else ""}>{esc(label)}</option>'
        for key, label in category_pairs()
    )
    action = f'/admin/{product["id"]}' if product["id"] else "/admin/new"
    message = f'<p class="note">{esc(error)}</p>' if error else ""
    photos = "".join(
        f'<img src="{esc(url)}" alt="{esc(alt or product["name"])}">'
        for url, alt in (product.get("images") or [])[:8]
    )
    photo_block = f'<div class="admin-photos">{photos}</div>' if photos else ""
    back = admin_list_href(product.get("category") or "") if product.get("id") else "/admin/products"
    inner = f"""{message}
      {photo_block}
      <form class="auth-form" method="post" action="{action}">
        <label>Tên <input name="name" value="{esc(product["name"])}" required></label>
        <label>Hãng <input name="brand" value="{esc(product["brand"])}"></label>
        <label>Nhóm <select name="category">{options}</select></label>
        <label>Giá (đồng) <input name="price" inputmode="numeric" value="{esc(product["price"])}" required></label>
        <label>Tồn kho <input name="stock" inputmode="numeric" value="{esc(product.get("stock", 0))}" required></label>
        <label>Mô tả <input name="description" value="{esc(product["description"])}"></label>
        <button class="buy" type="submit">Lưu</button>
      </form>
      <p><a class="more" href="{back}">Về danh sách</a></p>"""
    heading = "Sửa sản phẩm" if product["id"] else "Thêm sản phẩm"
    return admin_page(heading, heading, inner, "products")


def save_product(conn, fields, product_id=None):
    name = (fields.get("name") or [""])[0].strip()
    brand = (fields.get("brand") or [""])[0].strip() or None
    category = (fields.get("category") or ["phone"])[0]
    price = (fields.get("price") or [""])[0].replace(".", "").replace(",", "")
    description = (fields.get("description") or [""])[0].strip() or None
    stock_raw = (fields.get("stock") or ["0"])[0].strip()
    if category not in category_map() or not name or not price.isdigit() or not stock_raw.isdigit():
        return None, "Nhập tên, nhóm, giá và tồn kho bằng số."
    stock = int(stock_raw)
    if product_id:
        conn.execute(
            """UPDATE products SET name=%s, brand=%s, category=%s, price_vnd=%s, stock=%s, description=%s, is_live_catalog=true
               WHERE source_product_id=%s""",
            (name, brand, category, int(price), stock, description, product_id),
        )
        return product_id, ""
    new_id = conn.execute("SELECT coalesce(max(source_product_id), 0) FROM products").fetchone()[0]
    new_id = new_id + 1 if new_id >= 9_000_000_000 else 9_000_000_000
    conn.execute(
        """INSERT INTO products(source_product_id, category, name, brand, description, url, price_vnd, stock, is_live_catalog)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,true)""",
        (new_id, category, name, brand, description, f"https://form.local/catalog/{new_id}", int(price), stock),
    )
    return new_id, ""


def find_catalog_product(conn, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        return conn.execute(
            "SELECT source_product_id, name, price_vnd FROM products WHERE source_product_id=%s",
            (int(text),),
        ).fetchone()
    rows = conn.execute(
        """
        SELECT source_product_id, name, price_vnd FROM products
        WHERE is_live_catalog AND name ILIKE %s
        ORDER BY price_vnd DESC NULLS LAST LIMIT 2
        """,
        (f"%{text.replace('%', '').replace('_', '')[:80]}%",),
    ).fetchall()
    return rows[0] if len(rows) == 1 else None


def render_review_form(review=None, error=""):
    review = review or {"product_id": "", "review_index": "", "author": "", "rating": "5", "body": "", "product": ""}
    if review["review_index"] != "":
        action = f'/admin/reviews/{review["product_id"]}/{review["review_index"]}'
        product_field = f'<label>Sản phẩm <input value="{esc(review["product"])}" disabled></label>'
    else:
        action = "/admin/reviews/new"
        product_field = '<label>Mã hoặc tên sản phẩm <input name="product" required></label>'
    inner = f"""{admin_note(error)}
    <form class="auth-form" method="post" action="{action}">
      {product_field}
      <label>Người viết <input name="author" value="{esc(review["author"])}" required></label>
      <label>Điểm <input name="rating" inputmode="decimal" min="1" max="5" step="0.5" value="{esc(review["rating"])}" required></label>
      <label>Nội dung <textarea name="body" required>{esc(review["body"])}</textarea></label>
      <button class="buy" type="submit">Lưu</button>
    </form>
    <p><a class="more" href="/admin/reviews">Về đánh giá</a></p>"""
    heading = "Sửa đánh giá" if review["review_index"] != "" else "Thêm đánh giá"
    return admin_page(heading, heading, inner, "reviews")


def save_review(conn, fields, product_id=None, review_index=None):
    author = (fields.get("author") or [""])[0].strip()
    body = (fields.get("body") or [""])[0].strip()
    rating = (fields.get("rating") or [""])[0].replace(",", ".")
    if len(author) < 2 or not body:
        return "Nhập người viết và nội dung."
    try:
        score = float(rating)
    except ValueError:
        return "Điểm phải là số từ 1 đến 5."
    if score < 1 or score > 5:
        return "Điểm phải là số từ 1 đến 5."
    if product_id is None:
        product = find_catalog_product(conn, (fields.get("product") or [""])[0])
        if not product:
            return "Không thấy đúng một sản phẩm. Nhập mã hoặc tên đầy đủ hơn."
        product_id = product[0]
    if review_index is None:
        review_index = conn.execute(
            "SELECT coalesce(max(review_index), -1) + 1 FROM product_reviews WHERE product_id=%s",
            (product_id,),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO product_reviews(product_id, review_index, author_name, rating_value, review_body, published_at_text)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (product_id, review_index, author, score, body, "Quản trị"),
        )
    else:
        conn.execute(
            """UPDATE product_reviews SET author_name=%s, rating_value=%s, review_body=%s
               WHERE product_id=%s AND review_index=%s""",
            (author, score, body, product_id, review_index),
        )
    return ""


def save_account(conn, fields, user_id=None):
    name = (fields.get("name") or [""])[0].strip()
    email = (fields.get("email") or [""])[0].strip().lower()
    password = (fields.get("password") or [""])[0]
    role = (fields.get("role") or ["customer"])[0]
    if role not in ("admin", "customer"):
        role = "customer"
    if len(name) < 2 or "@" not in email:
        return "Nhập tên và email hợp lệ."
    if password and len(password) < 6:
        return "Mật khẩu cần ít nhất 6 ký tự."
    if user_id is None and len(password) < 6:
        return "Mật khẩu cần ít nhất 6 ký tự."
    taken = conn.execute("SELECT id FROM app_users WHERE email=%s", (email,)).fetchone()
    if taken and (user_id is None or taken[0] != user_id):
        return "Email này đã có tài khoản."
    if user_id:
        current = conn.execute("SELECT role FROM app_users WHERE id=%s", (user_id,)).fetchone()
        if current and current[0] == "admin" and role != "admin":
            others = conn.execute(
                "SELECT count(*) FROM app_users WHERE role='admin' AND id<>%s", (user_id,)
            ).fetchone()[0]
            if others < 1:
                return "Cần giữ ít nhất một tài khoản quản trị."
        if password:
            conn.execute(
                "UPDATE app_users SET name=%s, email=%s, role=%s, password_hash=%s WHERE id=%s",
                (name, email, role, hash_password(password), user_id),
            )
        else:
            conn.execute(
                "UPDATE app_users SET name=%s, email=%s, role=%s WHERE id=%s",
                (name, email, role, user_id),
            )
        return ""
    conn.execute(
        "INSERT INTO app_users(email, name, password_hash, role) VALUES (%s,%s,%s,%s)",
        (email, name, hash_password(password), role),
    )
    return ""


def delete_account(conn, user_id, actor_id):
    if user_id == actor_id:
        return "Không xóa tài khoản đang đăng nhập."
    row = conn.execute("SELECT role FROM app_users WHERE id=%s", (user_id,)).fetchone()
    if not row:
        return ""
    if row[0] == "admin":
        others = conn.execute(
            "SELECT count(*) FROM app_users WHERE role='admin' AND id<>%s", (user_id,)
        ).fetchone()[0]
        if others < 1:
            return "Cần giữ ít nhất một tài khoản quản trị."
    orders = conn.execute("SELECT count(*) FROM orders WHERE user_id=%s", (user_id,)).fetchone()[0]
    if orders:
        return "Tài khoản còn đơn hàng. Hãy xóa đơn trước."
    conn.execute("DELETE FROM app_users WHERE id=%s", (user_id,))
    return ""


def create_admin_order(conn, fields):
    user_raw = (fields.get("user_id") or [""])[0]
    qty_raw = (fields.get("qty") or ["1"])[0]
    if not user_raw.isdigit() or not qty_raw.isdigit():
        return "Chọn khách và số lượng."
    qty = max(1, min(5, int(qty_raw)))
    account = conn.execute("SELECT id FROM app_users WHERE id=%s", (int(user_raw),)).fetchone()
    product = find_catalog_product(conn, (fields.get("product") or [""])[0])
    if not account or not product or not product[2]:
        return "Không thấy khách hoặc sản phẩm có giá."
    taken = conn.execute(
        "UPDATE products SET stock = stock - %s WHERE source_product_id=%s AND stock >= %s RETURNING stock",
        (qty, product[0], qty),
    ).fetchone()
    if not taken:
        return "Không đủ tồn kho."
    order_id = conn.execute(
        "INSERT INTO orders(user_id, status, total_vnd) VALUES (%s,'placed',%s) RETURNING id",
        (account[0], int(product[2]) * qty),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO order_items(order_id, product_id, name, unit_price, qty) VALUES (%s,%s,%s,%s,%s)",
        (order_id, product[0], product[1], int(product[2]), qty),
    )
    return ""


def advice_lead(text):
    cleaned = chat_plain(text)
    head, sep, tail = cleaned.partition(":")
    if sep and len(tail.strip()) > 40:
        cleaned = head.strip()
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        if re.search(r"màu (gì|nào|sắc)|chọn màu|muốn màu|màu sắc", sentence.casefold()):
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def chat_plain(text):
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", text or "", flags=re.S)
    cleaned = cleaned.replace("**", "").replace("*", "")
    lines = []
    for line in cleaned.splitlines():
        line = re.sub(r"^\s*\d+\.\s*", "", line).strip(" -")
        if line:
            lines.append(line)
    joined = " ".join(lines)
    intro = re.split(r"\s+\d+\.\s+", joined, maxsplit=1)[0].strip()
    return intro if len(intro) >= 12 else joined


_CHAT_COMPARE_SPECS = (
    "Chip", "RAM", "Bộ nhớ", "Pin", "Sạc", "Màn hình", "Card",
    "Camera sau", "Camera trước", "Camera", "Quay phim",
)


def _compare_diff(values):
    folded = [(value or "").casefold() for value in values]
    if len(set(folded)) <= 1:
        return [False] * len(values)
    counts = {}
    for item in folded:
        counts[item] = counts.get(item, 0) + 1
    top = max(counts.values())
    leaders = [item for item, count in counts.items() if count == top]
    if top > 1 and len(leaders) == 1:
        leader = leaders[0]
        return [item != leader for item in folded]
    return [True] * len(values)


def chat_compare_markup(products):
    """Side-by-side catalog facts for two to four machines in the chat."""
    columns = list(products[:4])
    blank = "—"

    def spec_map(item):
        found = {}
        for spec in item.get("specs") or []:
            name = spec.get("name") or ""
            if name and name not in found:
                found[name] = (spec.get("value") or "").strip()
        return found

    maps = [spec_map(item) for item in columns]
    heads = []
    for item in columns:
        image = shown_image(item.get("image_url"))
        title = display_name(item.get("name") or "")
        if item.get("color_name"):
            title += f" màu {item['color_name']}"
        photo = f'<img src="{esc(image)}" alt="">' if image else '<span class="chat-compare-photo"></span>'
        heads.append(
            f'<th scope="col"><a class="chat-compare-product" href="/p/{int(item["product_id"])}">'
            f'{photo}<strong>{esc(title)}</strong></a></th>'
        )

    def add_row(label, values):
        if all(value == blank for value in values):
            return ""
        cells = []
        for value, on in zip(values, _compare_diff(values)):
            mark = ' class="is-diff"' if on else ""
            cells.append(f"<td{mark}>{esc(value)}</td>")
        return f'<tr><th scope="row">{esc(label)}</th>{"".join(cells)}</tr>'

    rows = [
        add_row("Giá", [money(item.get("price")) for item in columns]),
        add_row("Tồn", [f"Còn {int(item.get('stock') or 0)}" for item in columns]),
    ]
    names = list(_CHAT_COMPARE_SPECS)
    for bag in maps:
        for name in bag:
            if name not in names:
                names.append(name)
    for name in names:
        rows.append(add_row(name, [bag.get(name) or blank for bag in maps]))
    actions = []
    for item in columns:
        actions.append(
            '<td><div class="ctas">'
            f'<a class="buy" href="/p/{int(item["product_id"])}">Xem chi tiết</a>'
            '<form method="post" action="/tro-ly">'
            '<input type="hidden" name="action" value="checkout">'
            f'<input type="hidden" name="product_id" value="{int(item["product_id"])}">'
            f'<input type="hidden" name="color" value="{esc(item.get("color_name") or "")}">'
            '<button class="order-help" type="submit">Đặt giúp tôi</button></form></div></td>'
        )
    rows.append(f'<tr class="chat-compare-buy"><th scope="row"></th>{"".join(actions)}</tr>')
    count = len(columns)
    body = "".join(row for row in rows if row)
    return (
        f'<div class="chat-compare cols-{count}">'
        f'<table><caption>So sánh {count} máy</caption>'
        f'<thead><tr><th scope="col"></th>{"".join(heads)}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )


def advice_cards(products):
    cards = []
    for item in products:
        image = shown_image(item.get("image_url"))
        photo = f'<img src="{esc(image)}" alt="{esc(item.get("color_name") or item["name"])}">' if image else '<span class="order-thumb"></span>'
        specs = "".join(f'<li>{esc(spec["name"])}: {esc(spec["value"])}</li>' for spec in item["specs"])
        title = esc(display_name(item["name"]))
        if item.get("color_name"):
            title += f" màu {esc(item['color_name'])}"
        reason = (item.get("reason") or "").strip()
        advice = f'<p class="advice-reason">{esc(reason)}</p>' if reason else ""
        cards.append(
            f'<article class="advice-card">'
            f'<a class="family-photo" href="/p/{item["product_id"]}">{photo}</a>'
            f'<h3>{title}</h3>'
            f'<ul class="advice-specs">{specs}</ul>'
            f'<p class="family-price">{esc(money(item["price"]))}<span>Còn {item["stock"]}</span></p>'
            f'<div class="ctas"><a class="buy" href="/p/{item["product_id"]}">Xem chi tiết</a>'
            f'<form method="post" action="/tro-ly">'
            f'<input type="hidden" name="action" value="checkout">'
            f'<input type="hidden" name="product_id" value="{item["product_id"]}">'
            f'<input type="hidden" name="color" value="{esc(item.get("color_name") or "")}">'
            f'<button class="order-help" type="submit">Đặt giúp tôi</button></form></div>'
            f'{advice}</article>'
        )
    return "".join(cards)


_BRAND_CHIPS = re.compile(
    r'<div class="brand-chips">(?:<button type="button" class="brand-chip" data-q="[^"]*">[^<]*</button>)*</div>'
)


def peel_brand_chips(text):
    """Keep generated brand chips as markup. Escape everything else with the lead."""
    match = _BRAND_CHIPS.search(text or "")
    if not match:
        return text or "", ""
    prose = ((text or "")[:match.start()] + (text or "")[match.end():]).strip()
    return prose, match.group(0)


def warranty_markup(spoken):
    """Show each retrieved passage as a citation. Do not add terms that were not retrieved."""
    passages = [
        item for item in (spoken.get("passages") or [])[:3]
        if (item.get("text") or "").strip()
    ]
    if not passages:
        prose = chat_plain(spoken.get("text") or "")
        if not prose:
            return '<p class="note">Mình chưa có câu trả lời.</p>'
        return f'<p class="chat-lead">{esc(prose)}</p>'
    blocks = []
    for item in passages:
        brand = (item.get("brand") or "").strip()
        title = (item.get("title") or "Điều khoản").strip()
        heading = " · ".join(part for part in (brand, title) if part)
        source = (item.get("source_url") or "").strip()
        link = ""
        if source.startswith("https://") or source.startswith("http://"):
            link = f'<p class="cite-source">Nguồn: <a href="{esc(source)}">{esc(source)}</a></p>'
        blocks.append(
            '<article class="citation">'
            f'<p class="cite-title">{esc(heading)}</p>'
            f'<blockquote>{esc(item.get("text") or "")}</blockquote>'
            f'{link}</article>'
        )
    return "".join(blocks)


def assistant_advice_markup(spoken):
    """Attach each model explanation to its matching product card."""
    if spoken.get("tool") == "search_documents" or spoken.get("passages"):
        return warranty_markup(spoken)
    import agent

    prose, chips = peel_brand_chips(spoken.get("text") or "")
    products = spoken.get("products") or []
    reasons = spoken.get("product_reasons") or {}
    if reasons:
        intro = chat_plain(prose)
        notes = reasons
    else:
        intro, notes = agent.split_advice(prose, products)
    shown = []
    for item in products:
        copy = dict(item)
        explanation = notes.get(item.get("product_id"))
        if explanation:
            copy["reason"] = explanation
        elif re.search(r"^Còn \d+ máy", copy.get("reason") or ""):
            copy["reason"] = ""
        shown.append(copy)
    if spoken.get("tool") == "compare_products" and len(shown) >= 2:
        cards = chat_compare_markup(shown)
    else:
        cards = advice_cards(shown) if shown else ""
    note = f'<p class="chat-lead">{esc(intro)}</p>' if intro else ""
    body = note + cards + chips
    return body or '<p class="note">Mình chưa có câu trả lời.</p>'


def assistant_checkout_form(payload, values=None, error=""):
    product = payload["product"]
    values = values or payload["fields"]
    start, end = delivery_bounds()
    slot_options = "".join(
        f'<option value="{esc(key)}"{" selected" if key == values.get("deliver_slot") else ""}>{esc(label)}</option>'
        for key, label in DELIVER_SLOTS
    )
    day = values.get("deliver_on") or start.isoformat()
    image = shown_image(product.get("image_url"))
    photo = f'<img src="{esc(image)}" alt="">' if image else ""
    colors = [color for color in (product.get("colors") or []) if color.get("color_name")]
    if len(colors) > 1:
        chosen = values.get("color") or product.get("color_name") or ""
        color_options = "".join(
            f'<option value="{esc(color["color_name"])}"{" selected" if color["color_name"] == chosen else ""}>{esc(color["color_name"])}</option>'
            for color in colors
        )
        color_field = f'<label>Màu <select name="color">{color_options}</select></label>'
    else:
        only = colors[0]["color_name"] if colors else (product.get("color_name") or "")
        color_field = f'<input type="hidden" name="color" value="{esc(only)}">'
    color_line = f" màu {esc(product['color_name'])}" if product.get("color_name") and len(colors) <= 1 else ""
    return f"""{admin_note(error)}
    <article class="advice-card">
      <p>Đặt {esc(display_name(product["name"]))}{color_line}. Còn {product["stock"]} máy.</p>
      <a class="family-photo" href="/p/{product["product_id"]}">{photo}</a>
      <form class="auth-form" method="post" action="/tro-ly">
        <input type="hidden" name="action" value="place">
        <input type="hidden" name="product_id" value="{product["product_id"]}">
        {color_field}
        <input type="hidden" name="qty" value="{payload["qty"]}">
        <label>Tên người nhận <input name="name" value="{esc(values.get("name", ""))}" required></label>
        <label>Email <input name="email" type="email" value="{esc(values.get("email", ""))}" required></label>
        <label>Số điện thoại <input name="phone" inputmode="tel" value="{esc(values.get("phone", ""))}" required></label>
        <label>Địa chỉ <textarea name="address" required>{esc(values.get("address", ""))}</textarea></label>
        <label>Ngày nhận <input name="deliver_on" type="date" min="{start.isoformat()}" max="{end.isoformat()}" value="{esc(day)}" required></label>
        <label>Buổi nhận <select name="deliver_slot">{slot_options}</select></label>
        {pay_fields(values)}
        <p class="note">{esc(payload["note"])}</p>
        <button class="buy" type="submit">Đặt hàng</button>
      </form>
    </article>"""


def assistant_receipt(order, invoice_note=""):
    """The confirmation the shopper sees in the chat. Same facts as the invoice email, no bank code."""
    slot = dict(DELIVER_SLOTS).get(order["deliver_slot"], order["deliver_slot"])
    pay = "Thanh toán khi nhận hàng" if (order.get("pay_method") or "cod") != "qr" else "Chuyển khoản trên máy này"
    note = invoice_note or invoice.invoice_status_note(None, "")
    color = f" màu {order['color_name']}" if order.get("color_name") else ""
    title = display_name(order["name"]) + color
    return (
        '<article class="chat-invoice">'
        '<header><p>Octopus Store</p>'
        f'<h3>Hoá đơn đơn hàng #{int(order["order_id"])}</h3></header>'
        '<p>Phiếu tham chiếu. Chưa trừ tiền thật.</p>'
        '<dl>'
        f'<div><dt>Nhận hàng</dt><dd>{esc(order.get("deliver_on") or "")} · {esc(slot)}</dd></div>'
        f'<div><dt>Thanh toán</dt><dd>{esc(pay)}</dd></div>'
        f'<div><dt>Người nhận</dt><dd>{esc(order.get("ship_name") or "")}</dd></div>'
        f'<div><dt>Điện thoại</dt><dd>{esc(order.get("ship_phone") or "")}</dd></div>'
        f'<div><dt>Địa chỉ</dt><dd>{esc(order.get("ship_address") or "")}</dd></div>'
        '</dl>'
        '<table><thead><tr><th>Sản phẩm</th><th>Số lượng</th><th>Thành tiền</th></tr></thead>'
        f'<tbody><tr><td>{esc(title)}</td><td>× {int(order.get("qty") or 0)}</td>'
        f'<td>{esc(money(order.get("total")))}</td></tr></tbody></table>'
        f'<p class="invoice-total"><span>Tổng</span><strong>{esc(money(order.get("total")))}</strong></p>'
        f'<p class="note">{esc(note)}</p>'
        f'<p><a class="buy" href="/orders/{int(order["order_id"])}">Xem phiếu</a></p>'
        '</article>'
    )


def order_track_markup(orders):
    if not orders:
        return '<p class="note">Bạn chưa có đơn nào.</p>'
    cards = []
    for order in orders:
        when = ""
        if order.get("deliver_on"):
            slot = order.get("deliver_slot") or ""
            when = f' · nhận {esc(order["deliver_on"])}' + (f" {esc(slot)}" if slot else "")
        cards.append(
            f'<article class="advice-card"><p>Đơn #{order["order_id"]} · {esc(order["status"])} · {esc(money(order["total"]))}</p>'
            f'<p class="note">{esc(order["items"])}<br>{esc(order["pay"])}{when}</p>'
            f'<p><a class="buy" href="/orders/{order["order_id"]}">Xem phiếu</a></p></article>'
        )
    return "".join(cards)


def assistant_panel(inner, question=""):
    return f"""<div class="assistant-sheet">
      <div class="thread">{inner}</div>
      <form class="auth-form" method="post" action="/tro-ly">
        <label>Bạn cần máy gì? <textarea name="q" placeholder="Điện thoại màu xanh, chơi game tốt, dưới 50 triệu">{esc(question)}</textarea></label>
        <button class="buy" type="submit">Hỏi</button>
      </form>
    </div>"""


def render_assistant(inner, question=""):
    body = f"""<main id="content" class="page"><div id="nav-sentinel"></div>
      <h1>Trợ lý</h1>
      {assistant_panel(inner, question)}
    </main>"""
    return layout("Trợ lý", body, 0)


class Handler(BaseHTTPRequestHandler):
    server_version = "OctopusStore/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path.startswith("/cutout/"):
                return self.serve_cutout(path[len("/cutout/"):])
            if path.startswith("/media/"):
                return self.serve_media(path[len("/media/"):])
            if path in ("/favicon.ico", "/favicon.svg"):
                return self.serve_static("favicon.svg")
            if path.startswith("/frontend/"):
                return self.serve_static(path[len("/frontend/"):])
            bag = parse_bag(self.headers.get("Cookie"))
            with connect() as conn:
                ensure_commerce(conn)
                bind_categories(conn)
                CURRENT_USER.set(user_from_cookie(conn, self.headers.get("Cookie")))
                user = CURRENT_USER.get()
                if path == "/api/suggest":
                    return self.send_json(suggest_products(conn, (query.get("q") or [""])[0]))
                if path == "/":
                    return self.send_html(render_home(conn, sum(qty for _, qty in bag)))
                if path == "/login":
                    if user:
                        return self.redirect("/")
                    return self.send_html(auth_page("Đăng nhập", "Đăng nhập", "/login", LOGIN_NOTE))
                if path == "/register":
                    if user:
                        return self.redirect("/")
                    return self.send_html(auth_page("Đăng ký", "Đăng ký", "/register", "Tạo tài khoản để đặt hàng."))
                if path == "/orders":
                    if not user:
                        return self.redirect("/login")
                    return self.send_html(render_orders(conn, user))
                if path.startswith("/orders/") and path.endswith("/pay-qr"):
                    if not user:
                        return self.redirect("/login")
                    ident = path[len("/orders/"):-len("/pay-qr")].strip("/")
                    if not ident.isdigit():
                        return self.send_html(self.missing(), 404)
                    return self.send_pay_qr(conn, user, int(ident))
                if path.startswith("/orders/") and path[len("/orders/"):].isdigit():
                    if not user:
                        return self.redirect("/login")
                    page = render_receipt(conn, user, int(path[len("/orders/"):]))
                    if page is None:
                        return self.send_html(self.missing(), 404)
                    return self.send_html(page)
                if path == "/gioi-thieu":
                    return self.send_html(render_about(sum(qty for _, qty in bag)))
                if path == "/lien-he":
                    note = "Đã gửi. Quản trị sẽ đọc yêu cầu này." if (query.get("sent") or [""])[0] == "1" else ""
                    return self.send_html(render_contact(user, message=note, bag_count=sum(qty for _, qty in bag)))
                if path == "/account":
                    if not user:
                        return self.redirect("/login")
                    message = "Đã lưu thông tin." if (query.get("saved") or [""])[0] == "1" else ""
                    return self.send_html(render_account(user, message))
                if path in ("/trace", "/tracing"):
                    if not user:
                        return self.redirect("/login")
                    if user["role"] != "admin":
                        return self.send_html(render_tracing_denied(), 403)
                    target = "/admin/tracing"
                    if parsed.query:
                        target += "?" + parsed.query
                    return self.redirect(target)
                if path == "/tracing/rev":
                    if not user:
                        return self.send_text("", 401)
                    if user["role"] != "admin":
                        return self.send_text("", 403)
                    return self.send_text(trace_revision(user.get("token") or ""))
                if path == "/tro-ly":
                    if not user:
                        return self.redirect("/login")
                    panel = (query.get("panel") or [""])[0] == "1"
                    welcome = '<p class="note">Nói nhu cầu và tầm giá. Mình tìm máy còn hàng. Màu chỉ hỏi khi đặt.</p>'
                    if panel:
                        return self.send_html(assistant_panel(welcome))
                    return self.send_html(render_assistant(welcome))
                if path == "/checkout":
                    if not user:
                        return self.redirect("/login")
                    return self.send_html(render_checkout(conn, user, bag))
                if path == "/admin":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin(conn))
                if path == "/admin/products":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    text = (query.get("q") or [""])[0].strip()[:80]
                    page_no = (query.get("page") or ["1"])[0]
                    group = (query.get("group") or [""])[0]
                    return self.send_html(render_admin_products(conn, text, int(page_no) if page_no.isdigit() else 1, group))
                note = (query.get("note") or [""])[0][:180]
                if path == "/admin/orders":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_orders(conn, note))
                if path == "/admin/support":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_support(conn))
                if path == "/admin/categories/new":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_category_form())
                if path.startswith("/admin/categories/") and path.count("/") == 3:
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    slug = path.split("/")[-1]
                    label = category_map().get(slug)
                    if not label:
                        return self.send_html(self.missing(), 404)
                    return self.send_html(render_category_form({"slug": slug, "label": label}))
                if path == "/admin/categories":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_categories(conn, note))
                if path == "/admin/users/new":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_account_form())
                if path.startswith("/admin/users/") and path.count("/") == 3 and path.split("/")[-1].isdigit():
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    account = conn.execute(
                        "SELECT id, name, email, role FROM app_users WHERE id=%s",
                        (int(path.split("/")[-1]),),
                    ).fetchone()
                    if not account:
                        return self.send_html(self.missing(), 404)
                    return self.send_html(render_account_form({
                        "id": account[0], "name": account[1], "email": account[2], "role": account[3],
                    }))
                if path == "/admin/users":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_users(conn, note))
                if path == "/admin/reviews/new":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_review_form())
                if path.startswith("/admin/reviews/") and path.count("/") == 4:
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    product_id, index = path.split("/")[-2:]
                    if product_id.isdigit() and index.isdigit():
                        review = conn.execute(
                            """
                            SELECT r.product_id, r.review_index, r.author_name, r.rating_value, r.review_body, p.name
                            FROM product_reviews r
                            JOIN products p ON p.source_product_id = r.product_id
                            WHERE r.product_id=%s AND r.review_index=%s
                            """,
                            (int(product_id), int(index)),
                        ).fetchone()
                        if review:
                            return self.send_html(render_review_form({
                                "product_id": review[0], "review_index": review[1],
                                "author": review[2] or "", "rating": review[3] or 5,
                                "body": review[4] or "", "product": display_name(review[5]),
                            }))
                    return self.send_html(self.missing(), 404)
                if path == "/admin/reviews":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    text = (query.get("q") or [""])[0].strip()[:80]
                    page_no = (query.get("page") or ["1"])[0]
                    return self.send_html(render_admin_reviews(conn, text, int(page_no) if page_no.isdigit() else 1, note))
                if path == "/admin/stats":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_stats(conn))
                if path == "/admin/documents":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_documents(conn, note))
                if path == "/admin/assistant":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    messages = load_chat(conn, user["id"], admin_chat_token(user), 40)
                    return self.send_html(render_admin_assistant(messages))
                if path == "/admin/profile":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    message = "Đã lưu." if (query.get("saved") or [""])[0] == "1" else ""
                    return self.send_html(render_admin_profile(user, message))
                if path == "/admin/tracing":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_trace(user, query))
                if path == "/admin/new":
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    return self.send_html(render_admin_form())
                if path.startswith("/admin/") and path[len("/admin/"):].isdigit():
                    if not user or user["role"] != "admin":
                        return self.redirect("/login")
                    product = self.load_admin_product(conn, int(path[len("/admin/"):]))
                    if not product:
                        return self.send_html(self.missing(), 404)
                    return self.send_html(render_admin_form(product))
                if path == "/shop":
                    return self.send_html(render_directory(conn, sum(qty for _, qty in bag)))
                if path.startswith("/c/"):
                    bits = [bit for bit in path[len("/c/"):].split("/") if bit]
                    if not bits or bits[0] not in category_map() or len(bits) > 2:
                        return self.send_html(self.missing(), 404)
                    page = self.shop(conn, bag, bits[0], query, bits[1] if len(bits) == 2 else None)
                    if page is None:
                        return self.send_html(self.missing(), 404)
                    return self.send_html(page)
                if path.startswith("/p/"):
                    ident = path[len("/p/"):]
                    if not ident.isdigit():
                        return self.send_html(self.missing(), 404)
                    notice = "Đã gửi đánh giá. Bài sẽ hiện sau khi được duyệt." if (query.get("review") or [""])[0] == "1" else ""
                    page, status = render_product(conn, sum(qty for _, qty in bag), int(ident), notice)
                    return self.send_html(page, status)
                if path == "/so-sanh":
                    raw_ids = []
                    for item in query.get("id") or []:
                        if item.isdigit():
                            raw_ids.append(int(item))
                    return self.send_html(render_compare(conn, sum(qty for _, qty in bag), raw_ids))
                if path == "/bag":
                    return self.send_html(render_bag(conn, bag))
            self.send_html(self.missing(), 404)
        except Exception as exc:
            detail = esc(exc) if DEMO_MODE else "Vui lòng thử lại sau."
            self.send_html(layout("Lỗi", f'<main id="content" class="page"><h1>Không đọc được danh mục.</h1><p class="note">{detail}</p></main>', 0), 500)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if PUBLIC_ORIGINS and (origin not in PUBLIC_ORIGINS or origin != f"https://{self.headers.get('Host')}"):
            return self.send_error(403, "Forbidden")
        path = urlparse(self.path).path
        if path == "/admin/documents":
            return self.handle_document_post()
        length = int(self.headers.get("Content-Length") or 0)
        fields = parse_qs(self.rfile.read(min(length, 20000)).decode("utf-8", "replace"))
        bag = parse_bag(self.headers.get("Cookie"))
        with connect() as conn:
            ensure_commerce(conn)
            bind_categories(conn)
            user = user_from_cookie(conn, self.headers.get("Cookie"))
            CURRENT_USER.set(user)
            if path == "/register":
                return self.handle_register(conn, fields)
            if path == "/login":
                return self.handle_login(conn, fields)
            if path == "/account":
                if not user:
                    return self.redirect("/login")
                posted, error = save_customer_account(conn, user, fields)
                if error:
                    return self.send_html(render_account(posted, error=error), 400)
                return self.redirect("/account?saved=1")
            if path == "/logout":
                if user and user.get("token"):
                    clear_chat(conn, user["id"], user["token"])
                    conn.execute("DELETE FROM app_sessions WHERE token=%s", (user["token"],))
                return self.expire_session()
            if path == "/lien-he":
                posted, error = save_support(conn, user, fields)
                if error:
                    return self.send_html(render_contact(user, posted, error=error), 400)
                return self.redirect("/lien-he?sent=1")
            if path.startswith("/p/") and path.endswith("/review"):
                if not user:
                    return self.redirect("/login")
                ident = path[len("/p/"):-len("/review")].strip("/")
                if not ident.isdigit():
                    return self.send_html(self.missing(), 404)
                error = save_customer_review(conn, user, int(ident), fields)
                if error:
                    page, _status = render_product(conn, sum(qty for _, qty in bag), int(ident), error)
                    return self.send_html(page, 400)
                return self.redirect(f"/p/{ident}?review=1")
            if path.startswith("/orders/") and path.endswith("/pay-check"):
                if not user:
                    return self.redirect("/login")
                ident = path[len("/orders/"):-len("/pay-check")].strip("/")
                if not ident.isdigit():
                    return self.send_html(self.missing(), 404)
                note, status = self.settle_transfer(conn, user, int(ident))
                page = render_receipt(conn, user, int(ident), note)
                if page is None:
                    return self.send_html(self.missing(), 404)
                return self.send_html(page, status)
            if path == "/checkout":
                return self.handle_checkout(conn, user, bag, fields)
            if path == "/tro-ly":
                return self.handle_assistant(conn, user, fields)
            if path == "/admin/assistant":
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                token = admin_chat_token(user)
                if (fields.get("action") or [""])[0] == "clear":
                    clear_chat(conn, user["id"], token)
                    return self.send_html(render_admin_assistant())
                question = (fields.get("q") or [""])[0].strip()
                messages = load_chat(conn, user["id"], token, 40)
                if not question:
                    return self.send_html(render_admin_assistant(messages, "Nhập một câu hỏi."), 400)
                history = messages[-8:]
                answer, note = ask_assistant(conn, question, history)
                save_chat(conn, user["id"], token, "user", question)
                save_chat(conn, user["id"], token, "bot", answer)
                messages = load_chat(conn, user["id"], token, 40)
                return self.send_html(render_admin_assistant(messages, note))
            if path == "/admin/profile":
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = save_profile(conn, user, fields)
                if error:
                    posted = dict(user)
                    posted["name"] = (fields.get("name") or [user["name"]])[0]
                    return self.send_html(render_admin_profile(posted, error=error), 400)
                return self.redirect("/admin/profile?saved=1")
            if path == "/admin/orders/new":
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = create_admin_order(conn, fields)
                return self.redirect("/admin/orders" + (f"?note={quote(error)}" if error else ""))
            if path.startswith("/admin/orders/") and path.endswith("/delete") and path.split("/")[-2].isdigit():
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                conn.execute("DELETE FROM orders WHERE id=%s", (int(path.split("/")[-2]),))
                return self.redirect("/admin/orders")
            if path.startswith("/admin/orders/") and path.count("/") == 3 and path.split("/")[-1].isdigit():
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                status = (fields.get("status") or ["placed"])[0]
                if status not in ORDER_LABEL:
                    status = "placed"
                conn.execute("UPDATE orders SET status=%s WHERE id=%s", (status, int(path.split("/")[-1])))
                return self.redirect("/admin/orders")
            if path == "/admin/categories/new":
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = save_category(conn, fields)
                if error:
                    return self.send_html(render_category_form(error=error), 400)
                return self.redirect("/admin/categories")
            if path.startswith("/admin/categories/") and path.endswith("/delete"):
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = delete_category(conn, path.split("/")[-2])
                return self.redirect("/admin/categories" + (f"?note={quote(error)}" if error else ""))
            if path.startswith("/admin/categories/") and path.count("/") == 3:
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                slug = path.split("/")[-1]
                if slug not in category_map():
                    return self.redirect("/admin/categories")
                error = save_category(conn, fields, slug)
                if error:
                    return self.send_html(render_category_form({"slug": slug, "label": (fields.get("label") or [""])[0]}, error), 400)
                return self.redirect("/admin/categories")
            if path == "/admin/users/new":
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = save_account(conn, fields)
                if error:
                    return self.send_html(render_account_form({
                        "id": "", "name": (fields.get("name") or [""])[0],
                        "email": (fields.get("email") or [""])[0],
                        "role": (fields.get("role") or ["customer"])[0],
                    }, error), 400)
                return self.redirect("/admin/users")
            if path.startswith("/admin/users/") and path.endswith("/delete") and path.split("/")[-2].isdigit():
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = delete_account(conn, int(path.split("/")[-2]), user["id"])
                return self.redirect("/admin/users" + (f"?note={quote(error)}" if error else ""))
            if path.startswith("/admin/users/") and path.count("/") == 3 and path.split("/")[-1].isdigit():
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                user_id = int(path.split("/")[-1])
                error = save_account(conn, fields, user_id)
                if error:
                    return self.send_html(render_account_form({
                        "id": user_id, "name": (fields.get("name") or [""])[0],
                        "email": (fields.get("email") or [""])[0],
                        "role": (fields.get("role") or ["customer"])[0],
                    }, error), 400)
                return self.redirect("/admin/users")
            if path == "/admin/reviews/new":
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                error = save_review(conn, fields)
                if error:
                    return self.send_html(render_review_form({
                        "product_id": "", "review_index": "",
                        "author": (fields.get("author") or [""])[0],
                        "rating": (fields.get("rating") or ["5"])[0],
                        "body": (fields.get("body") or [""])[0], "product": "",
                    }, error), 400)
                return self.redirect("/admin/reviews")
            if path.startswith("/admin/reviews/") and path.endswith("/approve"):
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                bits = [bit for bit in path.split("/") if bit]
                if len(bits) == 5 and bits[2].isdigit() and bits[3].isdigit():
                    conn.execute(
                        """
                        UPDATE product_reviews
                        SET approved=true,
                            published_at_text=CASE WHEN published_at_text='Chờ duyệt' THEN to_char(now(), 'DD.MM.YYYY') ELSE published_at_text END
                        WHERE product_id=%s AND review_index=%s
                        """,
                        (int(bits[2]), int(bits[3])),
                    )
                return self.redirect("/admin/reviews")
            if path.startswith("/admin/reviews/") and path.endswith("/delete"):
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                product_id, index = path.split("/")[-3:-1]
                if product_id.isdigit() and index.isdigit():
                    conn.execute(
                        "DELETE FROM product_reviews WHERE product_id=%s AND review_index=%s",
                        (int(product_id), int(index)),
                    )
                return self.redirect("/admin/reviews")
            if path.startswith("/admin/reviews/") and path.count("/") == 4:
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                product_id, index = path.split("/")[-2:]
                if not (product_id.isdigit() and index.isdigit()):
                    return self.redirect("/admin/reviews")
                error = save_review(conn, fields, int(product_id), int(index))
                if error:
                    review = {
                        "product_id": int(product_id), "review_index": int(index),
                        "author": (fields.get("author") or [""])[0],
                        "rating": (fields.get("rating") or [""])[0],
                        "body": (fields.get("body") or [""])[0],
                        "product": "",
                    }
                    return self.send_html(render_review_form(review, error), 400)
                return self.redirect("/admin/reviews")
            if path == "/admin/new" or (path.startswith("/admin/") and path.count("/") == 2 and path.split("/")[-1].isdigit()):
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                product_id = int(path.split("/")[-1]) if path != "/admin/new" else None
                saved, error = save_product(conn, fields, product_id)
                if error:
                    product = self.load_admin_product(conn, product_id) if product_id else None
                    return self.send_html(render_admin_form(product, error), 400)
                category = (fields.get("category") or [""])[0]
                return self.redirect(admin_list_href(category if category in category_map() else ""))
            if path.startswith("/admin/") and path.endswith("/delete") and path.count("/") == 3 and path.split("/")[2].isdigit():
                if not user or user["role"] != "admin":
                    return self.redirect("/login")
                ident = path.split("/")[-2]
                group = (fields.get("group") or [""])[0]
                if ident.isdigit():
                    try:
                        conn.execute("DELETE FROM products WHERE source_product_id=%s", (int(ident),))
                    except Exception:
                        conn.execute("UPDATE products SET is_live_catalog=false WHERE source_product_id=%s", (int(ident),))
                return self.redirect(admin_list_href(group if group in category_map() else ""))
        ident = (fields.get("id") or [""])[0]
        if ident.isdigit() and path in ("/bag/add", "/bag/set"):
            product_id = int(ident)
            mapping = dict(bag)
            if path == "/bag/add":
                mapping[product_id] = min(5, mapping.get(product_id, 0) + 1)
            else:
                qty = (fields.get("qty") or ["1"])[0]
                mapping[product_id] = max(0, min(5, int(qty))) if qty.isdigit() else mapping.get(product_id, 1)
            bag = [(key, value) for key, value in mapping.items() if value > 0]
        self.send_response(303)
        self.send_header("Location", "/bag")
        self.send_header("Set-Cookie", f"bag={dump_bag(bag)}; Path=/; Max-Age=2592000; SameSite=Lax; HttpOnly{COOKIE_SECURE}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_document_post(self):
        from rag.documents import accept_upload, remove_document, requeue
        from rag.settings import MAX_UPLOAD_BYTES
        from rag.upload import parse_multipart

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_response(413)
            self.send_header("Connection", "close")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        raw = self.rfile.read(length)
        with connect() as conn:
            ensure_commerce(conn)
            bind_categories(conn)
            user = user_from_cookie(conn, self.headers.get("Cookie"))
            CURRENT_USER.set(user)
            if not user or user["role"] != "admin":
                return self.redirect("/login")
            content_type = (self.headers.get("Content-Type") or "").lower()
            if "multipart/form-data" in content_type:
                try:
                    fields, files = parse_multipart(raw, self.headers.get("Content-Type") or "")
                except ValueError:
                    return self.send_html(render_admin_documents(conn, "Không đọc được tệp."), 400)
                upload = files.get("file") or {}
                error = accept_upload(
                    conn,
                    user["id"],
                    fields,
                    upload.get("filename") or "",
                    upload.get("data") or b"",
                )
                if error:
                    return self.send_html(render_admin_documents(conn, error), 400)
                return self.redirect("/admin/documents?note=" + quote("Đã đưa vào hàng đợi."))
            fields = parse_qs(raw.decode("utf-8", "replace"))
            action = (fields.get("action") or [""])[0]
            ident = (fields.get("id") or [""])[0]
            if not ident.isdigit():
                return self.redirect("/admin/documents")
            if action == "delete":
                error = remove_document(conn, int(ident))
            elif action == "reindex":
                error = requeue(conn, int(ident))
            else:
                error = ""
            if error:
                return self.redirect("/admin/documents?note=" + quote(error[:180]))
            return self.redirect("/admin/documents")

    def handle_register(self, conn, fields):
        name = (fields.get("name") or [""])[0].strip()
        email = (fields.get("email") or [""])[0].strip().lower()
        password = (fields.get("password") or [""])[0]
        if len(name) < 2 or "@" not in email or len(password) < 6:
            return self.send_html(auth_page("Đăng ký", "Đăng ký", "/register", "Tạo tài khoản để đặt hàng.", "Điền đủ tên, email và mật khẩu từ 6 ký tự."), 400)
        try:
            user_id = conn.execute(
                "INSERT INTO app_users(email, name, password_hash) VALUES (%s,%s,%s) RETURNING id",
                (email, name, hash_password(password)),
            ).fetchone()[0]
        except Exception:
            return self.send_html(auth_page("Đăng ký", "Đăng ký", "/register", "Tạo tài khoản để đặt hàng.", "Email này đã có tài khoản."), 400)
        return self.start_session(conn, user_id, "/")

    def handle_login(self, conn, fields):
        email = (fields.get("email") or [""])[0].strip().lower()
        password = (fields.get("password") or [""])[0]
        row = conn.execute("SELECT id, password_hash FROM app_users WHERE email=%s", (email,)).fetchone()
        if not row or not check_password(password, row[1]):
            return self.send_html(auth_page("Đăng nhập", "Đăng nhập", "/login", LOGIN_NOTE, "Email hoặc mật khẩu chưa đúng."), 400)
        return self.start_session(conn, row[0], "/")

    def handle_assistant(self, conn, user, fields):
        import agent
        if not user:
            return self.redirect("/login")
        panel = (fields.get("panel") or [""])[0] == "1" or self.headers.get("X-Assistant-Panel") == "1"
        def answer(inner, question="", status=200):
            if user and status == 200:
                if action == "checkout":
                    asked = "Đặt giúp tôi"
                elif action == "place":
                    asked = "Đặt hàng"
                else:
                    asked = (fields.get("q") or [""])[0].strip()
                if asked:
                    save_chat(conn, user["id"], user.get("token") or "", "user", asked)
                if inner:
                    save_chat(conn, user["id"], user.get("token") or "", "bot", inner)
            page = inner if panel else render_assistant(inner, question)
            return self.send_html(page, status)
        action = (fields.get("action") or [""])[0]
        if action == "clear":
            clear_chat(conn, user["id"], user.get("token") or "")
            return self.send_html("", 200)
        if action == "checkout":
            product_id = (fields.get("product_id") or [""])[0]
            color = (fields.get("color") or [""])[0]
            if not product_id.isdigit():
                return answer('<p class="note">Chưa chọn được máy để đặt.</p>', status=400)
            payload = agent.get_checkout_requirements(conn, user, int(product_id), color)
            if not payload.get("ok"):
                return answer(f'<p class="note">{esc(payload.get("note") or "")}</p>', status=400)
            return answer(assistant_checkout_form(payload))
        if action == "place":
            product_id = (fields.get("product_id") or [""])[0]
            color = (fields.get("color") or [""])[0]
            shipment, error = read_shipment(fields, user)
            payload = agent.get_checkout_requirements(conn, user, int(product_id), color) if product_id.isdigit() else {"ok": False, "note": "Chưa chọn máy."}
            if error or not payload.get("ok"):
                if payload.get("ok"):
                    return answer(assistant_checkout_form(payload, shipment, error), status=400)
                return answer(f'<p class="note">{esc(payload.get("note") or error)}</p>', status=400)
            result = agent.place_order(conn, user, shipment, int(product_id), color, (fields.get("qty") or ["1"])[0])
            if not result.get("ok"):
                return answer(assistant_checkout_form(payload, shipment, result.get("note")), status=400)
            note = invoice.deliver_invoice(conn, result["order_id"])
            return answer(assistant_receipt(result, note))
        question = (fields.get("q") or [""])[0].strip()
        if not question:
            return answer('<p class="note">Nhập câu hỏi.</p>', status=400)
        prior = load_chat(conn, user["id"], user.get("token") or "", 60)
        failure = "Mình gặp lỗi khi xử lý yêu cầu. Vui lòng thử lại sau."
        try:
            spoken = agent.answer_with_openai(conn, user, question, prior)
        except urllib.error.HTTPError as exc:
            print(f"OpenAI agent HTTP failed: {exc.code}")
            failure = "Dịch vụ tư vấn đang bận hoặc chưa sẵn sàng. Bạn gửi lại tin nhắn sau một lát nhé."
            spoken = None
        except (urllib.error.URLError, ConnectionResetError, ConnectionAbortedError,
                BrokenPipeError, TimeoutError, socket.timeout) as exc:
            print(f"OpenAI agent connection failed: {type(exc).__name__}")
            failure = "Kết nối đến dịch vụ tư vấn bị gián đoạn. Mình đã thử lại; bạn gửi lại tin nhắn sau một lát nhé."
            spoken = None
        except Exception as exc:
            print(f"OpenAI agent failed: {type(exc).__name__}")
            spoken = None
        if spoken is not None:
            remember_trace(user.get("token") or "", {
                "question": question[:500],
                "source": "model",
                "text_from": spoken.get("text_from") or "model",
                "answer": (spoken.get("text") or "")[:800],
                "steps": spoken.get("trace") or [],
            })
            lead = chat_plain(spoken.get("text") or "")
            if spoken.get("checkout"):
                ready = spoken["checkout"]
                if not ready.get("ok"):
                    return answer(f'<p class="note">{esc(ready.get("note") or "Chưa chọn được máy để đặt.")}</p>', question)
                form = assistant_checkout_form(ready)
                return answer(f'<p class="chat-lead">{esc(lead)}</p>{form}' if lead else form)
            if spoken.get("orders") is not None:
                note = f'<p class="chat-lead">{esc(lead)}</p>' if lead else ""
                return answer(note + order_track_markup(spoken["orders"]), question)
            return answer(assistant_advice_markup(spoken), question)
        return answer(f'<p class="note">{esc(failure)}</p>', question)

    def handle_checkout(self, conn, user, bag, fields):
        if not user:
            return self.redirect("/login")
        if not bag:
            return self.redirect("/bag")
        shipment, error = read_shipment(fields, user)
        if error:
            return self.send_html(render_checkout(conn, user, bag, shipment, error), 400)
        ids = [ident for ident, _ in bag]
        rows = conn.execute(
            "SELECT source_product_id, name, price_vnd, stock FROM products WHERE source_product_id = ANY(%s) AND is_live_catalog",
            (ids,),
        ).fetchall()
        found = {row[0]: row for row in rows}
        items = []
        total = 0
        for ident, qty in bag:
            row = found.get(ident)
            if not row or not row[2]:
                continue
            if int(row[3] or 0) < qty:
                return self.send_html(render_checkout(conn, user, bag, shipment, f"Chỉ còn {int(row[3] or 0)} máy {display_name(row[1])}."), 400)
            items.append((ident, row[1], int(row[2]), qty))
            total += int(row[2]) * qty
        if not items:
            return self.redirect("/bag")
        for ident, _name, _price, qty in items:
            taken = conn.execute(
                "UPDATE products SET stock = stock - %s WHERE source_product_id=%s AND stock >= %s RETURNING stock",
                (qty, ident, qty),
            ).fetchone()
            if not taken:
                return self.send_html(render_checkout(conn, user, bag, shipment, "Vừa hết hàng."), 400)
        order_id = conn.execute(
            """INSERT INTO orders(user_id, total_vnd, ship_name, ship_email, ship_phone, ship_address, deliver_on, deliver_slot, pay_method)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                user["id"], total, shipment["name"], shipment["email"], shipment["phone"],
                shipment["address"], shipment["deliver_on"], shipment["deliver_slot"],
                shipment.get("pay_method") or "cod",
            ),
        ).fetchone()[0]
        for ident, name, price, qty in items:
            conn.execute(
                "INSERT INTO order_items(order_id, product_id, name, unit_price, qty) VALUES (%s,%s,%s,%s,%s)",
                (order_id, ident, name, price, qty),
            )
        invoice.deliver_invoice(conn, order_id)
        self.send_response(303)
        self.send_header("Location", f"/orders/{order_id}")
        self.send_header("Set-Cookie", "bag=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def start_session(self, conn, user_id, location):
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO app_sessions(token, user_id) VALUES (%s,%s)", (token, user_id))
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", f"session={token}; Path=/; Max-Age=1209600; SameSite=Lax; HttpOnly{COOKIE_SECURE}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def expire_session(self):
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", "session=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def load_admin_product(self, conn, product_id):
        row = conn.execute(
            "SELECT source_product_id, name, brand, category, price_vnd, stock, description FROM products WHERE source_product_id=%s",
            (product_id,),
        ).fetchone()
        if not row:
            return None
        images = product_images(conn, row[0])
        return {
            "id": row[0], "name": row[1], "brand": row[2] or "", "category": row[3],
            "price": row[4] or "", "stock": row[5] or 0, "description": row[6] or "", "images": images,
        }

    def shop(self, conn, bag, category, query, brand_slug_value=None):
        text = (query.get("q") or [""])[0].strip()[:80]
        sort = (query.get("sort") or ["featured"])[0]
        if sort not in ("featured", "price-asc", "price-desc"):
            sort = "featured"
        page = (query.get("page") or ["1"])[0]
        page_no = int(page) if page.isdigit() else 1
        show_all = (query.get("all") or ["0"])[0] == "1"
        return render_shop(conn, sum(qty for _, qty in bag), category, text, sort, page_no, brand_slug_value, show_all)

    def missing(self):
        return layout("Không thấy", '<main id="content" class="page"><h1>Không thấy trang.</h1><p><a class="more" href="/">Về đầu</a></p></main>', 0)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text, status=200):
        data = (text or "").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_pay_qr(self, conn, user, order_id):
        order = payment.load_payable(conn, order_id)
        if not order or (order["user_id"] != user["id"] and user.get("role") != "admin"):
            return self.send_html(self.missing(), 404)
        if order["pay_method"] != "qr" or order["paid_at"] or not payment.bank_ready():
            return self.send_error(404)
        try:
            data = payment.fetch_vietqr(order["total"], payment.transfer_reference(order_id))
        except RuntimeError:
            return self.send_text("Chưa lấy được mã chuyển khoản.", 502)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            return

    def settle_transfer(self, conn, user, order_id):
        order = payment.load_payable(conn, order_id)
        if not order or (order["user_id"] != user["id"] and user.get("role") != "admin"):
            return "Không thấy đơn.", 404
        if order["pay_method"] != "qr":
            return "Đơn này trả khi nhận hàng.", 400
        if order["paid_at"]:
            return payment.paid_note(order), 200
        try:
            rows = payment.recent_credits()
        except RuntimeError as exc:
            return str(exc), 400
        hit = payment.match_credit(rows, payment.transfer_reference(order_id), order["total"])
        if not hit:
            return "Chưa thấy chuyển khoản khớp mã và số tiền.", 400
        return payment.mark_paid(conn, order, hit), 200

    def send_html(self, page, status=200):
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_cutout(self, name):
        if not re.fullmatch(r"[0-9a-f]{12}\.png", name):
            return self.send_error(404)
        target = (CUTOUT_ROOT / name).resolve()
        if not str(target).startswith(str(CUTOUT_ROOT)):
            return self.send_error(404)
        if not target.is_file():
            remote = COLOR_SOURCES.get(name)
            if remote:
                self.send_response(302)
                self.send_header("Location", remote)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            return self.send_error(404)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            return

    def serve_media(self, rel):
        rel = rel.split("?", 1)[0]
        if not re.fullmatch(r"(phone|laptop|headphones|tablet|smartwatch)/\d+/[\w.-]+", rel):
            return self.send_error(404)
        target = (MEDIA_ROOT / rel).resolve()
        if not str(target).startswith(str(MEDIA_ROOT)) or not target.is_file():
            return self.send_error(404)
        kind = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif", ".avif": "image/avif"}.get(target.suffix.lower(), "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, name):
        files = {
            "store.css": "text/css; charset=utf-8",
            "store.js": "text/javascript; charset=utf-8",
            "favicon.svg": "image/svg+xml",
            "assistant-robot.jpg": "image/jpeg",
            "logo.png": "image/png",
        }
        kind = files.get(name)
        target = STATIC / name
        if kind is None:
            parts = name.split("/")
            root = (STATIC / "agent-robot-avatar").resolve()
            target = (STATIC / name).resolve()
            allowed = (
                parts
                and parts[0] == "agent-robot-avatar"
                and ".." not in parts
                and target.suffix == ".js"
                and target.is_file()
                and str(target).startswith(str(root) + "/")
            )
            if not allowed:
                root = (STATIC / "reasons").resolve()
                allowed = (
                    parts
                    and parts[0] == "reasons"
                    and ".." not in parts
                    and target.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                    and target.is_file()
                    and str(target).startswith(str(root) + "/")
                )
                if not allowed:
                    return self.send_error(404)
                kind = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                }[target.suffix.lower()]
            else:
                kind = "text/javascript; charset=utf-8"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def flush_color_sources():
    with COLOR_SOURCE_LOCK:
        CUTOUT_ROOT.mkdir(parents=True, exist_ok=True)
        (CUTOUT_ROOT / "sources.json").write_text(json.dumps(COLOR_SOURCES))


def prebuild_cutouts():
    try:
        os.nice(12)
    except Exception:
        pass
    try:
        with connect() as conn:
            covers = conn.execute(
                """
                SELECT local_path FROM (
                    SELECT DISTINCT ON (i.product_id) i.local_path, p.category
                    FROM product_images i
                    JOIN products p ON p.source_product_id = i.product_id
                    WHERE p.is_live_catalog AND i.local_path IS NOT NULL
                    ORDER BY i.product_id,
                             CASE i.image_role WHEN 'thumbnail' THEN 0 WHEN 'primary' THEN 1 ELSE 2 END,
                             i.display_order
                ) covers
                ORDER BY CASE category WHEN 'laptop' THEN 0 WHEN 'phone' THEN 1 ELSE 2 END
                """
            ).fetchall()
            colors = conn.execute(
                """
                SELECT image_url FROM (
                    SELECT DISTINCT ON (i.product_id, i.color_name) i.image_url, p.category
                    FROM product_color_images i
                    JOIN products p ON p.source_product_id = i.product_id
                    WHERE p.is_live_catalog AND coalesce(i.image_url, '') <> ''
                      AND i.image_url NOT ILIKE '%%/Kit/%%'
                      AND i.image_url NOT ILIKE '%%tem-%%'
                      AND i.image_url NOT ILIKE '%%-glr-%%'
                    ORDER BY i.product_id, i.color_name,
                             CASE
                               WHEN i.image_url ILIKE '%%/Kit/%%' OR i.image_url ILIKE '%%tem-%%' OR i.image_url ILIKE '%%-glr-%%' THEN 1
                               ELSE 0
                             END,
                             i.display_order
                ) colors
                ORDER BY CASE category WHEN 'phone' THEN 0 ELSE 1 END
                """
            ).fetchall()
    except Exception as exc:
        print(f"cutout prebuild không đọc được danh sách: {type(exc).__name__}", flush=True)
        return
    local_jobs = []
    for (path,) in covers:
        source = ROOT / path
        if not source.is_file():
            continue
        dest = CUTOUT_ROOT / cutout_name(source)
        if dest.is_file() and dest.stat().st_size > 32 and dest.stat().st_mtime >= source.stat().st_mtime:
            continue
        local_jobs.append(source)
    remote_jobs = []
    for (url,) in colors:
        if not url or not url.startswith("https://"):
            continue
        name = remote_cutout_name(url)
        dest = CUTOUT_ROOT / name
        if dest.is_file() and dest.stat().st_size > 32:
            continue
        remote_jobs.append((name, url))
    print(f"cutout prebuild: {len(local_jobs)} ảnh local, {len(remote_jobs)} ảnh màu", flush=True)
    for index, source in enumerate(local_jobs, 1):
        try:
            make_cutout(source, CUTOUT_ROOT / cutout_name(source))
        except Exception:
            pass
        if index % 100 == 0:
            print(f"cutout local {index}/{len(local_jobs)}", flush=True)
        time.sleep(0.02)
    pending = 0
    for index, (name, url) in enumerate(remote_jobs, 1):
        with COLOR_SOURCE_LOCK:
            COLOR_SOURCES[name] = url
        pending += 1
        try:
            write_remote_cutout(name, CUTOUT_ROOT / name)
        except Exception:
            pass
        if pending >= 25:
            try:
                flush_color_sources()
            except Exception:
                pass
            pending = 0
        if index % 50 == 0:
            print(f"cutout màu {index}/{len(remote_jobs)}", flush=True)
        time.sleep(0.02)
    try:
        flush_color_sources()
    except Exception:
        pass
    print("cutout prebuild xong", flush=True)


if __name__ == "__main__":
    load_color_sources()
    threading.Thread(target=prebuild_cutouts, name="cutouts", daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Octopus Store đang chạy tại http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
