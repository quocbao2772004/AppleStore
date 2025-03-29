from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from mbbank import MBBank
import requests
import random
import base64
from urllib.parse import quote
from datetime import datetime, timedelta
import json
import sqlite3
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.middleware.cors import CORSMiddleware
import logging
import re
import uuid
from google import genai
from google.genai import types
from typing import Optional

app = FastAPI(title="Apple Store Unified API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Cấu hình ngân hàng cho VietQR
BANK_ID = "MB"
ACCOUNT_NUMBER = "6866820048888"
ACCOUNT_NAME = "Le Tran Quoc Bao"

# Cấu hình email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "letranquocbao.nd@gmail.com"
EMAIL_PASSWORD = "zgob orxx wlzv kelf"  # App Password
EMAIL_RECEIVER = "k100iltqbao@gmail.com"

# SQLite cho pending_orders
def get_db_connection():
    conn = sqlite3.connect('pending_orders.db')
    conn.row_factory = sqlite3.Row
    return conn

with get_db_connection() as conn:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pending_orders (
            order_id TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL
        )
    ''')
    conn.commit()

# Cấu hình MBBank
def load_bank_config():
    try:
        with open("../config/bank_config.json", "r") as config_file:
            config = json.load(config_file)
            return config["username"], config["password"]
    except Exception as e:
        raise Exception(f"Error loading bank config: {str(e)}")

username, password = load_bank_config()
mb = MBBank(username=username, password=password)

# --- bank_transaction_history ---
@app.get("/balance")
async def get_balance():
    try:
        balance = mb.getBalance()
        logger.debug(f"Dữ liệu số dư: {balance}")
        return balance
    except Exception as e:
        return {"error": str(e)}

@app.get("/transactions")
async def get_transactions():
    try:
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(hours=1)
        history = mb.getTransactionAccountHistory(
            accountNo="6866820048888",
            from_date=from_dt,
            to_date=to_dt
        )
        return history
    except Exception as e:
        return {"error": str(e)}

class TransactionCheck(BaseModel):
    order_id: str
    description: str
    amount: int

async def check_transaction(check: TransactionCheck):
    try:
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=1)
        history = mb.getTransactionAccountHistory(
            accountNo="6866820048888",
            from_date=from_dt,
            to_date=to_dt
        )
        transactionHistoryList = history.get('transactionHistoryList', [])
        logger.debug(f"Transaction History: {transactionHistoryList}")
        for transaction in transactionHistoryList:
            actual_description = str(transaction.get('addDescription', ''))
            actual_amount = int(transaction.get('creditAmount', '0'))
            if str(actual_description).find(str(check.description)) != -1:
                return {
                    "success": True,
                    "message": "Giao dịch khớp",
                    "transaction": {
                        "description": actual_description,
                        "amount": actual_amount,
                        "transactionDate": transaction.get('transactionDate', '')
                    }
                }
        return {
            "success": False,
            "message": "Chưa tìm thấy giao dịch khớp",
            "order_id": check.order_id,
            "description": check.description
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

@app.post("/check-transaction")
async def check_transaction_endpoint(check: TransactionCheck):
    result = await check_transaction(check)
    return JSONResponse(status_code=200, content=result)

# --- generate_qr & generate_qr_cart ---
def generate_qr_code(product_id=None, quantity=None, items=None, amount=None, source=""):
    random_number = random.randint(10000000, 99999999)
    if items:  # generate_qr_cart
        description_parts = []
        for item in items:
            pid = item.get('product_id')
            qty = item.get('quantity')
            if not isinstance(pid, int) or not isinstance(qty, int):
                raise HTTPException(status_code=400, detail="Invalid product_id or quantity")
            description_parts.append(f"{pid}{qty}")
        description = f"Ma hoa don {random_number}{' '.join(description_parts)}"
        order_id = f"{random_number}{''.join(description_parts)}"
    else:  # generate_qr
        description = f"Ma hoa don {random_number}{product_id}{quantity}"
        order_id = f"{random_number}{product_id}{quantity}"

    encoded_description = quote(description)
    encoded_account_name = quote(ACCOUNT_NAME)

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO pending_orders (order_id, amount, description, created_at, source) VALUES (?, ?, ?, ?, ?)",
            (order_id, amount, description, datetime.now().isoformat(), source)
        )
        conn.commit()

    vietqr_url = (
        f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NUMBER}-compact2.png"
        f"?amount={int(amount)}&addInfo={encoded_description}&accountName={encoded_account_name}"
    )
    response = requests.get(vietqr_url, timeout=10)
    if response.status_code == 200:
        qr_base64 = base64.b64encode(response.content).decode('utf-8')
        qr_data_url = f"data:image/png;base64,{qr_base64}"
        return {
            'success': True,
            'qr_code': qr_data_url,
            'order_id': order_id
        }
    raise HTTPException(status_code=500, detail=f"Lỗi từ VietQR: HTTP {response.status_code}")

@app.post('/generate-qr')
async def generate_qr(
    product_id: int = Form(...),
    quantity: int = Form(...),
    amount: float = Form(...)
):
    try:
        return generate_qr_code(product_id=product_id, quantity=quantity, amount=amount, source="product_detail")
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Lỗi hệ thống: {str(e)}'})

@app.post('/generate-qr-cart')
async def generate_qr_cart(
    items: str = Form(...),
    amount: float = Form(...)
):
    try:
        items_list = json.loads(items)
        if not isinstance(items_list, list) or not items_list:
            return JSONResponse(status_code=400, content={'success': False, 'message': 'Items must be a non-empty list'})
        return generate_qr_code(items=items_list, amount=amount, source="cart")
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={'success': False, 'message': 'Invalid JSON format for items'})
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Lỗi hệ thống: {str(e)}'})

@app.get('/check-payment/{order_id}')
async def check_payment(order_id: str):
    try:
        with get_db_connection() as conn:
            result = conn.execute("SELECT * FROM pending_orders WHERE order_id = ?", (order_id,)).fetchone()
        
        if not result:
            # Nếu không tìm thấy trong pending_orders, vẫn thử kiểm tra lịch sử giao dịch
            check_payload = {"order_id": order_id, "description": f"Ma hoa don {order_id}", "amount": 0}
        else:
            transaction_info = dict(result)
            check_payload = {
                "order_id": order_id,
                "description": transaction_info["description"],
                "amount": int(transaction_info["amount"])
            }

        # Gọi trực tiếp hàm check_transaction thay vì qua HTTP
        check_result = await check_transaction(TransactionCheck(**check_payload))
        
        if check_result.get("success"):
            with get_db_connection() as conn:
                conn.execute("DELETE FROM pending_orders WHERE order_id = ?", (order_id,))
                conn.commit()
        
        return JSONResponse(status_code=200, content=check_result)
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Lỗi hệ thống: {str(e)}'})

# --- rag_chatbot ---
class UserQuery(BaseModel):
    query: str
    session_id: Optional[str] = None

chat_history = {}

def load_config():
    with open("../config/config.json", "r") as f:
        return json.load(f)

def get_mysql_connection():
    config = load_config()
    connection = mysql.connector.connect(
        host=config.get("MYSQL_HOST", "localhost"),
        user=config.get("MYSQL_USER", "root"),
        password=config.get("MYSQL_PASSWORD", ""),
        database=config.get("MYSQL_DATABASE", "apple_store")
    )
    try:
        yield connection
    finally:
        connection.close()

def retrieve_products(query: str, connection: mysql.connector.connection.MySQLConnection):
    cursor = connection.cursor(dictionary=True)
    irrelevant_words = {"giá", "bao", "nhiều", "của", "là", "hỏi", "về", "tôi", "muốn", "biết"}
    search_terms = [word for word in query.lower().split() if word not in irrelevant_words]
    if not search_terms:
        search_terms = ["%"]
    conditions = " OR ".join(["LOWER(p.name) LIKE %s" for _ in search_terms])
    sql_query = f"""
        SELECT p.id, p.name, p.price, p.image, p.category, p.quantity, 
               AVG(c.rating) as avg_rating, COUNT(c.rating) as rating_count,
               pd.description
        FROM products p
        LEFT JOIN comments c ON p.id = c.product_id
        LEFT JOIN product_descriptions pd ON p.id = pd.product_id
        WHERE ({conditions}) OR LOWER(p.category) LIKE %s
        GROUP BY p.id, p.name, p.price, p.image, p.category, p.quantity, pd.description
    """
    search_params = [f"%{term}%" for term in search_terms] + [f"%{query.lower()}%"]
    cursor.execute(sql_query, tuple(search_params))
    products = cursor.fetchall()
    cursor.close()
    for product in products:
        product['avg_rating'] = float(product['avg_rating']) if product['avg_rating'] is not None else None
    return products

def direct_answer(query: str, products: list):
    query_lower = query.lower()
    if "giá bao nhiêu" in query_lower:
        query_name = " ".join(word for word in query_lower.split() if word not in {"giá", "bao", "nhiều"})
        for product in products:
            if all(word in product['name'].lower() for word in query_name.split()):
                return f"Giá của {product['name']} là {product['price']}."
    if "dùng tốt" in query_lower or "tốt nhất" in query_lower:
        rated_products = [p for p in products if p['avg_rating'] is not None]
        if rated_products:
            best_product = max(rated_products, key=lambda x: x['avg_rating'])
            return (
                f"Dựa trên đánh giá, {best_product['name']} là sản phẩm tốt nhất "
                f"với điểm trung bình {best_product['avg_rating']:.1f}/5 ({best_product['rating_count']} đánh giá)."
            )
        return "Không có đánh giá để xác định sản phẩm tốt nhất."
    return None

def create_prompt(query: str, products: list, session_id: str):
    if not products:
        return (
            f"User hỏi: {query}\nKhông tìm thấy sản phẩm phù hợp trong cơ sở dữ liệu."
        )
    product_list = "\n".join([
        f"- Tên: {p['name']}, Giá: {p['price']}, Danh mục: {p['category']}, "
        f"Số lượng: {p['quantity']}, Đánh giá trung bình: {p['avg_rating'] if p['avg_rating'] else 'Chưa có'}, "
        f"({p['rating_count']} đánh giá), Mô tả: {p['description'] if p['description'] else 'Không có'}"
        for p in products
    ])
    history = chat_history.get(session_id, [])
    history_text = "\n".join([f"User: {item['query']}\nBot: {item['response']}" for item in history])
    prompt = (
        f"Bạn là trợ lý ảo Apple Intelligence của Apple Store.\n"
        f"Lịch sử chat:\n{history_text}\n"
        f"User hỏi: {query}\n"
        f"Thông tin sản phẩm:\n{product_list}\n"
        f"Trả lời dựa trên thông tin trên. Nếu không đủ thông tin, nói 'Xin lỗi, mình không có thông tin cho câu hỏi này.'"
    )
    return prompt

def generate_with_rag(query: str, products: list, session_id: str):
    direct_response = direct_answer(query, products)
    if direct_response:
        return direct_response
    config = load_config()
    api_key = config.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    model = "gemini-2.0-flash"
    prompt = create_prompt(query, products, session_id)
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
    generate_content_config = types.GenerateContentConfig(
        temperature=0.7, top_p=0.9, top_k=40, max_output_tokens=8192, response_mime_type="text/plain"
    )
    response = ""
    for chunk in client.models.generate_content_stream(model=model, contents=contents, config=generate_content_config):
        response += chunk.text
    return response

def is_greeting(text):
    greetings = [r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bgood (morning|afternoon|evening|day)\b"]
    pattern = re.compile("|".join(greetings), re.IGNORECASE)
    return bool(pattern.search(text))

@app.post("/ask")
async def ask_bot(user_query: UserQuery, connection: mysql.connector.connection.MySQLConnection = Depends(get_mysql_connection)):
    query = user_query.query
    session_id = user_query.session_id if user_query.session_id else str(uuid.uuid4())
    if is_greeting(query):
        response = "Xin chào! Mình là trợ lý ảo của Apple Store."
    else:
        products = retrieve_products(query, connection)
        response = generate_with_rag(query, products, session_id)
    if session_id not in chat_history:
        chat_history[session_id] = []
    chat_history[session_id].append({"query": query, "response": response})
    return {"response": response, "session_id": session_id}

# --- send_email ---
@app.post('/send-email')
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    message: str = Form(...)
):
    try:
        if not all([name, email, phone, message]):
            raise HTTPException(status_code=400, detail="Vui lòng điền đầy đủ thông tin!")
        subject = 'Tin nhắn mới từ Apple Store Contact Form'
        body = f"Họ và tên: {name}\nEmail: {email}\nSố điện thoại: {phone}\nTin nhắn:\n{message}"
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return {'success': True, 'message': 'Tin nhắn của bạn đã được gửi thành công!'}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Có lỗi khi gửi tin nhắn: {str(e)}'})

# --- transaction_notification ---
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

@app.post('/send-email-notification')
async def send_email_notification(
    email_receiver: str = Form(...),
    cart_items: str = Form(...),
    total: float = Form(...)
):
    try:
        if not is_valid_email(email_receiver):
            raise HTTPException(status_code=400, detail="Địa chỉ email không hợp lệ!")
        if not cart_items or total <= 0:
            raise HTTPException(status_code=400, detail="Dữ liệu không hợp lệ!")
        cart_items_list = json.loads(cart_items)
        subject = 'Xác nhận đơn hàng từ Apple Store'
        html_body = """
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }
                .header { text-align: center; background-color: #007bff; color: white; padding: 15px; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; border-bottom: 1px solid #ddd; }
                .total { font-weight: bold; font-size: 18px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h2>Xác nhận đơn hàng</h2></div>
                <div class="content">
                    <p>Cảm ơn bạn đã mua sắm!</p>
                    <table>
                        <tr><th>Sản phẩm</th><th>Số lượng</th><th>Giá</th><th>Tổng</th></tr>
        """
        for item in cart_items_list:
            subtotal = float(item['price']) * float(item['quantity'])
            html_body += f"<tr><td>{item['name']}</td><td>{item['quantity']}</td><td>{int(item['price']):,} VNĐ</td><td>{int(subtotal):,} VNĐ</td></tr>"
        html_body += f"""
                    </table>
                    <p class="total">Tổng cộng: {int(total):,} VNĐ</p>
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
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        return {'success': True, 'message': 'Email xác nhận đã được gửi thành công!'}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Có lỗi khi gửi email: {str(e)}'})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=4090, reload=True)