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
import google.generativeai as genai
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

# --- save_order_to_db ---
def save_order_to_db(connection, user_email: str, total: float, status: str = "completed"):
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Tìm user_id từ email
        cursor.execute("SELECT id FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        if not user:
            raise Exception(f"Không tìm thấy người dùng với email: {user_email}")
        
        user_id = user['id']
        
        # Chèn vào bảng orders
        sql = """
            INSERT INTO orders (user_id, email, total, status)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (user_id, user_email, f"{int(total):,} VND", status))
        connection.commit()
        logger.debug(f"Đã lưu đơn hàng cho user_id={user_id}, email={user_email}, total={total}")
        
        return {"success": True, "message": "Đơn hàng đã được lưu thành công"}
    except Exception as e:
        logger.error(f"Lỗi khi lưu đơn hàng: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu đơn hàng: {str(e)}")
    finally:
        cursor.close()

# --- MySQL connection ---
def get_mysql_connection():
    config = load_config()
    connection = mysql.connector.connect(
        host=config.get("MYSQL_HOST", "localhost"),
        user=config.get("MYSQL_USER", "root"),
        password=config.get("MYSQL_PASSWORD", "root"),
        database=config.get("MYSQL_DATABASE", "apple_store")
    )
    try:
        yield connection
    finally:
        connection.close()

# --- check_payment ---
@app.get('/check-payment/{order_id}')
async def check_payment(
    order_id: str,
    user_email: str,  # Thêm tham số user_email từ query string
    connection: mysql.connector.connection.MySQLConnection = Depends(get_mysql_connection)
):
    try:
        logger.debug(f"Checking payment for order_id={order_id}, user_email={user_email}")
        with get_db_connection() as conn:
            result = conn.execute("SELECT * FROM pending_orders WHERE order_id = ?", (order_id,)).fetchone()
        logger.debug(f"Pending order result: {result}")

        if not result:
            logger.warning(f"No pending order found for order_id={order_id}")
            check_payload = {"order_id": order_id, "description": f"Ma hoa don {order_id}", "amount": 0}
        else:
            transaction_info = dict(result)
            check_payload = {
                "order_id": order_id,
                "description": transaction_info["description"],
                "amount": int(transaction_info["amount"])
            }
            logger.debug(f"Check payload: {check_payload}")

        # Gọi hàm check_transaction
        check_result = await check_transaction(TransactionCheck(**check_payload))
        logger.debug(f"Check transaction result: {check_result}")

        if check_result.get("success"):
            logger.debug(f"Attempting to delete pending order with order_id={order_id}")
            with get_db_connection() as conn:
                conn.execute("DELETE FROM pending_orders WHERE order_id = ?", (order_id,))
                conn.commit()
            logger.debug(f"Deleted pending order with order_id={order_id}")

            # Lưu đơn hàng vào bảng orders
            if result:  # Chỉ lưu nếu có thông tin trong pending_orders
                logger.debug(f"Saving order to database for user_email={user_email}")
                save_order_to_db(
                    connection=connection,
                    user_email=user_email,
                    total=transaction_info["amount"],
                    status="completed"
                )
                check_result["message"] += " Đơn hàng đã được lưu vào hệ thống."
            else:
                logger.warning(f"Skipping order save due to missing pending order data")
                check_result["message"] += " Không lưu đơn hàng do thiếu dữ liệu pending order."
        
        return JSONResponse(status_code=200, content=check_result)
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra thanh toán: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Lỗi hệ thống: {str(e)}'})

# --- rag_chatbot ---
# Models
class UserQuery(BaseModel):
    query: str
    session_id: Optional[str] = None

# Thông tin liên hệ
CONTACT_INFO = {
    "address": "96A Trần Phú, Hà Đông, Hà Nội",
    "email": "k100iltqbao@gmail.com",
    "phone": "0988888888",
    "working_hours": "9:00 - 18:00, Thứ 2 - Thứ 7"
}

# Helper functions
COMMON_REF_WORDS = ["nó", "này", "sản phẩm này", "sản phẩm đó", "cái đó", "ấy", "cái ấy", "nữa không", "có xịn không", "còn không"]
AGREE_WORDS = ["có chứ", "vâng", "ok", "dạ", "đúng rồi", "đúng vậy", "có", "oke", "ok bạn", "ừ", "ừm", "ờ"]

def is_greeting(text: str):
    greetings = [r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bgood (morning|afternoon|evening|day)\b", r"\bchào\b"]
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
    if any(word in query_lower for word in ["địa chỉ", "chỗ nào", "ở đâu", "nằm đâu"]):
        return "ask_address"
    if any(word in query_lower for word in ["email", "mail", "thư điện tử"]):
        return "ask_email"
    if any(word in query_lower for word in ["điện thoại", "số điện thoại", "hotline", "sđt"]):
        return "ask_phone"
    if any(word in query_lower for word in ["giờ làm việc", "mở cửa", "đóng cửa", "giờ nào"]):
        return "ask_working_hours"
    return "general"

def load_config():
    try:
        with open("../config/config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise HTTPException(status_code=500, detail="Cannot load configuration")

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
    params = (session_id, user_query, bot_response, related_product_id, related_category, datetime.now())
    logger.debug(f"Executing SQL: {sql} with params: {params}")
    try:
        cursor.execute(sql, params)
        connection.commit()
        logger.debug(f"Saved chat history: session_id={session_id}, query={user_query}, product_id={related_product_id}")
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}", exc_info=True)
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

def create_prompt(query: str, products: list, history: list, related_product_name: Optional[str] = None, intent: str = "general"):
    # Thông tin sản phẩm
    product_info = "\n".join([
        f"- {p['name']}: Giá {p['price']}, Danh mục: {p['category']}, Mô tả: {p.get('description', 'Không có mô tả')}"
        for p in products
    ]) or "Không có thông tin sản phẩm."

    # Thông tin liên hệ
    contact_info = (
        f"Thông tin liên hệ:\n"
        f"- Địa chỉ: {CONTACT_INFO['address']}\n"
        f"- Email: {CONTACT_INFO['email']}\n"
        f"- Số điện thoại: {CONTACT_INFO['phone']}\n"
        f"- Giờ làm việc: {CONTACT_INFO['working_hours']}"
    )

    # Lịch sử hội thoại
    history_text = "\n".join([
        f"User: {h['user_query']}\nBot: {h['bot_response']}" 
        for h in history[-3:]
    ]) if history else "Không có lịch sử hội thoại."

    # Ngữ cảnh sản phẩm
    context_text = (
        f"Người dùng đang hỏi về '{related_product_name}'. "
        f"Khi thấy từ 'nó', 'này', hoặc 'sản phẩm này', hiểu là '{related_product_name}'.\n"
    ) if related_product_name else "Không có sản phẩm nào được nhắc trước đó.\n"

    # Prompt chính
    prompt = (
        f"Bạn là trợ lý của Apple Store Hà Nội, xưng hô là 'Shop' và gọi người dùng là 'bạn'. "
        f"Trả lời bằng tiếng Việt, lịch sự, thân thiện, đúng trọng tâm câu hỏi. "
        f"Bắt đầu câu trả lời bằng 'Xin chào bạn' nếu đây là câu hỏi đầu tiên hoặc câu hỏi độc lập. "
        f"Ngữ cảnh: {context_text}"
        f"Sản phẩm liên quan:\n{product_info}\n"
        f"{contact_info}\n"
        f"Lịch sử hội thoại:\n{history_text}\n"
        f"Câu hỏi: {query}\n"
        f"Hướng dẫn:\n"
        f"- Nếu hỏi về sản phẩm (giá, chất lượng, đánh giá), trả lời dựa trên thông tin sản phẩm, ví dụ: "
        f"'Xin chào bạn, Shop có iPhone 14 - 128GB với giá 20,990,000 VNĐ. Bạn cần thêm thông tin gì không ạ?'.\n"
        f"- Nếu hỏi về địa chỉ, email, số điện thoại, giờ làm việc, trả lời thân thiện, ví dụ: "
        f"'Xin chào bạn, Shop nằm tại 96A Trần Phú, Hà Đông, Hà Nội. Bạn ghé Shop nhé!'.\n"
        f"- Nếu câu hỏi có 'nó', tập trung vào '{related_product_name}'.\n"
        f"- Nếu không rõ, trả lời: 'Xin chào bạn, Shop chưa hiểu rõ câu hỏi. Bạn có thể nói thêm chi tiết không ạ?'.\n"
        f"Không thêm thông tin ngoài dữ liệu cung cấp."
    )
    logger.debug(f"Generated prompt:\n{prompt}")
    return prompt

def generate_with_gemini(prompt):
    config = load_config()
    genai.configure(api_key=config["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    contents = [
        {
            "role": "user",
            "parts": [{"text": prompt}]
        }
    ]
    generate_config = genai.types.GenerationConfig(
        temperature=0.6,
        top_p=0.9,
        top_k=40,
        max_output_tokens=2048
    )
    try:
        response = ""
        for chunk in model.generate_content(contents=contents, generation_config=generate_config, stream=True):
            response += chunk.text
        logger.debug(f"Gemini response: {response}")
        if "không hiểu" in response.lower() or "sản phẩm nào" in response.lower():
            logger.warning(f"Gemini failed to understand context, response: {response}")
            return None
        return response
    except Exception as e:
        logger.error(f"Error with Gemini API: {str(e)}")
        return None

# Main chatbot endpoint
@app.post("/ask")
async def ask_bot(user_query: UserQuery, connection: mysql.connector.connection.MySQLConnection = Depends(get_mysql_connection)):
    query = user_query.query.strip()
    session_id = user_query.session_id or str(uuid.uuid4())
    logger.debug(f"Processing query: {query}, session_id: {session_id}, client_session_id: {user_query.session_id}")

    if not query:
        return JSONResponse(
            status_code=400,
            content={"response": "Xin chào bạn, vui lòng gửi câu hỏi để Shop hỗ trợ!", "session_id": session_id}
        )

    # Xử lý lời chào
    if is_greeting(query):
        response = "Xin chào bạn! Shop là trợ lý Apple Store Hà Nội. Bạn muốn tìm hiểu về sản phẩm hay thông tin liên hệ hôm nay?"
        try:
            save_chat_history(session_id, query, response, connection)
            logger.debug(f"Saved greeting response for session_id={session_id}")
        except Exception as e:
            logger.error(f"Failed to save greeting chat history: {str(e)}", exc_info=True)
        return {"response": response, "session_id": session_id}

    cursor = connection.cursor(dictionary=True)

    # Tải lịch sử hội thoại
    history = load_chat_history(session_id, connection)
    logger.debug(f"Chat history: {history}")

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

    # Xác định intent
    intent = detect_intent(query)
    logger.debug(f"Detected intent: {intent}")

    # Xử lý các câu hỏi về thông tin liên hệ
    if intent in ["ask_address", "ask_email", "ask_phone", "ask_working_hours"]:
        response = {
            "ask_address": f"Xin chào bạn, Shop nằm tại {CONTACT_INFO['address']}. Bạn ghé Shop nhé!",
            "ask_email": f"Xin chào bạn, email liên hệ của Shop là {CONTACT_INFO['email']}. Bạn cần hỗ trợ qua email không ạ?",
            "ask_phone": f"Xin chào bạn, số điện thoại liên hệ của Shop là {CONTACT_INFO['phone']}. Bạn có thể gọi trong giờ làm việc nhé!",
            "ask_working_hours": f"Xin chào bạn, Shop mở cửa từ {CONTACT_INFO['working_hours']}. Bạn ghé Shop trong khung giờ này nhé!"
        }[intent]
        try:
            save_chat_history(session_id, query, response, connection)
            logger.debug(f"Saved contact info response for session_id={session_id}")
        except Exception as e:
            logger.error(f"Failed to save chat history: {str(e)}", exc_info=True)
        cursor.close()
        return {"response": response, "session_id": session_id}

    # Xử lý câu hỏi về sản phẩm
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
            # Chọn sản phẩm khớp nhất với truy vấn
            query_lower = query.lower()
            best_match = None
            max_match_score = 0
            for product in products:
                product_name = product['name'].lower()
                match_score = sum(1 for term in query_lower.split() if term in product_name)
                if match_score > max_match_score:
                    max_match_score = match_score
                    best_match = product
            if best_match:
                related_product_id = best_match['id']
                related_product_name = best_match['name']
                related_category = best_match['category']
                products = [best_match] + [p for p in products if p['id'] != best_match['id']]
                logger.debug(f"Best match: {related_product_name} (ID={related_product_id})")
            else:
                related_product_id = products[0]['id']
                related_product_name = products[0]['name']
                related_category = products[0]['category']
            logger.debug(f"Found products: {[p['name'] for p in products]}")
        else:
            logger.debug(f"No products found for query: {query}")

    # Tạo prompt và trả lời
    response = None
    if products or intent == "general":
        prompt = create_prompt(query, products, history, related_product_name, intent)
        response = generate_with_gemini(prompt)
        if response is None:
            # Fallback: Trả lời với sản phẩm khớp nhất
            if related_product_name and intent == "ask_price":
                response = f"Xin chào bạn, giá {related_product_name} là {products[0]['price']} VNĐ. Bạn cần thêm thông tin gì không ạ?"
            elif related_product_name and intent == "ask_quality":
                response = f"Xin chào bạn, {related_product_name} là sản phẩm chất lượng cao, được nhiều khách hàng yêu thích. Bạn muốn biết thêm chi tiết không ạ?"
            elif related_product_name:
                response = f"Xin chào bạn, Shop có {related_product_name}. Bạn muốn tìm hiểu thêm về giá hay tính năng không ạ?"
            else:
                response = "Xin chào bạn, Shop chưa hiểu rõ câu hỏi. Bạn có thể nói rõ hơn về sản phẩm hoặc thông tin bạn cần không ạ?"
            logger.debug(f"Using fallback response for {related_product_name}")
    else:
        response = "Xin chào bạn, Shop chưa tìm thấy sản phẩm bạn nhắc tới. Bạn có thể nói rõ hơn về sản phẩm bạn quan tâm không ạ?"
        logger.warning(f"No products matched query: {query}")

    # Lưu lịch sử
    try:
        save_chat_history(
            session_id=session_id,
            user_query=query,
            bot_response=response,
            connection=connection,
            related_product_id=related_product_id,
            related_category=related_category
        )
        logger.debug(f"Successfully saved chat history for session_id={session_id}")
    except Exception as e:
        logger.error(f"Failed to save chat history: {str(e)}", exc_info=True)
        response += f" (Lưu ý: Không thể lưu lịch sử chat do lỗi: {str(e)})"

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