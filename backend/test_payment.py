"""Transfer match and confirmation mail. Does not call a bank or a mailbox."""

import os
import unittest
from email.message import EmailMessage
from unittest.mock import patch

import payment


class PaymentTests(unittest.TestCase):
    def test_reference_and_vietqr_use_env_account(self):
        self.assertEqual(payment.transfer_reference(12), "OCTO12")
        env = {
            "BANK_ID": "MB",
            "BANK_ACCOUNT": "000111222",
            "BANK_ACCOUNT_NAME": "Cua hang",
        }
        with patch.dict(os.environ, env, clear=False):
            url = payment.vietqr_url(16990000, "OCTO12")
        self.assertIn("/MB-000111222-compact2.png", url)
        self.assertIn("amount=16990000", url)
        self.assertIn("addInfo=OCTO12", url)
        self.assertNotIn("6866", url)

    def test_match_credit_needs_reference_and_amount(self):
        rows = [
            {"addDescription": "chuyen khoan khac", "creditAmount": "16990000"},
            {"addDescription": "OCTO12 dat hang", "creditAmount": "1000"},
            {"description": "nop octo12", "creditAmount": 16990000},
        ]
        hit = payment.match_credit(rows, "OCTO12", 16990000)
        self.assertEqual(hit["amount"], 16990000.0)
        self.assertIn("octo12", hit["description"].casefold())
        self.assertIsNone(payment.match_credit(rows, "OCTO99", 16990000))
        self.assertIsNone(payment.match_credit([{"addDescription": "OCTO12", "creditAmount": 0}], "OCTO12", 0))
        self.assertIsNone(payment.match_credit([{"addDescription": "OCTO123", "creditAmount": 16990000}], "OCTO12", 16990000))

    def test_missing_bank_login_does_not_call_the_bank(self):
        with patch.dict(os.environ, {"BANK_USERNAME": "", "BANK_PASSWORD": "", "BANK_ACCOUNT": ""}, clear=False):
            with self.assertRaises(RuntimeError) as caught:
                payment.recent_credits()
        self.assertIn("Chưa cấu hình", str(caught.exception))

    def test_confirmation_mail_escapes_the_name_and_names_the_order(self):
        order = {
            "id": 12,
            "ship_name": "Bảo <script>",
            "ship_email": "khach@form.local",
            "total": 16990000,
        }
        sent_messages = []

        class FakeSMTP:
            def __init__(self, host, port, timeout=0):
                self.host = host

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

            def send_message(self, message):
                sent_messages.append(message)

        env = {
            "SMTP_HOST": "smtp.example",
            "SMTP_PORT": "587",
            "SMTP_USER": "shop@form.local",
            "SMTP_PASSWORD": "secret",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("payment.smtplib.SMTP", FakeSMTP):
                sent, error = payment.send_payment_confirmation(order, {"transactionDate": "2026-10-10"})
        self.assertTrue(sent)
        self.assertEqual(error, "")
        message = sent_messages[0]
        self.assertIsInstance(message, EmailMessage)
        self.assertEqual(message["Subject"], "Đã nhận chuyển khoản đơn #12")
        self.assertEqual(message["To"], "khach@form.local")
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertNotIn("<script>", html)
        self.assertIn("OCTO12", html)
        self.assertIn("Đã nhận chuyển khoản", html)

    def test_history_rows_reads_model_dump(self):
        class Row:
            def model_dump(self):
                return {
                    "addDescription": "OCTO12 dat hang",
                    "creditAmount": "16990000",
                    "transactionDate": "10/10/2026",
                }

        class History:
            transactionHistoryList = [Row()]

        rows = payment.history_rows(History())
        hit = payment.match_credit(rows, "OCTO12", 16990000)
        self.assertEqual(hit["amount"], 16990000.0)
        self.assertEqual(hit["transactionDate"], "10/10/2026")


if __name__ == "__main__":
    unittest.main()
