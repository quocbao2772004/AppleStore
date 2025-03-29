import json
with open('/home/anonymous/code/web/btl3/controllers/history.json', 'r', encoding="utf-8") as f:
    history = json.load(f)
    transactionHistoryList = history['transactionHistoryList']
    for i in transactionHistoryList:
        if i['addDescription'] == 'TRAN QUOC VUONG chuyen tien ':
            print(i['creditAmount'])