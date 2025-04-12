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
# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Models ---
class UserQuery(BaseModel):
    query: str
    session_id: Optional[str] = None

# --- Helper functions ---
COMMON_REF_WORDS = ["nó", "này", "sản phẩm này", "sản phẩm đó", "cái đó", "ấy", "cái ấy", "nữa không", "có xịn không", "còn không"]
AGREE_WORDS = ["có chứ", "vâng", "ok", "dạ", "đúng rồi", "đúng vậy", "có", "oke", "ok bạn", "ừ", "ừm", "ờ"]

def is_greeting(text: str):
    greetings = [r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bgood (morning|afternoon|evening|day)\b"]
    return bool(re.search("|".join(greetings), text, re.IGNORECASE))

def query_is_reference(query: str) -> bool:
    return any(word in query.lower() for word in COMMON_REF_WORDS)

def is_user_agreeing(query: str) -> bool:
    return any(phrase in query.lower() for phrase in AGREE_WORDS)

def detect_intent(query: str):
    query_lower = query.lower()
    if any(word in query_lower for word in ["giá", "bao nhiêu", "giá bao nhiêu"]):
        return "ask_price"
    if any(word in query_lower for word in ["xịn", "tốt", "dùng tốt", "xài tốt", "chất lượng"]):
        return "ask_quality"
    if any(word in query_lower for word in ["đánh giá", "nhận xét", "bình luận"]):
        return "ask_reviews"
    return "general"

def load_config():
    try:
        with open("../config/config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise HTTPException(status_code=500, detail="Cannot load configuration")

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

def retrieve_products(query: str, connection):
    cursor = connection.cursor(dictionary=True)
    irrelevant_words = {"giá", "bao", "nhiều", "của", "là", "hỏi", "về", "tôi", "muốn", "biết", "có", "không"}
    search_terms = [word for word in query.lower().split() if word not in irrelevant_words]
    if not search_terms:
        search_terms = ["%"]
    conditions = " OR ".join(["LOWER(p.name) LIKE %s" for _ in search_terms])

    sql = """
        SELECT 
            p.id, 
            p.name, 
            p.price, 
            p.image, 
            p.category, 
            p.quantity, 
            pd.description
        FROM products p
        LEFT JOIN product_descriptions pd ON p.id = pd.product_id
        WHERE (%s) OR LOWER(p.category) LIKE %s
        LIMIT 5
    """
    params = [f"%{term}%" for term in search_terms] + [f"%{query.lower()}%"]
    try:
        cursor.execute(sql % (conditions, "%s"), params)
        products = cursor.fetchall()
        logger.debug(f"Retrieved {len(products)} products for query: {query} - {[p['name'] for p in products]}")
        return products
    except Exception as e:
        logger.error(f"Error retrieving products: {str(e)}")
        return []
    finally:
        cursor.close()

def save_chat_history(session_id, user_query, bot_response, connection, related_product_id=None, related_category=None):
    cursor = connection.cursor()
    sql = """
        INSERT INTO chat_history 
        (session_id, user_query, bot_response, related_product_id, related_category, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        cursor.execute(sql, (
            session_id, 
            user_query, 
            bot_response, 
            related_product_id, 
            related_category, 
            datetime.now()
        ))
        connection.commit()
        logger.debug(f"Saved chat history: session_id={session_id}, query={user_query}, product_id={related_product_id}")
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving chat history: {str(e)}")
    finally:
        cursor.close()

def load_chat_history(session_id: str, connection):
    cursor = connection.cursor(dictionary=True)
    sql = """
        SELECT 
            user_query, 
            bot_response, 
            related_product_id, 
            related_category
        FROM chat_history
        WHERE session_id = %s
        ORDER BY created_at ASC
        LIMIT 10
    """
    try:
        cursor.execute(sql, (session_id,))
        history = cursor.fetchall()
        logger.debug(f"Loaded {len(history)} chat history records for session_id: {session_id}")
        return history
    except Exception as e:
        logger.error(f"Error loading chat history: {str(e)}")
        return []
    finally:
        cursor.close()

def create_prompt(query: str, products: list, history: list, related_product_name: Optional[str] = None):
    product_info = "\n".join([
        f"- {p['name']}: Giá {p['price']}, Danh mục: {p['category']}, Mô tả: {p.get('description', 'Không có mô tả')}"
        for p in products[:2]  # Giới hạn 2 sản phẩm để prompt ngắn hơn
    ]) or "Không có thông tin sản phẩm."

    # Chỉ lấy 3 hội thoại cuối để tránh prompt quá dài
    history_text = "\n".join([
        f"User: {h['user_query']}\nBot: {h['bot_response']}" 
        for h in history[-3:]
    ]) if history else "Không có lịch sử hội thoại."

    # Đơn giản hóa ngữ cảnh
    context_text = (
        f"Người dùng đang hỏi về '{related_product_name}'. "
        f"Khi thấy từ 'nó', 'này', hoặc 'sản phẩm này', hiểu là '{related_product_name}'.\n"
    ) if related_product_name else "Không có sản phẩm nào được nhắc trước đó.\n"

    prompt = (
        f"Bạn là trợ lý Apple Store Hà Nội, trả lời bằng tiếng Việt, ngắn gọn, thân thiện, đúng thông tin.\n"
        f"Ngữ cảnh: {context_text}"
        f"Sản phẩm liên quan:\n{product_info}\n"
        f"Lịch sử hội thoại:\n{history_text}\n"
        f"Câu hỏi: {query}\n"
        f"Trả lời dựa trên thông tin sản phẩm và lịch sử. Nếu câu hỏi có 'nó', tập trung vào '{related_product_name}'. "
        f"Nếu không rõ, hỏi lại lịch sự. Không thêm thông tin ngoài dữ liệu."
    )
    logger.debug(f"Generated prompt:\n{prompt}")
    return prompt

def generate_with_gemini(prompt):
    config = load_config()
    client = genai.Client(api_key=config["GOOGLE_API_KEY"])
    model = "gemini-2.0-flash"
    contents = [types.Content(role="user", parts=[types.Part.from_text(prompt)])]
    generate_config = types.GenerateContentConfig(
        temperature=0.6,  # Giảm temperature để trả lời chính xác hơn
        top_p=0.9,
        top_k=40,
        max_output_tokens=2048  # Giảm token để nhanh hơn
    )
    try:
        response = ""
        for chunk in client.models.generate_content_stream(model=model, contents=contents, config=generate_config):
            response += chunk.text
        logger.debug(f"Gemini response: {response}")
        # Fallback nếu Gemini không trả lời đúng
        if "không hiểu" in response.lower() or "sản phẩm nào" in response.lower():
            logger.warning(f"Gemini failed to understand context, response: {response}")
            return None
        return response
    except Exception as e:
        logger.error(f"Error with Gemini API: {str(e)}")
        return None

# --- Main chatbot endpoint ---
@app.post("/ask")
async def ask_bot(user_query: UserQuery, connection: mysql.connector.connection.MySQLConnection = Depends(get_mysql_connection)):
    query = user_query.query.strip()
    session_id = user_query.session_id or str(uuid.uuid4())
    logger.debug(f"Processing query: {query}, session_id: {session_id}, client_session_id: {user_query.session_id}")

    if not query:
        return JSONResponse(
            status_code=400,
            content={"response": "Vui lòng gửi câu hỏi!", "session_id": session_id}
        )

    # Xử lý lời chào
    if is_greeting(query):
        response = "Chào bạn! Mình là trợ lý Apple Store Hà Nội. Bạn muốn tìm hiểu về sản phẩm nào hôm nay?"
        save_chat_history(session_id, query, response, connection)
        return {"response": response, "session_id": session_id}

    cursor = connection.cursor(dictionary=True)

    # Tải lịch sử hội thoại
    history = load_chat_history(session_id, connection)
    if not history:
        logger.debug(f"No chat history found for session_id: {session_id}")

    # Tìm sản phẩm gần nhất
    cursor.execute("""
        SELECT p.id, p.name, p.price, p.category, p.image, p.quantity, pd.description
        FROM chat_history h
        JOIN products p ON h.related_product_id = p.id
        LEFT JOIN product_descriptions pd ON p.id = pd.product_id
        WHERE h.session_id = %s AND h.related_product_id IS NOT NULL
        ORDER BY h.created_at DESC
        LIMIT 1
    """, (session_id,))
    last_product = cursor.fetchone()
    logger.debug(f"Last product: {last_product['name'] if last_product else 'None'}")

    # Xác định intent và sản phẩm
    intent = detect_intent(query)
    logger.debug(f"Detected intent: {intent}")

    products = []
    related_product_id = None
    related_product_name = None
    related_category = None

    # Xử lý câu hỏi tham chiếu hoặc hỏi về chất lượng
    if last_product and (query_is_reference(query) or intent == "ask_quality" or is_user_agreeing(query)):
        products = [last_product]
        related_product_id = last_product['id']
        related_product_name = last_product['name']
        related_category = last_product['category']
        logger.debug(f"Linked to last product: {related_product_name} (ID={related_product_id})")
    else:
        # Tìm sản phẩm mới
        products = retrieve_products(query, connection)
        if products:
            related_product_id = products[0]['id']
            related_product_name = products[0]['name']
            related_category = products[0]['category']
            logger.debug(f"Found new products: {[p['name'] for p in products]}")
        else:
            logger.debug(f"No products found for query: {query}")

    # Tạo prompt và trả lời
    response = None
    if products or last_product:
        prompt = create_prompt(query, products or [last_product], history, related_product_name)
        response = generate_with_gemini(prompt)
        # Fallback nếu Gemini trả lời không đúng
        if response is None and related_product_name:
            response = (
                f"Xin lỗi, mình chưa hiểu rõ ý bạn. Bạn đang hỏi về {related_product_name}, đúng không? "
                f"Nó có giá {last_product['price']} và rất được ưa chuộng. Bạn muốn biết thêm gì về sản phẩm này ạ?"
            )
            logger.debug(f"Using fallback response for {related_product_name}")
    else:
        response = "Xin lỗi, mình chưa tìm thấy sản phẩm bạn nhắc tới. Bạn có thể nói rõ hơn về sản phẩm bạn quan tâm không ạ?"
        logger.warning(f"No products matched query: {query}")

    # Lưu lịch sử
    save_chat_history(
        session_id=session_id,
        user_query=query,
        bot_response=response,
        connection=connection,
        related_product_id=related_product_id,
        related_category=related_category
    )

    cursor.close()
    return {"response": response, "session_id": session_id}
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