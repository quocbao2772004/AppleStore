"""One embedding model for documents and for the question. The collection cannot mix models."""
import json
import re
import urllib.error
import urllib.request

from .settings import VECTOR_SIZE, embedding_model, openai_base, openai_key

_BATCH = 16


def public_error(exc):
    text = str(exc or "")
    text = re.sub(r"amqp://\S+", "amqp://…", text)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "…", text)
    text = re.sub(r"Bearer\s+\S+", "Bearer …", text, flags=re.I)
    return text[:300]


def embed_texts(texts):
    """Return one 1536-d vector per text, using text-embedding-3-small unless EMBEDDING_MODEL overrides it."""
    key = openai_key()
    if not key:
        raise RuntimeError("Thiếu OPENAI_API_KEY nên chưa tạo được vector.")
    model = embedding_model()
    url = openai_base() + "/embeddings"
    vectors = []
    for start in range(0, len(texts), _BATCH):
        part = texts[start:start + _BATCH]
        body = json.dumps({"model": model, "input": part}).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:240].decode("utf-8", "replace")
            raise RuntimeError("API embedding trả {0}: {1}".format(exc.code, public_error(detail))) from None
        rows = sorted(payload.get("data") or [], key=lambda row: row.get("index") or 0)
        if len(rows) != len(part):
            raise RuntimeError("API embedding trả thiếu vector.")
        for row in rows:
            vector = row.get("embedding") or []
            if len(vector) != VECTOR_SIZE:
                raise RuntimeError(
                    "Vector không đúng {0} chiều (nhận {1}). Model phải là {2}.".format(
                        VECTOR_SIZE, len(vector), model
                    )
                )
            vectors.append(vector)
    return vectors
