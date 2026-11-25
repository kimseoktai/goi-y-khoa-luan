"""Nạp giảng viên hướng dẫn từ file CSV (cột: title,advisor) khi trang NEU không cung cấp.

Khớp theo tiêu đề (cùng cách chuẩn hóa như khi nhập khóa luận). Nhiều giảng viên cách nhau dấu ';'.
Dùng: python scripts/import_advisors.py advisors.csv [--db data/db/jobs.sqlite]
Sau đó: python scripts/build_thesis_data.py
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.thesisdb import advisors as adv, db   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    con = db.connect(a.db)
    by_key = {}
    for r in con.execute("SELECT thesis_id, title FROM thesis_raw"):
        by_key.setdefault(db.title_key(r["title"]), []).append(r["thesis_id"])
    ok = miss = 0
    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            names = adv.split_names(row.get("advisor"))
            ids = by_key.get(db.title_key(row.get("title") or ""))
            if not ids or not names:
                miss += 1
                continue
            for tid in ids:
                db.set_advisors(con, tid, names)
            ok += 1
    con.commit()
    print(f"Đã gắn giảng viên cho {ok} khóa luận; {miss} dòng không khớp tiêu đề hoặc không có tên.")


if __name__ == "__main__":
    main()
