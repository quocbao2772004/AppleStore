from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.middleware.cors import CORSMiddleware
import logging

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hoặc thay bằng ["http://localhost:3000"] nếu chạy trên cổng khác
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Cấu hình email
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_SENDER = 'letranquocbao.nd@gmail.com'  # Thay bằng email Gmail của bạn
EMAIL_PASSWORD = 'zgob orxx wlzv kelf'   # Thay bằng App Password từ Gmail
EMAIL_RECEIVER = 'k100iltqbao@gmail.com'

@app.post('/send-email')
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    message: str = Form(...)
):
    try:
        logger.debug(f"Received POST request - Name: {name}, Email: {email}, Phone: {phone}, Message: {message}")

        # Kiểm tra dữ liệu
        if not all([name, email, phone, message]):
            logger.warning("Missing form data")
            raise HTTPException(status_code=400, detail="Vui lòng điền đầy đủ thông tin!")

        # Tạo nội dung email
        subject = 'Tin nhắn mới từ Apple Store Contact Form'
        body = f"Họ và tên: {name}\nEmail: {email}\nSố điện thoại: {phone}\nTin nhắn:\n{message}"

        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Gửi email qua SMTP
        logger.debug("Connecting to SMTP server")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            logger.debug("Logging in to SMTP server")
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            logger.debug("Sending email")
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
            logger.debug("Email sent successfully")

        return {'success': True, 'message': 'Tin nhắn của bạn đã được gửi thành công!'}

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Có lỗi xảy ra khi gửi tin nhắn: {str(e)}'}
        )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)