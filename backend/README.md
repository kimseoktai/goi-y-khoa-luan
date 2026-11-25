# Backend API (Phase 12)

Lớp API mỏng bên trên `ml/`. Backend chỉ ĐỌC dữ liệu đã xử lý và gọi lại code ML (matching, novelty, recommendation); không huấn luyện, không sửa dữ liệu gốc.

## Chạy (PowerShell, đã bật .venv, đứng ở thư mục rec)
```
pip install -r requirements-backend.txt
uvicorn backend.main:create_app --factory --reload
```
Mở http://127.0.0.1:8000/docs để xem và thử các endpoint.

Biến môi trường (tùy chọn): `REC_ROOT`, `REC_EMBEDDING_MODEL` (mặc định intfloat/multilingual-e5-base), `REC_EMBEDDING_BACKEND` (st|hash),
`REC_CORS_ORIGINS` (phân tách bằng dấu phẩy), `REC_LOG_LEVEL`.

## Cấu trúc
- `routes/`: endpoint FastAPI (chỉ nhận tham số, gọi service, trả JSON).
- `services/`: nghiệp vụ (catalog, matching, novelty, recommendation), dùng lại `ml/`.
- `database/store.py`: nạp CSV/JSON một lần, embedding nạp lười. Chưa có CSDL quan hệ.
- `errors.py`, `settings.py`, `main.py`: lỗi → mã HTTP (400/404/503/500), cấu hình, khởi tạo app.

## Endpoint
| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| GET | /health, /meta/versions | Trạng thái dữ liệu; phiên bản taxonomy/mô hình/trọng số/ngưỡng |
| GET | /taxonomy/topics, /taxonomy/domains | Taxonomy từ repository (lọc `status`) |
| GET | /jobs, /jobs/{id} | Danh sách (q, topic, domain, phân trang) và chi tiết kèm bằng chứng nhãn |
| GET | /thesis, /thesis/{id} | Danh sách (q, topic, domain, year) và chi tiết |
| GET | /thesis/{id}/similar | Thesis tương tự (embedding) |
| GET | /thesis/{id}/novelty | Novelty của một Thesis so với phần còn lại của kho |
| GET | /market/summary, /market/{table} | Nhu cầu thị trường, cung–cầu (có CI và cờ đủ bằng chứng) |
| GET | /matching/jobs/{id} | Top Thesis cho Job (tùy chọn w_topic, w_domain, w_semantic) |
| POST | /novelty/check | Body: title, topics, domains, top_k → Novel/Similar/Duplicate |
| GET | /recommendations/jobs/{id} | Top Thesis Direction kèm giải thích (top_k, mmr, novelty_mode, w_*) |

## Lưu ý
- Endpoint cần embedding trả 503 kèm hướng dẫn nếu chưa có file embedding. `use_semantic=false` cho matching sơ bộ không cần embedding.
- Yêu cầu `/novelty/check` đầu tiên nạp mô hình embedding nên chậm (vài giây đến hơn chục giây); các yêu cầu sau nhanh.
- Chưa có xác thực người dùng và chưa có giới hạn tốc độ; chỉ chạy nội bộ/phát triển cho đến khi thêm.
- Trọng số mặc định và ngưỡng novelty là điểm khởi đầu đã hiệu chỉnh trên mẫu nhỏ, không phải giá trị tối ưu; response có trường `note` nhắc điều này.
