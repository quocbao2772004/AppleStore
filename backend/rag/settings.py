"""Env for the document index. Defaults match a broker and Qdrant on this machine."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "store_documents"
QUEUE = "rag.documents"
VECTOR_SIZE = 1536
EMBEDDING_MODEL_DEFAULT = "text-embedding-3-small"
FILE_DIR = ROOT / "data" / "rag" / "files"
MAX_UPLOAD_BYTES = 2_200_000
MAX_CHUNKS = 450
CHUNK_CHARS = 700
CHUNK_OVERLAP = 100
MIN_SCORE = 0.28

DOC_TYPES = (
    ("warranty", "Bảo hành"),
    ("store_policy", "Chính sách cửa hàng"),
    ("return", "Đổi trả"),
    ("privacy", "Quyền riêng tư"),
    ("eula", "Giấy phép phần mềm"),
    ("other", "Khác"),
)
DOC_TYPE_KEYS = {key for key, _label in DOC_TYPES}


def load_env():
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def database_url():
    return os.environ.get("DATABASE_URL", "dbname=tgdd_products")


def qdrant_url():
    return os.environ.get("QDRANT_URL", "http://127.0.0.1:6333").strip().rstrip("/")


def rabbitmq_url():
    return os.environ.get("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/").strip()


def embedding_model():
    return os.environ.get("EMBEDDING_MODEL", EMBEDDING_MODEL_DEFAULT).strip() or EMBEDDING_MODEL_DEFAULT


def openai_base():
    return os.environ.get("base_url", "https://api.openai.com/v1").strip().rstrip("/")


def openai_key():
    return os.environ.get("OPENAI_API_KEY", "").strip()
