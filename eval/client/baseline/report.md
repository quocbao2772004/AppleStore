# Đánh giá offline trợ lý Form

Lần chạy này không gọi API và không tạo đơn. Tool lý tưởng là tool đáng có cho câu đó. Router offline chỉ chọn `search_products` hoặc `list_orders`.

Số case: **500**.

| Metric | Giá trị |
| --- | --- |
| Intent accuracy | 58.0 |
| Argument accuracy | 92.9 |
| Exact argument match | 80.5 |
| Tool selection accuracy | 49.6 |
| Precision@4 | 63.5 |
| Recall@4 | 10.4 |
| MRR | 0.635 |
| Hit@4 | 63.5 |
| Requirement satisfaction | 91.2 |
| Task success | 50.2 |
| Unauthorized action rate | 0.0 |

Độ trễ search trung bình: 4.8 ms. Chi phí API: không đo, vì lượt này không gọi model.

Recall@4 là độ phủ trên toàn bộ máy đúng điều kiện. Tool chỉ trả tối đa 4 thẻ, nên recall thấp khi tập đúng lớn. Precision@4, Hit@4 và MRR nói chất lượng thứ hạng.

## Theo nhóm

| Nhóm | Case | Intent | Argument | Tool | Task |
| --- | ---: | ---: | ---: | ---: | ---: |
| product_search | 150 | 98.7 | 94.5 | 100.0 | 53.3 |
| product_detail | 80 | 55.0 | 86.7 | 0.0 | 30.0 |
| comparison | 60 | 0.0 | None | 0.0 | 0.0 |
| recommendation | 70 | 100.0 | 100.0 | 100.0 | 91.4 |
| inventory | 50 | 0.0 | 80.0 | 0.0 | 70.0 |
| order_tracking | 40 | 70.0 | 0.0 | 70.0 | 70.0 |
| checkout | 30 | 0.0 | None | 0.0 | 0.0 |
| safety | 20 | 0.0 | None | 0.0 | 100.0 |

## Theo field

| Field | Đúng |
| --- | ---: |
| category | 87.7 |
| brand | 97.5 |
| use | 100.0 |
| price_max | 100.0 |
| price_target | 100.0 |
| ram_gb | 79.3 |
| min_ram | 0.0 |
| storage_gb | 0.0 |
| line | 90.9 |
| chip | 100.0 |
| screen | 100.0 |
| color | 100.0 |
| specific | 79.5 |
| priorities | 100.0 |
| order_id | 0.0 |

## Việc bộ này cho thấy

- Intent của router offline chỉ có product_search, product_detail khi câu chứa RAM/màn hình/chip, recommendation khi học AI hoặc tầm giá, và order_tracking khi câu khớp mẫu đơn hàng.
- So sánh, tồn kho, đặt hàng và câu tấn công chưa có intent riêng, nên các nhóm đó kéo intent accuracy xuống.
- Tool offline không có compare_products, check_inventory, prepare_checkout hay refuse. Những câu đó đang rơi vào search_products, trừ câu khớp mẫu đơn.
- 256GB đang bị đọc thành RAM và chữ Pro trên iPhone bị đọc thành dòng MacBook. Field storage_gb chưa có.
- Trong 29 câu iPhone có lọc giá, 29 câu không có iPhone nào trong top 4. Slot brand vẫn là Apple, nhưng tool đổi Apple thành điều kiện MacBook.
- Câu MacBook tầm hoặc dưới một mức giá để học AI được chấm ở requirement satisfaction: máy dưới ngân sách đứng trước, Air đứng sau và bị ghi là không quá phù hợp.
- prepare_checkout không được router gọi. Hợp đồng form, khi eval tự gọi với số lượng 999, kẹp còn 5 và buổi nhận không phải màu.
- Không có lượt nào tạo đơn, sửa tồn hoặc đọc đơn của user khác.
