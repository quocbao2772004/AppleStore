from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from mbbank import MBBank
import datetime, json
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_bank_config():
    try:
        with open("../config/bank_config.json", "r") as config_file: 
            config = json.load(config_file)
            return config["username"], config["password"]
    except FileNotFoundError:
        raise Exception("Không tìm thấy file bank_config.json")
    except KeyError:
        raise Exception("File bank_config.json thiếu username hoặc password")
    except json.JSONDecodeError:
        raise Exception("File bank_config.json không đúng định dạng JSON")

username, password = load_bank_config()  
mb = MBBank(username=username, password=password)

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

# Model cho dữ liệu gửi từ server 4001
class TransactionCheck(BaseModel):
    order_id: str
    description: str
    amount: int

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
            actual_description = str(transaction.get('addDescription', ''))  # Dùng addDescription như bạn đã kiểm tra
            actual_amount = int(transaction.get('creditAmount', '0'))  # Giả sử creditAmount là số tiền nhận
            print("actual_description = " + actual_description)
            print("actual_amount = " , actual_amount)
            print("check.description = " + check.description)
            print("check.amount = ", int(check.amount))
            # So sánh description và amount
            if (str(actual_description).find(str(check.description))!=-1 ):  
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
        return JSONResponse(
            status_code=500,
            content={"error": f"Lỗi hệ thống: {str(e)}"}
        )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5005, reload=True)