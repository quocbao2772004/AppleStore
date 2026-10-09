"""One short RabbitMQ connection per upload. The message is only the document id."""
import json

from .settings import QUEUE, rabbitmq_url


def _parameters():
    import pika

    params = pika.URLParameters(rabbitmq_url())
    params.socket_timeout = 5
    params.connection_attempts = 2
    params.retry_delay = 0.5
    params.heartbeat = 0
    params.blocked_connection_timeout = 30
    return params


def publish(document_id):
    import pika

    connection = pika.BlockingConnection(_parameters())
    try:
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=json.dumps({"id": int(document_id)}).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()


def queue_ready():
    """True when the broker accepts a connection. Does not publish."""
    connection = None
    try:
        import pika

        connection = pika.BlockingConnection(_parameters())
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE, durable=True)
        return True
    finally:
        if connection is not None:
            connection.close()
