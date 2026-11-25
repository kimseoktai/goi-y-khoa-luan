"""Phase 11 - đề xuất Thesis Direction cho Job.
  python scripts\\recommend_directions.py --embedding-model intfloat/multilingual-e5-base            (mọi Job)
  python scripts\\recommend_directions.py --embedding-model intfloat/multilingual-e5-base --job-id 4  (một Job, in giải thích)
  thêm --no-semantic nếu chưa có embedding (khi đó chỉ dùng JobRelevance/Topic/Domain, kết quả sơ bộ)
Đầu ra: data/processed/recommendation/job_recommendations.csv (Top-k) và candidates_all.csv (mọi hướng + thành phần điểm).
"""
import argparse, json, logging, sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                    # noqa: E402
from ml.embedding.embedder import Embedder, model_tag         # noqa: E402
from ml.matching import matcher as M                          # noqa: E402
from ml.recommendation import recommender as R                # noqa: E402
from ml.recommendation import pipeline as P                   # noqa: E402

log = logging.getLogger("recommend")
rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
OUT = C.ROOT / "data/processed/recommendation"


def load_vecs(name, ids, tag):
    f, ix = C.EMBED_DIR / f"{name}_{tag}.npy", C.EMBED_DIR / f"{name}_{tag}_index.csv"
    if not f.exists() or not ix.exists():
        raise SystemExit(f"thiếu {f.name}; chạy ml/embedding/build_embeddings.py trước")
    E, have = M.l2norm(np.load(f)), [str(i) for i in rd(ix).id]
    pos = {i: k for k, i in enumerate(have)}
    miss = [i for i in ids if str(i) not in pos]
    if miss:
        raise SystemExit(f"{len(miss)} id của {name} không có embedding (ví dụ {miss[:3]}); tạo lại embedding")
    return E[[pos[str(i)] for i in ids]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--thesis", default=str(C.ROOT / "data/processed/thesis/thesis_processed.csv"))
    ap.add_argument("--embedding-model", default=C.DEFAULT_EMBED_MODEL)
    ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    ap.add_argument("--no-semantic", action="store_true")
    ap.add_argument("--weights", default=None, help="JSON, ví dụ '{\"job_relevance\":0.2,\"topic\":0.2,\"domain\":0.1,\"semantic\":0.3,\"novelty\":0.2}'")
    ap.add_argument("--novelty-mode", default="label", choices=["label", "semantic"], help="label: 1/(1+số Thesis cùng nhãn) (mặc định); semantic: novelty theo embedding")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--mmr", type=float, default=0.0, help=">0: giảm trùng lặp nhãn giữa các hướng trong Top-k (chưa được đánh giá, mặc định tắt)")
    ap.add_argument("--job-id", default=None)
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    W = dict(R.DEFAULT_WEIGHTS); W.update(json.loads(a.weights) if a.weights else {})
    jobs, thesis = rd(a.jobs).reset_index(drop=True), rd(a.thesis).reset_index(drop=True)
    skill_map = R.build_skill_map(rd(C.ROOT / "data/repository/skill_topic_map.csv"))
    cand = P.build_candidate_table(jobs, thesis, skill_map)
    n_no = jobs.job_id.nunique() - cand.job_id.nunique()
    log.info("%d hướng cho %d/%d Job (%d Job không có Topic nên không sinh được hướng)", len(cand), cand.job_id.nunique(), len(jobs), n_no)

    if a.no_semantic:
        log.warning("KHÔNG dùng semantic và novelty: xếp hạng chỉ theo JobRelevance/Topic/Domain, kết quả sơ bộ")
        meta = {}
    else:
        tag = "hash256" if a.embedding_backend == "hash" else model_tag(a.embedding_model)
        Ej = load_vecs("jobs", jobs.job_id.tolist(), tag); Et = load_vecs("thesis", thesis.thesis_id.tolist(), tag)
        emb = Embedder(a.embedding_model, a.embedding_backend).load_cache()
        cand = P.build_candidate_table(jobs, thesis, skill_map, Ej, Et, emb.encode, a.novelty_mode)
        emb.save_cache()
        meta = cand.attrs.get("semantic_norm", {})
    cand["score"] = R.score(cand, W)
    market = P.market_context(C.ROOT / "data/processed/market")
    jt = {str(r.job_id): json.loads(r.technical_topic_scores) for r in jobs.itertuples()}

    rows = []
    for jid, g in cand.groupby("job_id", sort=False):
        if a.job_id is not None and str(jid) != str(a.job_id):
            continue
        g = g.reset_index(drop=True)
        for rk, i in enumerate(R.rank(g, W, a.top_k, a.mmr), 1):
            r = g.iloc[i]
            rows.append(dict(job_id=jid, job_title=r.job_title, rank=rk, direction_topics=" + ".join(r.topics),
                             direction_domains=" + ".join(r.domains), suggested_technologies=r.suggested_technologies,
                             recommendation_score=round(float(r.score), 4),
                             **{f"c_{c}": (None if pd.isna(r.get(f"c_{c}", np.nan)) else round(float(r[f"c_{c}"]), 4)) for c in R.COMPONENTS},
                             nearest_thesis_id=r.get("nearest_thesis_id"), nearest_thesis_title=r.get("nearest_thesis_title"),
                             nearest_similarity=None if "nearest_similarity" not in r else round(float(r.nearest_similarity), 4),
                             combo_support=r.get("combo_support"), same_label_thesis_title=r.get("same_label_thesis_title"),
                             same_label_similarity=None if pd.isna(r.get("same_label_similarity", np.nan)) else round(float(r.same_label_similarity), 4),
                             same_label_level=r.get("same_label_level"), cand_id=r.cand_id, explanation=R.explain(r, jt[str(jid)], market)))
    res = pd.DataFrame(rows)
    if a.job_id is None:
        res.to_csv(out / "job_recommendations.csv", index=False, encoding="utf-8-sig")
        c2 = cand.copy(); c2["topics"] = c2.topics.map(" | ".join); c2["domains"] = c2.domains.map(" | ".join)
        c2.to_csv(out / "candidates_all.csv", index=False, encoding="utf-8-sig")
        json.dump(dict(novelty_mode=a.novelty_mode, weights=W, mmr=a.mmr, top_k=a.top_k, semantic=not a.no_semantic, semantic_norm=meta, n_jobs_with_candidates=int(cand.job_id.nunique()),
                       n_jobs_without_candidates=int(n_no), embedding_model=a.embedding_model, created=datetime.now().isoformat(timespec="seconds"),
                       note="Trọng số mặc định chưa được tuning; novelty là tương đối giữa các hướng; xem ml/recommendation/recommender.py"),
                  open(out / "recommendation_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log.info("đã ghi %s", out / "job_recommendations.csv")
    else:
        for r in res.itertuples():
            print(f"#{r.rank} [{r.recommendation_score:.3f}] {r.direction_topics} | {r.direction_domains or '-'}\n    {r.explanation}\n")


if __name__ == "__main__":
    main()
