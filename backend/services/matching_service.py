"""Job -> Thesis (Phase 9) và Thesis tương tự. Dùng lại ml.matching, không viết lại công thức."""
import numpy as np

from backend.errors import BadRequest, Unavailable
from backend.services.common import check_weights, job_index, jsonable, thesis_index
from ml.matching import matcher as M


def _matrices(ds):
    def build():
        Jt = M.score_matrix(ds.jobs, ds.topics.topic_name.tolist(), "technical_topic_scores")
        Tt = M.score_matrix(ds.thesis, ds.topics.topic_name.tolist(), "technical_topic_scores")
        Jd = M.score_matrix(ds.jobs, ds.domains.domain_name.tolist(), "domain_scores")
        Td = M.score_matrix(ds.thesis, ds.domains.domain_name.tolist(), "domain_scores")
        out = dict(topic=M.cosine_matrix(Jt, Tt), domain=M.cosine_matrix(Jd, Td),
                   domain_ok=(Jd.sum(1) > 0)[:, None] & (Td.sum(1) > 0)[None, :], sem_raw=None, sem=None, lo=None, hi=None)
        if ds.has_embeddings():
            S = ds.job_vectors() @ ds.thesis_vectors().T
            lo, hi = M.semantic_normalizer(S)
            out.update(sem_raw=S, sem=np.clip((S - lo) / max(hi - lo, 1e-9), 0, 1), lo=lo, hi=hi)
        return out
    return ds.cached("match_mats", build)


def match_job(ds, job_id, top_k=10, weights=None, use_semantic=True):
    if not (1 <= top_k <= 100):
        raise BadRequest("top_k phải trong khoảng 1..100")
    i = job_index(ds, job_id)
    w = dict(M.DEFAULT_WEIGHTS); w.update(check_weights(weights, M.DEFAULT_WEIGHTS) or {})
    mats = _matrices(ds)
    sem_ok = mats["sem"] is not None and use_semantic
    if use_semantic and mats["sem"] is None:
        raise Unavailable("chưa có embedding nên không tính được thành phần semantic; gửi use_semantic=false để xem kết quả sơ bộ")
    if not sem_ok:
        w["semantic"] = 0.0
    if w["topic"] + w["domain"] + w["semantic"] <= 0:
        raise BadRequest("tổng trọng số phải > 0")
    sl = slice(i, i + 1)
    score = M.combine(mats["topic"][sl], mats["domain"][sl], mats["domain_ok"][sl], mats["sem"][sl] if sem_ok else None, w)
    best = M.top_k(score, top_k)[0]
    jt, jd = set(ds.jobs._technical_topics[i]), set(ds.jobs._domains[i])
    items = []
    for r, j in enumerate(best, 1):
        shared_t, shared_d = sorted(jt & set(ds.thesis._technical_topics[j])), sorted(jd & set(ds.thesis._domains[j]))
        dok = bool(mats["domain_ok"][i, j]); sr = float(mats["sem_raw"][i, j]) if sem_ok else None
        items.append(dict(rank=r, thesis_id=ds.thesis.thesis_id[j], title=ds.thesis.title[j], score=round(float(score[0, j]), 4),
                          topic_match=round(float(mats["topic"][i, j]), 4), domain_match=round(float(mats["domain"][i, j]), 4) if dok else None,
                          semantic_norm=round(float(mats["sem"][i, j]), 4) if sem_ok else None, semantic_raw=None if sr is None else round(sr, 4),
                          shared_topics=shared_t, shared_domains=shared_d,
                          label_source=ds.thesis.label_source[j],
                          explanation=M.explain(ds.jobs.job_title[i], shared_t, shared_d, sr, dok)))
    return jsonable(dict(job_id=ds.jobs.job_id[i], job_title=ds.jobs.job_title[i], weights=w, semantic_used=sem_ok,
                         semantic_range=[mats["lo"], mats["hi"]] if sem_ok else None, items=items,
                         note="Trọng số mặc định là điểm khởi đầu, chưa được coi là tối ưu. Nhãn Topic của Job sinh từ luật, nên điểm khớp có thể cao hơn thực tế."))


def similar_thesis(ds, thesis_id, top_k=10):
    if not (1 <= top_k <= 100):
        raise BadRequest("top_k phải trong khoảng 1..100")
    i = thesis_index(ds, thesis_id)
    E = ds.thesis_vectors()
    s = E @ E[i]; s[i] = -np.inf
    order = np.argsort(-s, kind="stable")[:top_k]
    t = ds.thesis
    return jsonable(dict(thesis_id=t.thesis_id[i], title=t.title[i], items=[
        dict(rank=r, thesis_id=t.thesis_id[j], title=t.title[j], similarity=round(float(s[j]), 4),
             shared_topics=sorted(set(ds.thesis._technical_topics[i]) & set(ds.thesis._technical_topics[j])),
             shared_domains=sorted(set(ds.thesis._domains[i]) & set(ds.thesis._domains[j]))) for r, j in enumerate(order, 1)]))
