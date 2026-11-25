"""Recommendation (Phase 11): Job -> Thesis Direction. Dùng lại ml.recommendation.pipeline."""
import numpy as np

from backend.errors import BadRequest
from backend.services.common import check_weights, job_index, jsonable
from ml.recommendation import pipeline as P
from ml.recommendation import recommender as R


def _table(ds):
    def build():
        if ds.has_embeddings():
            return P.build_candidate_table(ds.jobs, ds.thesis, ds.skill_map, ds.job_vectors(), ds.thesis_vectors(), ds.encode, "label")
        return P.build_candidate_table(ds.jobs, ds.thesis, ds.skill_map)
    return ds.cached("cand_table", build)


def recommend(ds, job_id, top_k=5, weights=None, mmr=0.0, novelty_mode="label"):
    if not (1 <= top_k <= 20):
        raise BadRequest("top_k phải trong khoảng 1..20")
    if not (0.0 <= mmr <= 1.0):
        raise BadRequest("mmr phải trong khoảng 0..1")
    if novelty_mode not in ("label", "semantic"):
        raise BadRequest("novelty_mode phải là 'label' hoặc 'semantic'")
    i = job_index(ds, job_id)
    w = dict(R.DEFAULT_WEIGHTS); w.update(check_weights(weights, R.DEFAULT_WEIGHTS) or {})
    cand = _table(ds)
    sem_ok = "c_semantic" in cand
    if not sem_ok:
        w["semantic"] = 0.0; w["novelty"] = 0.0
    if sum(w.values()) <= 0:
        raise BadRequest("tổng trọng số phải > 0")
    job = ds.jobs.iloc[i]
    g = cand[cand.job_id == job.job_id].copy()
    head = dict(job_id=job.job_id, job_title=job.job_title, company=job.company, skills=job._skills[:15],
                job_technical_topics=job._technical_topics, job_domains=job._domains, weights=w,
                semantic_used=sem_ok, novelty_mode=novelty_mode if sem_ok else None)
    if g.empty:
        return jsonable(dict(head, items=[], message="Job chưa có Technical Topic nên chưa sinh được hướng đề tài (nhãn Job sinh từ luật, một số vai trò phi kỹ thuật không có Topic)."))
    if sem_ok:
        g["c_novelty"] = g["c_novelty_label" if novelty_mode == "label" else "c_novelty_semantic"]
    items = P.direction_rows(g, w, top_k, mmr, job._technical_topic_scores, ds.market_ctx)
    return jsonable(dict(head, n_candidates=len(g), items=items,
                         note=("Hướng được sinh từ Topic/Domain của chính Job và là mô tả nhãn, chưa phải tiêu đề đề tài. Trọng số mặc định chưa tối ưu; "
                               "mức liên quan trong mẫu đánh giá bão hòa nên chưa phân biệt được các bộ trọng số. Novelty mặc định = 1/(1+số Thesis cùng nhãn).")))
