"""Tạo embedding cho Thesis, Gold, Job, Technical Topic, Domain và lưu vào data/processed/embeddings/.

Chạy MỘT LẦN trên máy có mạng (tải mô hình lần đầu):
    pip install sentence-transformers
    python ml/embedding/build_embeddings.py
Kết quả: cache_<model>.npz (dùng cho train/predict) + <tên>_<model>.npy/_index.csv + embedding_manifest.csv
"""
import argparse, json, logging, sys
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                      # noqa: E402
from ml.embedding.embedder import Embedder      # noqa: E402

log = logging.getLogger("embeddings")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=C.DEFAULT_EMBED_MODEL)
    ap.add_argument("--backend", default="st", choices=["st", "hash"])
    ap.add_argument("--thesis", default=str(C.THESIS)); ap.add_argument("--jobs", default=str(C.JOBS))
    ap.add_argument("--jobs-name", default="jobs", help="tên bộ embedding Jobs ('jobs_db' cho dữ liệu từ CSDL, tránh trùng id với bộ cũ)")
    ap.add_argument("--only", default=None, help="chỉ dựng các bộ này (phân tách bằng dấu phẩy), ví dụ: thesis")
    ap.add_argument("--job-chars", type=int, default=1500, help="số ký tự description đưa vào embedding Job")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    emb = Embedder(a.model, a.backend).load_cache()

    gold = pd.read_csv(C.GOLD, encoding="utf-8-sig")
    neg = pd.read_csv(C.GOLD_NEGATIVES, encoding="utf-8-sig")
    topics = pd.read_csv(C.TOPICS, encoding="utf-8-sig"); domains = pd.read_csv(C.DOMAINS, encoding="utf-8-sig")
    sets = {
        "gold": (gold.gold_id.tolist(), gold.title.tolist()),
        "gold_negatives": (neg.thesis_id.tolist(), neg.title.tolist()),
        "technical_topics": (topics.topic_id.tolist(), (topics.topic_name + ". " + topics.description + " " + topics.keywords.str.replace("|", ", ")).tolist()),
        "domains": (domains.domain_id.tolist(), (domains.domain_name + ". " + domains.description + " " + domains.keywords.str.replace("|", ", ")).tolist()),
    }
    if Path(a.thesis).exists():
        t = pd.read_csv(a.thesis, encoding="utf-8-sig"); sets["thesis"] = (t.thesis_id.tolist(), t.title.tolist())
    else:
        log.warning("không thấy %s, bỏ qua Thesis", a.thesis)
    if Path(a.jobs).exists():
        j = pd.read_csv(a.jobs, encoding="utf-8-sig")
        txt = (j.job_title + ". Skills: " + j.skills.map(lambda v: ", ".join(json.loads(v))) + ". " + j.description.str.slice(0, a.job_chars)).tolist()
        sets[a.jobs_name] = (j.job_id.tolist(), txt)
    else:
        log.warning("không thấy %s, bỏ qua Jobs", a.jobs)

    if a.only:
        keep = {x.strip() for x in a.only.split(",")}
        sets = {k: v for k, v in sets.items() if k in keep}
        if not sets:
            raise SystemExit(f"--only không khớp bộ nào (có: thesis, gold, gold_negatives, technical_topics, domains, {a.jobs_name})")
    C.EMBED_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, (ids, texts) in sets.items():
        vecs = emb.encode(texts)
        np.save(C.EMBED_DIR / f"{name}_{emb.tag}.npy", vecs)
        pd.DataFrame({"id": ids}).to_csv(C.EMBED_DIR / f"{name}_{emb.tag}_index.csv", index=False)
        rows.append(dict(set=name, model=a.model, backend=a.backend, dim=vecs.shape[1], count=len(ids), created_at=date.today().isoformat()))
        log.info("%s: %s", name, vecs.shape)
    emb.save_cache()
    man = C.EMBED_DIR / "embedding_manifest.csv"
    old = pd.read_csv(man) if man.exists() else pd.DataFrame()
    new = pd.concat([old, pd.DataFrame(rows)]).drop_duplicates(["set", "model", "backend"], keep="last")
    new.to_csv(man, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
