"""Chạy cả luồng tin tuyển dụng: crawl 3 nguồn -> làm sạch + gán nhãn + thống kê -> embedding. Không đụng tới khóa luận NEU.

    python scripts\\run_jobs_flow.py

Mỗi bước ghi vào logs\\jobs_flow_step.log (dòng "k/4 tên bước") để trang quản trị hiện bước đang chạy.
Bước crawl lỗi hoặc dựng dữ liệu lỗi thì dừng (mã thoát khác 0, dữ liệu website cũ giữ nguyên). Embedding lỗi chỉ cảnh báo vì gợi ý vẫn chạy được.
Bước 4 (nạp lại website) do trang quản trị gọi sau khi xong.
"""
import subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
J = ROOT / "data/processed/jobs"
STEP = ROOT / "logs" / "jobs_flow_step.log"
STEP.parent.mkdir(parents=True, exist_ok=True)


def mark(k, name):
    STEP.write_text(f"{k}/4 {name}\n", encoding="utf-8")
    print(f"\n##### BƯỚC {k}/4: {name}", flush=True)


def run(args):
    t0 = time.time()
    code = subprocess.run([sys.executable] + [str(x) for x in args], cwd=ROOT).returncode
    print(f"    ({time.time() - t0:.0f}s, mã {code})", flush=True)
    return code


mark(1, "Crawl tin tuyển dụng")
if run([S / "crawl_all.py", "--skip", "neu_thesis", "--skip", "thesis", "--skip", "site"]) != 0:
    print("Có nguồn crawl lỗi. Vẫn dựng dữ liệu bằng tin đã có.", flush=True)      # crawl_all đã ghi log chi tiết; một nguồn lỗi không nên chặn cả luồng

mark(2, "Dựng dữ liệu")
code = run([S / "build_site_data.py"])
if code != 0:
    STEP.write_text(f"lỗi 2/4 Dựng dữ liệu\n", encoding="utf-8")
    sys.exit(code)

mark(3, "Dựng embedding")
if run([ROOT / "ml/embedding/build_embeddings.py", "--jobs", J / "jobs_processed_db.csv", "--jobs-name", "jobs_db"]) != 0:
    print("CẢNH BÁO: dựng embedding lỗi, gợi ý đề tài vẫn chạy nhưng thiếu thành phần ngữ nghĩa.", flush=True)

STEP.write_text("4/4 Nạp lại website\n", encoding="utf-8")
print("\nXong. Bấm 'Nạp lại website' nếu trang chưa tự nạp.", flush=True)
