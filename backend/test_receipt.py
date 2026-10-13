"""Receipt layout and transfer settlement. No bank call and no mailbox."""

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import payment
import server


ROOT = Path(__file__).resolve().parents[1]


class ScriptedConn:
    def __init__(self, order_row, items=None):
        self.order_row = order_row
        self.items = items or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        row = self.order_row
        items = self.items

        class Result:
            def fetchone(_self):
                return row

            def fetchall(_self):
                return items

        return Result()


def receipt_row(pay_method="qr", paid_at=None, user_id=7, email_sent=None, email_error=None):
    return (
        12,
        user_id,
        16990000,
        "placed",
        "Bảo <script>",
        "khach@form.local",
        "0900000000",
        "Hà Nội",
        date(2026, 10, 11),
        "afternoon",
        pay_method,
        None,
        None,
        None,
        paid_at,
        email_sent,
        email_error,
    )


def payable_row(pay_method="qr", paid_at=None, user_id=7):
    return (12, user_id, 16990000, pay_method, "Bảo", "khach@form.local", paid_at, None, "")


BANK = {"BANK_ID": "MB", "BANK_ACCOUNT": "000111222", "BANK_ACCOUNT_NAME": "Cua hang"}
NO_BANK = {"BANK_ID": "", "BANK_ACCOUNT": "", "BANK_ACCOUNT_NAME": ""}


class ReceiptLayoutTests(unittest.TestCase):
    def test_unpaid_transfer_puts_the_code_beside_the_order(self):
        conn = ScriptedConn(receipt_row(), [("iPhone 16 128GB", 1, 16990000)])
        user = {"id": 7, "role": "customer"}
        with patch.dict("os.environ", BANK, clear=False):
            page = server.render_receipt(conn, user, 12)
        pane = page.index('class="pay-pane"')
        info = page.index('class="receipt-info"')
        self.assertLess(pane, info)
        self.assertIn('class="receipt-grid"', page)
        self.assertIn('src="/orders/12/pay-qr"', page)
        self.assertIn("OCTO12", page)
        self.assertIn('action="/orders/12/pay-check"', page)
        self.assertIn("Đối soát chuyển khoản", page)
        self.assertIn("16.990.000₫", page)
        self.assertNotIn("<script>", page)
        self.assertIn("Bảo &lt;script&gt;", page)

    def test_transfer_without_bank_config_keeps_the_local_mark(self):
        conn = ScriptedConn(receipt_row())
        with patch.dict("os.environ", NO_BANK, clear=False):
            page = server.render_receipt(conn, {"id": 7, "role": "customer"}, 12)
        self.assertIn('class="pay-mark"', page)
        self.assertIn('class="receipt-grid"', page)
        self.assertNotIn("/pay-qr", page)
        self.assertNotIn("Đối soát chuyển khoản", page)

    def test_paid_transfer_and_cash_stay_one_column(self):
        owner = {"id": 7, "role": "customer"}
        paid = server.render_receipt(
            ScriptedConn(receipt_row(paid_at="2026-10-10", email_sent="2026-10-10")),
            owner,
            12,
        )
        cash = server.render_receipt(ScriptedConn(receipt_row(pay_method="cod")), owner, 12)
        self.assertNotIn("receipt-grid", paid)
        self.assertIn("Đã khớp chuyển khoản", paid)
        self.assertNotIn("/pay-qr", paid)
        self.assertNotIn("receipt-grid", cash)
        self.assertIn("Thanh toán khi nhận hàng", cash)
        self.assertNotIn("pay-mark", cash)
        self.assertIsNone(server.render_receipt(ScriptedConn(receipt_row()), {"id": 9, "role": "customer"}, 12))
        admin = server.render_receipt(ScriptedConn(receipt_row(pay_method="cod")), {"id": 1, "role": "admin"}, 12)
        self.assertIn("Phiếu đơn #12", admin)

    def test_stylesheet_sizes_the_code_beside_the_sheet(self):
        css = (ROOT / "frontend" / "store.css").read_text()
        self.assertIn("grid-template-columns: minmax(340px, 440px) minmax(0, 1fr)", css)
        self.assertIn("max-width: 392px", css)
        self.assertIn(".pay-pane form { order: -1;", css)
        self.assertIn("store.css?v=105", (ROOT / "backend" / "server.py").read_text())


class SettlementTests(unittest.TestCase):
    def test_cash_order_does_not_read_the_bank(self):
        conn = ScriptedConn(payable_row(pay_method="cod"))
        with patch("payment.recent_credits", side_effect=AssertionError("bank")):
            note, status = server.Handler.settle_transfer(None, conn, {"id": 7, "role": "customer"}, 12)
        self.assertEqual(status, 400)
        self.assertIn("trả khi nhận hàng", note)

    def test_paid_order_does_not_read_the_bank(self):
        conn = ScriptedConn(payable_row(paid_at="2026-10-10"))
        with patch("payment.recent_credits", side_effect=AssertionError("bank")):
            note, status = server.Handler.settle_transfer(None, conn, {"id": 7, "role": "customer"}, 12)
        self.assertEqual(status, 200)
        self.assertIn("Đã khớp chuyển khoản", note)

    def test_unmatched_transfer_stays_unpaid(self):
        conn = ScriptedConn(payable_row())
        with patch("payment.recent_credits", return_value=[{"addDescription": "khac", "creditAmount": "1"}]):
            with patch("payment.mark_paid", side_effect=AssertionError("paid")):
                note, status = server.Handler.settle_transfer(None, conn, {"id": 7, "role": "customer"}, 12)
        self.assertEqual(status, 400)
        self.assertIn("Chưa thấy chuyển khoản", note)
        self.assertFalse(any(sql.startswith("UPDATE") for sql, _params in conn.calls))

    def test_matching_transfer_marks_paid_before_mail(self):
        conn = ScriptedConn(payable_row())
        hit = {"description": "OCTO12", "amount": 16990000.0, "transactionDate": "10/10/2026"}
        with patch("payment.recent_credits", return_value=[hit]):
            with patch("payment.send_payment_confirmation", return_value=(False, "Chưa cấu hình hộp thư gửi xác nhận.")):
                note = payment.mark_paid(conn, {"id": 12, "ship_email": "khach@form.local", "ship_name": "Bảo", "total": 16990000}, hit)
        sql = [item[0] for item in conn.calls]
        self.assertTrue(sql[0].startswith("UPDATE orders SET paid_at"))
        self.assertIn("payment_email_error", sql[1])
        self.assertIn("Đã khớp chuyển khoản", note)
        self.assertIn("Chưa cấu hình hộp thư", note)

    def test_other_customer_cannot_settle(self):
        conn = ScriptedConn(payable_row(user_id=7))
        note, status = server.Handler.settle_transfer(None, conn, {"id": 9, "role": "customer"}, 12)
        self.assertEqual(status, 404)
        self.assertIn("Không thấy đơn", note)

    def test_qr_image_uses_the_order_total_and_refuses_cash(self):
        class FakeHandler:
            def __init__(self):
                self.status = None
                self.headers = []
                self.body = b""

            def send_error(self, status):
                self.status = status

            def send_text(self, text, status=200):
                self.status = status
                self.body = text.encode("utf-8")

            def send_response(self, status):
                self.status = status

            def send_header(self, key, value):
                self.headers.append((key, value))

            def end_headers(self):
                return None

            def write(self, data):
                self.body += data

        class Writer:
            def __init__(self, handler):
                self.handler = handler

            def write(self, data):
                self.handler.body += data

        cash = FakeHandler()
        server.Handler.send_pay_qr(cash, ScriptedConn(payable_row(pay_method="cod")), {"id": 7, "role": "customer"}, 12)
        self.assertEqual(cash.status, 404)

        image = FakeHandler()
        image.wfile = Writer(image)
        with patch.dict("os.environ", BANK, clear=False):
            with patch("payment.fetch_vietqr", return_value=b"\x89PNG\r\n\x1a\nqr") as fetch:
                server.Handler.send_pay_qr(image, ScriptedConn(payable_row()), {"id": 7, "role": "customer"}, 12)
        fetch.assert_called_once_with(16990000, "OCTO12")
        self.assertEqual(image.status, 200)
        self.assertIn(("Content-Type", "image/png"), image.headers)
        self.assertTrue(image.body.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
