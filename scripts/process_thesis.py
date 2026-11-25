"""Phase 6 - xử lý Thesis: Technical Topics + Domains + Keywords + tham chiếu Embedding.

Chỉ PREDICT bằng mô hình đã lưu. Không suy ra Skill cho Thesis. Thesis có thể không có Domain (hợp lệ).
Ví dụ:
  python scripts/process_thesis.py --topic-version v1.2 --domain-version v1.2 --embedding-model intfloat/multilingual-e5-base
"""
import argparse, json, logging, sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                    # noqa: E402
from ml.classification.predict import load_bundle             # noqa: E402
from ml.classification.apply_models import label_texts, merge_gold_labels  # noqa: E402
from ml.classification.dataset import norm_text               # noqa: E402
from ml.embedding.embedder import model_tag                   # noqa: E402
from ml.preprocessing.keyword_extractor import KeywordExtractor  # noqa: E402

log = logging.getLogger("process_thesis")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thesis", default=str(C.THESIS))
    ap.add_argument("--topic-version", default="v1.2"); ap.add_argument("--domain-version", default="v1.2")
    ap.add_argument("--embedding-model", default=None, help="nếu có: kiểm tra file embedding Thesis khớp số dòng")
    ap.add_argument("--out", default=str(C.ROOT / "data/processed/thesis/thesis_processed.csv"))
    ap.add_argument("--summary", default=str(C.ROOT / "data/processed/thesis/thesis_label_summary.csv"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    t = pd.read_csv(a.thesis, encoding="utf-8-sig")
    topics = pd.read_csv(C.TOPICS, encoding="utf-8-sig"); domains = pd.read_csv(C.DOMAINS, encoding="utf-8-sig")
    gold = pd.read_csv(C.GOLD, encoding="utf-8-sig")
    tb, db = load_bundle("topic", a.topic_version), load_bundle("domain", a.domain_version)
    if tb["taxonomy_version"] != db["taxonomy_version"]:
        raise SystemExit("hai mô hình khác taxonomy_version")
    log.info("thesis=%d | topic %s (%s) | domain %s (%s)", len(t), tb["model_version"], tb["taxonomy_version"], db["model_version"], db["taxonomy_version"])

    lab = label_texts(t.title.tolist(), tb, db, topics, domains)
    kx = KeywordExtractor().fit(t.title.map(norm_text))
    matched = [json.loads(m) for m in lab.taxonomy_keywords]
    top = kx.top_terms(t.title.map(norm_text), k=3, exclude=matched)
    kws = [json.dumps(list(dict.fromkeys(m + tt))[:8], ensure_ascii=False) for m, tt in zip(matched, top)]

    out = pd.concat([t[["thesis_id", "title"] + [c for c in ["year", "source", "report_url", "source_code_url", "advisors"] if c in t]].reset_index(drop=True), lab], axis=1)
    out["keywords"] = kws
    out["in_gold"] = t.title.map(norm_text).isin(set(gold.title.map(norm_text))).values   # mẫu đã dùng để train: không dùng để đánh giá
    out = merge_gold_labels(out, gold)
    out["taxonomy_version"] = tb["taxonomy_version"]; out["topic_model_version"] = tb["model_version"]
    out["domain_model_version"] = db["model_version"]; out["dataset_version"] = tb["dataset_version"]
    out["processed_at"] = datetime.now().isoformat(timespec="seconds")

    emb_ref = ""
    if a.embedding_model:
        f = C.EMBED_DIR / f"thesis_{model_tag(a.embedding_model)}.npy"
        idx = C.EMBED_DIR / f"thesis_{model_tag(a.embedding_model)}_index.csv"
        if not f.exists() or not idx.exists():
            raise SystemExit(f"thiếu {f.name}; chạy ml/embedding/build_embeddings.py trước")
        n = np.load(f, mmap_mode="r").shape[0]
        ids = pd.read_csv(idx).id.tolist()
        if n != len(t) or ids != t.thesis_id.tolist():
            raise SystemExit("embedding Thesis không khớp thứ tự/số dòng thesis_clean.csv; tạo lại embedding")
        emb_ref = f"embeddings/{f.name}"
    out["embedding_file"] = emb_ref

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")

    rows = []
    for kind, col, names in [("technical_topic", "technical_topics", topics.topic_name), ("domain", "domains", domains.domain_name)]:
        lists = out[col].map(json.loads)
        for n in names:
            m = lists.map(lambda l: n in l)
            rows.append(dict(type=kind, label=n, thesis_count=int(m.sum()), pct=round(100 * m.mean(), 1),
                             count_gold_labelled=int((m & out.in_gold).sum()), count_model_only=int((m & ~out.in_gold).sum())))
    pd.DataFrame(rows).to_csv(a.summary, index=False, encoding="utf-8-sig")
    log.info("no_technical_topic=%d | no_domain=%d | low_conf_topic=%d",
             out.review_flag.str.contains("no_technical_topic").sum(), (out.domains == "[]").sum(),
             out.review_flag.str.contains("low_confidence_topic").sum())
    log.info("đã lưu %s", a.out)


if __name__ == "__main__":
    main()
