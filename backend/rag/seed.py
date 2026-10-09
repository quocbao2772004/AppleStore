"""Put the usable warranty extracts on the RabbitMQ queue.

    .venv/bin/python backend/rag/seed.py

Does not embed by itself. The worker does that. Blocked and wrong pages are not in the list.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rag.documents import connect, enqueue_warranty_corpus, ensure_table
from rag.settings import load_env


def main():
    load_env()
    force = "--refresh" in sys.argv
    with connect() as conn:
        ensure_table(conn)
        queued, skipped = enqueue_warranty_corpus(conn, force=force)
    print("queued={0} skipped={1}".format(queued, skipped))


if __name__ == "__main__":
    main()
