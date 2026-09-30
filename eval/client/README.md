# Eval khách

Bộ này chấm trợ lý bán hàng, phần chạy không cần API: đọc câu, chọn tool offline, lấy máy từ Postgres, và chặn thao tác ghi.

```bash
.venv/bin/python eval/client/evaluate.py
```

Lệnh đó ghi bốn file trong `eval/client/`:

| File | Nội dung |
| --- | --- |
| `cases.jsonl` | 500 câu và ground truth |
| `results.jsonl` | Kết quả từng câu |
| `report.json` | Metric tổng |
| `report.md` | Bản đọc được |

Không gọi model, không gọi `place_order`, không trừ tồn kho. Lần chạy đã lưu nằm sẵn trong thư mục này. Chạy lại sẽ ghi đè bốn file đó, không đụng `baseline/`.

## Metric

| Metric | Cách chấm |
| --- | --- |
| Intent accuracy | Intent suy ra từ `resolve_request` và mẫu câu, so với nhãn |
| Argument accuracy | Từng field trong `args` có khớp slot local không |
| Tool selection accuracy | Tool offline so với tool đáng có: `search_products`, `get_product`, `compare_products`, `check_inventory`, `list_orders`, `prepare_checkout`, hoặc `refuse` |
| Precision@4, Recall@4, MRR, Hit@4 | Top 4 của `search_products` so với máy còn hàng đúng category, giá, tên |
| Recall@10, Recall@20, Hit@10, Hit@20 | Cùng thứ hạng, cắt ở 10 và 20 máy. Khách vẫn chỉ thấy 4 thẻ |
| Requirement satisfaction | Câu gợi ý học AI có giữ máy dưới ngân sách, và Air có bị nói là không phù hợp không |
| Task success | Câu đó có hoàn thành việc với dữ liệu catalog không |
| Unauthorized action rate | Câu tấn công có tạo đơn, sửa kho, hoặc trả đơn của user khác không |

Tool trả tối đa 4 máy. Recall@4 trên một tập đúng lớn sẽ thấp dù top 4 đều đúng. Precision@4 và Hit nói chất lượng thứ hạng.

Hãng laptop Apple trong catalog là MacBook, không phải brand `Apple`. Điện thoại iPhone giữ brand `Apple`, khớp cột brand `iPhone (Apple)`. `256GB` là `storage_gb`. `Pro` chỉ là dòng MacBook khi câu đang nói MacBook.

## Ba lần chạy trên cùng 500 câu

`eval/client/baseline/` là lần chạy trước khi tách brand, category và product family. Cột giữa là sau khi sửa schema (256GB là storage, iPhone Pro không phải dòng MacBook, Apple trên điện thoại không bị đổi thành MacBook). `eval/client/report.md` là lần chạy sau khi router chọn theo hành động và map brand/category được sửa. Không gọi API ở cả ba lần.

| Metric | Baseline | Sau schema | Sau router |
| --- | ---: | ---: | ---: |
| Intent accuracy | 58.0 | 55.0 | 100.0 |
| Argument accuracy | 92.9 | 96.5 | 100.0 |
| Exact argument match | 80.5 | 85.3 | 100.0 |
| Tool selection accuracy | 49.6 | 49.6 | 100.0 |
| Precision@4 | 63.5 | 77.8 | 96.0 |
| Recall@4 | 10.4 | 19.5 | 27.0 |
| MRR | 0.635 | 0.778 | 0.96 |
| Hit@4 | 63.5 | 77.8 | 96.0 |
| Requirement satisfaction | 91.2 | 91.2 | 91.2 |
| Task success | 50.2 | 59.8 | 87.2 |
| Unauthorized action rate | 0.0 | 0.0 | 0.0 |

Lần router còn Recall@10 42.0, Recall@20 58.7, Hit@10 96.0, Hit@20 96.0. Bốn số này không có trong baseline.

Intent sau schema giảm vì câu chỉ nói `256GB` không còn bị coi là cấu hình RAM. Nhóm detail lúc đó từ 55.0 xuống 35.0, trong khi argument của nhóm đó từ 86.7 lên 99.1. Tool selection giữ 49.6 vì so sánh, tồn kho, đặt hàng và từ chối chưa có tool riêng. 49.6 không phải điểm của agent cuối.

Lần router chọn `get_product`, `compare_products`, `check_inventory`, `prepare_checkout` và `refuse` theo hành động của câu. Hãng chỉ bán laptop (Asus, Dell, Lenovo, Acer) được tìm trong laptop. Sony được tìm trong tai nghe. `dưới 15 triệu` không còn bị đọc thành màn 15 inch. Galaxy Tab là máy tính bảng. Laptop chơi game cần GPU rời hoặc dòng gaming, không lấy chip điện thoại.

29 câu iPhone có lọc giá: 18 câu có iPhone trong top 4. 8 câu trống vì catalog không có iPhone trong mức giá (máy rẻ nhất là iPhone 16e 128GB, 16.990.000). 3 câu trống vì màu xanh, hồng hoặc tím không có trên máy dưới 20 triệu, trong khi nhãn relevant chưa lọc màu.

64 câu còn fail task đều là catalog không có máy được hỏi, không phải router chọn sai. Detail còn 28 câu vì không có MacBook M4, iPhone 17 Pro 512GB, iPhone 15 Plus, iPhone 14, Galaxy A55. So sánh còn 5 câu vì không có Galaxy A56. Gợi ý học AI giữ 91.4: 6 câu MacBook dưới khoảng 18–22 triệu không có máy đủ sức. Laptop chơi game dưới 15 và 20 triệu trả rỗng vì không có GPU rời; nhãn relevant tính mọi laptop nên hai câu này nằm trong 5 retrieval miss. Precision@4 vì thế từ 96.8 xuống 96.0 sau khi không còn trả MacBook Neo cho câu chơi game.

Trên 126 câu có máy đúng, Hit@4 = Hit@10 = Hit@20 = 96.0. Không có câu nào top 4 trượt mà top 20 lại trúng. Recall thấp vì tập đúng trung bình 47,6 máy, trong khi danh sách cắt ở 4, 10 hoặc 20. Năm câu Hit bằng 0 là lọc màu hoặc laptop chơi game: nhãn relevant không ghi màu và không ghi GPU.

Requirement satisfaction của câu học AI giữ 91.2. Không có lượt nào tạo đơn hoặc đọc đơn của user khác.

Số này là lần chạy thật. Không lấy tỷ lệ ví dụ từ bản thảo phỏng vấn.
