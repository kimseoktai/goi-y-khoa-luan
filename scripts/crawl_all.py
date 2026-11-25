"""Chạy lần lượt cả ba nguồn (TopDev -> ITviec -> CareerViet) rồi làm sạch + gán nhãn + cập nhật dữ liệu website. Dùng cho crawl định kỳ hằng tuần.

    python scripts\\crawl_all.py                # chạy đầy đủ
    python scripts\\crawl_all.py --make-bat     # tạo scripts\\run_crawl_all.bat (dùng cho Task Scheduler, ghi sẵn đường dẫn Python đang dùng)
    python scripts\\crawl_all.py --skip itviec  # bỏ qua một nguồn (lặp lại để bỏ nhiều nguồn)

Một nguồn lỗi không làm dừng các nguồn còn lại. Nhật ký ghi ở logs\\crawl_all_<ngày>.log. Mã thoát 0 khi tất cả thành công.
"""
import argparse, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [("topdev", "crawl_topdev.py"), ("itviec", "crawl_itviec.py"), ("careerviet", "crawl_careerviet.py"), ("neu_thesis", "crawl_neu_thesis.py"), ("thesis", "build_thesis_data.py"), ("site", "build_site_data.py")]

ap = argparse.ArgumentParser()
ap.add_argument("--skip", action="append", default=[], choices=[s for s, _ in STEPS])
ap.add_argument("--make-bat", action="store_true")
a = ap.parse_args()

if a.make_bat:
    bat = ROOT / "scripts" / "run_crawl_all.bat"
    bat.write_text(f'@echo off\r\ncd /d "{ROOT}"\r\n"{sys.executable}" scripts\\crawl_all.py\r\n', encoding="ascii", errors="replace")
    print(f"Đã tạo {bat}")
    sys.exit(0)

log_path = ROOT / "logs" / f"crawl_all_{datetime.now():%Y-%m-%d}.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
failed = []
with open(log_path, "a", encoding="utf-8") as log:
    def say(msg):
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        print(line, flush=True)
        log.write(line + "\n"); log.flush()
    say(f"=== Bắt đầu crawl định kỳ ({datetime.now():%Y-%m-%d}) ===")
    for name, script in STEPS:
        if name in a.skip:
            say(f"- bỏ qua {name}")
            continue
        if name == "site" and failed:
            say("- vẫn cập nhật dữ liệu website bằng dữ liệu hiện có")
        say(f"- {name}: bắt đầu")
        t0 = time.time()
        p = subprocess.Popen([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        tail = []
        for line in p.stdout:
            log.write("    " + line); log.flush()
            tail.append(line.rstrip())
            tail = tail[-4:]
        code = p.wait()
        status = "xong" if code == 0 else f"LỖI (mã {code})"
        say(f"- {name}: {status} sau {(time.time() - t0) / 60:.1f} phút. " + (" | ".join(x for x in tail if x.startswith(('Xong', 'Xong'))) or ""))
        if code != 0:
            failed.append(name)
            say("    " + " / ".join(tail))
    say("=== Kết thúc: " + ("tất cả thành công" if not failed else f"có lỗi ở: {', '.join(failed)}") + " ===")
sys.exit(1 if failed else 0)
