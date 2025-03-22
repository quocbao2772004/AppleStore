from datetime import datetime, timedelta

yesterday = datetime.now() - timedelta(days=1)
print(yesterday.strftime("%Y-%m-%d"))  # Định dạng thành chuỗi YYYY-MM-DD
print(datetime.now().strftime("%Y-%m-%d"))