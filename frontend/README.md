# Frontend (Phase 13)

Giao diện web thuần HTML + JavaScript (ES modules), **không cần npm, không cần build**. Chỉ gọi API của backend; không chứa logic ML.

## Chạy (PowerShell, trong `C:\Users\anhta\rec`)

Cửa sổ 1, backend:

    .\.venv\Scripts\Activate.ps1
    uvicorn backend.main:create_app --factory --reload

Cửa sổ 2, giao diện (cổng 5173 nằm sẵn trong danh sách CORS của backend):

    cd frontend
    python -m http.server 5173

Mở http://localhost:5173. Nếu API ở địa chỉ khác, mở `http://localhost:5173/?api=http://địa-chỉ:cổng` (địa chỉ được nhớ trong trình duyệt).

## Cấu trúc

| File | Việc |
|---|---|
| `index.html`, `styles.css` | khung trang và kiểu dáng |
| `js/app.js` | điều hướng theo `#/đường-dẫn`, thanh bên, hiển thị phiên bản |
| `js/api.js` | gọi API, dịch lỗi (0/404/503/400/422/500) sang tiếng Việt kèm cách xử lý |
| `js/labels.js` | nhãn tiếng Việt cho giá trị kỹ thuật (Novel→Mới, Similar→Khá giống, Duplicate→Trùng, tên tiêu chí, mức thiếu) |
| `js/ui.js`, `js/dom.js` | thành phần dùng chung; dựng DOM bằng `textContent`, không dùng `innerHTML` vì dữ liệu crawl không đáng tin |
| `js/pages/*.js` | 5 màn: Tổng quan, Gợi ý đề tài theo job, Kiểm tra đề tài có trùng không, Job so với luận văn, Kho luận văn |

## Điều cần biết

- Các màn cần embedding (kiểm tra trùng, "Ít người làm", so luận văn) trả 503 khi chưa chạy `scripts/build_embeddings.py`; giao diện nói rõ cách xử lý, các phần còn lại vẫn dùng được.
- Chưa có biểu đồ xu hướng theo thời gian vì dữ liệu job chưa có ngày đăng; sẽ thêm khi crawler thu được ngày.
- Nhóm công việc nhỏ (dưới ngưỡng 10 tin và 3 công ty) được gộp vào nhóm khác theo `data/repository/role_groups.csv` (bạn sửa file này được). Khi một nhóm đang gộp đạt ngưỡng, nó hiện ở trang **Quản trị** kèm huy hiệu số lượng; admin chọn "Duyệt, tách riêng" hoặc "Từ chối, giữ gộp".
- Trang Quản trị cần mã: đặt `$env:REC_ADMIN_TOKEN="mã-của-bạn"` trước khi chạy uvicorn. Chưa đặt thì các route `/admin/*` trả 403 (tắt hẳn). Không có tài khoản người dùng, chỉ dùng nội bộ.
- Nút **Gợi ý tên đề tài** ở trang Gợi ý đề tài gọi Gemini: đặt `$env:GEMINI_API_KEY="khóa"` trước khi chạy backend (nội dung prompt được gửi tới Google; đổi mô hình bằng `REC_GEMINI_MODEL`, thời gian chờ bằng `REC_LLM_TIMEOUT`). Mô hình chỉ viết tên đề tài; chủ đề, công nghệ, đề tài liên quan và mức trùng lấy từ dữ liệu của hệ thống. Chưa đặt khóa thì chỉ nút này báo lỗi, phần còn lại vẫn dùng được.
- Không có đăng nhập hay giới hạn tốc độ; chỉ chạy nội bộ.
