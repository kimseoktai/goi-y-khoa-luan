"""Kiểm tra có nên huấn luyện lại bộ phân loại khóa luận chưa, và tạo danh sách để bạn XÁC NHẬN nhãn của khóa luận mới.

Nguyên tắc: nhãn do mô hình dự đoán KHÔNG được dùng lại để huấn luyện (mô hình tự học lại lỗi của chính nó).
Chỉ nhãn do người xác nhận mới vào Gold. Quy trình:
  1) python scripts\\thesis_retrain_check.py                  # báo cáo + tạo data\\processed\\gold\\gold_review_new.csv
  2) Mở gold_review_new.csv, điền cột confirm_topics / confirm_domains (tên nhãn, phân tách bằng dấu |) cho khóa luận đã xem xét
  3) python scripts\\thesis_retrain_check.py --apply           # chuyển các dòng đã xác nhận sang gold_additions.csv
  4) Gộp vào Gold (ml\\labeling\\merge_annotations.py), huấn luyện bản mới (ml\\classification\\train.py), so với phiên bản hiện hành, chỉ thay khi tốt hơn.
"""
import argparse, json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                      # noqa: E402
from ml.jobsdb import db as jobsdb              # noqa: E402
from ml.thesisdb import admin, db                      # noqa: E402

G = C.ROOT / "data/processed/gold"
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(jobsdb.DB_PATH))
ap.add_argument("--min-new", type=int, default=50, help="số khóa luận mới đã xác nhận tối thiểu để cân nhắc huấn luyện lại")
ap.add_argument("--queue", default=str(G / "gold_review_new.csv"))
ap.add_argument("--additions", default=str(G / "gold_additions.csv"))
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()

topics = pd.read_csv(C.TOPICS, encoding="utf-8-sig"); domains = pd.read_csv(C.DOMAINS, encoding="utf-8-sig")
tnames, dnames = set(topics.topic_name), set(domains.domain_name)
qpath = Path(a.queue)
old = pd.read_csv(qpath, encoding="utf-8-sig", dtype=str).fillna("") if qpath.exists() else pd.DataFrame(columns=["thesis_id", "confirm_topics", "confirm_domains"])


def split(v):
    return [x.strip() for x in str(v or "").split("|") if x.strip()]


if a.apply:
    rows, bad = [], []
    for r in old.itertuples():
        for kind, names, col in (("technical_topic", tnames, r.confirm_topics), ("domain", dnames, r.confirm_domains)):
            for n in split(col):
                (rows if n in names else bad).append((r.thesis_id, kind, n))
    if bad:
        sys.exit("Nhãn không có trong taxonomy: " + "; ".join(f"thesis {t}: {n}" for t, _, n in bad[:10]))
    ap_ = Path(a.additions)
    cur = pd.read_csv(ap_, encoding="utf-8-sig", dtype=str) if ap_.exists() else pd.DataFrame(columns=["thesis_id", "label_type", "label_name", "note"])
    have = set(zip(cur.thesis_id.astype(str), cur.label_type, cur.label_name))
    add = [dict(thesis_id=t, label_type=k, label_name=n, note="người dùng xác nhận (thesis_retrain_check)") for t, k, n in rows if (str(t), k, n) not in have]
    pd.concat([cur, pd.DataFrame(add)], ignore_index=True).to_csv(ap_, index=False, encoding="utf-8-sig")
    print(f"Đã thêm {len(add)} nhãn xác nhận vào {ap_.name} ({len({r[0] for r in rows})} khóa luận). Bước tiếp: ml\\labeling\\merge_annotations.py rồi ml\\classification\\train.py.")
    sys.exit(0)

con = db.connect(a.db)
gold = pd.read_csv(C.GOLD, encoding="utf-8-sig")
gold_keys = set(gold.title.map(db.title_key))
new = pd.read_sql_query("SELECT thesis_id, title, source, first_seen FROM thesis_raw WHERE status='active' AND origin IN ('crawl','manual') ORDER BY thesis_id", con)
new = new[~new.title.map(db.title_key).isin(gold_keys)].copy()
proc_f = C.ROOT / "data/processed/thesis/thesis_processed.csv"
proc = pd.read_csv(proc_f, encoding="utf-8-sig").set_index("thesis_id") if proc_f.exists() else pd.DataFrame()
def pred(tid, col):
    if tid in proc.index and col in proc.columns:
        return "|".join(json.loads(proc.at[tid, col]))
    return ""
new["pred_topics"] = new.thesis_id.map(lambda t: pred(t, "technical_topics"))
new["pred_domains"] = new.thesis_id.map(lambda t: pred(t, "domains"))
new["topic_confidence"] = new.thesis_id.map(lambda t: proc.at[t, "topic_confidence"] if t in proc.index and "topic_confidence" in proc.columns else "")
keep = old.set_index("thesis_id")[["confirm_topics", "confirm_domains"]] if len(old) else None
ov = admin.overrides(con)             # nhãn người quản trị đã sửa tay trên website cũng là nhãn đã được người xác nhận
def prefill(t, c, k):
    cur = keep.at[str(t), c] if keep is not None and str(t) in keep.index else ""
    if cur or int(t) not in ov:
        return cur
    return "|".join(ov[int(t)][k])
for c, k in (("confirm_topics", 0), ("confirm_domains", 1)):
    new[c] = [prefill(t, c, k) for t in new.thesis_id]
new = new.sort_values("topic_confidence", key=lambda s: pd.to_numeric(s, errors="coerce"))   # ít chắc chắn trước
new.to_csv(qpath, index=False, encoding="utf-8-sig")
confirmed = int(((new.confirm_topics != "") | (new.confirm_domains != "")).sum())
hist = C.EVAL_DIR / "evaluation_history.csv"
last = pd.read_csv(hist).query("model_name == 'thesis_topic_clf'").training_date.max() if hist.exists() else "?"
print(f"Khóa luận thu thập sau thiết lập, đang hiệu lực, chưa có nhãn vàng: {len(new)}")
print(f"Đã xác nhận nhãn: {confirmed} (ngưỡng cân nhắc huấn luyện lại: {a.min_new}); lần huấn luyện gần nhất: {last}")
print(("ĐỦ ngưỡng: chạy lại với --apply rồi gộp vào Gold và huấn luyện bản mới." if confirmed >= a.min_new
       else f"Chưa đủ ({confirmed}/{a.min_new}); xác nhận thêm trong {qpath.name}.") + f"\nDanh sách: {qpath}")
