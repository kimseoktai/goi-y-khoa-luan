"""Nhập khóa luận hiện có (CSV) vào CSDL, giữ NGUYÊN thesis_id (khớp embedding, Gold và nhãn đã duyệt). Chạy lại được, không tạo bản trùng.

    python scripts\\import_thesis_to_db.py
    python scripts\\import_thesis_to_db.py --csv data\\processed\\thesis\\thesis_clean.csv
Sau đó chạy scripts\\crawl_neu_thesis.py: các khóa luận NEU đã có sẽ được nhận (gắn mã nguồn thật) thay vì tạo bản trùng.
"""
import argparse, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                      # noqa: E402
from ml.jobsdb import db as jobsdb              # noqa: E402
from ml.thesisdb import db                      # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--csv", default=None, help="mặc định: thesis_clean.csv, nếu không có thì thesis_processed.csv")
ap.add_argument("--db", default=str(jobsdb.DB_PATH))
a = ap.parse_args()
src = Path(a.csv) if a.csv else next((p for p in (C.THESIS, C.ROOT / "data/processed/thesis/thesis_processed.csv") if p.exists()), None)
if src is None or not src.exists():
    sys.exit("không thấy tệp khóa luận; dùng --csv")
df = pd.read_csv(src, encoding="utf-8-sig")
need = {"thesis_id", "title", "source"}
if not need <= set(df.columns):
    sys.exit(f"{src.name} thiếu cột: {sorted(need - set(df.columns))}")
con = db.connect(a.db)
rows = [dict(thesis_id=int(r.thesis_id), title=r.title, year=getattr(r, "year", None), source=r.source) for r in df.itertuples()]
n = db.import_legacy(con, rows)
total = con.execute("SELECT COUNT(*) FROM thesis_raw").fetchone()[0]
print(f"Đã nhập {n} khóa luận mới từ {src.name} ({len(df)} dòng); tổng trong CSDL: {total}.")
if n < len(df):
    print(f"  {len(df) - n} dòng đã có từ trước nên bỏ qua.")
