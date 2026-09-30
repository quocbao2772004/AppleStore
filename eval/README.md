# Đánh giá

Eval chia hai mục. Mỗi mục một lệnh, một báo cáo, không gọi API và không ghi database.

## Eval khách

Trợ lý bán hàng. 500 câu về tìm máy, xem thông số, gợi ý, so sánh, tồn kho, đơn của khách, đặt hàng và từ chối.

```bash
.venv/bin/python eval/client/evaluate.py
```

Lần đang lưu nằm ở `eval/client/report.md`. Baseline trước khi sửa schema nằm ở `eval/client/baseline/`. Chạy lại chỉ ghi đè file trong `eval/client/`, không đụng baseline và không đụng eval admin.

| Metric | Baseline | Sau router |
| --- | ---: | ---: |
| Intent accuracy | 58.0 | 100.0 |
| Tool selection accuracy | 49.6 | 100.0 |
| Precision@4 | 63.5 | 96.0 |
| Recall@4 | 10.4 | 27.0 |
| Recall@10 | — | 42.0 |
| Recall@20 | — | 58.7 |
| Hit@4 | 63.5 | 96.0 |
| Task success | 50.2 | 87.2 |
| Requirement satisfaction | 91.2 | 91.2 |
| Unauthorized action rate | 0.0 | 0.0 |

Cách chấm và ba cột đầy đủ (baseline, sau schema, sau router) nằm ở `eval/client/README.md`.

## Eval admin

Trợ lý quản trị. 84 câu về tổng quan, bán chạy, tồn kho, đơn, hàng chờ duyệt, và câu đòi xóa hoặc sửa dữ liệu.

```bash
.venv/bin/python eval/admin/evaluate.py
```

Báo cáo: `eval/admin/report.md`. Router chấm là `local_calls`. Không gọi model.

| Metric | Giá trị |
| --- | ---: |
| Intent accuracy | 86.9 |
| Argument accuracy | 87.4 |
| Exact argument match | 86.7 |
| Tool selection accuracy | 81.0 |
| Task success | 81.0 |
| Unauthorized action rate | 0.0 |

Tổng quan, bán chạy và hàng chờ đều 100. Phần còn thiếu là router: `máy tính` chưa được hiểu là laptop, `còn hàng không` chưa thành tra tồn kho, `hết hàng và sắp hết` chỉ trả một báo cáo, `đơn số 3` chưa tách được mã. Tám câu xóa hoặc sửa dữ liệu vẫn rơi vào tool đọc, nên task nhóm safety là 0, nhưng không câu nào ghi database.

Hai bộ không dùng chung một số. Khách đo tư vấn sản phẩm. Admin đo báo cáo cửa hàng.
