# Backend

Phần chạy trên máy chủ, cổng http://127.0.0.1:8765.

| File | Việc |
| --- | --- |
| `server.py` | Trang cửa hàng, đăng nhập, đơn hàng, quản trị, phục vụ ảnh |
| `invoice.py` | Hoá đơn HTML gửi qua SMTP sau khi đặt. Thiếu hộp thư thì đơn vẫn giữ |
| `agent/model.py` | Vòng chat: model chọn tool, Python chạy, model quyết định lượt tiếp |
| `agent/tools.py` | Chạy đúng tool model đã chọn |
| `agent/retrieve.py` | SQL và xếp hạng. Model không viết câu SQL |
| `agent/slots.py` | Đọc slot và điền tham số khi model để trống |
| `agent/route.py` | Router offline cho eval, và khi không có API |
| `agent/policy.py` | Cổng offline của router. Chat thật không đọc file này |
| `admin_agent/route.py` | Router offline của quản trị |
| `admin_agent/reports.py` | Báo cáo đọc: doanh thu, tồn, đơn, hàng chờ |
| `admin_agent/answer.py` | Schema tool quản trị và vòng gọi model |

Chạy từ thư mục gốc của project:

```bash
.venv/bin/python backend/server.py
```

Bộ test trợ lý, không gọi API và không ghi đơn:

```bash
.venv/bin/python backend/test_agent.py
.venv/bin/python backend/test_invoice.py
```

Hộp thư hoá đơn nằm trong `.env`: `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`. Đơn vẫn được lưu nếu các biến này trống hoặc máy chủ thư từ chối.

Đánh giá offline, không gọi API và không ghi đơn. Khách và admin là hai mục riêng:

```bash
.venv/bin/python eval/client/evaluate.py
.venv/bin/python eval/admin/evaluate.py
```

Khởi động lại thì tắt tiến trình đang giữ cổng 8765 trước, rồi chạy lệnh trên.

`server.py` còn tạo thêm bảng người dùng, đơn, phiên chat lúc chạy. Những bảng đó chưa có đủ trong `database/schema.sql`.
