"""Crawl ITviec và ghi vào CSDL data/db/jobs.sqlite (chạy hằng tuần). Không cần trình duyệt.

    python scripts\\crawl_itviec.py                    # lấy đủ danh sách, tải chi tiết cho tin mới / tin còn thiếu ngày đăng
    python scripts\\crawl_itviec.py --max-details 5    # chạy thử: chỉ đọc chi tiết 5 tin, KHÔNG đóng tin nào
Lần đầu sẽ đọc chi tiết cả ~400 tin cũ để bổ sung ngày đăng/hạn nộp (mất khoảng 20 đến 30 phút); các lần sau chỉ đọc tin mới.
"""
import argparse, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.jobsdb import db, htmlsites                               # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(db.DB_PATH))
ap.add_argument("--max-pages", type=int, default=60)
ap.add_argument("--max-details", type=int, default=None)
a = ap.parse_args()
con = db.connect(a.db)
r = htmlsites.crawl(con, htmlsites.ITviec, today=str(date.today()), max_pages=a.max_pages, max_details=a.max_details)
print(f"\nXong: {r['listed']} tin trong danh sách, thấy {r['seen']}, mới {r['new']}, đọc chi tiết {r['fetched']}, vừa đóng {r['closed']}. "
      + ("Đã duyệt đủ danh sách." if r["complete"] else f"CHƯA đủ ({r['note']}), không đóng tin nào."))
for e in r["errors"][:5]:
    print("  lỗi:", e)
