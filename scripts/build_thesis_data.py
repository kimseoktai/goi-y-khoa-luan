"""Làm sạch khóa luận trong CSDL -> dựng embedding -> gắn nhãn (bộ phân loại hiện hành) -> cập nhật thesis_processed.csv cho website.
Không có thay đổi so với lần dựng trước thì bỏ qua (nhanh). Dữ liệu cũ được sao lưu trước khi ghi.

    python scripts\\build_thesis_data.py
    python scripts\\build_thesis_data.py --force               # dựng lại dù không có thay đổi
    python scripts\\build_thesis_data.py --skip-embeddings     # chỉ làm sạch + xuất CSV (kiểm tra nhanh, không gắn nhãn)
Gắn nhãn dùng mô hình đã huấn luyện (mặc định v1.2); KHÔNG huấn luyện lại (xem scripts\\thesis_retrain_check.py).
"""
import argparse, hashlib, json, shutil, subprocess, sys, time
from datetime import datetime
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                      # noqa: E402
from ml.embedding.embedder import model_tag     # noqa: E402
from ml.jobsdb import db as jobsdb              # noqa: E402
from ml.thesisdb import admin, db, clean        # noqa: E402

ROOT = C.ROOT
TD = ROOT / "data/processed/thesis"
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(jobsdb.DB_PATH))
ap.add_argument("--out-csv", default=str(TD / "thesis_db_clean.csv"))
ap.add_argument("--force", action="store_true")
ap.add_argument("--skip-embeddings", action="store_true")
ap.add_argument("--embedding-model", default=C.DEFAULT_EMBED_MODEL)
ap.add_argument("--topic-version", default="v1.2"); ap.add_argument("--domain-version", default="v1.2")
a = ap.parse_args()


def step(title, args):
    print(f"\n=== {title}", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable] + [str(x) for x in args], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"LỖI ở bước '{title}' (mã {r.returncode}); dừng, dữ liệu website cũ giữ nguyên.")
    print(f"    ({time.time() - t0:.0f}s)", flush=True)


con = db.connect(a.db)
st = clean.run(con)
print(f"Làm sạch: {st['total']} khóa luận trong CSDL, hợp lệ {st['valid']}, không hợp lệ {st['invalid']}, bản trùng {st['dup']}")
n = db.export_csv(con, a.out_csv)
closed = con.execute("SELECT COUNT(*) FROM thesis_raw WHERE status='closed'").fetchone()[0]
print(f"Xuất {n} khóa luận đang hiệu lực -> {a.out_csv} (đã đóng, không xuất: {closed})")
if n == 0:
    sys.exit("CSDL khóa luận trống hoặc không có khóa luận hợp lệ; dừng để không ghi đè dữ liệu website. Chạy scripts\\import_thesis_to_db.py trước.")
df = pd.read_csv(a.out_csv, encoding="utf-8-sig")
ov = admin.overrides(con)
sig = hashlib.sha1(("\n".join(f"{r.thesis_id}|{r.title}|{r.year}|{r.source}|{r.report_url}|{r.source_code_url}|{r.advisors}" for r in df.itertuples())
                    + "\n#labels\n" + json.dumps(sorted(ov.items()), ensure_ascii=False)).encode("utf-8")).hexdigest()
state_f = TD / ".thesis_build_state.json"
state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else {}
if a.skip_embeddings:
    sys.exit(0)
if state.get("sig") == sig and not a.force:
    state_f.write_text(json.dumps({**state, "built_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")   # thao tác quản trị không làm đổi dữ liệu thì cũng coi như đã áp
    print("Không có thay đổi so với lần dựng trước; bỏ qua (dùng --force để dựng lại).")
    sys.exit(0)

out = TD / "thesis_processed.csv"
prev_ids = set(pd.read_csv(out, encoding="utf-8-sig").thesis_id) if out.exists() else set()
tag = model_tag(a.embedding_model)
bk = TD / f"backup_{datetime.now():%Y%m%d_%H%M%S}"
files = [out, C.EMBED_DIR / f"thesis_{tag}.npy", C.EMBED_DIR / f"thesis_{tag}_index.csv"]
if any(f.exists() for f in files):
    bk.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.exists():
            shutil.copy2(f, bk / f.name)
    print(f"Đã sao lưu dữ liệu cũ vào {bk}")
step("Embedding khóa luận", [ROOT / "ml/embedding/build_embeddings.py", "--model", a.embedding_model, "--thesis", a.out_csv, "--only", "thesis"])
step("Gắn nhãn khóa luận", [ROOT / "scripts/process_thesis.py", "--thesis", a.out_csv, "--topic-version", a.topic_version, "--domain-version", a.domain_version,
                           "--embedding-model", a.embedding_model, "--out", out])
if ov:                                       # nhãn do người chỉnh tay thắng nhãn của mô hình
    p = pd.read_csv(out, encoding="utf-8-sig")
    hit = p.thesis_id.isin(ov.keys())
    for i in p.index[hit]:
        topics, doms = ov[int(p.at[i, "thesis_id"])]
        p.at[i, "technical_topics"] = json.dumps(topics, ensure_ascii=False)
        p.at[i, "technical_topic_scores"] = json.dumps({t: 1.0 for t in topics}, ensure_ascii=False)
        p.at[i, "domains"] = json.dumps(doms, ensure_ascii=False)
        p.at[i, "domain_scores"] = json.dumps({d: 1.0 for d in doms}, ensure_ascii=False)
        p.at[i, "topic_confidence"] = 1.0 if topics else p.at[i, "topic_confidence"]
        p.at[i, "domain_confidence"] = 1.0 if doms else p.at[i, "domain_confidence"]
        p.at[i, "review_flag"] = None
        p.at[i, "label_source"] = "manual"
    p.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Áp {int(hit.sum())} nhãn chỉnh tay (admin).")
new_ids = sorted(set(pd.read_csv(out, encoding="utf-8-sig").thesis_id) - prev_ids)
state_f.write_text(json.dumps(dict(sig=sig, built_at=datetime.now().isoformat(timespec="seconds"), n=n), ensure_ascii=False), encoding="utf-8")
print(f"\nXong: {n} khóa luận, mới gắn nhãn {len(new_ids)}. Khởi động lại máy chủ (hoặc bấm 'Nạp lại dữ liệu' ở trang quản trị) để website dùng dữ liệu mới.")
