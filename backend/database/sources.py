"""Chọn nguồn dữ liệu Jobs cho backend (chỉ xử lý đường dẫn, không nạp dữ liệu):

  csv  : data/processed/jobs/jobs_processed.csv (bộ 520 tin cũ) + data/processed/market + embedding "jobs"
  db   : jobs_processed_db.csv + market_db + embedding "jobs_db"  (tạo từ CSDL tin tuyển dụng bằng scripts/build_site_data.py)
  auto : dùng db nếu đủ file, ngược lại dùng csv (mặc định)

Jobs của CSDL có job_id riêng (trùng dải số với bộ cũ) nên embedding phải tách tên ("jobs_db"), tránh ghép nhầm vector của tin khác.
"""
from pathlib import Path

CSV_JOBS = "data/processed/jobs/jobs_processed.csv"
DB_JOBS = "data/processed/jobs/jobs_processed_db.csv"
CSV_MARKET = "data/processed/market"
DB_MARKET = "data/processed/market_db"
SOURCES = ("auto", "csv", "db")


def resolve_jobs(root, source="auto"):
    source = (source or "auto").strip().lower()
    if source not in SOURCES:
        raise ValueError(f"REC_JOBS_SOURCE phải là một trong {SOURCES}, nhận '{source}'")
    root = Path(root)
    db_ok = (root / DB_JOBS).exists() and (root / DB_MARKET / "market_summary.json").exists()
    if source == "db" and not db_ok:
        raise FileNotFoundError(f"chưa có dữ liệu Jobs từ CSDL ({DB_JOBS} và {DB_MARKET}); chạy: python scripts/build_site_data.py")
    use_db = source == "db" or (source == "auto" and db_ok)
    return dict(source="db" if use_db else "csv",
                jobs_path=root / (DB_JOBS if use_db else CSV_JOBS),
                market_dir=root / (DB_MARKET if use_db else CSV_MARKET),
                embed_name="jobs_db" if use_db else "jobs")
