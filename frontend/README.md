# Frontend

Phần chạy trên trình duyệt.

| File | Việc |
| --- | --- |
| `store.css` | Màu, cỡ chữ, bố cục trang và khung chat |
| `store.js` | Ô tìm kiếm, đổi ảnh theo màu, mở chat, nút nói, nút xóa lịch sử |

Trang HTML không nằm ở đây. Python trong `backend/server.py` ghép HTML rồi gửi cho trình duyệt. Trình duyệt tải hai file này qua `/frontend/store.css` và `/frontend/store.js`.

Sửa CSS xong thì tăng số `?v=` ở thẻ link trong `backend/server.py`, rồi khởi động lại server. Nếu không, trình duyệt có thể giữ bản CSS cũ.
