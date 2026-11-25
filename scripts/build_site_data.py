"""Tạo dữ liệu Jobs cho website từ CSDL tin tuyển dụng (làm sạch -> gán nhãn Phase 7 -> thống kê thị trường).

    python scripts\\build_site_data.py                # làm sạch + gán nhãn + thống kê (nhanh, không cần mạng)
    python scripts\\build_site_data.py --embeddings   # thêm embedding cho Jobs (cần sentence-transformers và mạng ở lần đầu)

Kết quả (backend tự dùng khi khởi động lại, REC_JOBS_SOURCE=auto):
    data\\processed\\jobs\\jobs_processed_db.csv, data\\processed\\market_db\\, [embedding jobs_db_*]
Bộ dữ liệu CSV cũ (jobs_processed.csv, market) KHÔNG bị thay đổi; muốn quay lại bộ cũ: đặt REC_JOBS_SOURCE=csv.
"""
import argparse, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
J = ROOT / "data/processed/jobs"

ap = argparse.ArgumentParser()
ap.add_argument("--db", default=None, help="đường dẫn jobs.sqlite (mặc định data/db/jobs.sqlite)")
ap.add_argument("--embeddings", action="store_true", help="tạo thêm embedding cho Jobs (tên jobs_db)")
ap.add_argument("--embedding-model", default=None)
a = ap.parse_args()


def run(title, args):
    print(f"\n=== {title}", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable] + [str(x) for x in args], cwd=ROOT)
    if r.returncode != 0:
        print(f"LỖI ở bước '{title}' (mã {r.returncode}); dừng, dữ liệu website cũ giữ nguyên.")
        sys.exit(r.returncode)
    print(f"    ({time.time() - t0:.0f}s)", flush=True)


db = ["--db", a.db] if a.db else []
run("1/3 Làm sạch dữ liệu từ CSDL", [S / "clean_jobs_db.py", "--export-csv", "--out", J / "jobs_db_clean.csv"] + db)
run("2/3 Gán nhãn Job (Phase 7)", [S / "process_jobs.py", "--jobs", J / "jobs_db_clean.csv", "--out", J / "jobs_processed_db.csv", "--summary", J / "jobs_label_summary_db.csv"])
run("3/3 Thống kê nhu cầu thị trường", [S / "analyze_market.py", "--jobs", J / "jobs_processed_db.csv", "--out-dir", ROOT / "data/processed/market_db"])
if a.embeddings:
    m = ["--model", a.embedding_model] if a.embedding_model else []
    run("Embedding cho Jobs", [ROOT / "ml/embedding/build_embeddings.py", "--jobs", J / "jobs_processed_db.csv", "--jobs-name", "jobs_db"] + m)
else:
    print("\n(Chưa tạo embedding cho Jobs: gợi ý đề tài vẫn chạy nhưng không có thành phần 'ngữ nghĩa' và 'tính mới' cho Job; chạy lại với --embeddings để bật.)")
import pandas as pd                                      # noqa: E402
n = len(pd.read_csv(J / "jobs_processed_db.csv", encoding="utf-8-sig"))
print(f"\nXong: {n} tin Jobs sẵn sàng cho website. Khởi động lại backend để nạp dữ liệu mới.")
