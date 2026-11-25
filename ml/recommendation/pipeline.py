"""Phase 11/12 - ghép các bước của Recommendation thành hàm dùng chung cho script và backend (backend KHÔNG tự viết lại logic ML)."""
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

from ml.matching import matcher as M
from ml.recommendation import recommender as R

log = logging.getLogger("recommendation")


def build_candidate_table(jobs, thesis, skill_map, job_E=None, thesis_E=None, encode=None, novelty_mode="label"):
    """Sinh hướng cho mọi Job và (nếu có embedding) thêm Semantic/Novelty/Thesis gần nhất.
    job_E, thesis_E: embedding đã chuẩn hóa L2, cùng thứ tự với jobs, thesis. encode(texts) -> mảng vector (chưa chuẩn hóa cũng được)."""
    cand = R.build_candidates(jobs, skill_map)
    if job_E is None or thesis_E is None or encode is None:
        return cand
    texts = list(dict.fromkeys(cand.direction_text))
    V = M.l2norm(np.asarray(encode(texts), dtype=np.float32))
    labels = [(set(json.loads(t)), set(json.loads(d))) for t, d in zip(thesis.technical_topics, thesis.domains)]
    return R.add_semantic_and_novelty(cand, {str(j): job_E[i] for i, j in enumerate(jobs.job_id)}, dict(zip(texts, V)),
                                      thesis_E, thesis.thesis_id.tolist(), thesis.title.tolist(), labels, novelty_mode)


def market_context(market_dir):
    """Bảng thị trường (Phase 8) -> dict dùng trong giải thích. Thiếu file thì trả dict rỗng (giải thích bỏ phần Market Demand)."""
    d, out = Path(market_dir), {"topics": {}, "domains": {}}
    rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
    try:
        t = rd(d / "demand_topics.csv"); g = rd(d / "supply_vs_demand_topics.csv").set_index("topic")
        for r in t.itertuples():
            out["topics"][r.item] = dict(share=r.share, ci_low=r.ci_low, ci_high=r.ci_high, support_ok=bool(r.support_ok),
                                         gap_status=g.gap_status.get(r.item, "n/a"))
        for r in rd(d / "demand_domains.csv").itertuples():
            out["domains"][r.item] = dict(share=r.share_of_labelled, support_ok=bool(r.support_ok))
    except FileNotFoundError:
        log.warning("không thấy bảng thị trường (Phase 8) trong %s", d)
    return out


def direction_rows(g, W, top_k, mmr, job_topic_scores, market):
    """g: các hướng của MỘT job (đã có cột score hoặc sẽ được tính theo W). Trả về list dict Top-k kèm giải thích."""
    g = g.reset_index(drop=True)
    rows = []
    for rk, i in enumerate(R.rank(g, W, top_k, mmr), 1):
        r = g.iloc[i]
        comp = {c: (None if f"c_{c}" not in r or pd.isna(r[f"c_{c}"]) else round(float(r[f"c_{c}"]), 4)) for c in R.COMPONENTS}
        rows.append(dict(rank=rk, direction_topics=list(r.topics), direction_domains=list(r.domains),
                         suggested_technologies=json.loads(r.suggested_technologies),
                         recommendation_score=None if pd.isna(R.score(g.iloc[[i]], W)[0]) else round(float(R.score(g.iloc[[i]], W)[0]), 4),
                         components=comp, combo_support=None if "combo_support" not in r or pd.isna(r.get("combo_support")) else int(r.combo_support),
                         nearest_thesis_same_labels=None if not isinstance(r.get("same_label_thesis_title"), str) else dict(
                             thesis_id=int(r.same_label_thesis_id), title=r.same_label_thesis_title,
                             similarity=round(float(r.same_label_similarity), 4), match_level=r.same_label_level),
                         explanation=R.explain(r, job_topic_scores, market)))
    return rows
