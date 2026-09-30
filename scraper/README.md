# Bộ cào dữ liệu

Lấy sản phẩm từ thegioididong.com vào PostgreSQL. Không phải giao diện cửa hàng.

Chạy từ thư mục gốc của project:

```bash
.venv/bin/python scraper/tgdd_scraper.py --mode all
.venv/bin/python scraper/test_tgdd_scraper.py
```

Ảnh tải về `data/images/`. Schema được đọc từ `database/schema.sql`.
