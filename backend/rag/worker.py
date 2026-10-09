"""Consume rag.documents and embed each id.

Run from the repository root:

    .venv/bin/python backend/rag/worker.py

A store restart does not stop this process. Leave it running while admin uploads are in the queue.
Heartbeats are off because one document can take longer than a broker heartbeat to embed.
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rag.documents import connect, ensure_table, process_document
from rag.embed import public_error
from rag.settings import QUEUE, embedding_model, load_env


def handle(body):
    payload = json.loads(body.decode())
    document_id = int(payload["id"])
    with connect() as conn:
        ensure_table(conn)
        process_document(conn, document_id)
    print("ready id={0}".format(document_id), file=sys.stderr, flush=True)


def main():
    load_env()
    import pika

    from rag.broker import _parameters

    print("worker model={0} queue={1}".format(embedding_model(), QUEUE), file=sys.stderr, flush=True)
    connection = pika.BlockingConnection(_parameters())
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(channel, method, _properties, body):
        try:
            handle(body)
        except Exception as exc:
            print("failed {0}".format(public_error(exc)), file=sys.stderr, flush=True)
        channel.basic_ack(method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=on_message, auto_ack=False)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    connection.close()


if __name__ == "__main__":
    main()
