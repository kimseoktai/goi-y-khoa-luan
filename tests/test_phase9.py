import json
import numpy as np
import pandas as pd
from ml.matching import matcher as M
from ml.matching import tune_weights as T


def test_cosine_and_topk_order():
    A = np.array([[1, 0], [0, 1]], dtype=np.float32); B = np.array([[1, 0], [1, 1], [0, 1]], dtype=np.float32)
    S = M.cosine_matrix(A, B)
    assert np.allclose(S[0, 0], 1) and np.allclose(S[0, 2], 0)
    assert M.top_k(S, 2)[0].tolist() == [0, 1]


def test_missing_domain_is_not_penalised():
    topic = np.array([[0.8]], dtype=np.float32); domain = np.array([[0.0]], dtype=np.float32)
    w = {"topic": 0.4, "domain": 0.2, "semantic": 0.4}
    no_dom = M.combine(topic, domain, np.array([[False]]), None, w)
    assert np.allclose(no_dom, 0.8)                                  # chỉ còn Topic, chuẩn hóa lại
    with_dom = M.combine(topic, domain, np.array([[True]]), None, w)
    assert with_dom[0, 0] < no_dom[0, 0]                             # Domain khác nhau thì bị trừ điểm


def test_semantic_normalizer_range():
    S = np.random.default_rng(0).uniform(0.6, 0.9, size=(20, 30))
    lo, hi = M.semantic_normalizer(S)
    assert 0.6 <= lo < hi <= 0.9


def test_explanation_mentions_components():
    e = M.explain("Data Engineer", ["Data Engineering"], [], 0.81, False)
    assert "Data Engineering" in e and "không xét" in e and "0.81" in e


def test_tuning_picks_informative_component():
    rng = np.random.default_rng(1); rows = []
    for j in range(10):
        for t in range(8):
            rel = rng.integers(0, 3)
            rows.append(dict(job_id=j, topic_match=float(rng.random()), domain_match=0.0, domain_ok=False,
                             semantic_norm=float(rel / 2 + rng.normal(0, 0.05)), gain=rel))
    df = pd.DataFrame(rows)
    sem_only = T.mean_ndcg(df, {"topic": 0.001, "domain": 0, "semantic": 1.0}); topic_only = T.mean_ndcg(df, {"topic": 1.0, "domain": 0, "semantic": 0})
    assert sem_only > topic_only


def test_preview_matches_schema():
    m = pd.read_csv("data/processed/matching/job_thesis_matches_PREVIEW_no_semantic.csv", encoding="utf-8-sig")
    assert m.job_id.nunique() == 520 and m.groupby("job_id").size().eq(10).all()
    assert m.score.between(0, 1).all() and m.semantic_raw.isna().all()
    assert (m.thesis_label_source.isin(["gold", "gold+model", "model"])).all()
