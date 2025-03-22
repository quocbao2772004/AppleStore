from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import re

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_SENDER = 'letranquocbao.nd@gmail.com'
EMAIL_PASSWORD = 'zgob orxx wlzv kelf'

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

@app.post('/send-email')
async def send_email(
    email_receiver: str = Form(...),
    cart_items: str = Form(...),
    total: float = Form(...)
):
    try:
        logger.debug(f"Received: email_receiver={email_receiver}, cart_items={cart_items}, total={total}")

        if not email_receiver or not is_valid_email(email_receiver):
            logger.error(f"Invalid email: {email_receiver}")
            raise HTTPException(status_code=400, detail="Địa chỉ email không hợp lệ!")
        if not cart_items:
            logger.error("Cart items is empty")
            raise HTTPException(status_code=400, detail="Cart items không được để trống!")
        if total <= 0:
            logger.error("Invalid total amount")
            raise HTTPException(status_code=400, detail="Tổng tiền phải lớn hơn 0!")

        try:
            cart_items_list = json.loads(cart_items)
            logger.debug(f"Parsed cart_items: {cart_items_list}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Lỗi parse JSON cart_items: {str(e)}")

        # Đảm bảo total là số thực hợp lệ
        total = float(total)  # Ép kiểu lại để chắc chắn

        # Tạo nội dung email HTML
        subject = 'Xác nhận đơn hàng từ Apple Store'
        html_body = """
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; color: #333; line-height: 1.6; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }
                .header { text-align: center; background-color: #007bff; color: white; padding: 15px; border-radius: 10px 10px 0 0; }
                .content { padding: 20px; background-color: white; border-radius: 0 0 10px 10px; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
                .total { font-weight: bold; font-size: 18px; color: #007bff; }
                .footer { text-align: center; font-size: 12px; color: #777; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Xác nhận đơn hàng từ Apple Store</h2>
                </div>
                <div class="content">
                    <p>Xin chào,</p>
                    <p>Cảm ơn bạn đã mua sắm tại Apple Store! Dưới đây là chi tiết đơn hàng của bạn:</p>
                    <table>
                        <tr>
                            <th>Sản phẩm</th>
                            <th>Số lượng</th>
                            <th>Giá</th>
                            <th>Tổng</th>
                        </tr>
        """

        for item in cart_items_list:
            subtotal = float(item['price']) * float(item['quantity'])  # Ép kiểu để tránh lỗi
            html_body += f"""
                        <tr>
                            <td>{item['name']}</td>
                            <td>{item['quantity']}</td>
                            <td>{int(item['price']):,} VNĐ</td> <!-- Định dạng số nguyên -->
                            <td>{int(subtotal):,} VNĐ</td>
                        </tr>
            """

        html_body += f"""
                    </table>
                    <p class="total">Tổng cộng: {int(total):,} VNĐ</p> <!-- Định dạng số nguyên -->
                    <p>Chúng tôi sẽ xử lý đơn hàng của bạn sớm nhất có thể. Nếu có thắc mắc, vui lòng liên hệ qua email <a href="mailto:{EMAIL_SENDER}">{EMAIL_SENDER}</a>.</p>
                </div>
                <div class="footer">
                    <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = email_receiver
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        logger.debug("Connecting to SMTP server")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            logger.debug("Logging in to SMTP server")
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            logger.debug(f"Sending email to {email_receiver}")
            server.sendmail(EMAIL_SENDER, email_receiver, msg.as_string())
            logger.debug("Email sent successfully")

        return {'success': True, 'message': 'Email xác nhận đã được gửi thành công!'}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Có lỗi xảy ra khi gửi email: {str(e)}'}
        )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=4010, reload=True)