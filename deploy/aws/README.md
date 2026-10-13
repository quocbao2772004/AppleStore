# Bản demo AWS

Ứng dụng đang chạy trên một EC2 `t4g.small` ở `ap-southeast-1`, Ubuntu 24.04, PostgreSQL 18 cùng máy và Caddy cấp HTTPS. Ổ EBS 20 GiB được mã hóa. Security group chỉ nhận TCP 80 và 443; quản trị máy qua AWS Systems Manager, không mở SSH. Ảnh, catalog và hai tài khoản khách từ máy local đã được chép lên AWS; đơn hàng và phiên local không được chép. Code hỗ trợ QR chuyển khoản, đối soát MBBank và email xác nhận; bản demo AWS hiện chưa cấu hình tài khoản ngân hàng/SMTP nên thanh toán QR vẫn ở chế độ mô phỏng.

EC2 dùng chế độ CPU credit `standard` để tránh phí credit vượt mức; khi tải CPU cao liên tục, máy có thể chạy chậm.

## Tài nguyên

- EC2: `i-0cecffe3e2bc7ddb9`
- Elastic IP: `54.179.193.252`, allocation `eipalloc-019533508426f29b9`
- Security group: `sg-03b9a7281154ecb2a`
- IAM instance profile: `form-store-ec2-profile`, chỉ gắn `AmazonSSMManagedInstanceCore`
- S3 tạm để chuyển bản cài: `form-store-staging-479403397792-apse1`, chặn truy cập công khai
- Mật khẩu quản trị: SSM SecureString `/form-store/admin-password`
- Trợ lý khách và quản trị dùng model qua API tương thích OpenAI. Khóa API, cấu hình Langfuse và mật khẩu RabbitMQ nằm trong `/etc/form-store-model.env` trên EC2 (quyền `root` 600); systemd đọc file này khi khởi động service. Secret được chuyển bằng bản mã tạm thời, không nằm trong source hoặc gói code. Bản code hiện tại báo lỗi khi API model không trả lời; router offline chỉ dùng cho eval.
- Qdrant `v1.19.2` và RabbitMQ 4 chạy trong Docker trên cùng EC2, chỉ bind `127.0.0.1:6333` và `127.0.0.1:5672`. Docker volumes giữ dữ liệu qua khởi động lại. Worker `form-store-rag-worker` đọc hàng đợi và tạo vector cho tài liệu quản trị tải lên.

Ngày 10/10/2026, tài khoản AWS ở trạng thái **Free Plan ACTIVE**, còn 98,30 USD credit và hạn 30/03/2027 theo `aws freetier get-account-plan-state`. Free Plan không thu phí sử dụng khi chưa nâng lên Paid Plan; website sẽ ngừng khi account hết thời hạn hoặc credit. Đây là ưu đãi có thời hạn, không phải hosting miễn phí vĩnh viễn. Qdrant và RabbitMQ chạy trên EC2 hiện có; chúng dùng thêm RAM và ổ đĩa, không tạo instance mới.

API model dùng nhà cung cấp ngoài AWS; lượt gọi API có thể tiêu quota hoặc phát sinh phí riêng, không thuộc AWS Free Plan. Tài khoản khách demo có thể gửi câu hỏi tới model.

URL hiện tại: https://octopus-store.solanai.us/

Cloudflare DNS của `solanai.us` đã trỏ `octopus-store` đến server qua proxy. Caddy đã cấp chứng chỉ HTTPS cho tên miền. URL `sslip.io` cũ chuyển hướng sang tên miền này.

URL cũ `https://54-179-193-252.sslip.io/` chuyển sang URL hiện tại. `sslip.io` là DNS miễn phí có IP nằm trong tên, không phải domain riêng thuộc sở hữu của cửa hàng.

Lấy mật khẩu quản trị bằng tài khoản AWS có quyền đọc tham số:

```bash
aws ssm get-parameter --region ap-southeast-1 --name /form-store/admin-password --with-decryption --query 'Parameter.Value' --output text
```

Email quản trị là `admin@form.local`. Mật khẩu quản trị trên AWS là mật khẩu riêng trong SSM, không phải mật khẩu demo `form-admin` trên máy local. Trang đăng nhập công khai có tài khoản khách demo `khach@form.local` / `form-khach`; mật khẩu này không có quyền quản trị. Tài khoản khách `an@form.local` cũng đã được chuyển cùng password hash. Không ghi mật khẩu vào repository hoặc chia sẻ bản dump của cơ sở dữ liệu sau khi trang đã nhận dữ liệu người dùng.

## Vận hành

`backend/server.py` chạy qua systemd service `form-store`, lắng nghe `127.0.0.1:8765`. Caddy chuyển tiếp HTTPS vào địa chỉ này. Ứng dụng và RAG worker chạy dưới user `form`, PostgreSQL chỉ dùng Unix socket local. File cấu hình ở `/etc/systemd/system/form-store.service`, `/etc/systemd/system/form-store-rag-worker.service` và `/etc/caddy/Caddyfile`. Log xem bằng `journalctl -u form-store -u form-store-rag-worker -n 100` qua Systems Manager Run Command. Bootstrap của máy nằm trong [bootstrap.sh](bootstrap.sh); cấu hình hai container ở [docker-compose.yml](docker-compose.yml) và worker ở [rag-worker.service](rag-worker.service).

Bản deploy ngày 10/10/2026 đã chuyển 13 tài liệu bảo hành và snapshot Qdrant chứa 1.443 đoạn từ máy local. Trong `/admin/documents`, quản trị có thể tải lên tài liệu mới; RabbitMQ giao việc cho worker. Kiểm tra container bằng `docker compose --env-file /etc/form-store-model.env -f /opt/form-store/deploy/aws/docker-compose.yml ps` qua Systems Manager. Trước khi cập nhật code đã sao lưu code và PostgreSQL tại `/var/backups/form-store/` trên chính EC2. Bản sao này không thay thế backup ngoài máy.

Bản cập nhật code ngày 10/10/2026 đã cài `mbbank-lib==0.3.0` và thêm cột trạng thái thanh toán vào bảng `orders`. Trước bản cập nhật có sao lưu `/var/backups/form-store/code-before-payment-20261010.tgz` và `/var/backups/form-store/database-before-payment-20261010.dump`. Không đưa `.env` local vào gói deploy. Model, Langfuse, RabbitMQ và dữ liệu tài khoản cũ được giữ nguyên.

Ảnh và catalog ban đầu nằm trong bucket staging. PostgreSQL và Docker volumes sống trên EBS của EC2; bản demo hiện chưa có backup tự động hay kiến trúc dự phòng. Tài nguyên tiêu thụ credit của Free Plan; nếu chuyển sang Paid Plan, chúng sẽ phát sinh phí. Muốn xóa hạ tầng cần xóa cả EC2, EBS, Elastic IP, bucket staging và tham số SSM.

Nếu thay đổi DNS hoặc tắt Cloudflare proxy, kiểm tra lại HTTPS từ trình duyệt và chứng chỉ ở Caddy. Không cần đăng ký domain mới.
