"""Invoice mail: HTML body and SMTP hand-off. Does not place an order or open a real mailbox."""

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import invoice


def sample_order():
    return {
        "id": 12,
        "ship_name": "Bảo <script>",
        "ship_email": "khach@form.local",
        "ship_phone": "0900000000",
        "ship_address": "Quận 1",
        "deliver_on": datetime(2026, 10, 2).date(),
        "deliver_slot": "morning",
        "pay_method": "cod",
        "total": 16990000,
        "created_at": datetime(2026, 10, 1, 9, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
        "items": [{"name": "Tai nghe <b>", "qty": 2, "unit_price": 8495000}],
    }


class InvoiceBodyTests(unittest.TestCase):
    def test_html_escapes_names_and_lists_the_line_total(self):
        plain, page = invoice.invoice_bodies(sample_order())
        self.assertIn("Hoá đơn đơn hàng #12", invoice.invoice_subject(sample_order()))
        self.assertNotIn("<script>", page)
        self.assertIn("Bảo &lt;script&gt;", page)
        self.assertIn("Tai nghe &lt;b&gt;", page)
        self.assertIn("16.990.000₫", page)
        self.assertIn("Sáng 8:00–12:00", plain)
        self.assertIn("Thanh toán khi nhận hàng", plain)
        self.assertIn("Chưa trừ tiền thật.", plain)

    def test_status_note_distinguishes_sent_missing_and_failed(self):
        self.assertIn("Đã gửi hoá đơn", invoice.invoice_status_note(True, ""))
        self.assertIn("Chưa gửi hoá đơn", invoice.invoice_status_note(None, ""))
        self.assertIn("Không gửi được", invoice.invoice_status_note(None, "Không gửi được hoá đơn qua email."))
        self.assertIn("Chưa trừ tiền thật.", invoice.invoice_status_note(True, ""))


class InvoiceSendTests(unittest.TestCase):
    def test_missing_mailbox_does_not_open_smtp(self):
        env = {"SMTP_HOST": "", "SMTP_USER": "", "SMTP_PASSWORD": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch("invoice.smtplib.SMTP") as smtp:
                sent, note = invoice.send_invoice(sample_order())
        self.assertFalse(sent)
        self.assertIn("Chưa cấu hình", note)
        smtp.assert_not_called()

    def test_configured_mailbox_logs_in_and_sends_html(self):
        env = {
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": "587",
            "SMTP_USER": "shop@example.test",
            "SMTP_PASSWORD": "secret",
        }
        sent_messages = []

        class FakeSMTP:
            def __init__(self, host, port, timeout=None):
                self.host = host
                self.port = port

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def ehlo(self):
                return None

            def starttls(self):
                return None

            def login(self, user, password):
                self.user = user
                self.password = password

            def send_message(self, message):
                sent_messages.append(message)

        with patch.dict("os.environ", env, clear=False):
            with patch("invoice.smtplib.SMTP", FakeSMTP):
                sent, note = invoice.send_invoice(sample_order())
        self.assertTrue(sent)
        self.assertEqual(note, "")
        self.assertEqual(len(sent_messages), 1)
        message = sent_messages[0]
        self.assertEqual(message["To"], "khach@form.local")
        self.assertIn("Octopus Store", message["From"])
        html_part = message.get_body(preferencelist=("html",))
        self.assertIn("16.990.000₫", html_part.get_content())
        self.assertIn("Tai nghe &lt;b&gt;", html_part.get_content())


class DeliverInvoiceTests(unittest.TestCase):
    def test_failed_send_is_stored_and_the_order_stays(self):
        class Result:
            def __init__(self, one=None, rows=None):
                self.one = one
                self.rows = rows or []

            def fetchone(self):
                return self.one

            def fetchall(self):
                return self.rows

        class Conn:
            def __init__(self):
                self.writes = []

            def execute(self, sql, params=None):
                if "FROM orders" in sql:
                    order = sample_order()
                    return Result(one=(
                        order["id"], order["ship_name"], order["ship_email"], order["ship_phone"],
                        order["ship_address"], order["deliver_on"], order["deliver_slot"],
                        order["pay_method"], order["total"], order["created_at"],
                    ))
                if "order_items" in sql:
                    return Result(rows=[("Tai nghe", 2, 8495000)])
                self.writes.append((sql, params))
                return Result()

        conn = Conn()
        env = {"SMTP_HOST": "", "SMTP_USER": "", "SMTP_PASSWORD": ""}
        with patch.dict("os.environ", env, clear=False):
            note = invoice.deliver_invoice(conn, 12)
        self.assertIn("Chưa cấu hình", note)
        self.assertIn("Chưa trừ tiền thật.", note)
        self.assertEqual(len(conn.writes), 1)
        sql, params = conn.writes[0]
        self.assertIn("invoice_error", sql)
        self.assertNotIn("DELETE", sql.upper())
        self.assertEqual(params[1], 12)


if __name__ == "__main__":
    unittest.main()
