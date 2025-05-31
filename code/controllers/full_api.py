from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, XAI_API_KEY, SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, CHAT_HISTORY_FILE, CHAT_HISTORY_LOCK
from openai import OpenAI
from mysql.connector import pooling
import mysql.connector.errors
import logging
from fastapi import *
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from image_embedding import find_similar_images
import os, uvicorn
import json 
from fastapi.responses import JSONResponse
import requests, random
import base64
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from email.utils import formataddr
import mysql.connector
from mysql.connector import Error
from mbbank import MBBank
from urllib.parse import quote
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

db_config = {
    "host": MYSQL_HOST,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "database": MYSQL_DATABASE
}

app = FastAPI(title="Apple Store Chatbot", description="Chatbot for Apple Store")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
connection_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=10, **db_config)

def get_mysql_connection():
    try:
        cnx = connection_pool.get_connection()
        return cnx
    except mysql.connector.errors.PoolError as e:
        logger.error(f"Failed to get connection from pool: {str(e)}")
        raise HTTPException(status_code=500, detail="Database connection pool exhausted")
# ------------------------------------------------------------------user--------------------------------------------------------------
def save_chat_history(user_id: str, session_id: str, query: str, response: str):
    try:
        with CHAT_HISTORY_LOCK:
            history = {}

            # Tạo file nếu chưa tồn tại hoặc rỗng
            if os.path.exists(CHAT_HISTORY_FILE):
                if os.path.getsize(CHAT_HISTORY_FILE) > 0:
                    with open(CHAT_HISTORY_FILE, "r") as f:
                        history = json.load(f)

            if user_id not in history:
                history[user_id] = {}
            if session_id not in history[user_id]:
                history[user_id][session_id] = []

            history[user_id][session_id].append({
                "query": query,
                "response": response
            })

            with open(CHAT_HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=4)

    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")


def get_chat_history(user_id: str, session_id: str):
    try:
        with CHAT_HISTORY_LOCK:
            history = {}
            if os.path.exists(CHAT_HISTORY_FILE) and os.path.getsize(CHAT_HISTORY_FILE) > 0:
                with open(CHAT_HISTORY_FILE, "r") as f:
                    history = json.load(f)

            if user_id in history and session_id in history[user_id]:
                return history[user_id][session_id]
            else:
                return []
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        return []
    
    
def get_mysql_connection():
    try:
        cnx = connection_pool.get_connection()
        return cnx
    except mysql.connector.errors.PoolError as e:
        logger.error(f"Failed to get connection from pool: {str(e)}")
        raise HTTPException(status_code=500, detail="Database connection pool exhausted")

def analyze_prompt(prompt: str, user_id: str, session_id: str):
    history = get_chat_history(user_id, session_id)
    categories = ", ".join(get_category())
    safe_prompt = prompt.replace('"', '\\"').replace('\n', ' ')
    analysis_prompt = f""" Bạn là trợ lý AI phân tích câu hỏi của người dùng để tạo truy vấn SQL cho cơ sở dữ liệu về truy vấn sản phẩm với bảng như sau:
                          CREATE TABLE products (
                              id INT PRIMARY KEY AUTO_INCREMENT,
                              name VARCHAR(255) NOT NULL UNIQUE,
                              slug VARCHAR(255) NOT NULL UNIQUE,
                              description TEXT,
                              price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                              stock INT NOT NULL DEFAULT 0,
                              image VARCHAR(255),
                              category_id INT,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
                          );

                          CREATE TABLE categories (
                              id INT PRIMARY KEY AUTO_INCREMENT,
                              name VARCHAR(100) NOT NULL UNIQUE,
                              slug VARCHAR(100) NOT NULL UNIQUE,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                          );
                          
                          CREATE TABLE orders (
                                id INT PRIMARY KEY AUTO_INCREMENT,
                                user_id INT NOT NULL,
                                total_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                                status ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
                                payment_method VARCHAR(50),
                                shipping_phone VARCHAR(20),
                                shipping_name VARCHAR(100),
                                notes TEXT,
                                product_id INT NOT NULL,
                                quantity INT NOT NULL DEFAULT 1,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                            );
                            ALTER TABLE orders
                                ADD order_group_id INT NOT NULL,
                                ADD qr_code TEXT,
                                ADD qr_data TEXT;
                            ALTER TABLE orders ADD shipping_address TEXT NOT NULL;
                            
                          Nhiệm vụ của bạn:
                            - Phân tích câu hỏi của người dùng để xác định sản phẩm (nếu có) và các thuộc tính cần truy vấn (tên sản phẩm, giá, hình ảnh, danh mục, số lượng, mô tả sản phẩm, đơn hàng của người dùng đó với user = {user_id})
                            - Trả về một JSON với các trường:
                            - `product`: Tên sản phẩm (hoặc null nếu không xác định được, hoặc all nếu người dùng muốn xem tất cả).
                            - `attribute`: Thuộc tính cần truy vấn (price, quantity, all, products_consulting, order, image, date hoặc null nếu không rõ).
                            - `sql_query`: Truy vấn SQL phù hợp (sử dụng LIKE cho tên sản phẩm).
                            - `error`: Thông báo lỗi nếu không thể phân tích (hoặc null nếu thành công).
                            - `category`: Danh mục sản phẩm ({categories}).
                            - Bạn biết được lịch sử chat trước đó của người dùng và câu trả lời của shop, dựa vào đó để đưa ra câu trả lời phù hợp 
                              dựa trên lịch sử chat: {history} trong đó query là câu hỏi của người dùng và response là câu trả lời của shop, 
                              tùy thuộc vào ngữ cảnh và dựa vào câu hỏi của người dùng và câu trả lời của shop ở lịch sử chat để đưa ra câu trả lời phù hợp 
                              Ví dụ: 
                              history = [
                                {{"query": "iphone 15 giá bao nhiêu", "response": "Chào bạn! iPhone 15 bản 128GB đang có giá là 15,990,000 VNĐ."}},
                              ]
                              Mà khách hỏi nó có xịn không? Thì tức là họ đang hỏi về iphone 15 dựa trên lịch sử câu chat trước đó của họ 
                          Câu hỏi: "Giá của iPhone là bao nhiêu?"
                          Kết quả: {{
                              "product": "iphone",
                              "attribute": "price",
                              "category": "iphone",
                              "sql_query": "SELECT products.name, products.price 
                                            FROM products 
                                            join categories on products.category_id = categories.id
                                            WHERE LOWER(products.name) LIKE '%iphone%' and categories.name = 'iphone'
                                            ",
                              "error": null
                          }}
                          
                          Câu hỏi: "iphone 15 pro max giá bao nhiêu?"
                          Kết quả: {{
                              "product": "iphone 15 pro max",
                              "attribute": "price",
                              "category": "iphone",
                              "sql_query": "SELECT p.name, p.price 
                                            FROM products p 
                                            join categories c on p.category_id = c.id
                                            WHERE LOWER(p.name) LIKE '%iphone 15 pro max%' and c.name = 'iphone'
                                            ",
                              "error": null
                          }}
                          
                          Câu hỏi: "Thông tin về MacBook"
                          Kết quả: {{
                              "product": "macbook",
                              "attribute": "all",
                              "category": "macbook",
                              "sql_query": "SELECT p.name,p.price, p.description   
                                          FROM products p 
                                          join categories c on p.category_id = c.id 
                                          WHERE LOWER(p.name) LIKE '%macbook%' and c.name = 'macbook'
                                            ",
                              "error": null
                          }}
                          Câu hỏi: "iphone 16 có xịn không?"
                          Kết quả: {{
                              "product": "iphone 16",
                              "attribute": "descriptions",
                              "category": "iphone",
                              "sql_query": "
                                            select p.id, p.name, p.description 
                                            from products p
                                            join categories c on p.category_id = c.id
                                            where LOWER(p.name) like '%iPhone 16 pro max%' and c.name = 'iphone'
                                            ",
                              "error": null
                          }}
                          Câu hỏi: "ốp điện thoại iphone 16 pro max có xịn không?"
                          Kết quả: {{
                              "product": "iphone 16",
                              "attribute": "descriptions",
                              "category": "case",
                              "sql_query": "
                                            select p.id, p.name, p.description 
                                            from products p
                                            join categories c on p.category_id = c.id
                                            where LOWER(p.name) like '%iPhone 16 pro max%' and c.name = 'case'
                                            ",
                              "error": null
                          }}
                          Câu hỏi: "Sản phẩm nào đang giảm giá?"
                          Kết quả: {{
                              "product": null,
                              "attribute": null,
                              "category": null,
                              "sql_query": null,
                              "error": "Không thể xác định sản phẩm hoặc thuộc tính cụ thể."
                          }}
                          Câu hỏi: "Tư vấn cho tôi điện thoại dưới 20 triệu"
                          Kết quả: {{
                              "product": "iphone",
                              "attribute": "products_consulting",
                              "category": "iphone",
                              "sql_query": "
                                            SELECT p.name, p.price, p.description
                                            FROM products p 
                                            join categories c on p.category_id = c.id
                                            WHERE LOWER(p.name) LIKE '%iphone%' and c.name = 'iphone' and p.price < 20000000;
                                            ",
                              "error": null
                          }}
                          Câu hỏi: "Tư vấn cho tôi tai nghe dưới 5 triệu"
                          Kết quả: {{
                              "product": "airpod",
                              "attribute": "products_consulting",
                              "category": "airpod",
                              "sql_query": "
                                            SELECT p.name, p.price, p.description
                                            FROM products p 
                                            join categories c on p.category_id = c.id
                                            WHERE LOWER(p.name) LIKE '%airpod%' and c.name = 'airpod' and p.price < 5000000;
                                            ",
                              "error": null
                          }}
                          Câu hỏi: "So sánh ảnh iPhone 15 và iPhone 16"
                            Kết quả: {{
                                "product": "iphone",
                                "attribute": "image",
                                "category": "iphone",
                                "sql_query": "SELECT p.name, p.image FROM products p JOIN categories c ON p.category_id = c.id WHERE LOWER(p.name) LIKE '%iphone%' AND LOWER(c.name) = 'iphone'",
                                "error": null
                            }}
                            Câu hỏi: "Tôi muốn xem tất cả đơn hàng của tôi"
                            Kết quả: {{
                                "product": "all",
                                "attribute": "order",
                                "category": "all",
                                "sql_query": "select u.name as user_name, u.email as user_email, u.phone as user_phonenumber, p.name as product_name, o.total_price as price,
                                                o.created_at as buy_at
                                                from users u 
                                                join orders o on o.user_id = u.id 
                                                join products p on p.id = o.product_id
                                                where user_id  = {user_id};"
                            }}
                            Câu hỏi: "Liệt kê tất cả sản phẩm mà tôi đã mua"
                            Kết quả: {{
                                "product": "all",
                                "attribute": "order",
                                "category": "all",
                                "sql_query": "select distinct p.name 
                                                from users u 
                                                join orders o on o.user_id = u.id 
                                                join products p on p.id = o.product_id
                                                where u.id  = {user_id};"
                            }}
                            Câu hỏi: "Hôm nay ngày bao nhiêu"
                            Kết quả: {{
                                "product": "null",
                                "attribute": "date",
                                "category": "null",
                                "sql_query": "SELECT NOW() AS current_datetime;"
                            }}
                            Câu hỏi: "Tôi muốn xem tất cả đơn hàng của tôi trong ngày hôm qua"
                            Kết quả: {{
                                "product": "all",
                                "attribute": "date, order",
                                "category": "all",
                                "sql_query": "  SELECT 
                                                    u.name AS user_name, 
                                                    u.email AS user_email, 
                                                    u.phone AS user_phonenumber, 
                                                    p.name AS product_name, 
                                                    o.total_price AS price,
                                                    o.created_at AS time_order
                                                FROM users u 
                                                JOIN orders o ON o.user_id = u.id 
                                                JOIN products p ON p.id = o.product_id
                                                WHERE u.id = {user_id} 
                                                AND DATE(o.created_at) = CURDATE() - INTERVAL 1 DAY;
                                                "
                            }}
                          Bây giờ, phân tích câu hỏi sau: "{safe_prompt}"
                          """
    
    completion = client.chat.completions.create(
        model="grok-3-mini-fast-beta",
        messages=[
            {"role": "system", "content": analysis_prompt},
            {"role": "user", "content": safe_prompt}
        ],
        max_tokens=5000,
        temperature=0
    )
    with open ("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
        f.write(f"Kết quả phân tích trong analyze_prompt: \n" + "raw: " + "\n" +completion.choices[0].message.content + "\n" )
    try: 
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        return {
            "product": "null",
            "attribute": "null",
            "category": "null",
            "sql_query": "null",
            "error": str(e)
        }

def get_answer(prompt: Optional[str] = None, image_path: Optional[str] = None, user_id: str = None, session_id: str = None):
    history = get_chat_history(user_id, session_id)
    with open ("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
        f.write(f"Lịch sử chat: {history}\n")
    systemp = """
                  Bạn là Octopus Kraken một trợ lí ảo thông minh của Apple Store - 1 cửa hàng chuyên bán sản phẩm của Apple với các thiết bị như: Iphone, Macbook,
                  AppleWatch, MacStudio, MacMini, AirPod, Case, ...
                  
                  - Hướng dẫn:
                        Nhiệm vụ chính: Trả lời các câu hỏi của người dùng về các sản phẩm và những thông tin khác liên quan đến Apple Store. Câu trả lời phải rõ ràng, rành mạch, nhất quán 
                        để người dùng có thể hiểu được rõ nhất về các sản phẩm của cửa hàng.
                        Phong cách giao tiếp: Trả lời với giọng điệu lịch sự, thân thiện và gần gũi, câu trả lời tự nhiên giống như nhân viên tư vấn trực tiếp. Xưng hô "shop", "bạn" để tạo sự gần gũi
                        Khi một câu hỏi nào đó mà không biết thì phải trả lời thẳng thắn rồi gợi ý cho người dùng nhắn tin trực tiếp qua:
                            - Gmail: k100iltqbao@gmail.com
                            - Facebook: https://www.facebook.com/scammer2k4hehe 
                            - Số điện thoại/Zalo: 0917947910
                        Nếu bạn biết câu trả lời thì trả lời luôn không cần gơi ý người dùng nhắn qua thông tin trên nữa
                        Đưa ra câu trả lời với mỗi sản phẩm hoặc thông tin thì xuống dòng, gạch đầu dòng, không viết im đâm, tất cả đề in thường, viết cho dễ nhìn với người dùng nhất có thể
                  - Dựa trên `attribute`:
                    - `price`: Tập trung vào giá.
                    - `quantity`: Tập trung vào số lượng tồn kho.
                    - `description`: Tập trung vào mô tả.
                    - `all`: Cung cấp đầy đủ thông tin (tên, giá, mô tả).
                    - `products_consulting`: Giới thiệu sản phẩm kèm mô tả và giá.
                    - `image`: Mô tả hoặc so sánh dựa trên ảnh.
              """
    analysis = analyze_prompt(prompt, user_id, session_id)
    with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
        f.write(f"Phân tích: \n" + json.dumps(analysis, indent=4) + "\n")
        f.write("image: " + image_path + "\n")
    
    # Nếu không có ảnh và có câu hỏi
    if (not image_path or image_path == "" or image_path == None) and prompt:
        with open ("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"\n" + "Không có ảnh và có câu hỏi" "\n")
        # print(f"API response: {analysis}")
        response = ""
        if analysis.get("sql_query") and not analysis.get("error"):
            results = query_database(analysis["sql_query"])
            with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
                f.write(f"Kết quả truy vấn: {results}\n")
            if isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict):
                 
                completion = client.chat.completions.create(
                    model="grok-3-mini-fast-beta",
                    messages=[
                        {"role": "system", "content": systemp},
                        {
                            "role": "user",
                            "content": f"""
                            Dựa trên câu hỏi: "{prompt}"
                            Và dữ liệu sau: {results}
                            Dữ liệu lịch sử chat: history = "{history}" trong đó query là câu hỏi của người dùng và response là câu trả lời của shop, 
                            tùy thuộc vào ngữ cảnh và dựa vào câu hỏi của người dùng và câu trả lời của shop ở lịch sử chat để đưa ra câu trả lời phù hợp 
                            Ví dụ: 
                            history = [
                                {{"query": "iphone 15 giá bao nhiêu", "response": "Chào bạn! iPhone 15 bản 128GB đang có giá là 15,990,000 VNĐ."}},
                            ]
                            Mà khách hỏi nó có xịn không? Thì tức là họ đang hỏi về iphone 15 dựa trên lịch sử câu chat trước đó của họ 
                            
                            Hãy tạo câu trả lời tự nhiên, thân thiện, đúng phong cách trợ lí của Apple Store. Xưng hô "shop", "bạn" để tạo sự gần gũi.
                            
                            """
                        }
                    ],
                    max_tokens=5000,
                    temperature=0.7  
                )
                response = completion.choices[0].message.content
                
                    
        else:
            try:
                completion = client.chat.completions.create(
                    model="grok-3-mini-fast-beta",
                    messages=[
                        {
                            "role": "system", 
                            "content": systemp
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    max_tokens=5000,
                    temperature=0
                )
                return completion.choices[0].message.content
            except Exception as e:
                logger.error(f"API call error: {str(e)}")
                response = (
                    f"Xin lỗi bạn, shop gặp chút trục trặc khi xử lý câu hỏi về {analysis['product']}. "
                    "Bạn thử lại sau hoặc liên hệ shop qua:\n"
                    "- Gmail: k100iltqbao@gmail.com\n"
                    "- Facebook: https://www.facebook.com/scammer2k4hehe\n"
                    "- Số điện thoại/Zalo: 0917947910\n"
                )
        if "không có thông tin" in response or "không thể xử lý" in response or analysis.get("error"):
            response += (
                "Bạn vui lòng liên hệ shop qua:\n"
                "- Gmail: k100iltqbao@gmail.com\n"
                "- Facebook: https://www.facebook.com/scammer2k4hehe\n"
                "- Số điện thoại/Zalo: 0917947910\n"
                "Shop sẽ hỗ trợ bạn ngay!"
            )
        return response
    # Nếu có ảnh 
    else:
        with open ("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"\n" + "Có ảnh" "\n")
        results_image = get_image_information(image_path)
        with open ("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"Kết quả trích xuất từ ảnh: {results_image}\n")                                                                                                                            
        if results_image[0]['distance'] < 0.5:
            name = results_image[0]['name']
            query = ""
            if name.find("case") != -1 or name.find("ốp") != -1:
                category = "case"
            elif name.find("iphone") != -1:
                category = "iphone" 
            elif name.find("macbook") != -1:
                category = "macbook"
            elif name.find("airpod") != -1:
                category = "airpod"
            elif name.find("watch") != -1:
                category = "watch"
            elif name.find("studio") != -1:
                category = "macstudio"
            elif name.find("mini") != -1:
                category = "macmini"
            else:
                category = "ipad"
            print(f"Tên sản phẩm: {name}, danh mục: {category}")
            query = f"""select p.name, p.price, p.description 
                        from products p
                        join categories c 
                        on p.category_id = c.id 
                        where p.name like '%{name}%' and c.name = '{category}'
                        """
            res = query_database(query)
           
            completion = client.chat.completions.create(
                            model="grok-3-mini-fast-beta",
                            messages=[
                                {"role": "system", "content": systemp},
                                {
                                    "role": "user",
                                    "content": f"Câu hỏi của người dùng: {prompt}" + f"""
                                    Dựa trên hình ảnh mà người dùng gửi lên ở hiện tại, tôi đã trích xuất được thông tin sau:
                                    - thông tin từ ảnh người dùng gửi có nội dung: {res}
                                    Dữ liệu lịch sử chat: history = {history} trong đó query là câu hỏi của người dùng và response là câu trả lời của shop, 
                                    tùy thuộc vào ngữ cảnh và dựa vào câu hỏi của người dùng và câu trả lời của shop ở lịch sử chat để đưa ra câu trả lời phù hợp 
                                    Hãy tạo câu trả lời tự nhiên, thân thiện, đúng phong cách trợ lí của Apple Store. Xưng hô "shop", "bạn" để tạo sự gần gũi
                                    """
                                }
                            ],
                            max_tokens=5000,
                            temperature=0.7  
                        )
            response = completion.choices[0].message.content
            return response

        
def get_category():
    query = "SELECT * from categories"
    return [item['name'] for item in query_database(query)]

def query_database(query: str, params=None):
    cnx = None 
    cursor = None 
    try:
        cnx = get_mysql_connection()
        cursor = cnx.cursor(dictionary=True)
        cursor.execute(query, params or ())
        result = cursor.fetchall()
        return result
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if cnx:
            cnx.close()

def get_image_information(image_path: str):
    save_infor = []
    results =  find_similar_images(image_path, 1)
    for res in results:
        infor = res['filename'].split("_")
        name = infor[1].replace("-", " ").split() 
        len_name = len(name)
        if name[0] == "iphone":
            len_name = len(name) - 1
        name = " ".join(name[:len_name])
        
        save_infor.append({
            "name": name,
            "distance": res['distance']
        })
    return save_infor

@app.get("/")
async def root():
    return {"message": "API is running!"}

# class ChatRequest(BaseModel):
#     query: Optional[str] = None
#     user_id: str = Field(..., description="Unique identifier for the user")
#     session_id: str = Field(..., description="Unique identifier for the chat session")
    
@app.post("/chat")
async def chat(
    user_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    query: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    try:
        image_path = ""
        if image and image.filename:
            if image.content_type not in ["image/png", "image/jpeg"]:
                raise HTTPException(status_code=400, detail="Only PNG or JPEG images are supported")
            upload_dir = "/home/anonymous/code/web/v0/uploads/temp"
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, image.filename)
            with open(image_path, "wb") as f:
                f.write(await image.read())

        if not query and not image:
            raise HTTPException(status_code=400, detail="At least one of query or image is required")
        with open ("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"\n###############################################################################################\n")
            f.write("Cuộc hội thoại tiếp theo")
            f.write(f"\n###############################################################################################\n")
            
        response = get_answer(query, image_path, user_id, session_id)
        with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"\n------------------------------------------------------------------\n")
            f.write(f"\n******************************************************************\n")
            f.write(f"Câu hỏi: {query}\n")
            f.write(f"Trả lời: {response}\n")
            f.write(f"\n******************************************************************\n")
            f.write(f"\n------------------------------------------------------------------\n")
        save_chat_history(user_id, session_id, query, response)
        analysis = analyze_prompt(query, user_id, session_id) if query else {
            "product": None,
            "attribute": "image",
            "category": None,
            "sql_query": None,
            "error": None
        }
        return {
            "query": query,
            "response": response,
            "analysis": analysis,
            "image_filename": image.filename if image and isinstance(image, UploadFile) else None
        }
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logger.debug(f"Removed temp image: {image_path}")
            except Exception as e:
                logger.error(f"Error removing temp image: {str(e)}")
#----------------------------------------------------------admin----------------------------------------------------------
def analyze_prompt_admin(prompt: str):
    categories = ", ".join(get_category())
    safe_prompt = prompt.replace('"', '\\"').replace('\n', ' ')
    analysis_prompt = f"""Bạn là trợ lý AI phân tích câu hỏi của admin để tạo truy vấn SQL cho cơ sở dữ liệu về sản phẩm, người dùng, đơn hàng, đánh giá, và giỏ hàng với các bảng sau:

                          {get_table_definitions()}

                          Nhiệm vụ của bạn:
                            - Phân tích câu hỏi của admin để xác định loại truy vấn (sản phẩm, người dùng, đơn hàng, đánh giá, giỏ hàng).
                            - Xác định các thuộc tính cần truy vấn (tên sản phẩm, giá, số lượng, mô tả, thông tin người dùng, trạng thái đơn hàng, đánh giá, hoặc giỏ hàng).
                            - Nếu trong câu hỏi có một phần không liên quan đến các bảng trên thì bạn chỉ cần thực hiện trả về JSON hoàn chỉnh với các thông tin liên quan
                            (Ví dụ khi admin hỏi: "Cửa hàng bạn có iphone không? Bán cho tôi Xiaomi" thì câu liên quan là "Cửa hàng bạn có iphone không?".
                            hay khi admin hỏi: "Đưa ra 2 sản phẩm tồn kho ít nhất và phân tích lí do tại sao sản phẩm đó tồn kho ít nhất" thì câu liên quan là "Đưa ra 2 sản phẩm tồn kho ít nhất")
                            - Trả về một JSON hoàn chỉnh với các trường:
                              - `type`: Loại truy vấn (product, user, order, review, cart, date).
                              - `entity`: Tên sản phẩm, email người dùng, ID đơn hàng, v.v. (hoặc null nếu không xác định được).
                              - `attribute`: Thuộc tính cần truy vấn (price, quantity, description,product_info, all, user_info, order_status, review_details, cart_details hoặc null nếu không rõ).
                              - `sql_query`: Truy vấn SQL phù hợp (sử dụng LIKE cho tìm kiếm tên hoặc email, đảm bảo an toàn SQL).
                              - `error`: Thông báo lỗi nếu không thể phân tích (hoặc null nếu thành công).
                              - `category`: Danh mục sản phẩm (nếu liên quan đến sản phẩm, lấy từ {categories}, hoặc null).
                            
                          Ví dụ:
                          Câu hỏi: "Giá của iPhone 15 Pro Max là bao nhiêu?"
                          Kết quả: {{
                              "type": "product",
                              "entity": "iphone 15 pro max",
                              "attribute": "price",
                              "category": "iphone",
                              "sql_query": "SELECT p.name, p.price 
                                            FROM products p 
                                            JOIN categories c ON p.category_id = c.id 
                                            WHERE LOWER(p.name) LIKE '%iphone 15 pro max%' AND c.name = 'iphone'
                                            ",
                              "error": null
                          }}

                          Câu hỏi: "Thông tin người dùng với email user@example.com"
                          Kết quả: {{
                              "type": "user",
                              "entity": "user@example.com",
                              "attribute": "user_info",
                              "category": null,
                              "sql_query": "SELECT name, email, phone, address, role 
                                            FROM users 
                                            WHERE LOWER(email) = 'user@example.com'
                                            ",
                              "error": null
                          }}

                          Câu hỏi: "Đơn hàng của người dùng user@example.com"
                          Kết quả: {{
                              "type": "order",
                              "entity": "user@example.com",
                              "attribute": "order_status",
                              "category": null,
                              "sql_query": "SELECT o.id, o.total_price, o.status, o.shipping_address, p.name AS product_name 
                                            FROM orders o 
                                            JOIN users u ON o.user_id = u.id 
                                            JOIN products p ON o.product_id = p.id 
                                            WHERE LOWER(u.email) = 'user@example.com'
                                            ",
                              "error": null
                          }}

                          Câu hỏi: "Đánh giá của sản phẩm iPhone 15"
                          Kết quả: {{
                              "type": "review",
                              "entity": "iphone 15",
                              "attribute": "review_details",
                              "category": "iphone",
                              "sql_query": "SELECT r.rating, r.comment, r.status, u.name AS user_name 
                                            FROM reviews r 
                                            JOIN products p ON r.product_id = p.id 
                                            JOIN categories c ON p.category_id = c.id 
                                            JOIN users u ON r.user_id = u.id 
                                            WHERE LOWER(p.name) LIKE '%iphone 15%' AND c.name = 'iphone'
                                            ",
                              "error": null
                          }}

                          Câu hỏi: "Giỏ hàng của người dùng user@example.com"
                          Kết quả: {{
                              "type": "cart",
                              "entity": "user@example.com",
                              "attribute": "cart_details",
                              "category": null,
                              "sql_query": "SELECT c.quantity, p.name, p.price 
                                            FROM cart c 
                                            JOIN users u ON c.user_id = u.id 
                                            JOIN products p ON c.product_id = p.id 
                                            WHERE LOWER(u.email) = 'user@example.com'
                                            ",
                              "error": None
                          }}

                          Câu hỏi: "Sản phẩm nào đang giảm giá?"
                          Kết quả: {{
                              "type": "product",
                              "entity": null,
                              "attribute": null,
                              "category": null,
                              "sql_query": None,
                              "error": "Không thể xác định sản phẩm hoặc thuộc tính cụ thể."
                          }}
                          
                          Câu hỏi: "Đưa ra cho tôi thông tin của những khách hàng đánh giá tốt về sản phẩm của shop mình và các sản phẩm họ đánh giá tương ứng"
                          Kết quả: {{
                              "type": "user",
                              "entity": null,
                              "attribute": "user_info",
                              "category": null,
                              "sql_query": "SELECT u.id, u.name, u.email, p.name AS product_name, v.rating, v.comment 
                                            FROM users u 
                                            JOIN reviews v ON u.id = v.user_id 
                                            JOIN products p ON p.id = v.product_id
                                            WHERE v.rating >= 4
                                            ",
                              "error": None
                          }}
                          
                          Câu hỏi: "Đưa ra cho tôi thông tin của những khách hàng thân thiết nhất"
                          Kết quả: {{
                              "type": "user",
                              "entity": null,
                              "attribute": "user_info",
                              "category": null,
                              "sql_query": "SELECT u.id, u.name, u.email, SUM(o.total_price) AS total_spent
                                            FROM users u
                                            JOIN orders o ON u.id = o.user_id
                                            GROUP BY u.id, u.name, u.email
                                            ORDER BY total_spent DESC
                                            LIMIT 5;
                                            ",
                              "error": None
                          }}
                          Câu hỏi: "Đưa ra cho tôi thông tin của 5 sản phẩm tồn kho nhiều nhất"
                          Kết quả: {{
                              "type": "product",
                              "entity": null,
                              "attribute": "product_info",
                              "category": null,
                              "sql_query": "SELECT id, name, stock
                                            FROM products
                                            ORDER BY stock DESC
                                            LIMIT 5;
                                            ",
                              "error": None
                          }}
                          Câu hỏi: "Đưa ra cho tôi thông tin của 5 sản phẩm tồn kho nhiều nhất và đưa ra lí do tại sao sản phẩm đó tồn kho nhiều"
                          Kết quả: {{
                              "type": "product",
                              "entity": null,
                              "attribute": "product_info",
                              "category": null,
                              "sql_query": "SELECT id, name, stock
                                            FROM products
                                            ORDER BY stock DESC
                                            LIMIT 5;
                                            ",
                              "error": None
                          }}
                           Câu hỏi: "đưa ra thông tin của những khách hàng mua, sản phẩm được bán vào hôm 5/9/2025"
                          Kết quả: {{
                              "type": "user, product, order",
                              "entity": null,
                              "attribute": "user_info, product_info, order_status",
                              "category": null,
                              "sql_query": "SELECT 
                                                u.id AS user_id,
                                                u.name AS user_name,
                                                u.email,
                                                p.id AS product_id,
                                                p.name AS product_name,
                                                o.quantity,
                                                o.total_price,
                                                o.created_at
                                            FROM orders o
                                            JOIN users u ON o.user_id = u.id
                                            JOIN products p ON o.product_id = p.id
                                            WHERE DATE(o.created_at) = '2025-05-09';
                                            ",
                              "error": None
                          }}
                          Câu hỏi: "đưa ra các sản phẩm được bán vào hôm 5/9/2025 và tổng tiền bán được"
                          Kết quả: {{
                              "type": " product, order",
                              "entity": null,
                              "attribute": "product_info, order_status",
                              "category": null,
                              "sql_query": "SELECT 
                                                p.id AS product_id,
                                                p.name AS product_name,
                                                SUM(o.quantity) AS total_quantity_sold,
                                                SUM(o.quantity * p.price) AS total_revenue
                                            FROM orders o
                                            JOIN products p ON o.product_id = p.id
                                            WHERE DATE(o.created_at) = '2025-05-09'
                                            GROUP BY p.id, p.name
                                            ORDER BY total_revenue DESC;
                                            ",
                              "error": None
                          }}
                          Câu hỏi: "Hôm nay bán được bao nhiêu sản phẩm"
                          Kết quả: {{
                              "type": " product, order",
                              "entity": null,
                              "attribute": "product_info, order_status",
                              "category": null,
                              "sql_query": "SELECT SUM(quantity) AS total_products_sold_today
                                            FROM orders
                                            WHERE DATE(created_at) = CURDATE();
                                            ",
                              "error": None
                          }}
                           Câu hỏi: "Hôm nay ngày bao nhiêu"
                          Kết quả: {{
                              "type": "date",
                              "entity": null,
                              "attribute": null,
                              "category": null,
                              "sql_query": "SELECT NOW() AS current_datetime;",
                              "error": null
                          }}
                          Bây giờ, phân tích câu hỏi sau: "{safe_prompt}"
                          """
    try:
        completion = client.chat.completions.create(
            model="grok-3-mini-fast-beta",
            messages=[
                {"role": "system", "content": analysis_prompt},
                {"role": "user", "content": safe_prompt}
            ],
            max_tokens=5000,
            temperature=0
        )
        response_content = completion.choices[0].message.content.strip()
        with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"Kết quả truy vấn: {response_content}\n")
        # Kiểm tra và làm sạch phản hồi để đảm bảo JSON hợp lệ
        return json.loads(response_content)
    except Exception as e:
        logger.error(f"API call error: {str(e)}")
        return {
            "type": "unknown",
            "entity": None,
            "attribute": None,
            "category": None,
            "sql_query": None,
            "error": f"API error: {str(e)}"
        }
def get_table_definitions():
    return """
    CREATE TABLE categories (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL UNIQUE,
        slug VARCHAR(100) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(100) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        phone VARCHAR(20),
        address TEXT,
        role ENUM('admin', 'customer') DEFAULT 'customer',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE products (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL UNIQUE,
        slug VARCHAR(255) NOT NULL UNIQUE,
        description TEXT,
        price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        stock INT NOT NULL DEFAULT 0,
        image VARCHAR(255),
        category_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
    );

    CREATE TABLE orders (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        total_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        status ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
        payment_method VARCHAR(50),
        shipping_phone VARCHAR(20),
        shipping_name VARCHAR(100),
        notes TEXT,
        product_id INT NOT NULL,
        quantity INT NOT NULL DEFAULT 1,
        shipping_address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    CREATE TABLE reviews (
        id INT PRIMARY KEY AUTO_INCREMENT,
        product_id INT NOT NULL,
        user_id INT NOT NULL,
        rating INT NOT NULL DEFAULT 0,
        comment TEXT,
        status ENUM('approved', 'pending', 'rejected') DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE cart (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        product_id INT NOT NULL,
        quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """

def get_answer_admin(prompt: str):
    system_prompt = """
        Bạn là Octopus Kraken, trợ lý ảo thông minh của Apple Store - cửa hàng chuyên bán sản phẩm Apple như iPhone, MacBook, Apple Watch, Mac Studio, Mac Mini, AirPods, Case, v.v.
        - Nhiệm vụ chính: Trả lời các câu hỏi của admin về sản phẩm, người dùng, đơn hàng, đánh giá, và giỏ hàng một cách rõ ràng, rành mạch, và chuyên nghiệp.
        - Phong cách giao tiếp: Lịch sự, thân thiện, xưng hô "shop" và "bạn" để tạo sự gần gũi.
        - Nếu không có thông tin hoặc không xử lý được câu hỏi, trả lời thẳng thắn và gợi ý liên hệ qua:
            - Gmail: k100iltqbao@gmail.com
            - Facebook: https://www.facebook.com/scammer2k4hehe
            - Số điện thoại/Zalo: 0917947910
        - Dựa trên `attribute`:
            - `price`: Tập trung vào giá sản phẩm.
            - `quantity`: Tập trung vào số lượng tồn kho.
            - `description`: Tập trung vào mô tả sản phẩm.
            - `all`: Cung cấp đầy đủ thông tin sản phẩm (tên, giá, mô tả).
            - `products_consulting`: Giới thiệu sản phẩm kèm mô tả và giá.
            - `image`: Mô tả hoặc so sánh dựa trên ảnh.
            - `user_info`: Thông tin người dùng (tên, email, số điện thoại, địa chỉ, vai trò).
            - `order_status`: Thông tin đơn hàng (ID, tổng giá, trạng thái, địa chỉ giao hàng, sản phẩm).
            - `review_details`: Thông tin đánh giá (điểm, bình luận, trạng thái, người đánh giá).
            - `cart_details`: Thông tin giỏ hàng (sản phẩm, số lượng, giá).
            - `product_info`: Thông tin sản phẩm (tên, giá, mô tả, tồn kho, danh mục).
    """
    
    try:
        analysis = analyze_prompt_admin(prompt)
        response = ""
        with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write(f"sql_query: {analysis.get('sql_query')}\n")
            f.write(f"error: {analysis.get('error')}\n")
            f.write(f"Kết quả phân tích: {analysis}\n")
            # f.write(f"sql_query: {analysis.get('sql_query')}\n")
            # f.write(f"error: {analysis.get('error')}\n")
        if analysis.get("sql_query") and not analysis.get("error"):
            results = query_database(analysis["sql_query"])
            with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
                f.write(f"có vào vòng lặp \n Kết quả truy vấn dữ liệu: {results}\n")
            if results:
                try:
                    completion = client.chat.completions.create(
                        model="grok-3-mini-fast-beta",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": f"""
                                Dựa trên câu hỏi: "{prompt}"
                                Và dữ liệu sau: {results}
                                Hãy tạo câu trả lời tự nhiên, thân thiện, đúng phong cách trợ lý của Apple Store. Xưng hô "shop", "bạn" để tạo sự gần gũi.
                                """
                            }
                        ],
                        max_tokens=5000,
                        temperature=0.7
                    )
                    response = completion.choices[0].message.content
                except Exception as e:
                    response = (
                        f"Xin lỗi bạn, shop gặp chút trục trặc khi xử lý câu hỏi về {analysis['entity']}. "
                        "Bạn thử lại sau hoặc liên hệ shop qua:\n"
                        "- Gmail: k100iltqbao@gmail.com\n"
                        "- Facebook: https://www.facebook.com/scammer2k4hehe\n"
                        "- Số điện thoại/Zalo: 0917947910\n"
                    )
            else:
                try:
                    completion = client.chat.completions.create(
                        model="grok-3-mini-fast-beta",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=5000,
                        temperature=0.7
                    )
                    response = completion.choices[0].message.content
                except Exception as e:
                    response = "Shop không thể xử lý câu hỏi này ngay bây giờ. "
            if "không có thông tin" in response or "không thể xử lý" in response or analysis.get("error"):
                response += (
                    "Bạn vui lòng liên hệ shop qua:\n"
                    "- Gmail: k100iltqbao@gmail.com\n"
                    "- Facebook: https://www.facebook.com/scammer2k4hehe\n"
                    "- Số điện thoại/Zalo: 0917947910\n"
                    "Shop sẽ hỗ trợ bạn ngay!"
                )
            return response
        else:
            try:
                with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
                    f.write(f"\n Không vào vòng lặp, phân tích: {analysis}\n")
                completion = client.chat.completions.create(
                    model="grok-3-mini-fast-beta",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=5000,
                    temperature=0.7
                )
                response = completion.choices[0].message.content
            except Exception as e:
                response = "Shop không thể xử lý câu hỏi này ngay bây giờ. "
            return response
    except Exception as e:
        return (
            "Shop không thể xử lý câu hỏi này ngay bây giờ. "
            "Bạn vui lòng gửi lại hoặc liên hệ shop qua:\n"
            "- Gmail: k100iltqbao@gmail.com\n"
            "- Facebook: https://www.facebook.com/scammer2k4hehe\n"
            "- Số điện thoại/Zalo: 0917947910\n"
        )
def determine_category(name: str) -> str:
    name_lower = name.lower()
    if "case" in name_lower or "ốp" in name_lower:
        return "case"
    elif "iphone" in name_lower:
        return "iphone"
    elif "macbook" in name_lower:
        return "macbook"
    elif "airpod" in name_lower:
        return "airpod"
    elif "watch" in name_lower:
        return "watch"
    elif "studio" in name_lower:
        return "macstudio"
    elif "mini" in name_lower:
        return "macmini"
    else:
        return "ipad"
@app.post("/chatadmin")
async def chatadmin(
    query: Optional[str] = Form(None),

):
    try:
        with open("/home/anonymous/code/web/v0/controllers/test_answer.json", "a") as f:
            f.write("-------------------------------------------------------------------------------------------\n")
            f.write(f"Câu hỏi: {query}\n")
        response = get_answer_admin(query,)
        analysis = analyze_prompt_admin(query) if query else {
            "type": "image",
            "entity": None,
            "attribute": "image",
            "category": None,
            "sql_query": None,
            "error": None
        }
        return {
            "query": query,
            "response": response,
            "analysis": analysis,
            
        }
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    finally:
        pass
# ------------------------------------------------------------------qrcode--------------------------------------------------------------
BANK_ID = "MB"
ACCOUNT_NUMBER = "6866820048888"
ACCOUNT_NAME = "Le Tran Quoc Bao"

pending_transactions = {}  

@app.post('/generate-qr')
async def generate_qr(
    items: str = Form(...),  
    amount: float = Form(...)
):
    print(f"[DEBUG] Received data: items={items}, amount={amount}")
    try:
        try:
            items_list = json.loads(items)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={'success': False, 'message': 'Invalid JSON format for items'}
            )

        if not isinstance(items_list, list) or not items_list:
            return JSONResponse(
                status_code=400,
                content={'success': False, 'message': 'Items must be a non-empty list'}
            )
        random_number = random.randint(10000000, 99999999)
        description_parts = []
        for item in items_list:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            if not isinstance(product_id, int) or not isinstance(quantity, int):
                return JSONResponse(
                    status_code=400,
                    content={'success': False, 'message': 'Each item must have valid product_id and quantity'}
                )
            description_parts.append(f"{product_id}{quantity}")
        description = f"Ma hoa don {random_number}{' '.join(description_parts)}"
        encoded_description = quote(description)
        encoded_account_name = quote(ACCOUNT_NAME)
        order_id = f"{random_number}{''.join(description_parts)}"
        pending_transactions[order_id] = {
            "amount": amount,
            "description": description,
            "created_at": datetime.now().isoformat()
        }
        vietqr_url = (
            f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NUMBER}-compact2.png"
            f"?amount={int(amount)}&addInfo={encoded_description}&accountName={encoded_account_name}"
        )
        print(f"[DEBUG] VietQR URL: {vietqr_url}")
        response = requests.get(vietqr_url, timeout=10)

        if response.status_code == 200:
            qr_base64 = base64.b64encode(response.content).decode('utf-8')
            qr_data_url = f"data:image/png;base64,{qr_base64}"
            return JSONResponse(
                status_code=200,
                content={
                    'success': True,
                    'qr_code': qr_data_url,
                    'order_id': order_id,
                    'description': description  # Thêm description vào phản hồi
                }
            )

        return JSONResponse(
            status_code=500,
            content={
                'success': False,
                'message': f'Lỗi từ VietQR: HTTP {response.status_code}',
                'url': vietqr_url
            }
        )

    except requests.exceptions.Timeout:
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': 'Lỗi: Request rekomendasi timeout (VietQR phản hồi chậm)'}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Lỗi hệ thống: {str(e)}'}
        )

@app.get('/check-payment/{order_id}')
async def check_payment(order_id: str):
    try:
        if order_id not in pending_transactions:
            return JSONResponse(
                status_code=404,
                content={'success': False, 'message': 'Không tìm thấy đơn hàng'}
            )
        transaction_info = pending_transactions[order_id]
        description = transaction_info["description"]
        amount = transaction_info["amount"]
        check_payload = {
            "order_id": order_id,
            "description": description,
            "amount": amount
        }
        try:
            check_response = requests.post(
                "http://localhost:4070/check-transaction",
                json=check_payload,
                timeout=5
            )
            check_result = check_response.json()
            print(f"[DEBUG] Response from 5005: {check_result}")

            if check_result.get("success"):
                del pending_transactions[order_id]
            return JSONResponse(
                status_code=200,
                content=check_result
            )
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Error sending to 5005: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={'success': False, 'message': f'Lỗi kết nối server 5005: {str(e)}'}
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Lỗi hệ thống: {str(e)}'}
        )

# ------------------------------------------------------------------check-transaction--------------------------------------------------------------
def load_bank_config():
    try:
        with open("../config/bank_config.json", "r") as config_file:
            config = json.load(config_file)
            return (
                config["username"],
                config["password"],
                config["smtp_host"],
                config["smtp_port"],
                config["smtp_user"],
                config["smtp_password"],
                config["mysql_host"],
                config["mysql_user"],
                config["mysql_password"],
                config["mysql_database"]
            )
    except FileNotFoundError:
        raise Exception("Không tìm thấy file bank_config.json")
    except KeyError as e:
        raise Exception(f"File bank_config.json thiếu khóa: {str(e)}")
    except json.JSONDecodeError:
        raise Exception("File bank_config.json không đúng định dạng JSON")

(
    username,
    password,
    smtp_host,
    smtp_port,
    smtp_user,
    smtp_password,
    mysql_host,
    mysql_user,
    mysql_password,
    mysql_database
) = load_bank_config()

mb = MBBank(username=username, password=password)

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        return connection
    except Error as e:
        raise Exception(f"Lỗi kết nối MySQL: {str(e)}")

def get_user_email(user_id: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        query = "SELECT email FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except Error as e:
        raise Exception(f"Lỗi khi lấy email: {str(e)}")
    finally:
        cursor.close()
        connection.close()

def send_payment_confirmation_email(to_email: str, subject: str, order_id: str, amount: float, transaction_date: str, items: list):
    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg['Subject'] = subject

    # Template HTML cho email
    items_html = ""
    for item in items:
        items_html += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{item['name']}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{item['quantity']}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">
                {format(item['price'] * item['quantity'], ',.0f')}₫
            </td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #28a745; color: white; padding: 10px; text-align: center; }}
            .content {{ padding: 20px; border: 1px solid #ddd; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 8px; border: 1px solid #ddd; }}
            th {{ background-color: #f4f4f4; }}
            .footer {{ margin-top: 20px; text-align: center; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Xác nhận thanh toán đơn hàng #{order_id}</h2>
            </div>
            <div class="content">
                <p>Kính gửi Quý khách,</p>
                <p>Chúng tôi xin thông báo rằng thanh toán cho đơn hàng của bạn đã được xác nhận thành công. Dưới đây là chi tiết:</p>
                <p><strong>Mã đơn hàng:</strong> {order_id}</p>
                <p><strong>Số tiền:</strong> {format(amount, ',.0f')}₫</p>
                <p><strong>Ngày giao dịch:</strong> {transaction_date}</p>
                <h3>Chi tiết đơn hàng</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Sản phẩm</th>
                            <th>Số lượng</th>
                            <th>Thành tiền</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                <p>Đơn hàng của bạn sẽ được xử lý trong vòng 24 giờ. Cảm ơn bạn đã mua sắm với chúng tôi!</p>
            </div>
            <div class="footer">
                <p>Trân trọng,<br>Đội ngũ cửa hàng</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        print(f"[DEBUG] Email sent to {to_email}")
    except Exception as e:
        print(f"[DEBUG] Email sending failed: {str(e)}")
        raise Exception(f"Lỗi khi gửi email: {str(e)}")

@app.get("/balance")
async def get_balance():
    try:
        balance = mb.getBalance()
        print("Dữ liệu số dư:", balance)
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
        transactionHistoryList = history.get('transactionHistoryList', [])
        return history
    except Exception as e:
        return {"error": str(e)}

class TransactionCheck(BaseModel):
    order_id: str
    description: str
    amount: float
    user_id: int
    items: list

@app.post("/check-transaction")
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
        print(f"[DEBUG] Transaction History: {transactionHistoryList}")
        for transaction in transactionHistoryList:
            actual_description = str(transaction.get('addDescription', ''))
            actual_amount = float(transaction.get('creditAmount', '0'))
            print(f"[DEBUG] actual_description = {actual_description}")
            print(f"[DEBUG] actual_amount = {actual_amount}")
            print(f"[DEBUG] check.description = {check.description}")
            print(f"[DEBUG] check.amount = {check.amount}")
            if (actual_description.find(check.description) != -1 and abs(actual_amount - check.amount) < 0.01):
                # Lấy email người dùng
                user_email = get_user_email(check.user_id)
                if not user_email:
                    print(f"[DEBUG] No email found for user_id: {check.user_id}")
                
                # Gửi email thông báo
                if user_email:
                    send_payment_confirmation_email(
                        to_email=user_email,
                        subject=f"Xác nhận thanh toán đơn hàng #{check.order_id}",
                        order_id=check.order_id,
                        amount=check.amount,
                        transaction_date=transaction.get('transactionDate', ''),
                        items=check.items
                    )
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Giao dịch khớp",
                        "transaction": {
                            "description": actual_description,
                            "amount": actual_amount,
                            "transactionDate": transaction.get('transactionDate', '')
                        }
                    }
                )

        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "message": "Chưa tìm thấy giao dịch khớp",
                "order_id": check.order_id,
                "description": check.description
            }
        )
    except Exception as e:
        print(f"[DEBUG] Error in check-transaction: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Lỗi hệ thống: {str(e)}"}
        )
# ------------------------------------------------------------------send_email--------------------------------------------------------------


@app.post('/send-email')
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    content: str = Form(...),
    message: str = Form(...)
):
    try:
        logger.debug(f"Received POST request - Name: {name}, Email: {email}, Content: {content}, Message: {message}")

        # Kiểm tra dữ liệu
        if not all([name, email, content, message]):
            logger.warning("Missing form data")
            raise HTTPException(status_code=400, detail="Vui lòng điền đầy đủ thông tin!")

        # Tạo nội dung email
        subject = 'Tin nhắn mới từ Apple Store Contact Form'
        body = f"Họ và tên: {name}\nEmail: {email}\nNội dung: {content}\nTin nhắn:\n{message}"

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
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4070)
