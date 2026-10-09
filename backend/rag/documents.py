"""Rows in rag_documents. Uploads and the warranty seed only publish an id; the worker embeds."""
import json
from pathlib import Path

import psycopg

from .embed import public_error
from .settings import DOC_TYPE_KEYS, FILE_DIR, MAX_CHUNKS, database_url, load_env
from .textutil import allowed_name, chunk_text, extract_text, safe_name

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    brand_key TEXT NOT NULL DEFAULT '',
    doc_type TEXT NOT NULL DEFAULT 'warranty',
    lang TEXT NOT NULL DEFAULT 'vi',
    scope TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_key TEXT UNIQUE,
    line TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    uploaded_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Pages whose extracted text is a real warranty policy. Wrong articles and block pages stay out.
WARRANTY_SEEDS = (
    ("samsung", "Samsung", "Chính sách bảo hành Samsung Việt Nam", "vi", "Samsung tại Việt Nam", ""),
    ("apple-ios", "Apple", "Bảo hành iPhone và iPad", "vi", "iPhone và iPad", "iphone"),
    ("apple-mac", "Apple", "Bảo hành Mac", "vi", "Mac", "mac"),
    ("apple-watch", "Apple", "Bảo hành Apple Watch", "vi", "Apple Watch", "watch"),
    ("apple-accessory", "Apple", "Bảo hành phụ kiện Apple và Beats", "vi", "Phụ kiện Apple và Beats", "accessory"),
    ("xiaomi", "Xiaomi", "Bảo hành Xiaomi Việt Nam", "vi", "Xiaomi tại Việt Nam", ""),
    ("oppo", "OPPO", "Thời hạn bảo hành OPPO", "vi", "Thân máy, pin và phụ kiện OPPO", ""),
    ("vivo", "vivo", "Điều khoản bảo hành vivo", "vi", "vivo", ""),
    ("honor", "HONOR", "Chính sách bảo hành HONOR Việt Nam", "vi", "HONOR tại Việt Nam", ""),
    ("realme", "realme", "Chính sách bảo hành realme", "vi", "realme", ""),
    ("acer-vn", "Acer", "Chính sách bảo hành Acer Việt Nam", "vi", "Acer Việt Nam. Chi tiết có thể nằm trong sổ đi kèm máy.", ""),
    ("logitech-warranty", "Logitech", "Bảo hành phần cứng Logitech", "en", "Phần cứng Logitech", ""),
    ("dell-peripherals", "Dell", "Bảo hành phụ kiện Dell", "en", "Phụ kiện và thiết bị rời Dell. Không phải laptop Dell.", ""),
)


def connect():
    load_env()
    return psycopg.connect(database_url(), autocommit=True)


def ensure_table(conn):
    conn.execute(TABLE_SQL)
    conn.execute("ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS line TEXT NOT NULL DEFAULT ''")


def brand_key(value):
    text = " ".join((value or "").strip().casefold().split())
    aliases = {
        "iphone": "apple",
        "ipad": "apple",
        "mac": "apple",
        "macbook": "apple",
        "beats": "apple",
    }
    return aliases.get(text, text)


def _clean(title, brand, doc_type, lang, source_url, scope):
    title = " ".join((title or "").split())
    brand = " ".join((brand or "").split())
    scope = " ".join((scope or "").split())
    source_url = (source_url or "").strip()
    doc_type = (doc_type or "warranty").strip()
    lang = (lang or "vi").strip().lower()
    if len(title) < 2 or len(title) > 160:
        return "Tiêu đề cần từ 2 đến 160 ký tự."
    if len(brand) > 40:
        return "Tên hãng quá dài."
    if doc_type not in DOC_TYPE_KEYS:
        return "Loại tài liệu không hợp lệ."
    if lang not in ("vi", "en"):
        return "Ngôn ngữ chỉ nhận vi hoặc en."
    if source_url and not (source_url.startswith("https://") or source_url.startswith("http://")):
        return "URL nguồn phải bắt đầu bằng http:// hoặc https://."
    if len(source_url) > 300:
        return "URL nguồn quá dài."
    if len(scope) > 200:
        return "Phạm vi quá dài."
    return {
        "title": title,
        "brand": brand,
        "brand_key": brand_key(brand),
        "doc_type": doc_type,
        "lang": lang,
        "scope": scope,
        "source_url": source_url,
    }


def _write_file(document_id, filename, data):
    FILE_DIR.mkdir(parents=True, exist_ok=True)
    path = FILE_DIR / "{0}-{1}".format(int(document_id), safe_name(filename))
    path.write_bytes(data)
    return path


def _managed(path):
    try:
        Path(path).resolve().relative_to(FILE_DIR.resolve())
        return True
    except ValueError:
        return False


def _mark_failed(conn, document_id, message):
    conn.execute(
        "UPDATE rag_documents SET status='failed', error=%s WHERE id=%s",
        (public_error(message), int(document_id)),
    )


def _publish_or_fail(conn, document_id):
    from .broker import publish

    try:
        publish(document_id)
    except Exception as exc:
        _mark_failed(conn, document_id, "Không gửi được vào RabbitMQ. {0}".format(public_error(exc)))
        return "Không gửi được vào RabbitMQ. Broker chưa chạy thì tài liệu ở trạng thái Lỗi."
    return ""


def enqueue_bytes(conn, *, title, brand, doc_type, lang, filename, data, source_url="", scope="", uploaded_by=None, source_key=None, line="", force=False):
    """Store the original bytes and publish {"id": document_id}. Returns an error string."""
    meta = _clean(title, brand, doc_type, lang, source_url, scope)
    if isinstance(meta, str):
        return meta
    if not allowed_name(filename):
        return "Chỉ nhận tệp .txt, .md hoặc .html."
    if not data:
        return "Tệp trống."
    row = None
    if source_key:
        row = conn.execute(
            "SELECT id, status FROM rag_documents WHERE source_key=%s",
            (source_key,),
        ).fetchone()
    if row and row[1] in ("queued", "processing", "ready") and not force:
        return ""
    if row:
        document_id = row[0]
        path = _write_file(document_id, filename, data)
        conn.execute(
            """
            UPDATE rag_documents
            SET title=%s, brand=%s, brand_key=%s, doc_type=%s, lang=%s, scope=%s, line=%s,
                filename=%s, stored_path=%s, source_url=%s, status='queued', error='', chunk_count=0
            WHERE id=%s
            """,
            (
                meta["title"], meta["brand"], meta["brand_key"], meta["doc_type"], meta["lang"], meta["scope"],
                (line or "")[:40], safe_name(filename), str(path), meta["source_url"], document_id,
            ),
        )
        return _publish_or_fail(conn, document_id)
    document_id = conn.execute(
        """
        INSERT INTO rag_documents (
            title, brand, brand_key, doc_type, lang, scope, line, filename, source_url, source_key, uploaded_by, status
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued')
        RETURNING id
        """,
        (
            meta["title"], meta["brand"], meta["brand_key"], meta["doc_type"], meta["lang"], meta["scope"],
            (line or "")[:40], safe_name(filename), meta["source_url"], source_key, uploaded_by,
        ),
    ).fetchone()[0]
    path = _write_file(document_id, filename, data)
    conn.execute("UPDATE rag_documents SET stored_path=%s WHERE id=%s", (str(path), document_id))
    return _publish_or_fail(conn, document_id)


def accept_upload(conn, user_id, fields, filename, data):
    def one(name):
        return (fields.get(name) or [""])[0]

    return enqueue_bytes(
        conn,
        title=one("title"),
        brand=one("brand"),
        doc_type=one("doc_type") or "warranty",
        lang=one("lang") or "vi",
        filename=filename,
        data=data,
        source_url=one("source_url"),
        scope=one("scope"),
        uploaded_by=user_id,
    )


def requeue(conn, document_id):
    row = conn.execute("SELECT id FROM rag_documents WHERE id=%s", (int(document_id),)).fetchone()
    if not row:
        return "Không thấy tài liệu."
    conn.execute(
        "UPDATE rag_documents SET status='queued', error='' WHERE id=%s",
        (int(document_id),),
    )
    return _publish_or_fail(conn, document_id)


def remove_document(conn, document_id):
    row = conn.execute(
        "SELECT stored_path FROM rag_documents WHERE id=%s",
        (int(document_id),),
    ).fetchone()
    if not row:
        return "Không thấy tài liệu."
    try:
        from .vectors import delete_document

        delete_document(document_id)
    except Exception as exc:
        return "Chưa xóa được vector trên Qdrant. {0}".format(public_error(exc))
    path = row[0] or ""
    if path and _managed(path):
        Path(path).unlink(missing_ok=True)
    conn.execute("DELETE FROM rag_documents WHERE id=%s", (int(document_id),))
    return ""


def list_documents(conn, limit=80):
    rows = conn.execute(
        """
        SELECT id, title, brand, doc_type, lang, filename, status, chunk_count, error, created_at, scope
        FROM rag_documents
        ORDER BY id DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "title": row[1],
            "brand": row[2],
            "doc_type": row[3],
            "lang": row[4],
            "filename": row[5],
            "status": row[6],
            "chunk_count": row[7],
            "error": row[8] or "",
            "created_at": row[9],
            "scope": row[10] or "",
        })
    return items


def broker_status():
    parts = []
    try:
        from .vectors import point_count

        parts.append("Qdrant đang mở, {0} đoạn.".format(point_count()))
    except Exception:
        parts.append("Qdrant chưa mở.")
    try:
        from .broker import queue_ready

        if queue_ready():
            parts.append("RabbitMQ đang mở.")
    except Exception:
        parts.append("RabbitMQ chưa mở.")
    return " ".join(parts)


def load_document(conn, document_id):
    row = conn.execute(
        """
        SELECT id, title, brand, brand_key, doc_type, lang, scope, line, filename, stored_path, source_url, status
        FROM rag_documents WHERE id=%s
        """,
        (int(document_id),),
    ).fetchone()
    if not row:
        return None
    keys = (
        "id", "title", "brand", "brand_key", "doc_type", "lang", "scope", "line",
        "filename", "stored_path", "source_url", "status",
    )
    return dict(zip(keys, row))


def process_document(conn, document_id):
    """Chunk, embed, and replace this document's points. Failures are stored on the row."""
    document = load_document(conn, document_id)
    if not document:
        return
    conn.execute(
        "UPDATE rag_documents SET status='processing', error='' WHERE id=%s",
        (int(document_id),),
    )
    try:
        path = document["stored_path"]
        if not path or not Path(path).is_file():
            raise RuntimeError("Không thấy file đã lưu.")
        parts = chunk_text(extract_text(path))
        if not parts:
            raise RuntimeError("File không có đoạn chữ để nhúng.")
        if len(parts) > MAX_CHUNKS:
            raise RuntimeError("Tài liệu dài quá {0} đoạn. Hãy tách nhỏ.".format(MAX_CHUNKS))
        from .embed import embed_texts
        from .vectors import upsert_document

        heading = document["title"]
        if document.get("scope"):
            heading = heading + ". " + document["scope"]
        embedded = [heading + "\n" + part for part in parts]
        vectors = embed_texts(embedded)
        payloads = [
            {
                "document_id": int(document_id),
                "chunk_index": index,
                "title": document["title"],
                "brand": document["brand"],
                "brand_key": document["brand_key"],
                "doc_type": document["doc_type"],
                "lang": document["lang"],
                "scope": document["scope"],
                "line": document.get("line") or "",
                "source_url": document["source_url"],
                "text": embedded[index],
            }
            for index, part in enumerate(parts)
        ]
        upsert_document(document_id, vectors, payloads)
    except Exception as exc:
        _mark_failed(conn, document_id, exc)
        raise
    conn.execute(
        "UPDATE rag_documents SET status='ready', chunk_count=%s, error='' WHERE id=%s",
        (len(parts), int(document_id)),
    )


def _warranty_bytes(root, slug):
    from .textutil import extract_text

    raw_path = root / "raw" / slug / "body.html"
    text_path = root / "text" / (slug + ".txt")
    if raw_path.is_file():
        text = extract_text(raw_path)
        if len(text) > 400:
            return (slug + ".txt", text.encode("utf-8"))
    if text_path.is_file():
        return (slug + ".txt", text_path.read_bytes())
    return None


def enqueue_warranty_corpus(conn, force=False):
    """Copy the usable warranty extracts into the queue. Skips a slug that is already queued or ready."""
    root = Path(__file__).resolve().parents[2] / "data" / "warranty"
    queued = 0
    skipped = 0
    for slug, brand, title, lang, scope, line in WARRANTY_SEEDS:
        loaded = _warranty_bytes(root, slug)
        if not loaded:
            continue
        filename, data = loaded
        source_url = ""
        meta_path = root / "raw" / slug / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text())
            source_url = (meta.get("final_url") or meta.get("requested_url") or "")[:300]
        before = conn.execute(
            "SELECT status FROM rag_documents WHERE source_key=%s",
            ("warranty:" + slug,),
        ).fetchone()
        error = enqueue_bytes(
            conn,
            title=title,
            brand=brand,
            doc_type="warranty",
            lang=lang,
            filename=filename,
            data=data,
            source_url=source_url,
            scope=scope,
            line=line,
            source_key="warranty:" + slug,
            force=force,
        )
        if error:
            raise RuntimeError(error)
        if before and before[0] in ("queued", "processing", "ready") and not force:
            skipped += 1
        else:
            queued += 1
    return queued, skipped
