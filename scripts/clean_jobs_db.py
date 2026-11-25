"""Chạy tầng sạch trên CSDL tin tuyển dụng và in báo cáo kiểm tra. Không sửa dữ liệu raw.

    python scripts\\clean_jobs_db.py                    # xây lại bảng sạch + báo cáo
    python scripts\\clean_jobs_db.py --export-csv       # thêm: xuất data\\processed\\jobs\\jobs_db_clean.csv (đầu vào Phase 7)
    python scripts\\clean_jobs_db.py --all-status        # xuất cả tin đã đóng (mặc định chỉ tin đang tuyển)
Chạy khi crawler còn đang chạy cũng được (đọc xong mới ghi một lần).
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                           # noqa: E402
from ml.jobsdb import db, clean                                      # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(db.DB_PATH))
ap.add_argument("--export-csv", action="store_true")
ap.add_argument("--out", default=str(C.ROOT / "data/processed/jobs/jobs_db_clean.csv"))
ap.add_argument("--all-status", action="store_true")
a = ap.parse_args()

con = db.connect(a.db)
st = clean.run(con)
print(f"Đã làm sạch {st['jobs']} tin: CNTT {st['it']}, loại (không phải CNTT/không rõ) {st['non_it']}, bản trùng giữa các nguồn {st['dup']}, chưa rõ vai trò {st['no_role']}\n")

print("Theo nguồn (CNTT / tổng):")
for r in con.execute("SELECT j.source, SUM(c.is_it) it, COUNT(*) n, SUM(c.is_it AND c.dup_of IS NULL) uniq FROM jobs j JOIN jobs_clean c USING(job_id) GROUP BY 1"):
    print(f"  {r['source']:<11}{r['it']:>5} / {r['n']:<5} (không trùng: {r['uniq']})")
print("\nVai trò (tin CNTT, không trùng):")
for r in con.execute("SELECT role, COUNT(*) n FROM jobs_clean WHERE is_it=1 AND dup_of IS NULL GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {r['role'] or '(chưa rõ)':<30}{r['n']:>5}")
print("\nKỹ năng: nguồn gốc")
for r in con.execute("SELECT origin, COUNT(*) n, COUNT(DISTINCT job_id) jobs FROM job_skills_clean GROUP BY 1"):
    print(f"  {r['origin']:<10}{r['n']:>6} lượt gán, {r['jobs']} tin")
print("\nTin KHÔNG phải CNTT bị loại (mẫu 15, kiểm tra xem có loại nhầm không):")
for r in con.execute("SELECT j.source, j.title_raw, c.reason FROM jobs j JOIN jobs_clean c USING(job_id) WHERE c.is_it=0 ORDER BY RANDOM() LIMIT 15"):
    print(f"  [{r['source'][:2]}] {r['title_raw'][:70]}  <- {r['reason']}")
print("\nTin CNTT nhưng chưa có vai trò (mẫu 15, cần thêm quy tắc vào data\\repository\\title_role_rules.csv):")
for r in con.execute("SELECT j.source, j.title_raw FROM jobs j JOIN jobs_clean c USING(job_id) WHERE c.is_it=1 AND c.role='' ORDER BY RANDOM() LIMIT 15"):
    print(f"  [{r['source'][:2]}] {r['title_raw'][:80]}")
print("\nThẻ kỹ năng chưa có trong skills.csv (20 thẻ phổ biến nhất, xem có nên thêm vào repository không):")
for r in con.execute("SELECT raw, n_jobs FROM skill_unmapped ORDER BY n_jobs DESC LIMIT 20"):
    print(f"  {r['raw']:<30}{r['n_jobs']:>4}")
if a.export_csv:
    n = clean.export_csv(con, a.out, only_active=not a.all_status)
    print(f"\nĐã xuất {n} tin ra {a.out}")
