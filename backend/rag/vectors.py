"""Qdrant collection store_documents. Payload holds the passage. Price and stock stay in Postgres."""
import uuid

from .settings import COLLECTION, VECTOR_SIZE, qdrant_url

_NAMESPACE = uuid.UUID("6f3c1c3e-7a1e-4d1a-9c1e-0c0a0a0a0a01")


def point_id(document_id, index):
    return str(uuid.uuid5(_NAMESPACE, "{0}:{1}".format(int(document_id), int(index))))


def _client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=qdrant_url(), timeout=20, prefer_grpc=False, check_compatibility=False)


def _vector_size(info):
    vectors = info.config.params.vectors
    if hasattr(vectors, "size"):
        return vectors.size
    if isinstance(vectors, dict) and "size" in vectors:
        return vectors["size"]
    raise RuntimeError("Collection {0} không phải một vector đặc.".format(COLLECTION))


def ensure_collection(client=None):
    from qdrant_client.models import Distance, VectorParams

    client = client or _client()
    names = [item.name for item in client.get_collections().collections]
    if COLLECTION not in names:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    else:
        size = _vector_size(client.get_collection(COLLECTION))
        if size != VECTOR_SIZE:
            raise RuntimeError(
                "Collection {0} đang là {1} chiều, cần {2} cho text-embedding-3-small.".format(
                    COLLECTION, size, VECTOR_SIZE
                )
            )
    for field, schema in (("document_id", "integer"), ("doc_type", "keyword"), ("brand_key", "keyword"), ("line", "keyword")):
        try:
            client.create_payload_index(COLLECTION, field, field_schema=schema)
        except Exception:
            pass
    return client


def point_count():
    client = ensure_collection()
    info = client.get_collection(COLLECTION)
    return int(info.points_count or 0)


def delete_document(document_id):
    from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

    client = ensure_collection()
    client.delete(
        collection_name=COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=int(document_id)))]
            )
        ),
    )


def upsert_document(document_id, vectors, payloads):
    from qdrant_client.models import PointStruct

    client = ensure_collection()
    delete_document(document_id)
    points = [
        PointStruct(id=point_id(document_id, index), vector=vector, payload=payload)
        for index, (vector, payload) in enumerate(zip(vectors, payloads))
    ]
    for start in range(0, len(points), 64):
        client.upsert(collection_name=COLLECTION, points=points[start:start + 64])


def query_passages(vector, doc_type="", brand_key="", line="", limit=4):
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = ensure_collection()
    must = []
    if doc_type:
        must.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if brand_key:
        must.append(FieldCondition(key="brand_key", match=MatchValue(value=brand_key)))
    if line:
        must.append(FieldCondition(key="line", match=MatchValue(value=line)))
    found = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=Filter(must=must) if must else None,
        limit=limit,
        with_payload=True,
    )
    passages = []
    for point in found.points:
        payload = point.payload or {}
        passages.append({
            "score": round(float(point.score or 0), 4),
            "title": payload.get("title") or "",
            "brand": payload.get("brand") or "",
            "doc_type": payload.get("doc_type") or "",
            "scope": payload.get("scope") or "",
            "line": payload.get("line") or "",
            "source_url": payload.get("source_url") or "",
            "text": payload.get("text") or "",
        })
    return passages
