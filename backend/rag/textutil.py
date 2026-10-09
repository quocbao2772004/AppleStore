"""Turn an uploaded file into overlapping passages."""
import re
from pathlib import Path

from .settings import CHUNK_CHARS, CHUNK_OVERLAP

_ALLOWED = {".txt", ".md", ".html", ".htm"}
_POLICY_RE = re.compile(r"bảo hành|bao hanh|warranty|thời hạn|đổi trả|doi tra|tháng|năm|ngày", re.I)
_JUNK_RE = re.compile(r"window\.|pageDsl|linkTarget|\"cmps\"|CustomHtmlScript", re.I)
_CSS_RE = re.compile(r"!important|nth-of-type|font-family|@media|html-text-component", re.I)
_DURATION_RE = re.compile(r"\d+\s*(tháng|năm|ngày)", re.I)


def allowed_name(filename):
    suffix = Path(filename or "").suffix.lower()
    return suffix in _ALLOWED


def safe_name(filename):
    base = Path(filename or "").name
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-")[:80]
    return base or "tai-lieu.txt"


def _unescape(html):
    html = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), html)
    return html.replace("\\n", "\n").replace("\\t", " ").replace("\\/", "/").replace('\\"', '"')


def _keep_line(line):
    if not line or _JUNK_RE.search(line) or _CSS_RE.search(line):
        return False
    if len(line) >= 40:
        return True
    return _POLICY_RE.search(line) is not None


def _header_row(cells, following):
    """A first row of td cells is a header when the next row carries the duration."""
    if not following or len(cells) != len(following):
        return False
    if _DURATION_RE.search(" ".join(cells)):
        return False
    return _DURATION_RE.search(" ".join(following)) is not None


def _row_line(headers, cells):
    if headers and len(cells) == len(headers):
        pairs = [
            "{0}: {1}".format(header, cell)
            for header, cell in zip(headers, cells)
            if cell and cell.strip() != "/"
        ]
        return "; ".join(pairs)
    return " | ".join(cell for cell in cells if cell and cell.strip() != "/")


def _table_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = [
            " ".join(td.get_text(" ", strip=True).split())
            for td in tr.find_all(["th", "td"], recursive=False)
        ]
        if cells:
            rows.append((bool(tr.find("th", recursive=False)), cells))
    return rows


def _header_index(rows):
    for index, (is_header, cells) in enumerate(rows):
        if is_header and len(cells) > 1:
            return index
    for index in range(len(rows) - 1):
        if _header_row(rows[index][1], rows[index + 1][1]):
            return index
    return None


def _tables_to_lines(soup):
    for table in soup.find_all("table"):
        rows = _table_rows(table)
        if not rows:
            continue
        header_at = _header_index(rows)
        if header_at is None:
            lines = [_row_line([], cells) for _is_header, cells in rows]
        else:
            lines = [_row_line([], cells) for _is_header, cells in rows[:header_at]]
            headers = rows[header_at][1]
            lines.extend(_row_line(headers, cells) for _is_header, cells in rows[header_at + 1:])
        table.replace_with("\n".join(line for line in lines if line) + "\n")


def _html_text(html):
    from bs4 import BeautifulSoup

    html = _unescape(html)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "noscript"]):
        tag.decompose()
    # A policy packed inside a script is the page. Other scripts are chrome.
    scripts = soup.find_all("script")
    policy_scripts = []
    for script in scripts:
        content = script.string or script.get_text() or ""
        if _POLICY_RE.search(content) and ("<table" in content.lower() or "<p" in content.lower() or "<h1" in content.lower()):
            policy_scripts.append(_unescape(content))
        script.decompose()
    _tables_to_lines(soup)
    visible = soup.get_text("\n", strip=True)
    if policy_scripts:
        extra = BeautifulSoup("\n".join(policy_scripts), "html.parser")
        _tables_to_lines(extra)
        visible = visible + "\n" + extra.get_text("\n", strip=True)
    lines = []
    for raw_line in visible.splitlines():
        line = " ".join(raw_line.split())
        if _keep_line(line):
            lines.append(line)
    return "\n".join(lines)


def extract_text(path):
    """Visible policy text. Tables become 'cột: giá trị' so a duration stays attached to its part."""
    raw = Path(path).read_bytes()
    suffix = Path(path).suffix.lower()
    text = raw.decode("utf-8", "replace")
    if suffix in {".html", ".htm"} or "<html" in text[:500].lower() or "\\u003c" in text[:2000]:
        return _html_text(text)
    lines = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.replace("\\n", "\n").split())
        if _keep_line(line):
            lines.append(line)
    return "\n".join(lines)


def _junk_piece(piece):
    if _JUNK_RE.search(piece) or _CSS_RE.search(piece):
        return True
    symbols = sum(1 for char in piece if char in '{}"[]')
    return symbols > max(12, int(len(piece) * 0.06))


def _split_long(para, size, overlap):
    sentences = [part.strip() for part in re.split(r"(?<=[\.!?])\s+", para) if part.strip()]
    if len(sentences) == 1:
        start = 0
        pieces = []
        while start < len(para):
            pieces.append(para[start:start + size])
            if start + size >= len(para):
                break
            start += size - overlap
        return pieces
    packed = []
    buf = ""
    for sentence in sentences:
        if len(sentence) > size:
            if buf:
                packed.append(buf)
                buf = ""
            packed.extend(_split_long(sentence, size, overlap))
            continue
        if buf and len(buf) + 1 + len(sentence) > size:
            packed.append(buf)
            buf = sentence
        else:
            buf = (buf + " " + sentence).strip() if buf else sentence
    if buf:
        packed.append(buf)
    return packed


def chunk_text(text, size=CHUNK_CHARS, overlap=CHUNK_OVERLAP):
    """Pack sentences near `size` characters. JSON and menu noise are left out."""
    cleaned = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if not cleaned:
        return []
    pieces = []
    for para in re.split(r"\n\s*\n", cleaned):
        para = re.sub(r"[ \t]{2,}", " ", para).strip()
        if not para or _junk_piece(para):
            continue
        if len(para) <= size:
            pieces.append(para)
        else:
            pieces.extend(part for part in _split_long(para, size, overlap) if not _junk_piece(part))
    blocks = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + 2 + len(piece) > size:
            blocks.append(buf)
            tail = buf[-overlap:].strip()
            letters = [char for char in tail if char.isalpha()]
            upper = sum(1 for char in letters if char.isupper()) / len(letters) if letters else 0
            if upper > 0.6:
                tail = ""
            buf = (tail + "\n" + piece).strip() if tail else piece
            if len(buf) > size + overlap:
                buf = piece
        else:
            buf = (buf + "\n" + piece).strip() if buf else piece
    if buf:
        blocks.append(buf)
    kept = [block for block in blocks if len(block) >= 80 or _POLICY_RE.search(block)]
    kept = [block for block in kept if len(block) >= 40]
    if kept:
        return kept
    if len(cleaned) >= 40:
        return [cleaned[:size]]
    return []
