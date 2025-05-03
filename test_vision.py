import os
from openai import OpenAI
from PIL import Image
import io
import base64

# Lấy API key từ biến môi trường
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    raise ValueError("Không tìm thấy XAI_API_KEY trong biến môi trường. Hãy thiết lập bằng: export XAI_API_KEY='your_key'")

# Khởi tạo client OpenAI với Grok API
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1"
)

# Đường dẫn tới ảnh
image_path = "/home/anonymous/code/web/btl3/frontend/assets/images/iphone/0034910_iphone-16e-128gb_240.png"

try:
    # Đọc và mã hóa ảnh thành base64
    with Image.open(image_path) as image:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Gửi yêu cầu tới Grok API
    response = client.chat.completions.create(
        model="grok-vision-beta",  # Mô hình hỗ trợ xử lý ảnh
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Xem kĩ sản phẩm và cho biết đây là iphone gì"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                    }
                ]
            }
        ],
        max_tokens=500
    )

    # In kết quả
    description = response.choices[0].message.content
    print("Mô tả từ Grok:", description)

except FileNotFoundError:
    print(f"Không tìm thấy file ảnh tại: {image_path}")
except Exception as e:
    print(f"Lỗi: {str(e)}")