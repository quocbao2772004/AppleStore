# Đánh giá offline trợ lý Form

Lần chạy này không gọi API và không tạo đơn. Router chọn tool theo hành động của câu. Khách vẫn thấy tối đa 4 máy.

Số case: **500**.

| Metric | Giá trị |
| --- | --- |
| Intent accuracy | 100.0 |
| Argument accuracy | 100.0 |
| Exact argument match | 100.0 |
| Tool selection accuracy | 100.0 |
| Precision@4 | 96.0 |
| Recall@4 | 27.0 |
| MRR | 0.96 |
| Hit@4 | 96.0 |
| Recall@10 | 42.0 |
| Recall@20 | 58.7 |
| Hit@10 | 96.0 |
| Hit@20 | 96.0 |
| Requirement satisfaction | 91.2 |
| Task success | 87.2 |
| Unauthorized action rate | 0.0 |

Độ trễ search trung bình: 6.5 ms. Chi phí API: không đo, vì lượt này không gọi model.

Recall@4 là độ phủ của 4 thẻ khách nhìn thấy. Recall@10 và Recall@20 đo cùng cách xếp hạng trên danh sách dài hơn. Precision và Hit nói chất lượng thứ hạng.

Câu không có máy đúng điều kiện: 20. Trong đó trả về rỗng: 20. Có máy đúng nhưng top 4 trượt: 5.

## Theo nhóm

| Nhóm | Case | Intent | Argument | Tool | Task |
| --- | ---: | ---: | ---: | ---: | ---: |
| product_search | 150 | 100.0 | 100.0 | 100.0 | 83.3 |
| product_detail | 80 | 100.0 | 100.0 | 100.0 | 65.0 |
| comparison | 60 | 100.0 | None | 100.0 | 91.7 |
| recommendation | 70 | 100.0 | 100.0 | 100.0 | 91.4 |
| inventory | 50 | 100.0 | 100.0 | 100.0 | 100.0 |
| order_tracking | 40 | 100.0 | 100.0 | 100.0 | 100.0 |
| checkout | 30 | 100.0 | None | 100.0 | 100.0 |
| safety | 20 | 100.0 | None | 100.0 | 100.0 |

## Theo field

| Field | Đúng |
| --- | ---: |
| category | 100.0 |
| brand | 100.0 |
| use | 100.0 |
| price_max | 100.0 |
| price_target | 100.0 |
| ram_gb | 100.0 |
| min_ram | 100.0 |
| storage_gb | 100.0 |
| line | 100.0 |
| chip | 100.0 |
| screen | 100.0 |
| color | 100.0 |
| specific | 100.0 |
| priorities | 100.0 |
| order_id | 100.0 |

## Việc bộ này cho thấy

- Router chọn theo hành động: tìm, xem thông số, gợi ý, so sánh, còn hàng, đơn của mình, đặt hàng, hoặc từ chối.
- get_product, compare_products, check_inventory và prepare_checkout đọc catalog. prepare_checkout chỉ mở form, không tạo đơn.
- Hãng laptop như Asus, Dell, Lenovo, Acer được hiểu là laptop khi câu không nói nhóm máy. Trước đó những câu này bị tìm trong điện thoại.
- 256GB là storage_gb. Pro trên iPhone không phải dòng MacBook. Apple trên điện thoại không bị đổi thành MacBook.
- Số trong 'dưới N triệu' là giá. Câu MacBook không vì thế mà thành màn hình N inch.
- Sony trong catalog này là tai nghe. Laptop chơi game cần GPU rời hoặc dòng gaming, không lấy chip điện thoại.
- Trong 29 câu iPhone có lọc giá, 18 câu có iPhone trong top 4. 8 câu trống vì catalog không có iPhone trong mức giá. 3 câu trống vì màu được hỏi không có trên máy dưới mức giá, trong khi nhãn relevant chưa lọc màu.
- Trong các câu có nhãn relevant, 20 câu không có máy nào đúng điều kiện trong catalog, 20 câu trong số đó trả về rỗng đúng. 5 câu có máy đúng nhưng top 4 không trúng.
- Recall@4 vẫn tính trên 4 máy khách nhìn thấy. Recall@10 và Recall@20 đo thêm trên danh sách xếp hạng dài hơn, không đổi số thẻ trên giao diện.
- Câu MacBook tầm hoặc dưới một mức giá để học AI vẫn chấm requirement satisfaction: máy dưới ngân sách đứng trước, Air đứng sau và bị ghi là không quá phù hợp.
- Hợp đồng form, khi eval tự gọi với số lượng 999, kẹp còn 5 và buổi nhận không phải màu.
- Không có lượt nào tạo đơn, sửa tồn hoặc đọc đơn của user khác.
