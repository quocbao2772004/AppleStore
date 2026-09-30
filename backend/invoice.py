"""HTML invoice mail for a placed order.

SMTP settings come from the environment (SMTP_HOST, SMTP_PORT, SMTP_USER,
SMTP_PASSWORD). A missing mailbox or a failed send does not undo the order.
"""

import html
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SLOTS = {
    "morning": "Sáng 8:00–12:00",
    "afternoon": "Chiều 13:00–17:00",
    "evening": "Tối 18:00–21:00",
}
PAY = {
    "cod": "Thanh toán khi nhận hàng",
    "qr": "Chuyển khoản trên máy này",
}


def money(value):
    return f"{int(value or 0):,}".replace(",", ".") + "₫"


def invoice_status_note(sent_at, error):
    tail = "Chưa trừ tiền thật."
    if sent_at:
        return f"Đã gửi hoá đơn tới email nhận hàng. {tail}"
    if error:
        return f"{error} {tail}"
    return f"Chưa gửi hoá đơn qua email. {tail}"


def _esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def _stamp(value, with_time=False):
    if not value:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(ZONE)
        pattern = "%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y"
        return value.strftime(pattern)
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _lines(order):
    rows = []
    for item in order.get("items") or []:
        qty = int(item.get("qty") or 0)
        price = int(item.get("unit_price") or 0)
        rows.append({
            "name": item.get("name") or "Sản phẩm",
            "qty": qty,
            "total": price * qty,
        })
    return rows


def invoice_subject(order):
    return f"Hoá đơn đơn hàng #{order['id']}"


def invoice_bodies(order):
    """Return (plain, html) for one order. Caller-supplied text is escaped in the HTML."""
    lines = _lines(order)
    placed = _stamp(order.get("created_at"), with_time=True)
    receive = _stamp(order.get("deliver_on"))
    slot = SLOTS.get(order.get("deliver_slot") or "", order.get("deliver_slot") or "")
    when = " · ".join(part for part in (receive, slot) if part)
    pay = PAY.get(order.get("pay_method") or "cod", "Thanh toán khi nhận hàng")
    name = order.get("ship_name") or "Quý khách"
    plain_items = "\n".join(
        f"- {item['name']} × {item['qty']} — {money(item['total'])}" for item in lines
    ) or "- (không có dòng hàng)"
    plain = (
        "Octopus Store\n"
        f"Hoá đơn đơn hàng #{order['id']}\n\n"
        f"Kính gửi {name},\n\n"
        f"Mã đơn: {order['id']}\n"
        f"Ngày đặt: {placed}\n"
        f"Nhận hàng: {when}\n"
        f"Thanh toán: {pay}\n"
        f"Người nhận: {name}\n"
        f"Điện thoại: {order.get('ship_phone') or ''}\n"
        f"Địa chỉ: {order.get('ship_address') or ''}\n\n"
        f"{plain_items}\n\n"
        f"Tổng: {money(order.get('total'))}\n\n"
        "Đây là phiếu tham chiếu. Chưa trừ tiền thật.\n"
        "Trân trọng,\n"
        "Octopus Store\n"
    )
    body_rows = "".join(
        "<tr>"
        f'<td style="padding:8px 10px;border-bottom:1px solid #e8e8ed;">{_esc(item["name"])}</td>'
        f'<td style="padding:8px 10px;border-bottom:1px solid #e8e8ed;text-align:center;">{item["qty"]}</td>'
        f'<td style="padding:8px 10px;border-bottom:1px solid #e8e8ed;text-align:right;">{_esc(money(item["total"]))}</td>'
        "</tr>"
        for item in lines
    ) or (
        '<tr><td colspan="3" style="padding:8px 10px;">Không có dòng hàng.</td></tr>'
    )
    page = f"""<!DOCTYPE html>
<html lang="vi">
<body style="margin:0;background:#f5f5f7;color:#1d1d1f;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:24px;">
    <div style="background:#1d1d1f;color:#fff;padding:20px 24px;border-radius:16px 16px 0 0;">
      <p style="margin:0;font-size:13px;letter-spacing:.04em;">OCTOPUS STORE</p>
      <h1 style="margin:8px 0 0;font-size:22px;font-weight:600;">Hoá đơn đơn hàng #{_esc(order["id"])}</h1>
    </div>
    <div style="background:#fff;padding:24px;border-radius:0 0 16px 16px;">
      <p>Kính gửi {_esc(name)},</p>
      <p>Đơn hàng đã được ghi nhận. Đây là phiếu tham chiếu, chưa trừ tiền thật.</p>
      <p><strong>Mã đơn:</strong> {_esc(order["id"])}<br>
         <strong>Ngày đặt:</strong> {_esc(placed)}<br>
         <strong>Nhận hàng:</strong> {_esc(when)}<br>
         <strong>Thanh toán:</strong> {_esc(pay)}</p>
      <p><strong>Người nhận:</strong> {_esc(name)}<br>
         <strong>Điện thoại:</strong> {_esc(order.get("ship_phone") or "")}<br>
         <strong>Địa chỉ:</strong> {_esc(order.get("ship_address") or "")}</p>
      <table style="width:100%;border-collapse:collapse;margin-top:8px;">
        <thead>
          <tr>
            <th style="padding:8px 10px;text-align:left;background:#f5f5f7;">Sản phẩm</th>
            <th style="padding:8px 10px;text-align:center;background:#f5f5f7;">Số lượng</th>
            <th style="padding:8px 10px;text-align:right;background:#f5f5f7;">Thành tiền</th>
          </tr>
        </thead>
        <tbody>{body_rows}</tbody>
      </table>
      <p style="text-align:right;font-size:18px;"><strong>Tổng {_esc(money(order.get("total")))}</strong></p>
      <p style="color:#6e6e73;font-size:13px;">Trân trọng,<br>Octopus Store</p>
    </div>
  </div>
</body>
</html>"""
    return plain, page


def smtp_ready():
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = os.environ.get("SMTP_PASSWORD") or ""
    return bool(host and user and password.strip())


def send_invoice(order):
    """Send one invoice. Returns (sent, customer_note_without_the_money_line)."""
    email = (order.get("ship_email") or "").strip()
    if not email:
        return False, "Đơn chưa có email nhận hoá đơn."
    if not smtp_ready():
        return False, "Chưa cấu hình hộp thư gửi hoá đơn."
    host = os.environ["SMTP_HOST"].strip()
    user = os.environ["SMTP_USER"].strip()
    password = os.environ["SMTP_PASSWORD"]
    try:
        port = int(os.environ.get("SMTP_PORT") or "587")
    except ValueError:
        return False, "Cổng SMTP chưa đúng."
    plain, page = invoice_bodies(order)
    message = EmailMessage()
    message["From"] = formataddr(("Octopus Store", user))
    message["To"] = email
    message["Subject"] = invoice_subject(order)
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
        print(f"invoice order {order.get('id')} failed: {type(exc).__name__}")
        return False, "Không gửi được hoá đơn qua email."
    print(f"invoice order {order.get('id')} sent")
    return True, ""


def load_invoice_order(conn, order_id):
    row = conn.execute(
        """
        SELECT id, ship_name, ship_email, ship_phone, ship_address,
               deliver_on, deliver_slot, coalesce(pay_method, 'cod'), total_vnd, created_at
        FROM orders WHERE id=%s
        """,
        (order_id,),
    ).fetchone()
    if not row:
        return None
    items = conn.execute(
        "SELECT name, qty, unit_price FROM order_items WHERE order_id=%s ORDER BY id",
        (order_id,),
    ).fetchall()
    return {
        "id": row[0],
        "ship_name": row[1] or "",
        "ship_email": row[2] or "",
        "ship_phone": row[3] or "",
        "ship_address": row[4] or "",
        "deliver_on": row[5],
        "deliver_slot": row[6] or "",
        "pay_method": row[7] or "cod",
        "total": int(row[8] or 0),
        "created_at": row[9],
        "items": [
            {"name": name, "qty": int(qty or 0), "unit_price": int(price or 0)}
            for name, qty, price in items
        ],
    }


def deliver_invoice(conn, order_id):
    """Send the invoice for a saved order and remember the result. Returns the receipt note."""
    order = load_invoice_order(conn, order_id)
    if not order:
        return "Không thấy đơn để gửi hoá đơn."
    sent, error = send_invoice(order)
    if sent:
        conn.execute(
            "UPDATE orders SET invoice_sent_at = now(), invoice_error = NULL WHERE id=%s",
            (order_id,),
        )
    else:
        conn.execute(
            "UPDATE orders SET invoice_error = %s WHERE id=%s",
            (error, order_id),
        )
    return invoice_status_note(sent, error)
