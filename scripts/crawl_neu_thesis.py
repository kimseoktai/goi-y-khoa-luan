"""Crawl danh sách khóa luận NEU (fit.neu.edu.vn/theses) vào CSDL: thêm khóa luận mới, đóng khóa luận không còn trên trang, lưu đường dẫn file báo cáo.
Chỉ 1 yêu cầu tới /theses (được phép theo robots.txt); không gọi /api/, không tải PDF.

    python scripts\\crawl_neu_thesis.py                     # tải trang và cập nhật
    python scripts\\crawl_neu_thesis.py --html trang.html   # đọc từ tệp HTML đã lưu (không cần mạng)
Chạy scripts\\import_thesis_to_db.py MỘT LẦN trước (nhập 1.431 khóa luận có sẵn) để khóa luận cũ không bị tạo bản trùng.
"""
import argparse, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.jobsdb import db as jobsdb              # noqa: E402
from ml.thesisdb import db, neu                 # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(jobsdb.DB_PATH))
ap.add_argument("--html", default=None)
a = ap.parse_args()
con = db.connect(a.db)
if con.execute("SELECT COUNT(*) FROM thesis_raw").fetchone()[0] == 0:
    # Bảng trống mà crawl thì mã thesis_id sẽ đánh lại từ 1, lệch embedding, Gold và nhãn đã duyệt -> từ chối.
    sys.exit("Bảng khóa luận đang trống. Chạy scripts\\import_thesis_to_db.py MỘT LẦN trước (giữ thesis_id và nhãn đã duyệt), rồi chạy lại lệnh này.")
html = Path(a.html).read_text(encoding="utf-8", errors="replace") if a.html else None
r = neu.crawl(con, html=html, today=str(date.today()))
print(f"Xong: thấy {r['seen']} khóa luận, mới {r['new']}, đổi tiêu đề {r['title_changed']}, vừa đóng {r['closed']}. "
      + ("Danh sách đầy đủ." if r["complete"] else f"CHƯA đủ ({r['note']})."))
if r["new"] or r["closed"]:
    print("Có thay đổi: chạy scripts\\build_thesis_data.py để gắn nhãn khóa luận mới và dựng lại dữ liệu website.")
