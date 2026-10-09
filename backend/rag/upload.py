"""Multipart reader for the admin document form. The store has no other file upload."""
import re


def parse_multipart(body, content_type):
    """Return (fields, files). fields maps a name to a list of strings. files maps a name to bytes and a filename."""
    match = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))', content_type or "", re.I)
    if not match:
        raise ValueError("Thiếu boundary.")
    marker = b"--" + (match.group(1) or match.group(2)).encode("utf-8", "replace")
    fields = {}
    files = {}
    for part in body.split(marker):
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if not part or part == b"--" or part.startswith(b"--"):
            continue
        header_blob, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        header = header_blob.decode("utf-8", "replace")
        name_match = re.search(r'name="([^"]+)"', header)
        if not name_match:
            continue
        name = name_match.group(1)
        file_match = re.search(r'filename="([^"]*)"', header)
        if file_match:
            files[name] = {"filename": file_match.group(1), "data": data}
        else:
            fields.setdefault(name, []).append(data.decode("utf-8", "replace"))
    return fields, files
