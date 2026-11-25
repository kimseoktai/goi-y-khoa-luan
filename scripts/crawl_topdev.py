"""Crawl TopDev (qua API công khai, không cần trình duyệt) và ghi vào CSDL data/db/jobs.sqlite. Chạy hằng tuần.

    python scripts\\crawl_topdev.py                 # lấy các tin IT (13 nhóm ngành IT của TopDev)
    python scripts\\crawl_topdev.py --max-pages 1   # chạy thử 1 trang (100 tin), KHÔNG đóng tin nào
    python scripts\\crawl_topdev.py --prune-outside # chạy MỘT LẦN để xóa các tin TopDev ngoài phạm vi IT đã nạp nhầm trước đó
    python scripts\\crawl_topdev.py --all           # lấy toàn bộ TopDev (lẫn nhiều việc ngoài IT, không khuyến nghị)
Chỉ đóng tin hết hạn khi đã lấy đủ danh sách; chạy dở hoặc thiếu tin thì chỉ thêm/cập nhật.
"""
import argparse, json, random, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.jobsdb import db, topdev                                     # noqa: E402

PAGE_SIZE = 100          # API từ chối > 100 (lỗi 422)
HEAD = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://topdev.vn", "Referer": "https://topdev.vn/"}


def fetch(page, categories=""):
    params = {"locale": "en_US", "page": page, "page_size": PAGE_SIZE}
    if categories:
        params["job_categories_ids"] = categories
    q = urllib.parse.urlencode(params)
    url = f"{topdev.API}?{q}&fields[job]={urllib.parse.quote(topdev.FIELDS, safe=',')}"
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEAD), timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"Trang {page} lần {attempt} lỗi: {e}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"không tải được trang {page}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DB_PATH))
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--categories", default=topdev.IT_CATEGORIES, help="id nhóm ngành, cách nhau dấu phẩy (mặc định: 13 nhóm IT)")
    ap.add_argument("--all", action="store_true", help="bỏ lọc nhóm ngành, lấy toàn bộ TopDev")
    ap.add_argument("--prune-outside", action="store_true", help="sau khi duyệt đủ danh sách, xóa các tin TopDev trong DB không nằm trong danh sách này (dùng một lần)")
    a = ap.parse_args()
    con = db.connect(a.db)
    # dọn 3 tin do lần chạy thử bằng trình duyệt (mã tin kiểu chữ); tin API dùng mã số
    con.execute("DELETE FROM raw_pages WHERE source='topdev' AND source_job_id NOT GLOB '[0-9]*'")
    con.execute("DELETE FROM jobs WHERE source='topdev' AND source_job_id NOT GLOB '[0-9]*'")
    con.commit()

    today = str(date.today())
    run = db.start_run(con, topdev.SOURCE)
    seen, n_new, total, last_page, pages, note, complete, total_rows, errors = set(), 0, 0, 1, 0, None, False, 0, []
    try:
        page = 1
        while page <= min(last_page, a.max_pages):
            j = fetch(page, "" if a.all else a.categories)
            total, last_page = j["meta"]["total"], j["meta"]["last_page"]
            ids, new = topdev.ingest_items(con, j["data"], today=today, errors=errors)
            seen.update(ids); n_new += new; pages += 1; total_rows += len(j["data"])
            print(f"Trang {page}/{last_page}: {len(j['data'])} tin, +{new} mới (đến nay {len(seen)} tin khác nhau)")
            page += 1
            time.sleep(random.uniform(1, 2))
        complete = pages >= last_page and len(seen) > 0 and not errors   # meta.total tính trùng nên không dùng làm mốc; duyệt hết trang và không tin nào lỗi là đủ
        if not complete:
            note = f"chưa duyệt hết: {pages}/{last_page} trang, thấy {len(seen)} tin" if not errors else f"{len(errors)} tin bị lỗi, ví dụ: {errors[0]}"
        if errors:
            print(f"CẢNH BÁO: {len(errors)} tin bị bỏ qua. Ví dụ: {errors[:3]}")
    except KeyboardInterrupt:
        note = "bị dừng giữa chừng"
    except Exception as e:                                           # noqa: BLE001
        note = f"lỗi: {type(e).__name__}: {e}"
    pruned = 0
    if a.prune_outside:
        if complete and not a.all:
            pruned = db.prune_source(con, topdev.SOURCE, seen)
            print(f"Đã xóa {pruned} tin TopDev nằm ngoài phạm vi.")
        else:
            print("Bỏ qua --prune-outside vì chưa duyệt đủ danh sách (hoặc đang dùng --all).")
    closed = db.close_missing(con, run, topdev.SOURCE, seen, today=today) if complete else 0
    db.finish_run(con, run, n_seen=len(seen), n_new=n_new, ok=complete, note=note)
    print(f"\nXong: thấy {len(seen)} tin khác nhau ({total_rows} dòng, API báo total={total}), mới {n_new}, vừa đóng {closed}. "
          + ("Đã lấy đủ danh sách." if complete else f"CHƯA đủ ({note}), không đóng tin nào."))


if __name__ == "__main__":
    main()
