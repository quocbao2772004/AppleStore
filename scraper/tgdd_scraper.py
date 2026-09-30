#!/usr/bin/env python3
"""Resumable, polite scraper for five TGDD product categories."""
import argparse
import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import psycopg
import requests
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

BASE = "https://www.thegioididong.com"
AGENT = "TGDDResearchCatalog/1.0 (+contact: local research project)"
CATEGORIES = {
    "dtdd": "phone",
    "laptop": "laptop",
    "tai-nghe": "headphones",
    "may-tinh-bang": "tablet",
    "dong-ho-thong-minh": "smartwatch",
}
LOG = logging.getLogger("tgdd")
ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "data" / "images"


def clean_url(url):
    parsed = urlsplit(urljoin(BASE, url))
    if parsed.netloc != "www.thegioididong.com":
        return None
    return urlunsplit(("https", parsed.netloc, parsed.path.rstrip("/"), "", ""))


def color_option_url(url):
    parsed = urlsplit(urljoin(BASE, url or ""))
    if parsed.netloc != "www.thegioididong.com":
        return None
    code = (parse_qs(parsed.query).get("code") or [None])[0]
    query = f"code={code}" if code else ""
    return urlunsplit(("https", parsed.netloc, parsed.path.rstrip("/"), query, ""))


def category_of(url):
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) == 2 and parts[0] in CATEGORIES and parts[1]:
        return CATEGORIES[parts[0]]
    return None


def text_of(node):
    return node.get_text(" ", strip=True) if node else None


def money(value):
    if isinstance(value, (int, float)):
        amount = int(value)
        return amount if amount > 0 else None
    if re.fullmatch(r"\d+\.0+", str(value or "").strip()):
        amount = int(str(value).split(".", 1)[0])
        return amount if amount > 0 else None
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    amount = int(digits) if digits else None
    return amount if amount and amount > 0 else None


def repair_text(value):
    if not isinstance(value, str):
        return value
    if any(marker in value for marker in ("Ã", "Ä", "á»", "áº")):
        try:
            return value.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
    return value


def decimal(value):
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None


def parse_listing(html, slug):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for card in soup.select("ul.listproduct > li[data-id]"):
        link = card.select_one("a.main-contain[href]")
        if not link:
            continue
        url = clean_url(link["href"])
        if not url or category_of(url) != CATEGORIES[slug]:
            continue
        name = link.get("data-name") or text_of(card.select_one(".product-title"))
        image = card.select_one(".item-img img") or card.select_one("img")
        old = money(text_of(card.select_one(".price-old")))
        price = money(text_of(card.select_one("strong.price")))
        if price is None:
            price = money(link.get("data-price"))
        rating = decimal(text_of(card.select_one(".vote-txt b")))
        data = {
            "source_product_id": int(card["data-id"]),
            "category": CATEGORIES[slug],
            "source_category_id": int(slug_id(slug)),
            "product_code": card.get("data-productcode"),
            "name": repair_text(name),
            "brand": link.get("data-brand"),
            "url": url,
            "thumbnail_url": absolute_image(image.get("data-src") or image.get("src")) if image else None,
            "thumbnail_alt": repair_text(image.get("alt")) if image and image.get("alt") else None,
            "display_status": text_of(card.select_one(".item-txt-online")),
            "rating_value": rating,
            "sold_count_text": text_of(card.select_one(".rating_Compare > span")),
            "price_vnd": price,
            "original_price_vnd": old,
            "discount_percent": None,
            "listing_data": {"card_attributes": dict(card.attrs), "link_attributes": dict(link.attrs)},
            "variants": [],
            "offers": [],
        }
        percent = text_of(card.select_one(".percent"))
        data["discount_percent"] = decimal(percent.strip("-%")) if percent else None
        for variant in card.select(".prods-group li[data-id]"):
            variant_url = clean_url(variant.get("data-url", ""))
            data["variants"].append({
                "id": int(variant["data-id"]), "label": text_of(variant),
                "url": variant_url if category_of(variant_url or "") else None,
                "group": card.select_one(".prods-group").get("data-mergename"),
                "selected": "act" in variant.get("class", []),
            })
        for offer in card.select(".item-label span, .item-gift, .item-txt-online"):
            offer_text = text_of(offer)
            if offer_text:
                data["offers"].append(offer_text)
        found.append(data)
    return found


def slug_id(slug):
    return {"dtdd": 42, "laptop": 44, "tai-nghe": 54,
            "may-tinh-bang": 522, "dong-ho-thong-minh": 7077}[slug]


def absolute_image(url):
    if not url or url.startswith("data:"):
        return None
    absolute = urljoin(BASE, url.strip())
    if absolute.startswith("https://") and not absolute.endswith("/"):
        return absolute
    return None


def parse_detail(html, expected_url, expected_pid=None):
    soup = BeautifulSoup(html, "html.parser")
    product = None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            obj = json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and obj.get("@type") == "Product":
            product = obj
            break
    holder = soup.select_one(".box02__right[data-id], [data-productid]")
    holder_pid = None
    if holder:
        holder_pid = holder.get("data-id") or holder.get("data-productid")
    pid = (product or {}).get("sku") or (product or {}).get("mpn") or holder_pid or expected_pid
    if not str(pid).isdigit():
        raise ValueError("Product page has no numeric SKU")
    canonical = clean_url((product or {}).get("url") or expected_url)
    if category_of(canonical or "") is None:
        raise ValueError("Product URL is outside selected categories")
    brand = (product or {}).get("brand") or {}
    if isinstance(brand, dict):
        brand = brand.get("name")
    if isinstance(brand, list):
        brand = ", ".join(str(v) for v in brand)
    group_by_name = {}
    for group in soup.select(".box-specifi"):
        group_name = text_of(group.select_one("h3")) or ""
        for li in group.select("ul.text-specifi > li"):
            first = li.select_one("aside")
            spec_name = text_of(first)
            if spec_name:
                group_by_name[spec_name.rstrip(":").strip()] = group_name
    image = (product or {}).get("image")
    if isinstance(image, dict):
        images = [image.get("contentUrl") or image.get("url")]
    elif isinstance(image, list):
        images = [v.get("contentUrl") or v.get("url") if isinstance(v, dict) else v for v in image]
    else:
        images = [image] if image else []
    images = [absolute_image(v) for v in images]
    images = [v for v in images if v]
    image_alt = {}
    for tag in soup.select(".gallery-img .slider-img img, .item-img img"):
        candidate = absolute_image(tag.get("data-src") or tag.get("src"))
        if candidate and candidate not in images:
            images.append(candidate)
        if candidate and tag.get("alt"):
            image_alt[candidate] = repair_text(tag["alt"])
    holder_image = absolute_image(holder.get("data-img")) if holder else None
    if holder_image and holder_image not in images:
        images.append(holder_image)
    specs = []
    for i, item in enumerate((product or {}).get("additionalProperty") or []):
        if not isinstance(item, dict):
            continue
        name, value = item.get("name"), item.get("value")
        if name and value is not None:
            value = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
            normalized_name = str(name).rstrip(":").strip()
            specs.append((group_by_name.get(normalized_name,""), normalized_name, repair_text(value), i))
    if not specs:
        for group in soup.select(".box-specifi"):
            group_name = text_of(group.select_one("h3")) or ""
            for i, li in enumerate(group.select("ul.text-specifi > li")):
                asides = li.select("aside")
                if len(asides) >= 2:
                    name, value = text_of(asides[0]), text_of(asides[1])
                    if name and value:
                        specs.append((group_name, name.rstrip(":"), value, i))
    rating = (product or {}).get("aggregateRating") or {}
    offers = (product or {}).get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price_node = soup.select_one(".box-price-present")
    old_node = soup.select_one(".box-price-old")
    price = money(text_of(price_node)) or money(offers.get("price"))
    old_price = money(text_of(old_node))
    location_text = text_of(soup.select_one(".box04__txt")) or ""
    location = location_text.removeprefix("Giá tại ").strip() or "Thành phố Hồ Chí Minh"
    promotions = []
    for item in soup.select(".block__promo .pr-txtb, .block__promo .pr-txt, .block__promo li"):
        value = text_of(item)
        if value and len(value) <= 500 and value not in promotions:
            promotions.append(value)
    reviews = []
    for item in (product or {}).get("review") or []:
        if not isinstance(item, dict):
            continue
        author = item.get("author") or {}
        rating_node = item.get("reviewRating") or {}
        reviews.append({
            "author": repair_text(author.get("name") if isinstance(author, dict) else str(author)),
            "rating": decimal(rating_node.get("ratingValue") if isinstance(rating_node, dict) else None),
            "body": repair_text(item.get("reviewBody")),
            "published": item.get("datePublished"),
        })
    colors = parse_colors(soup)
    name = repair_text((product or {}).get("name") or (holder.get("data-name") if holder else None) or text_of(soup.select_one("h1")))
    if not name:
        raise ValueError("Product page has no name")
    return {
        "source_product_id": int(pid),
        "source_url": expected_url,
        "category": category_of(canonical),
        "name": name,
        "brand": repair_text(brand),
        "model": (product or {}).get("model") if isinstance((product or {}).get("model"), str) else None,
        "product_code": (soup.select_one(".gallery-img [data-code]") or {}).get("data-code"),
        "description": repair_text((product or {}).get("description")),
        "url": canonical,
        "canonical_url": canonical,
        "thumbnail_url": images[0] if images else None,
        "availability": offers.get("availability") if isinstance(offers, dict) else None,
        "rating_value": decimal(rating.get("ratingValue")),
        "rating_count": money(rating.get("reviewCount") or rating.get("reviewcount")),
        "price_vnd": price,
        "original_price_vnd": old_price,
        "price_location": location,
        "detail_data": product or {},
        "specs": specs,
        "images": images,
        "image_alt": image_alt,
        "offers": promotions,
        "reviews": reviews,
        "colors": colors,
    }


def parse_colors(source):
    soup = source if hasattr(source, "select") else BeautifulSoup(source, "html.parser")
    colors = []
    for index, link in enumerate(soup.select(".box03.color a.box03__item")):
        name = text_of(link)
        if not name:
            continue
        swatch = link.select_one("i")
        style = swatch.get("style", "") if swatch else ""
        match = re.search(r"background-color:\s*(#[0-9A-Fa-f]{3,8})", style)
        href = link.get("href") or ""
        colors.append({
            "name": name,
            "hex": match.group(1) if match else None,
            "code": link.get("data-code"),
            "color_id": link.get("data-color"),
            "url": color_option_url(href) if href else None,
            "selected": "act" in (link.get("class") or []),
            "order": index,
        })
    return colors


def gallery_images(source):
    soup = source if hasattr(source, "select") else BeautifulSoup(source, "html.parser")
    found = []
    for image in soup.select("#slider-default .item-img img"):
        raw = image.get("data-src") or image.get("src") or ""
        if not raw or raw.startswith("data:") or "180x125" in raw:
            continue
        absolute = raw if raw.startswith("http") else urljoin(BASE, raw)
        if absolute not in found:
            found.append(absolute)
    return found[:12]


def save_colors(conn, product_id, colors, galleries=None):
    galleries = galleries or {}
    with conn.cursor() as cur:
        cur.execute("DELETE FROM product_color_images WHERE product_id=%s", (product_id,))
        cur.execute("DELETE FROM product_colors WHERE product_id=%s", (product_id,))
        for color in colors:
            cur.execute("""
                INSERT INTO product_colors(product_id,color_name,hex_color,source_code,color_id,option_url,is_selected,display_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (product_id, color["name"], color["hex"], color["code"], color["color_id"],
                  color["url"], color["selected"], color["order"]))
            for index, image_url in enumerate(galleries.get(color["name"]) or []):
                cur.execute("""
                    INSERT INTO product_color_images(product_id,color_name,image_url,display_order)
                    VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING
                """, (product_id, color["name"], image_url, index))


class Fetcher:
    def __init__(self, delay=5):
        self.delay = max(5.0, delay)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": AGENT, "Accept-Language": "vi-VN,vi;q=0.9"})
        self.next_request = 0.0
        self.robots = RobotFileParser()
        self.robots.set_url(BASE + "/robots.txt")
        response = self.session.get(BASE + "/robots.txt", timeout=30)
        response.raise_for_status()
        self.robots.parse(response.text.splitlines())
        self.delay = max(self.delay, float(self.robots.crawl_delay(AGENT) or 0))
        self.next_request = time.monotonic() + self.delay

    def get(self, url):
        if not self.robots.can_fetch(AGENT, url):
            raise ValueError("Disallowed by robots.txt: " + url)
        for attempt in range(3):
            wait = self.next_request - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                response = self.session.get(url, timeout=40)
                self.next_request = time.monotonic() + self.delay
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    self.next_request = max(self.next_request,time.monotonic() + self.delay * (attempt + 1))
                    continue
                response.raise_for_status()
                response.encoding = "utf-8"
                return response.text
            except requests.RequestException:
                self.next_request = time.monotonic() + self.delay * (attempt + 1)
                if attempt == 2:
                    raise


def save_listing(conn, row, run_id):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO products (source_product_id,category,source_category_id,product_code,name,brand,url,
              thumbnail_url,display_status,rating_value,sold_count_text,price_vnd,original_price_vnd,
              listing_price_vnd,original_listing_price_vnd,discount_percent,is_live_catalog,last_run_id,listing_data)
            VALUES (%(source_product_id)s,%(category)s,%(source_category_id)s,%(product_code)s,%(name)s,
              %(brand)s,%(url)s,%(thumbnail_url)s,%(display_status)s,%(rating_value)s,%(sold_count_text)s,
              %(price_vnd)s,%(original_price_vnd)s,%(price_vnd)s,%(original_price_vnd)s,
              %(discount_percent)s,true,%(run_id)s,%(listing_data)s)
            ON CONFLICT (source_product_id) DO UPDATE SET
              category=excluded.category,source_category_id=excluded.source_category_id,
              product_code=excluded.product_code,
              name=CASE WHEN products.detail_fetched_at IS NULL THEN excluded.name ELSE products.name END,
              brand=coalesce(products.brand,excluded.brand),url=excluded.url,
              thumbnail_url=excluded.thumbnail_url,display_status=excluded.display_status,
              rating_value=excluded.rating_value,sold_count_text=excluded.sold_count_text,
              listing_price_vnd=excluded.listing_price_vnd,
              original_listing_price_vnd=excluded.original_listing_price_vnd,
              price_vnd=coalesce(products.detail_price_vnd,excluded.price_vnd),
              original_price_vnd=coalesce(products.original_detail_price_vnd,excluded.original_price_vnd),
              discount_percent=excluded.discount_percent,last_run_id=excluded.last_run_id,
              is_live_catalog=true,
              listing_data=excluded.listing_data,last_seen_at=now()
        """, {**row, "run_id": run_id, "listing_data": Jsonb(row["listing_data"])})
        for variant in row["variants"]:
            cur.execute("""
                INSERT INTO product_variants(parent_product_id,variant_product_id,label,variant_url,group_name,is_selected)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(parent_product_id,variant_product_id) DO UPDATE SET
                label=excluded.label,variant_url=excluded.variant_url,group_name=excluded.group_name,
                is_selected=excluded.is_selected,last_seen_at=now()
            """, (row["source_product_id"], variant["id"], variant["label"], variant["url"], variant["group"], variant["selected"]))
        for offer in row["offers"]:
            cur.execute("""INSERT INTO product_offers(product_id,offer_text,offer_type)
                VALUES (%s,%s,'listing') ON CONFLICT(product_id,offer_type,offer_text)
                DO UPDATE SET last_seen_at=now()""", (row["source_product_id"], offer))
        if row.get("thumbnail_url"):
            cur.execute("""INSERT INTO product_images(product_id,image_url,alt_text,image_role,display_order)
                VALUES (%s,%s,%s,'thumbnail',1000)
                ON CONFLICT(product_id,image_url) DO UPDATE SET
                alt_text=coalesce(product_images.alt_text,excluded.alt_text)""",
                (row["source_product_id"], row["thumbnail_url"], row.get("thumbnail_alt") or row["name"]))
        if row["price_vnd"] is not None:
            cur.execute("""INSERT INTO price_history(product_id,price_vnd,original_price_vnd,run_id)
                SELECT %s,%s,%s,%s WHERE NOT EXISTS (
                  SELECT 1 FROM price_history WHERE product_id=%s AND price_vnd IS NOT DISTINCT FROM %s
                  AND original_price_vnd IS NOT DISTINCT FROM %s AND observed_at > now()-interval '1 day')""",
                (row["source_product_id"],row["price_vnd"],row["original_price_vnd"],run_id,
                 row["source_product_id"],row["price_vnd"],row["original_price_vnd"]))
        cur.execute("""INSERT INTO discovery_urls(url,category,source,fetched_at,fetch_status)
            VALUES (%s,%s,'category',now(),'listing') ON CONFLICT(url) DO UPDATE SET
            fetched_at=now(),fetch_status='listing'""", (row["url"],row["category"]))


def save_detail(conn, row, run_id):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO products(source_product_id,category,name,brand,model,product_code,description,url,canonical_url,thumbnail_url,
              availability,rating_value,rating_count,price_vnd,original_price_vnd,
              detail_price_vnd,original_detail_price_vnd,price_location,last_run_id,detail_data,detail_fetched_at)
            VALUES (%(source_product_id)s,%(category)s,%(name)s,%(brand)s,%(model)s,%(product_code)s,%(description)s,%(url)s,
              %(canonical_url)s,%(thumbnail_url)s,%(availability)s,%(rating_value)s,%(rating_count)s,
              %(price_vnd)s,%(original_price_vnd)s,%(price_vnd)s,%(original_price_vnd)s,
              %(price_location)s,%(run_id)s,%(detail_data)s,now())
            ON CONFLICT(source_product_id) DO UPDATE SET
              category=excluded.category,name=excluded.name,brand=coalesce(excluded.brand,products.brand),
              model=coalesce(excluded.model,products.model),
              product_code=coalesce(excluded.product_code,products.product_code),
              description=excluded.description,canonical_url=excluded.canonical_url,
              thumbnail_url=coalesce(excluded.thumbnail_url,products.thumbnail_url),
              availability=excluded.availability,rating_value=coalesce(excluded.rating_value,products.rating_value),
              rating_count=excluded.rating_count,
              detail_price_vnd=excluded.detail_price_vnd,
              original_detail_price_vnd=excluded.original_detail_price_vnd,
              price_vnd=coalesce(excluded.detail_price_vnd,products.listing_price_vnd,products.price_vnd),
              original_price_vnd=coalesce(excluded.original_detail_price_vnd,products.original_listing_price_vnd,
                                          products.original_price_vnd),
              price_location=excluded.price_location,
              detail_data=excluded.detail_data,detail_fetched_at=now(),last_seen_at=now(),last_run_id=excluded.last_run_id
        """, {**row,"run_id":run_id,"detail_data":Jsonb(row["detail_data"])})
        pid = row["source_product_id"]
        cur.execute("DELETE FROM product_specifications WHERE product_id=%s", (pid,))
        for group, name, value, order in row["specs"]:
            cur.execute("""INSERT INTO product_specifications(product_id,group_name,spec_name,spec_value,display_order)
              VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""", (pid,group,name,value,order))
        for i, image in enumerate(row["images"]):
            cur.execute("""INSERT INTO product_images(product_id,image_url,alt_text,image_role,display_order)
              VALUES (%s,%s,%s,%s,%s) ON CONFLICT(product_id,image_url) DO UPDATE SET
              alt_text=coalesce(excluded.alt_text,product_images.alt_text),
              image_role=excluded.image_role,display_order=excluded.display_order""",
              (pid,image,row["image_alt"].get(image) or row["name"],"primary" if i == 0 else "gallery",i))
        for offer in row["offers"]:
            cur.execute("""INSERT INTO product_offers(product_id,offer_text,offer_type)
              VALUES (%s,%s,'detail') ON CONFLICT(product_id,offer_type,offer_text)
              DO UPDATE SET last_seen_at=now()""", (pid,offer))
        cur.execute("DELETE FROM product_reviews WHERE product_id=%s",(pid,))
        for i,review in enumerate(row["reviews"]):
            cur.execute("""INSERT INTO product_reviews(product_id,review_index,author_name,rating_value,review_body,published_at_text)
              VALUES (%s,%s,%s,%s,%s,%s)""",
              (pid,i,review["author"],review["rating"],review["body"],review["published"]))
        if row["price_vnd"] is not None:
            cur.execute("""INSERT INTO price_history(product_id,price_vnd,original_price_vnd,location,availability,run_id)
              SELECT %s,%s,%s,%s,%s,%s WHERE NOT EXISTS (
                SELECT 1 FROM price_history WHERE product_id=%s AND price_vnd IS NOT DISTINCT FROM %s
                AND original_price_vnd IS NOT DISTINCT FROM %s AND observed_at > now()-interval '1 day')""",
                (pid,row["price_vnd"],row["original_price_vnd"],row["price_location"],row["availability"],run_id,
                 pid,row["price_vnd"],row["original_price_vnd"]))
        cur.execute("""UPDATE discovery_urls SET fetched_at=now(),fetch_status='detail',error=NULL
          WHERE url IN (%s,%s)""", (row["url"],row["source_url"]))
        save_colors(conn, pid, row.get("colors") or [])


def error(conn, run_id, url, stage, exc):
    LOG.error("%s %s: %s", stage, url, exc)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO crawl_errors(run_id,url,stage,error) VALUES (%s,%s,%s,%s)",
                    (run_id,url,stage,str(exc)[:2000]))
        cur.execute("UPDATE crawl_runs SET errors=errors+1 WHERE id=%s", (run_id,))
    conn.commit()


def fetch_colors(conn, fetcher, run_id, limit=None):
    sql = """
        SELECT source_product_id, url FROM products
        WHERE is_live_catalog AND url IS NOT NULL
          AND colors_fetched_at IS NULL
        ORDER BY detail_fetched_at DESC NULLS LAST, source_product_id DESC
    """
    if limit:
        sql += " LIMIT %s"
        rows = conn.execute(sql, (limit,)).fetchall()
    else:
        rows = conn.execute(sql).fetchall()
    LOG.info("Color pages to fetch: %s", len(rows))
    for product_id, url in rows:
        try:
            html = fetcher.get(url)
            colors = parse_colors(html)
            galleries = {}
            selected = next((color for color in colors if color["selected"]), colors[0] if colors else None)
            if selected:
                galleries[selected["name"]] = gallery_images(html)
            for color in colors:
                if color["name"] in galleries or not color["url"] or color.get("selected"):
                    continue
                galleries[color["name"]] = gallery_images(fetcher.get(color["url"]))
            with conn.transaction():
                save_colors(conn, product_id, colors, galleries)
                conn.execute("UPDATE products SET colors_fetched_at=now() WHERE source_product_id=%s", (product_id,))
                conn.execute("UPDATE crawl_runs SET pages_fetched=pages_fetched+1 WHERE id=%s", (run_id,))
            LOG.info("Colors %s: %s", product_id, ", ".join(
                f"{name}({len(galleries.get(name) or [])})" for name in (color["name"] for color in colors)
            ) or "none")
        except Exception as exc:
            error(conn, run_id, url, "colors", exc)


def discover_categories(conn, fetcher, run_id, selected):
    for slug in selected:
        url = BASE + "/" + slug
        try:
            rows = parse_listing(fetcher.get(url),slug)
            with conn.transaction():
                for row in rows:
                    save_listing(conn,row,run_id)
                conn.execute("UPDATE crawl_runs SET pages_fetched=pages_fetched+1,products_seen=products_seen+%s WHERE id=%s",
                             (len(rows),run_id))
            LOG.info("Category %s: %s listing cards",slug,len(rows))
        except Exception as exc:
            error(conn,run_id,url,"category",exc)


def listing_total(html):
    match = re.search(r"document\.TotalCount\s*=\s*['\"]?(\d+)", html)
    return int(match.group(1)) if match else None


def fetch_catalog_segment(conn, fetcher, run_id, url, slug, html=None):
    if html is None:
        html = fetcher.get(url)
    rows = parse_listing(html,slug)
    total = listing_total(html)
    overflow = total is not None and total > len(rows)
    with conn.transaction():
        for row in rows:
            save_listing(conn,row,run_id)
        conn.execute("""INSERT INTO catalog_segments(url,category,expected_count,observed_count,overflow,run_id)
          VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(url) DO UPDATE SET
          expected_count=excluded.expected_count,observed_count=excluded.observed_count,
          overflow=excluded.overflow,fetched_at=now(),run_id=excluded.run_id""",
          (url,CATEGORIES[slug],total,len(rows),overflow,run_id))
        conn.execute("DELETE FROM catalog_segment_products WHERE segment_url=%s",(url,))
        for row in rows:
            conn.execute("INSERT INTO catalog_segment_products(segment_url,product_id) VALUES (%s,%s)",
                         (url,row["source_product_id"]))
        conn.execute("UPDATE crawl_runs SET pages_fetched=pages_fetched+1,products_seen=products_seen+%s WHERE id=%s",
                     (len(rows),run_id))
    return total,len(rows),overflow


def discover_catalog(conn, fetcher, run_id, selected, max_segments=None):
    fetched = 0
    for slug in selected:
        root_url = BASE + "/" + slug
        try:
            root_html = fetcher.get(root_url)
            root_total,root_count,_ = fetch_catalog_segment(conn,fetcher,run_id,root_url,slug,root_html)
            fetched += 1
            soup = BeautifulSoup(root_html,"html.parser")
            brand_urls = sorted({urljoin(BASE + "/",tag["href"])
                for tag in soup.select(".filter-list.manu a[data-href][href]")
                if tag["href"].startswith(slug + "-")})
            price_slugs = sorted({tag.get("data-href")
                for tag in soup.select(".filter-list.price a[data-href]") if tag.get("data-href")})
            LOG.info("Catalog %s: page count %s, first %s, brands %s, price bands %s",
                     slug,root_total,root_count,len(brand_urls),len(price_slugs))
            for brand_url in brand_urls:
                cached = conn.execute("SELECT expected_count,observed_count,overflow FROM catalog_segments WHERE url=%s",
                                      (brand_url,)).fetchone()
                if cached:
                    total,observed,overflow = cached
                else:
                    if max_segments and fetched >= max_segments:
                        return
                    try:
                        total,observed,overflow = fetch_catalog_segment(conn,fetcher,run_id,brand_url,slug)
                        fetched += 1
                    except Exception as exc:
                        error(conn,run_id,brand_url,"catalog-brand",exc)
                        continue
                if not overflow:
                    continue
                LOG.info("Brand segment %s: %s/%s, splitting by price",brand_url,observed,total)
                for price_slug in price_slugs:
                    segment_url = brand_url + "?p=" + price_slug
                    if conn.execute("SELECT 1 FROM catalog_segments WHERE url=%s",(segment_url,)).fetchone():
                        continue
                    if max_segments and fetched >= max_segments:
                        return
                    try:
                        count,shown,still_overflow = fetch_catalog_segment(conn,fetcher,run_id,segment_url,slug)
                        fetched += 1
                        if still_overflow:
                            LOG.warning("Catalog segment still truncated: %s (%s/%s)",segment_url,shown,count)
                    except Exception as exc:
                        error(conn,run_id,segment_url,"catalog-price",exc)
            found = conn.execute("SELECT count(*) FROM products WHERE category=%s",(CATEGORIES[slug],)).fetchone()[0]
            LOG.info("Catalog %s: %s unique product IDs vs. site count %s",slug,found,root_total)
        except Exception as exc:
            error(conn,run_id,root_url,"catalog-root",exc)


def supplement_catalog(conn, fetcher, run_id, max_pages=None):
    sitemap_url = BASE + "/newsitemap/sitemap-cate"
    try:
        root = ET.fromstring(fetcher.get(sitemap_url))
        category_urls = [node.text for node in root.iter() if node.tag.endswith("loc")]
    except Exception as exc:
        error(conn,run_id,sitemap_url,"category-sitemap",exc)
        return
    segments = conn.execute("""SELECT url,category,expected_count FROM catalog_segments
      WHERE overflow AND url LIKE '%%?p=%%' ORDER BY category,url""").fetchall()
    fetched = 0
    for parent_url,category,expected in segments:
        parsed = urlsplit(parent_url)
        brand_path = parsed.path.strip("/")
        brand_url = BASE + parsed.path
        band = parse_qs(parsed.query).get("p",[None])[0]
        slug = next((key for key in CATEGORIES if brand_path.startswith(key + "-")),None)
        if not slug or not band:
            continue
        mapped = conn.execute("SELECT product_id FROM catalog_segment_products WHERE segment_url=%s",
                              (parent_url,)).fetchall()
        if not mapped:
            try:
                fetch_catalog_segment(conn,fetcher,run_id,parent_url,slug)
                fetched += 1
            except Exception as exc:
                error(conn,run_id,parent_url,"catalog-overflow",exc)
                continue
        covered = {row[0] for row in conn.execute(
            "SELECT product_id FROM catalog_segment_products WHERE segment_url=%s",(parent_url,)).fetchall()}
        candidates = [url for url in category_urls if urlsplit(url).path.startswith("/" + brand_path + "-")][:12]
        for candidate in candidates:
            candidate_url = candidate + "?p=" + band
            mapped = conn.execute("SELECT product_id FROM catalog_segment_products WHERE segment_url=%s",
                                  (candidate_url,)).fetchall()
            if not mapped and not conn.execute("SELECT 1 FROM catalog_segments WHERE url=%s",(candidate_url,)).fetchone():
                if max_pages and fetched >= max_pages:
                    return
                try:
                    fetch_catalog_segment(conn,fetcher,run_id,candidate_url,slug)
                    fetched += 1
                    mapped = conn.execute("SELECT product_id FROM catalog_segment_products WHERE segment_url=%s",
                                          (candidate_url,)).fetchall()
                except Exception as exc:
                    error(conn,run_id,candidate_url,"catalog-supplement",exc)
                    continue
            covered.update(row[0] for row in mapped)
            if expected is not None and len(covered) >= expected:
                break
        LOG.info("Overflow %s: %s/%s unique products covered",parent_url,len(covered),expected)


def discover_sitemap(conn, fetcher, run_id, min_year=None, max_pages=None):
    index = BASE + "/newsitemap/sitemap-product"
    try:
        root = ET.fromstring(fetcher.get(index))
        pages = [node.text for node in root.iter() if node.tag.endswith("loc")]
    except Exception as exc:
        error(conn,run_id,index,"sitemap-index",exc)
        return
    if min_year:
        pages = [url for url in pages if int(re.search(r"sitemap-product-(\d{4})",url).group(1)) >= min_year]
    pages.reverse()  # Newer products first; checkpoints still make the full crawl resumable.
    if max_pages:
        pages = pages[:max_pages]
    LOG.info("Sitemap pages to inspect: %s",len(pages))
    for i, url in enumerate(pages,1):
        done = conn.execute("SELECT fetched_at FROM sitemap_pages WHERE url=%s",(url,)).fetchone()
        if done and done[0]:
            continue
        try:
            root = ET.fromstring(fetcher.get(url))
            count = 0
            with conn.transaction():
                for entry in root:
                    loc = next((child.text for child in entry if child.tag.endswith("loc")),None)
                    mod = next((child.text for child in entry if child.tag.endswith("lastmod")),None)
                    canonical = clean_url(loc) if loc else None
                    category = category_of(canonical or "")
                    if not category:
                        continue
                    lastmod = date.fromisoformat(mod) if mod else None
                    conn.execute("""INSERT INTO discovery_urls(url,category,source,sitemap_lastmod)
                      VALUES (%s,%s,'sitemap',%s) ON CONFLICT(url) DO UPDATE SET
                      sitemap_lastmod=excluded.sitemap_lastmod""",(canonical,category,lastmod))
                    count += 1
                conn.execute("""INSERT INTO sitemap_pages(url,fetched_at,url_count,error) VALUES (%s,now(),%s,NULL)
                  ON CONFLICT(url) DO UPDATE SET fetched_at=now(),url_count=excluded.url_count,error=NULL""",(url,count))
                conn.execute("UPDATE crawl_runs SET pages_fetched=pages_fetched+1 WHERE id=%s",(run_id,))
            if i % 10 == 0 or i == len(pages):
                LOG.info("Sitemaps %s/%s; target URLs in page: %s",i,len(pages),count)
        except Exception as exc:
            error(conn,run_id,url,"sitemap-page",exc)
            conn.execute("""INSERT INTO sitemap_pages(url,error) VALUES (%s,%s)
              ON CONFLICT(url) DO UPDATE SET error=excluded.error""",(url,str(exc)[:2000]))
            conn.commit()


def fetch_details(conn, fetcher, run_id, limit=None, retry_errors=False, only_listed=False):
    sql = """SELECT d.url,p.source_product_id FROM discovery_urls d LEFT JOIN products p ON p.url=d.url
      WHERE p.detail_fetched_at IS NULL AND ("""
    if only_listed:
        sql += "d.fetch_status='listing'"
        if retry_errors:
            sql += " OR (d.fetch_status='error' AND p.is_live_catalog)"
    else:
        sql += "d.fetched_at IS NULL OR d.fetch_status='listing'"
        if retry_errors:
            sql += " OR d.fetch_status='error'"
    sql += """)
      ORDER BY CASE WHEN d.fetch_status='listing' THEN 0 ELSE 1 END,
               d.sitemap_lastmod DESC NULLS LAST,d.discovered_at"""
    if limit:
        sql += " LIMIT " + str(int(limit))
    urls = conn.execute(sql).fetchall()
    LOG.info("Product detail pages to fetch: %s",len(urls))
    for i,(url,expected_pid) in enumerate(urls,1):
        try:
            row = parse_detail(fetcher.get(url),url,expected_pid)
            with conn.transaction():
                save_detail(conn,row,run_id)
                conn.execute("UPDATE crawl_runs SET pages_fetched=pages_fetched+1,products_seen=products_seen+1 WHERE id=%s",(run_id,))
            if i % 20 == 0 or i == len(urls):
                LOG.info("Details %s/%s",i,len(urls))
        except Exception as exc:
            error(conn,run_id,url,"detail",exc)
            conn.execute("UPDATE discovery_urls SET fetched_at=now(),fetch_status='error',error=%s WHERE url=%s",
                         (str(exc)[:2000],url))
            conn.commit()


def sniff_image_ext(content):
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return ".avif"
    return None


def sync_listing_thumbnails(conn):
    conn.execute("""
        INSERT INTO product_images(product_id,image_url,alt_text,image_role,display_order)
        SELECT source_product_id, thumbnail_url, name, 'thumbnail', 1000
        FROM products
        WHERE thumbnail_url IS NOT NULL
        ON CONFLICT(product_id,image_url) DO NOTHING
    """)


def download_one_image(row):
    product_id, url, order, category = row
    response = requests.get(url, headers={"User-Agent": AGENT}, timeout=40)
    response.raise_for_status()
    content = response.content
    if not 32 <= len(content) <= 15_000_000:
        raise ValueError(f"unexpected image size {len(content)}")
    ext = sniff_image_ext(content)
    if not ext:
        raise ValueError("response is not an image")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    relative = Path("data") / "images" / category / str(product_id) / f"{int(order)}-{digest}{ext}"
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(target)
    return product_id, url, relative.as_posix()


def download_pending_images(conn, workers=8):
    rows = conn.execute("""
        SELECT i.product_id, i.image_url, i.display_order, p.category
        FROM product_images i
        JOIN products p ON p.source_product_id=i.product_id
        WHERE i.local_path IS NULL AND i.download_error IS NULL
        ORDER BY i.product_id, i.display_order, i.image_url
    """).fetchall()
    LOG.info("Images to download: %s", len(rows))
    saved = failed = 0
    if not rows:
        return saved, failed
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_one_image, row): row for row in rows}
        for future in as_completed(futures):
            product_id, url, order, category = futures[future]
            try:
                product_id, url, relative = future.result()
            except Exception as exc:
                failed += 1
                message = str(exc)[:500]
                permanent = any(token in message for token in ("404", "not an image", "unexpected image size"))
                LOG.warning("Image failed %s: %s", url, message)
                if permanent:
                    conn.execute("""UPDATE product_images SET download_error=%s
                        WHERE product_id=%s AND image_url=%s AND local_path IS NULL""",
                        (message, product_id, url))
                continue
            conn.execute("""UPDATE product_images SET local_path=%s, download_error=NULL
                WHERE product_id=%s AND image_url=%s""", (relative, product_id, url))
            saved += 1
            if saved % 200 == 0:
                LOG.info("Images saved %s/%s", saved, len(rows))
    LOG.info("Image download saved=%s failed=%s", saved, failed)
    return saved, failed


def detail_crawler_running():
    import subprocess
    result = subprocess.run(["pgrep", "-f", "tgdd_scraper.py --mode details"], capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def write_gallery(conn):
    labels = {
        "phone": "Điện thoại", "laptop": "Laptop", "headphones": "Tai nghe",
        "tablet": "Máy tính bảng", "smartwatch": "Đồng hồ thông minh",
    }
    rows = conn.execute("""
        SELECT p.category, p.name, p.brand, p.price_vnd, p.url,
               COALESCE(
                 (SELECT i.local_path FROM product_images i
                  WHERE i.product_id=p.source_product_id AND i.local_path IS NOT NULL
                    AND i.image_role IN ('primary','thumbnail')
                  ORDER BY CASE i.image_role WHEN 'primary' THEN 0 ELSE 1 END, i.display_order
                  LIMIT 1),
                 (SELECT i.local_path FROM product_images i
                  WHERE i.product_id=p.source_product_id AND i.local_path IS NOT NULL
                  ORDER BY i.display_order LIMIT 1)
               ) AS local_path
        FROM products p
        WHERE p.is_live_catalog
        ORDER BY p.category, p.price_vnd NULLS LAST, p.name
    """).fetchall()

    def esc(value):
        return (str(value or "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))

    sections = []
    for category in ("phone", "laptop", "tablet", "headphones", "smartwatch"):
        items = [row for row in rows if row[0] == category]
        cards = []
        for _, name, brand, price, url, local_path in items:
            price_text = f"{price:,.0f}₫".replace(",", ".") if price else "Chưa có giá"
            src = local_path[len("data/"):] if local_path and local_path.startswith("data/") else local_path
            image = f'<img src="{esc(src)}" alt="{esc(name)}">' if src else '<div class="missing">Chưa có ảnh</div>'
            cards.append(
                f'<a class="card" href="{esc(url)}">{image}'
                f'<strong>{esc(name)}</strong><span>{esc(brand or "")}</span><em>{price_text}</em></a>'
            )
        sections.append(f'<section><h2>{labels[category]} ({len(items)})</h2><div class="grid">{"".join(cards)}</div></section>')
    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"><title>Sản phẩm Thế Giới Di Động</title>
<style>
body {{ font-family: sans-serif; margin: 24px; background: #f6f7f9; color: #1d1d1f; }}
h1 {{ margin-bottom: 8px; }} h2 {{ margin-top: 32px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }}
.card {{ display: flex; flex-direction: column; gap: 6px; background: white; padding: 10px; border-radius: 10px; text-decoration: none; color: inherit; }}
.card img {{ width: 100%; aspect-ratio: 1; object-fit: contain; background: #fff; }}
.missing {{ aspect-ratio: 1; display: grid; place-items: center; background: #eee; color: #666; }}
.card strong {{ font-size: 14px; }} .card span, .card em {{ font-size: 13px; color: #555; font-style: normal; }}
</style></head><body>
<h1>Danh mục đã cào</h1>
<p>{len(rows)} sản phẩm đang bán. Ảnh nằm trong <code>data/images</code> và được liên kết từ PostgreSQL.</p>
{''.join(sections)}
</body></html>"""
    path = ROOT / "data" / "gallery.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    LOG.info("Gallery written: %s", path)
    return path


def sync_images(conn, follow=False):
    first = True
    while True:
        sync_listing_thumbnails(conn)
        saved, failed = download_pending_images(conn)
        write_gallery(conn)
        if first:
            LOG.info("FIRST_PASS_DONE saved=%s failed=%s", saved, failed)
            first = False
        if not follow:
            return
        if saved == 0 and failed == 0 and not detail_crawler_running():
            LOG.info("IMAGE_SYNC_DONE")
            return
        time.sleep(20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn",default="dbname=tgdd_products",help="PostgreSQL connection string")
    parser.add_argument("--mode",choices=["categories","catalog","supplement","sitemap","details","colors","images","all"],default="all")
    parser.add_argument("--category",action="append",choices=CATEGORIES,help="Limit listing categories")
    parser.add_argument("--min-year",type=int,help="Only inspect sitemap pages from this year onward")
    parser.add_argument("--max-sitemap-pages",type=int)
    parser.add_argument("--max-catalog-segments",type=int)
    parser.add_argument("--max-supplement-pages",type=int)
    parser.add_argument("--max-details",type=int)
    parser.add_argument("--only-listed",action="store_true",help="Fetch detail only for products seen in live category listings")
    parser.add_argument("--retry-errors",action="store_true",help="Retry URLs previously marked as errors")
    parser.add_argument("--follow",action="store_true",help="Keep downloading images while the detail crawler is running")
    parser.add_argument("--delay",type=float,default=5.0,help="Seconds between requests, minimum 5")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    with psycopg.connect(args.dsn,autocommit=True) as conn:
        with (ROOT / "database" / "schema.sql").open(encoding="utf-8") as f:
            conn.execute(f.read())
        if args.mode == "images":
            run_id = conn.execute("INSERT INTO crawl_runs(notes) VALUES ('images') RETURNING id").fetchone()[0]
            try:
                sync_images(conn, args.follow)
                conn.execute("UPDATE crawl_runs SET finished_at=now(),status='completed' WHERE id=%s",(run_id,))
            except BaseException:
                conn.execute("UPDATE crawl_runs SET finished_at=now(),status='interrupted' WHERE id=%s",(run_id,))
                raise
            return
        run_id = conn.execute("INSERT INTO crawl_runs DEFAULT VALUES RETURNING id").fetchone()[0]
        try:
            fetcher = Fetcher(args.delay)
            if args.mode in ("categories","all"):
                discover_categories(conn,fetcher,run_id,args.category or list(CATEGORIES))
            if args.mode in ("catalog","all"):
                discover_catalog(conn,fetcher,run_id,args.category or list(CATEGORIES),args.max_catalog_segments)
            if args.mode in ("supplement","all"):
                supplement_catalog(conn,fetcher,run_id,args.max_supplement_pages)
            if args.mode in ("sitemap","all"):
                discover_sitemap(conn,fetcher,run_id,args.min_year,args.max_sitemap_pages)
            if args.mode in ("details","all"):
                fetch_details(conn,fetcher,run_id,args.max_details,args.retry_errors,args.only_listed)
            if args.mode == "colors":
                fetch_colors(conn,fetcher,run_id,args.max_details)
            conn.execute("UPDATE crawl_runs SET finished_at=now(),status='completed' WHERE id=%s",(run_id,))
        except BaseException:
            conn.execute("UPDATE crawl_runs SET finished_at=now(),status='interrupted' WHERE id=%s",(run_id,))
            raise


if __name__ == "__main__":
    main()
