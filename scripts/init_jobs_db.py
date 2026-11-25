"""Tạo CSDL tin tuyển dụng và nhập jobs_clean.csv (chạy lại được, không tạo bản trùng).

  python scripts/init_jobs_db.py
  python scripts/init_jobs_db.py --csv data/processed/jobs/jobs_clean.csv --db data/db/jobs.sqlite
"""
import argparse, sys
from datetime import date
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                    # noqa: E402
from ml.jobsdb import db                                      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(C.ROOT / "data/processed/jobs/jobs_clean.csv"))
    ap.add_argument("--db", default=str(db.DB_PATH))
    a = ap.parse_args()
    df = pd.read_csv(a.csv, encoding="utf-8-sig").fillna("")
    con = db.connect(a.db)
    run = db.start_run(con, "import")
    new = 0
    for r in df.itertuples():
        _, is_new = db.upsert_job(con, r.url, skills=db.parse_skills(r.skills), title_raw=r.job_title, title_norm=r.job_title,
                                  company=r.company, description=r.description)
        new += is_new
    db.finish_run(con, run, n_seen=len(df), n_new=new, note=f"nhập từ {Path(a.csv).name}, first_seen={date.today()}")
    q = lambda s: con.execute(s).fetchone()[0]
    n_jobs, n_skills = q("SELECT COUNT(*) FROM jobs"), q("SELECT COUNT(*) FROM job_skills")
    n_active = q("SELECT COUNT(*) FROM jobs WHERE status='active'")
    print(f"Đã nhập {new} tin mới ({len(df)} dòng CSV). Tổng: {n_jobs} tin, {n_skills} dòng kỹ năng, {n_active} đang active.")
    for s, n in con.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source"):
        print(f"  {s}: {n}")
    print("DB:", a.db)


if __name__ == "__main__":
    main()
