#!/usr/bin/env python3
"""Crawl official brand warranty pages and keep the original response bytes.

Writes under data/warranty/:
  raw/<slug>/body.*     exact response body
  raw/<slug>/meta.json  URL, status, headers, hash
  text/<slug>.txt       visible text extracted from HTML
  manifest.json         one row per page
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "warranty"
RAW = OUT / "raw"
TEXT = OUT / "text"
AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
PAUSE_S = 5
TIMEOUT = 40

# Official manufacturer pages. One brand can have several documents.
PAGES = [
    ("samsung", "Samsung", ["phone", "tablet", "smartwatch", "headphones"], "https://www.samsung.com/vn/support/warranty/"),
    ("apple-ios", "Apple", ["phone", "tablet"], "https://www.apple.com/legal/warranty/products/ios-warranty-rest-of-apac-vietnamese.html"),
    ("apple-mac", "Apple", ["laptop"], "https://www.apple.com/legal/warranty/products/embedded-mac-warranty-rest-of-apac-vietnamese.html"),
    ("apple-watch", "Apple", ["smartwatch"], "https://www.apple.com/legal/warranty/products/warranty-rest-of-apac-vietnamese.html"),
    ("apple-accessory", "Apple", ["headphones"], "https://www.apple.com/legal/warranty/products/accessory-warranty-vietnam.html"),
    ("xiaomi", "Xiaomi", ["phone", "tablet", "headphones", "smartwatch"], "https://www.mi.com/vn/support/warranty/"),
    ("oppo", "OPPO", ["phone", "tablet", "headphones"], "https://support.oppo.com/vn/warranty-policy/"),
    ("vivo", "vivo", ["phone"], "https://www.vivo.com/vn/index/warrantyTerms"),
    ("honor", "HONOR", ["phone", "tablet"], "https://www.honor.com/vn/support/warranty-policy/"),
    ("realme", "realme", ["phone", "headphones", "smartwatch"], "https://www.realme.com/vn/legal/warranty-terms"),
    ("huawei", "Huawei", ["phone", "tablet", "laptop", "headphones", "smartwatch"], "https://consumer.huawei.com/vn/support/warranty-policy/"),
    ("huawei-wearable", "Huawei", ["smartwatch", "headphones"], "https://consumer.huawei.com/vn/support/warranty-policy/wearable/"),
    ("huawei-phone", "Huawei", ["phone"], "https://consumer.huawei.com/vn/support/warranty-policy/smartphones/"),
    ("huawei-laptop", "Huawei", ["laptop"], "https://consumer.huawei.com/vn/support/warranty-policy/laptops/"),
    ("huawei-tablet", "Huawei", ["tablet"], "https://consumer.huawei.com/vn/support/warranty-policy/tablets/"),
    ("huawei-audio", "Huawei", ["headphones"], "https://consumer.huawei.com/vn/support/warranty-policy/audio/"),
    ("acer-vn", "Acer", ["laptop"], "https://www.acervietnam.com.vn/tin-tuc/chinh-sach-bao-hanh-san-pham-acer-viet-nam"),
    ("dell-peripherals", "Dell", ["headphones"], "https://www.dell.com/support/kbdoc/en-vn/000363939/dell-peripheral-warranty-coverage-guide?lang=en"),
    ("garmin", "Garmin", ["smartwatch"], "https://www.garmin.com/vi-VN/legal/consumer-limited-warranty/"),
    ("garmin-vn", "Garmin", ["smartwatch"], "https://support.garmin.com/vi-VN?faq=C9q6XzqCzW8BD3bF1kZvK6"),
    ("msi", "MSI", ["laptop"], "https://vn.msi.com/page/warranty/gd"),
    ("lenovo", "Lenovo", ["laptop", "tablet"], "https://support.lenovo.com/vn/en/solutions/ht505088-product-warranty-and-other-agreements"),
    ("sony", "Sony", ["headphones"], "https://www.sony.com.vn/electronics/support/articles/00242897"),
    ("sony-terms", "Sony", ["headphones"], "https://www.sony.com.vn/support/resources/vi_VN/html/Warranty/Warranty_Information/CSBH3.htm"),
    ("asus-article-839", "Asus", ["laptop", "headphones"], "https://www.asus.com/vn/support/Article/839/"),
    ("asus-premium-care", "Asus", ["laptop"], "https://www.asus.com/vn/support/faq/1040170/"),
    ("dell-warranty", "Dell", ["laptop", "headphones"], "https://www.dell.com/support/kbdoc/en-vn/000126556/dell-limited-hardware-warranty"),
    ("hp-warranty", "HP", ["laptop"], "https://support.hp.com/vn-en/document/c04719427"),
    ("acer-warranty", "Acer", ["laptop"], "https://www.acer.com/vn-vi/support"),
    ("nokia-warranty", "Nokia", ["phone"], "https://www.hmd.com/en_int/support/warranty"),
    ("motorola-warranty", "Motorola", ["phone"], "https://www.motorola.com/vn/en/legal/warranty"),
    ("jbl-warranty", "JBL", ["headphones"], "https://www.jbl.com/warranty.html"),
    ("logitech-warranty", "Logitech", ["headphones"], "https://www.logitech.com/vi-vn/tos/limited-hardware-warranty.html"),
    ("amazfit-warranty", "Amazfit", ["smartwatch", "headphones"], "https://www.amazfit.com/pages/warranty-policy"),
]


def robots_allows(session, url):
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = session.get(robots_url, timeout=12)
    except Exception as exc:
        return True, f"robots unread: {exc}"
    if response.status_code >= 400:
        return True, f"robots status {response.status_code}"
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    allowed = parser.can_fetch(AGENT, url)
    return allowed, "allowed" if allowed else "disallowed"


def extension_for(content_type, url):
    kind = (content_type or "").split(";")[0].strip().lower()
    if "html" in kind or url.lower().endswith(".htm"):
        return ".html"
    if "pdf" in kind or url.lower().endswith(".pdf"):
        return ".pdf"
    return ".bin"


def visible_text(body, content_type):
    if "html" not in (content_type or "").lower() and b"<html" not in body[:800].lower() and b"\\u003c" not in body[:4000]:
        return ""
    raw = body.decode("utf-8", "ignore")
    raw = raw.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&").replace("\\/", "/")
    soup = BeautifulSoup(raw, "html.parser")
    embedded = []
    for script in soup.find_all("script"):
        content = script.string or ""
        if any(token in content.lower() for token in ("bảo hành", "bao hanh", "<table", "thời hạn", "warranty")):
            embedded.append(BeautifulSoup(content, "html.parser").get_text("\n", strip=True))
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if embedded:
        lines.extend(line.strip() for chunk in embedded for line in chunk.splitlines() if line.strip())
    body_text = "\n".join(dict.fromkeys(lines))
    if title and title not in body_text[:200]:
        return title + "\n\n" + body_text
    return body_text


def already_saved(slug):
    meta_path = RAW / slug / "meta.json"
    if not meta_path.exists():
        return False
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return meta.get("status") == 200 and meta.get("bytes", 0) > 1000


def fetch(session, slug, brand, categories, url):
    if already_saved(slug):
        meta = json.loads((RAW / slug / "meta.json").read_text(encoding="utf-8"))
        text_path = TEXT / f"{slug}.txt"
        text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
        return {
            "slug": slug,
            "brand": brand,
            "categories": categories,
            "url": url,
            "ok": True,
            "skipped": True,
            "status": 200,
            "final_url": meta.get("final_url"),
            "bytes": meta.get("bytes"),
            "sha256": meta.get("sha256"),
            "content_type": meta.get("content_type"),
            "text_chars": len(text),
            "raw": str((RAW / slug).relative_to(ROOT)),
            "text": str(text_path.relative_to(ROOT)),
            "title": text.split("\n", 1)[0][:180] if text else "",
        }
    allowed, robots_note = robots_allows(session, url)
    record = {
        "slug": slug,
        "brand": brand,
        "categories": categories,
        "url": url,
        "robots": robots_note,
        "ok": False,
    }
    if not allowed:
        record["error"] = "robots.txt disallows this agent"
        return record
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    body = response.content
    content_type = response.headers.get("Content-Type", "")
    ext = extension_for(content_type, response.url)
    folder = RAW / slug
    folder.mkdir(parents=True, exist_ok=True)
    body_path = folder / f"body{ext}"
    body_path.write_bytes(body)
    meta = {
        "slug": slug,
        "brand": brand,
        "categories": categories,
        "requested_url": url,
        "final_url": response.url,
        "status": response.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_type": content_type,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "headers": {key: value for key, value in response.headers.items()},
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    text = visible_text(body, content_type)
    text_path = TEXT / f"{slug}.txt"
    text_path.write_text(text, encoding="utf-8")
    record.update({
        "ok": response.status_code == 200 and len(body) > 0,
        "status": response.status_code,
        "final_url": response.url,
        "bytes": len(body),
        "sha256": meta["sha256"],
        "content_type": content_type,
        "text_chars": len(text),
        "raw": str(body_path.relative_to(ROOT)),
        "text": str(text_path.relative_to(ROOT)),
        "title": text.split("\n", 1)[0][:180] if text else "",
    })
    return record


def refresh_text():
    """Rebuild text files from the saved raw bodies. Does not touch body.*."""
    for folder in sorted(RAW.iterdir()):
        if not folder.is_dir():
            continue
        bodies = list(folder.glob("body.*"))
        meta_path = folder / "meta.json"
        if not bodies or not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        text = visible_text(bodies[0].read_bytes(), meta.get("content_type", ""))
        (TEXT / f"{folder.name}.txt").write_text(text, encoding="utf-8")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": AGENT,
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    })
    rows = []
    for index, (slug, brand, categories, url) in enumerate(PAGES):
        if index:
            time.sleep(PAUSE_S)
        try:
            record = fetch(session, slug, brand, categories, url)
        except Exception as exc:
            record = {
                "slug": slug,
                "brand": brand,
                "categories": categories,
                "url": url,
                "ok": False,
                "error": str(exc),
            }
        rows.append(record)
        state = "ok" if record.get("ok") else "fail"
        detail = record.get("error") or record.get("robots") or ""
        print(f"{state:4} {str(record.get('status', '-')):>4} {slug} {record.get('bytes', 0)} {detail}", flush=True)
    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "pause_seconds": PAUSE_S,
        "pages": rows,
    }
    refresh_text()
    for row in rows:
        path = TEXT / f"{row['slug']}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            row["text_chars"] = len(text)
            row["title"] = text.split("\n", 1)[0][:180] if text else ""
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for row in rows if row.get("ok"))
    print(f"done {ok}/{len(rows)} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
