import os
import json
import mysql.connector
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from typing import Optional
from contextlib import contextmanager
from fastapi.middleware.cors import CORSMiddleware
# Khởi tạo FastAPI app
app = FastAPI(title="Apple Store Bot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Định nghĩa model cho request body
class UserQuery(BaseModel):
    query: str

# Đọc cấu hình từ config.json
def load_config():
    with open("../config/config.json", "r") as f:
        config = json.load(f)
    return config

# Quản lý kết nối MySQL
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

# Truy vấn sản phẩm từ cơ sở dữ liệu
def retrieve_products(query: str, connection: mysql.connector.connection.MySQLConnection):
    cursor = connection.cursor(dictionary=True)
    
    irrelevant_words = {"giá", "bao", "nhiều", "của", "là", "hỏi", "về", "tôi", "muốn", "biết"}
    search_terms = [word for word in query.lower().split() if word not in irrelevant_words and word]
    
    if not search_terms:
        search_terms = ["%"]
    
    conditions = " OR ".join(["LOWER(p.name) LIKE %s" for _ in search_terms])
    sql_query = f"""
        SELECT p.id, p.name, p.price, p.image, p.category, p.quantity, 
               AVG(c.rating) as avg_rating, COUNT(c.rating) as rating_count
        FROM products p
        LEFT JOIN comments c ON p.id = c.product_id
        WHERE ({conditions}) OR LOWER(p.category) LIKE %s
        GROUP BY p.id, p.name, p.price, p.image, p.category, p.quantity
    """
    
    search_params = [f"%{term}%" for term in search_terms] + [f"%{query.lower()}%"]
    print(f"Search terms: {search_terms}")
    print(f"SQL Query: {sql_query % tuple(search_params)}")
    
    cursor.execute(sql_query, tuple(search_params))
    products = cursor.fetchall()
    cursor.close()
    
    for product in products:
        product['avg_rating'] = float(product['avg_rating']) if product['avg_rating'] is not None else None
    
    print(f"Retrieved products: {products}")
    return products

# Trả lời trực tiếp nếu câu hỏi đơn giản
def direct_answer(query: str, products: list):
    query_lower = query.lower()
    
    if "giá bao nhiêu" in query_lower:
        query_name = " ".join(word for word in query_lower.split() if word not in {"giá", "bao", "nhiều"})
        for product in products:
            product_name_lower = product['name'].lower()
            if all(word in product_name_lower for word in query_name.split() if word):
                return f"Giá của {product['name']} là {product['price']}."
    
    if "dùng tốt" in query_lower or "tốt nhất" in query_lower:
        rated_products = [p for p in products if p['avg_rating'] is not None]
        if rated_products:
            best_product = max(rated_products, key=lambda x: x['avg_rating'])
            return (
                f"Dựa trên đánh giá của người dùng, {best_product['name']} là sản phẩm dùng tốt nhất "
                f"với điểm đánh giá trung bình {best_product['avg_rating']:.1f}/5 "
                f"(dựa trên {best_product['rating_count']} đánh giá)."
            )
        else:
            return (
                "Hiện tại không có đánh giá nào để xác định sản phẩm nào dùng tốt. "
                "Bạn có thể xem danh sách sản phẩm và thông tin chi tiết dưới đây."
            )
    
    return None

# Tạo prompt cho Gemini
def create_prompt(query: str, products: list):
    if not products:
        return (
            f"User hỏi: {query}\n"
            f"Không tìm thấy sản phẩm nào phù hợp trong cơ sở dữ liệu. "
            f"Đừng đưa ra thông tin không có trong cơ sở dữ liệu hoặc gợi ý cửa hàng khác."
        )
    
    product_list = "\n".join([
        f"- Tên: {p['name']}, Giá: {p['price']}, Danh mục: {p['category']}, "
        f"Số lượng: {p['quantity']}, Đánh giá trung bình: {p['avg_rating'] if p['avg_rating'] is not None else 'Chưa có đánh giá'} "
        f"({p['rating_count']} đánh giá)"
        for p in products
    ])
    
    prompt = (
        f"Bạn là trợ lý ảo tên là Apple Intelligence của Apple Store. Bạn phải trả lời thật tự nhiên và tôn trọng khách hàng\n"
        f"khi người dùng chào bạn thì bạn phải chào lại họ\n"
        f"khi họ hỏi về thông tin sản phẩm thì bạn phải trả lời chính xác thông tin sản phẩm\n"
        f"User hỏi: {query}\n"
        f"Dưới đây là thông tin sản phẩm từ cơ sở dữ liệu:\n"
        f"{product_list}\n"
        f"Hãy trả lời câu hỏi của người dùng chỉ dựa trên thông tin trong cơ sở dữ liệu trên. "
        f"Nếu câu hỏi hỏi về giá, hãy tìm sản phẩm phù hợp và trả lời chính xác giá. "
        f"Nếu câu hỏi hỏi về sản phẩm 'dùng tốt' hoặc 'tốt nhất', hãy dựa vào Đánh giá trung bình (avg_rating) "
        f"để xác định sản phẩm tốt nhất (điểm cao nhất). "
        f"Nếu không có đánh giá, hãy trả lời rằng không đủ thông tin để đánh giá và liệt kê các sản phẩm. "
        f"Không được thêm bất kỳ thông tin nào không có trong danh sách sản phẩm này, "
        f"và không được gợi ý người dùng đến các cửa hàng khác hoặc các nguồn khác.\n"
        f"Ngoài ra nếu khách hàng có hỏi về thông tin liên hệ thì bạn có thể trả lời về thông tin của shop như: "
        f"email liên hệ: k100iltqbao@gmail.com, số điện thoại liên hệ: 0988888888, giờ làm việc từ 9h-18h, thứ 2-thứ 7, "
        f"cửa hàng trực tiếp ở 96A, đường Trần Phú, phường Mộ Lao, quận Hà Đông, thành phố Hà Nội\n"
        f"Trả lời trọng tâm vào vấn đề mà khách hàng đặt ra, không được trả lời ngoài vấn đề mà khách hàng đặt ra."
        f"nếu không có câu trả lời thì phải trả lịch sự ví dụ như: xin lỗi quý khách, mình không có thông tin cho câu hỏi của quý khách, vui lòng nhắn tin đến số điện thoại: 0988888888 hoặc gửi email đến: k100iltqbao@gmail.com"
    )
    return prompt

# Sinh nội dung bằng Gemini API
def generate_with_rag(query: str, products: list, config: dict) -> str:
    direct_response = direct_answer(query, products)
    if direct_response:
        return direct_response
    
    api_key = config.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("API Key is missing! Set GOOGLE_API_KEY as an environment variable.")

    client = genai.Client(api_key=api_key)

    model = "gemini-2.0-flash"
    prompt = create_prompt(query, products)
    
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="text/plain",
    )

    response = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        response += chunk.text
    return response

# API endpoint để xử lý câu hỏi
@app.post("/ask")
async def ask_bot(user_query: UserQuery, connection: mysql.connector.connection.MySQLConnection = Depends(get_mysql_connection)):
    config = load_config()
    query = user_query.query
    
    # Truy xuất sản phẩm từ cơ sở dữ liệu
    products = retrieve_products(query, connection)
    
    # Tạo phản hồi
    response = generate_with_rag(query, products, config)
    
    return {"response": response}

# Endpoint kiểm tra trạng thái API
@app.get("/")
async def root():
    return {"message": "Apple Store Bot API is running!"}

# Chạy FastAPI app (chỉ để debug, thực tế sẽ chạy qua uvicorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)