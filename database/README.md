# Database

PostgreSQL local, database `tgdd_products`.

`schema.sql` là bảng danh mục sản phẩm: sản phẩm, ảnh, màu, thông số, đánh giá, và các bảng của bộ cào.

Bảng của cửa hàng được tạo khi server chạy, trong `backend/server.py`:

- `app_users` — tài khoản
- `app_sessions` — phiên đăng nhập
- `orders`, `order_items` — đơn hàng
- `app_chat_messages` — lịch sử chat theo phiên
- `app_categories` — tên nhóm trên menu

Nạp schema danh mục:

```bash
psql -d tgdd_products -f database/schema.sql
```
