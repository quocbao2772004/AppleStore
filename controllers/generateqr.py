from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests, random
import base64
from urllib.parse import quote
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BANK_ID = "MB"
ACCOUNT_NUMBER = "6866820048888"
ACCOUNT_NAME = "Le Tran Quoc Bao"

# Lưu trữ tạm thời các giao dịch đang chờ xác nhận
pending_transactions = {}  # {order_id: {"amount": float, "description": str}}

@app.post('/generate-qr')
async def generate_qr(
    product_id: int = Form(...),
    quantity: int = Form(...),
    amount: float = Form(...)
):
    print(f"[DEBUG] Received data: product_id={product_id}, quantity={quantity}, amount={amount}")
    try:
        random_number = random.randint(10000000, 99999999)
        # Mô tả giao dịch duy nhất
        description = f"Ma hoa don {random_number}{product_id}{quantity}"
        encoded_description = quote(description)
        encoded_account_name = quote(ACCOUNT_NAME)

        # Lưu thông tin giao dịch chờ xác nhận
        order_id = f"{random_number}{product_id}{quantity}"
        pending_transactions[order_id] = {
            "amount": amount,
            "description": description,
            "created_at": datetime.now().isoformat()
        }

        # URL của VietQR
        vietqr_url = (
            f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NUMBER}-compact2.png"
            f"?amount={int(amount)}&addInfo={encoded_description}&accountName={encoded_account_name}"
        )
        print(f"[DEBUG] VietQR URL: {vietqr_url}")

        # Gửi request tải ảnh QR code
        response = requests.get(vietqr_url, timeout=10)

        if response.status_code == 200:
            qr_base64 = base64.b64encode(response.content).decode('utf-8')
            qr_data_url = f"data:image/png;base64,{qr_base64}"
            return JSONResponse(
                status_code=200,
                content={
                    'success': True,
                    'qr_code': qr_data_url,
                    'order_id': order_id
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
            content={'success': False, 'message': 'Lỗi: Request timeout (VietQR phản hồi chậm)'}
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

        # Lấy thông tin giao dịch từ pending_transactions
        transaction_info = pending_transactions[order_id]
        description = transaction_info["description"]
        amount = transaction_info["amount"]

        # Gửi description và amount sang server 5005
        check_payload = {
            "order_id": order_id,
            "description": description,
            "amount": amount
        }
        try:
            check_response = requests.post(
                "http://localhost:5005/check-transaction",
                json=check_payload,
                timeout=5
            )
            check_result = check_response.json()
            print(f"[DEBUG] Response from 5005: {check_result}")

            if check_result.get("success"):
                # Xóa giao dịch khỏi danh sách chờ nếu xác nhận thành công
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

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=4001, reload=True)