"""Transfer QR, bank match, and the payment confirmation email.

BANK_ID, BANK_ACCOUNT and BANK_ACCOUNT_NAME build the VietQR.
BANK_USERNAME and BANK_PASSWORD are read only when đối soát asks the bank.
SMTP reuses SMTP_HOST, SMTP_PORT, SMTP_USER and SMTP_PASSWORD.
None of those values belong in this file.
"""

import os
import re
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

import requests

import invoice


def transfer_reference(order_id):
    return f"OCTO{int(order_id)}"


def _bank_id():
    raw = (os.environ.get("BANK_ID") or "MB").strip()
    cleaned = "".join(ch for ch in raw if ch.isalnum())
    return cleaned or "MB"


def _account():
    return "".join(ch for ch in (os.environ.get("BANK_ACCOUNT") or "") if ch.isalnum())


def _account_name():
    return " ".join((os.environ.get("BANK_ACCOUNT_NAME") or "").split())


def bank_ready():
    return bool(_account() and _account_name())


def login_ready():
    user = (os.environ.get("BANK_USERNAME") or "").strip()
    password = os.environ.get("BANK_PASSWORD") or ""
    return bool(user and password.strip() and _account())


def vietqr_url(amount, reference):
    if not bank_ready():
        raise RuntimeError("Chưa cấu hình tài khoản nhận chuyển khoản.")
    info = quote(reference)
    name = quote(_account_name())
    return (
        f"https://img.vietqr.io/image/{_bank_id()}-{_account()}-compact2.png"
        f"?amount={int(amount)}&addInfo={info}&accountName={name}"
    )


def fetch_vietqr(amount, reference):
    url = vietqr_url(amount, reference)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        print(f"vietqr failed: {type(exc).__name__}")
        raise RuntimeError("Chưa lấy được mã chuyển khoản.") from None
    if not response.content:
        raise RuntimeError("Chưa lấy được mã chuyển khoản.")
    return response.content


def match_credit(transactions, reference, amount):
    """Return the first credit that names this order and matches the amount."""
    needle = (reference or "").casefold()
    if not needle:
        return None
    try:
        target = float(amount)
    except (TypeError, ValueError):
        return None
    for row in transactions or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("addDescription") or row.get("description") or "")
        raw = row.get("creditAmount", row.get("amount", 0))
        try:
            got = float(raw or 0)
        except (TypeError, ValueError):
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", text.casefold()) and abs(got - target) < 0.01 and got > 0:
            return {
                "description": text,
                "amount": got,
                "transactionDate": str(row.get("transactionDate") or row.get("date") or ""),
            }
    return None


def history_rows(history):
    if isinstance(history, dict):
        rows = history.get("transactionHistoryList") or []
    else:
        rows = getattr(history, "transactionHistoryList", None) or []
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
        elif hasattr(row, "model_dump"):
            dumped = row.model_dump()
            if isinstance(dumped, dict):
                out.append(dumped)
    return out


def recent_credits():
    if not login_ready():
        raise RuntimeError("Chưa cấu hình đối soát ngân hàng.")
    user = os.environ["BANK_USERNAME"].strip()
    password = os.environ["BANK_PASSWORD"]
    account = _account()
    try:
        from mbbank import MBBank
        now = datetime.now()
        history = MBBank(
            username=user, password=password, retry_times=3, timeout=20
        ).getTransactionAccountHistory(
            accountNo=account,
            from_date=now - timedelta(days=1),
            to_date=now,
        )
    except Exception as exc:
        print(f"bank history failed: {type(exc).__name__}")
        raise RuntimeError("Chưa đọc được sao kê ngân hàng.") from None
    return history_rows(history)


def load_payable(conn, order_id):
    row = conn.execute(
        """
        SELECT id, user_id, total_vnd, coalesce(pay_method, 'cod'), ship_name, ship_email,
               paid_at, payment_email_sent_at, payment_email_error
        FROM orders WHERE id=%s
        """,
        (order_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "total": int(row[2] or 0),
        "pay_method": row[3] or "cod",
        "ship_name": row[4] or "",
        "ship_email": row[5] or "",
        "paid_at": row[6],
        "payment_email_sent_at": row[7],
        "payment_email_error": row[8] or "",
    }


def paid_note(order):
    if order.get("payment_email_sent_at"):
        return "Đã khớp chuyển khoản. Đã gửi email xác nhận tới email nhận hàng."
    if order.get("payment_email_error"):
        return "Đã khớp chuyển khoản. " + order["payment_email_error"]
    return "Đã khớp chuyển khoản."


def confirmation_bodies(order, matched):
    name = invoice._esc(order.get("ship_name") or "Quý khách")
    when = invoice._esc((matched or {}).get("transactionDate") or "")
    total = invoice._esc(invoice.money(order.get("total")))
    ref = invoice._esc(transfer_reference(order.get("id")))
    plain = (
        "Octopus Store\n"
        f"Đã nhận chuyển khoản cho đơn #{order.get('id')}\n\n"
        f"Kính gửi {order.get('ship_name') or 'Quý khách'},\n\n"
        f"Mã đơn: {order.get('id')}\n"
        f"Nội dung: {transfer_reference(order.get('id'))}\n"
        f"Số tiền: {invoice.money(order.get('total'))}\n"
        f"Thời điểm giao dịch: {(matched or {}).get('transactionDate') or ''}\n\n"
        "Shop đã thấy chuyển khoản khớp mã và số tiền.\n"
        "Trân trọng,\n"
        "Octopus Store\n"
    )
    page = f"""<!DOCTYPE html>
<html lang="vi"><body style="margin:0;background:#f5f5f7;color:#1d1d1f;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
  <div style="max-width:560px;margin:24px auto;background:#fff;border-radius:16px;padding:28px;">
    <p style="margin:0 0 8px;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#6e6e73;">Octopus Store</p>
    <h1 style="margin:0 0 16px;font-size:24px;">Đã nhận chuyển khoản</h1>
    <p>Kính gửi {name},</p>
    <p>Shop đã thấy chuyển khoản khớp mã và số tiền của đơn <strong>#{invoice._esc(order.get('id'))}</strong>.</p>
    <p>Nội dung: {ref}<br>Số tiền: {total}<br>Thời điểm: {when}</p>
    <p style="color:#6e6e73;font-size:13px;">Trân trọng,<br>Octopus Store</p>
  </div>
</body></html>"""
    return plain, page


def send_payment_confirmation(order, matched):
    email = (order.get("ship_email") or "").strip()
    if not email:
        return False, "Đơn chưa có email nhận xác nhận."
    if not invoice.smtp_ready():
        return False, "Chưa cấu hình hộp thư gửi xác nhận."
    host = os.environ["SMTP_HOST"].strip()
    user = os.environ["SMTP_USER"].strip()
    password = invoice.smtp_password()
    try:
        port = int(os.environ.get("SMTP_PORT") or "587")
    except ValueError:
        return False, "Cổng SMTP chưa đúng."
    plain, page = confirmation_bodies(order, matched)
    message = EmailMessage()
    message["From"] = formataddr(("Octopus Store", user))
    message["To"] = email
    message["Subject"] = f"Đã nhận chuyển khoản đơn #{order.get('id')}"
    message.set_content(plain)
    message.add_alternative(page, subtype="html")
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, password)
            server.send_message(message)
    except Exception as exc:
        print(f"payment mail order {order.get('id')} failed: {type(exc).__name__}")
        return False, "Không gửi được email xác nhận."
    print(f"payment mail order {order.get('id')} sent")
    return True, ""


def mark_paid(conn, order, matched):
    conn.execute(
        "UPDATE orders SET paid_at = now() WHERE id=%s AND paid_at IS NULL",
        (order["id"],),
    )
    sent, error = send_payment_confirmation(order, matched)
    if sent:
        conn.execute(
            "UPDATE orders SET payment_email_sent_at = now(), payment_email_error = NULL WHERE id=%s",
            (order["id"],),
        )
        return "Đã khớp chuyển khoản. Đã gửi email xác nhận tới email nhận hàng."
    conn.execute(
        "UPDATE orders SET payment_email_error = %s WHERE id=%s",
        (error, order["id"]),
    )
    return "Đã khớp chuyển khoản. " + error
