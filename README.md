# rec - Gợi ý đề tài khóa luận từ nhu cầu tuyển dụng IT

## Dữ liệu Jobs từ CSDL
Tin tuyển dụng (TopDev, ITviec, CareerViet) nằm trong `data/db/jobs.sqlite`. Tin hết hạn được giữ lại với trạng thái `closed`.

Cập nhật hàng tuần (PowerShell, trong thư mục dự án):

    python scripts\crawl_all.py                      # crawl 3 nguồn rồi dựng dữ liệu cho website
    python scripts\build_site_data.py                # chỉ dựng lại dữ liệu website
    python scripts\build_site_data.py --embeddings   # thêm embedding cho Jobs (chậm, chỉ khi dữ liệu đổi nhiều)

Đặt lịch hàng tuần: `python scripts\crawl_all.py --make-bat` rồi tạo tác vụ bằng `schtasks` trỏ tới `scripts\run_crawl_all.bat`.

## Cài đặt

Yêu cầu Python 3.10 trở lên và kết nối Internet ở lần cài đầu. Trong thư mục dự án (PowerShell):

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements-backend.txt
    pip install -r requirements-embedding.txt

Lần cài đầu khá lâu vì có thư viện torch (vài trăm MB).

Lưu ý khi chạy:
- Mô hình vector nhúng multilingual-e5-base không kèm trong gói nộp (khoảng 1,1 GB); lần đầu dùng so khớp hoặc đề xuất, thư viện sentence-transformers tự tải về `models/embeddings`, cần có mạng.
- Cơ sở dữ liệu tài khoản `data/db/accounts.sqlite` không kèm theo, được tạo tự động khi chạy. Nhập danh sách sinh viên bằng `python scripts\import_students.py`.
- Chức năng sinh tên đề tài cần khóa Gemini: `$env:GEMINI_API_KEY="khóa"` trước khi chạy máy chủ.

## Chạy website

    uvicorn backend.main:create_app --factory --reload     # cửa sổ 1
    cd frontend; python -m http.server 5173                # cửa sổ 2, mở http://localhost:5173

Sau khi chạy, kiểm tra máy chủ tại http://localhost:8000/health (trường `jobs_source` là `db`).

Nguồn Jobs: biến `REC_JOBS_SOURCE` = `auto` (mặc định) | `db` | `csv`. Kiểm tra ở `/health` (trường `jobs_source`). Quay lại bộ 520 tin cũ: `$env:REC_JOBS_SOURCE="csv"`.

## Kiểm thử

    pip install pytest
    python -m pytest -q

Chi tiết quy tắc gán nhãn và lịch sử thay đổi: `data/repository/CHANGELOG.md`.
