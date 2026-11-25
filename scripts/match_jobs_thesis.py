"""Phase 9 - so khớp Job -> Thesis, lưu top-k kèm các thành phần điểm và giải thích.

Có embedding (khuyên dùng):  python scripts/match_jobs_thesis.py --embedding-model intfloat/multilingual-e5-base
Không có embedding (chỉ Topic+Domain, kết quả sơ bộ, nhiều Thesis cùng điểm): thêm --no-semantic
"""
import argparse, json, logging, sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                           # noqa: E402
from ml.matching import matcher as M                                 # noqa: E402
from ml.matching.components import build_components                  # noqa: E402

log = logging.getLogger("matching")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--thesis", default=str(C.ROOT / "data/processed/thesis/thesis_processed.csv"))
    ap.add_argument("--embedding-model", default=None)
    ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    ap.add_argument("--no-semantic", action="store_true")
    ap.add_argument("--w-topic", type=float, default=M.DEFAULT_WEIGHTS["topic"])
    ap.add_argument("--w-domain", type=float, default=M.DEFAULT_WEIGHTS["domain"])
    ap.add_argument("--w-semantic", type=float, default=M.DEFAULT_WEIGHTS["semantic"])
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--out", default=str(C.ROOT / "data/processed/matching/job_thesis_matches.csv"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
    jobs, thesis, topics, domains = rd(a.jobs), rd(a.thesis), rd(C.TOPICS), rd(C.DOMAINS)
    W = {"topic": a.w_topic, "domain": a.w_domain, "semantic": a.w_semantic}

    if a.no_semantic:
        log.warning("KHÔNG dùng semantic: nhiều Thesis cùng điểm Topic nên thứ hạng chỉ mang tính sơ bộ")
        W["semantic"] = 0.0
    elif not a.embedding_model:
        raise SystemExit("cần --embedding-model (hoặc dùng --no-semantic)")
    comp = build_components(jobs, thesis, topics, domains, None if a.no_semantic else a.embedding_model, a.embedding_backend)
    topic, domain, domain_ok, sem_raw, sem, lo, hi = (comp[k] for k in ["topic", "domain", "domain_ok", "sem_raw", "sem", "lo", "hi"])
    if sem is not None:
        log.info("semantic cosine: lo(p5)=%.3f hi(p95)=%.3f", lo, hi)

    score = M.combine(topic, domain, domain_ok, sem, W)
    best = M.top_k(score, a.top_k)
    jt = jobs.technical_topics.map(json.loads).tolist(); tt = thesis.technical_topics.map(json.loads).tolist()
    jd = jobs.domains.map(json.loads).tolist(); td = thesis.domains.map(json.loads).tolist()
    rows = []
    for i in range(len(jobs)):
        for r, j in enumerate(best[i], 1):
            st_ = sorted(set(jt[i]) & set(tt[j])); sd_ = sorted(set(jd[i]) & set(td[j]))
            sr = None if sem_raw is None else float(sem_raw[i, j])
            rows.append(dict(job_id=jobs.job_id[i], job_title=jobs.job_title[i], company=jobs.company[i], rank=r,
                             thesis_id=thesis.thesis_id[j], thesis_title=thesis.title[j], score=round(float(score[i, j]), 4),
                             topic_match=round(float(topic[i, j]), 4),
                             domain_match=round(float(domain[i, j]), 4) if domain_ok[i, j] else None,
                             semantic_raw=None if sr is None else round(sr, 4),
                             semantic_norm=None if sem is None else round(float(sem[i, j]), 4),
                             shared_topics=json.dumps(st_, ensure_ascii=False), shared_domains=json.dumps(sd_, ensure_ascii=False),
                             thesis_label_source=thesis.label_source[j], thesis_in_gold=bool(thesis.in_gold[j]),
                             explanation=M.explain(jobs.job_title[i], st_, sd_, sr, bool(domain_ok[i, j]))))
    out = pd.DataFrame(rows)
    out["weights"] = json.dumps(W); out["semantic_range"] = json.dumps([lo, hi]); out["created_at"] = datetime.now().isoformat(timespec="seconds")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    log.info("jobs=%d thesis=%d top_k=%d weights=%s -> %s", len(jobs), len(thesis), a.top_k, W, a.out)


if __name__ == "__main__":
    main()
