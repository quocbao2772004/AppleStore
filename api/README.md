# API

Đường dẫn trả dữ liệu cho trang, không trả cả trang HTML.

| Đường dẫn | File | Việc |
| --- | --- | --- |
| `GET /api/suggest?q=` | `suggest.py` | Tối đa 8 sản phẩm còn bán, khớp tên đang gõ |

`backend/server.py` gọi `search_names`, rồi thêm tên hiển thị, giá và ảnh trước khi trả JSON.

Trợ lý không có REST riêng. Nút chat gửi `POST /tro-ly`, và `backend/agent.py` tự gọi công cụ tìm máy hoặc chuẩn bị đơn.
