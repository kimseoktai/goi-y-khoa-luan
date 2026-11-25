import json
import numpy as np
import pandas as pd
from ml.recommendation import recommender as R


def test_candidates_come_from_job_topics_only():
    c = R.gen_candidates({"AI/ML": 1.0, "Web Development": 0.6, "Database": 0.3, "Cloud & DevOps": 0.1}, {"Education": 1.0})
    topics = {t for ts, _ in c for t in ts}
    assert topics == {"AI/ML", "Web Development", "Database"}        # chỉ 3 Topic hàng đầu, không thêm Topic ngoài Job
    assert all(len(ts) <= 2 for ts, _ in c) and ((), ()) not in c
    assert any(dm == ("Education",) for _, dm in c) and any(dm == () for _, dm in c)


def test_job_without_domain_gets_no_domain_candidates_and_domain_skipped():
    c = R.gen_candidates({"AI/ML": 1.0}, {})
    assert c == [(("AI/ML",), ())]
    assert np.isnan(R.domain_match({}, ()))


def test_topic_match_and_job_relevance():
    assert np.isclose(R.topic_match({"A": 1.0, "B": 1.0}, ("A", "B")), 1.0)
    assert R.topic_match({"A": 1.0, "B": 1.0}, ("A",)) < 1.0
    sm = R.build_skill_map(pd.DataFrame(dict(skill_name=["Python", "Docker"], topic_name=["AI/ML", "Cloud & DevOps"], weight=[1.0, 1.0])))
    jr, tech = R.job_relevance(["Python", "Docker", "Unknown"], sm, ("AI/ML",))
    assert np.isclose(jr, 0.5) and tech == ["Python"]
    assert np.isnan(R.job_relevance(["Unknown"], sm, ("AI/ML",))[0])


def test_score_renormalises_over_available_components():
    df = pd.DataFrame(dict(c_job_relevance=[0.5], c_topic=[1.0], c_domain=[np.nan], c_semantic=[np.nan], c_novelty=[np.nan]))
    w = dict(R.DEFAULT_WEIGHTS)
    assert np.isclose(R.score(df, w)[0], (0.25 * 0.5 + 0.2 * 1.0) / 0.45)


def test_mmr_diversifies_and_zero_keeps_score_order():
    g = pd.DataFrame(dict(topics=[("A",), ("A", "B"), ("C",)], domains=[(), (), ()],
                          c_job_relevance=[1.0, 0.95, 0.7], c_topic=[1.0, 0.95, 0.7]))
    assert R.rank(g, k=2, mmr=0.0) == [0, 1]
    assert R.rank(g, k=2, mmr=0.9) == [0, 2]


def test_diversity_and_ndcg():
    assert R.diversity([{"A"}, {"A"}]) == 0.0 and R.diversity([{"A"}, {"B"}]) == 1.0
    assert np.isclose(R.ndcg_at_k(np.array([3, 2, 1.0]), np.array([2, 1, 0.0])), 1.0)
    assert R.ndcg_at_k(np.array([1, 2, 3.0]), np.array([2, 1, 0.0])) < 1.0


def test_semantic_and_novelty_columns():
    rng = np.random.default_rng(0)
    unit = lambda x: x / np.linalg.norm(x, axis=-1, keepdims=True)
    cand = R.build_candidates(pd.DataFrame([dict(job_id="1", job_title="J", company="C", skills=json.dumps(["Python"]),
                                                  technical_topic_scores=json.dumps({"AI/ML": 1.0, "Database": 0.5}), domain_scores="{}")]),
                              R.build_skill_map(pd.DataFrame(dict(skill_name=["Python"], topic_name=["AI/ML"], weight=[1.0]))))
    texts = list(dict.fromkeys(cand.direction_text)); V = unit(rng.normal(size=(len(texts), 8)))
    out = R.add_semantic_and_novelty(cand, {"1": unit(rng.normal(size=8))}, dict(zip(texts, V)), unit(rng.normal(size=(20, 8))),
                                     list(range(20)), [f"t{i}" for i in range(20)], [({"AI/ML"}, set())] * 3)
    assert out.c_semantic.between(0, 1).all() and out.c_novelty.between(0, 1).all() and out.c_novelty_semantic.between(0, 1).all()
    assert np.allclose(out.c_novelty, 1.0 / (1.0 + out.combo_support))
    assert out[out.topics == ("AI/ML",)].combo_support.iloc[0] == 3 and out[out.topics == ("Database",)].combo_support.iloc[0] == 0


def test_closest_same_label_filters_by_labels():
    E = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]); E = E / np.linalg.norm(E, axis=1, keepdims=True)
    L = [({"AI/ML"}, set()), ({"Web"}, set()), ({"Web", "Cloud"}, {"Finance"})]
    r = R.closest_same_label(("Web",), (), np.array([1.0, 0.0]), E, [10, 20, 30], ["a", "b", "c"], L)
    assert r["same_label_thesis_id"] == 30 and r["same_label_level"] == "same_labels"      # a gần hơn nhưng không cùng nhãn
    r = R.closest_same_label(("Web", "Cloud", "Mobile"), (), np.array([0.0, 1.0]), E, [10, 20, 30], ["a", "b", "c"], L)
    assert r["same_label_level"] == "partial_labels"
    r = R.closest_same_label(("Games",), (), np.array([0.0, 1.0]), E, [10, 20, 30], ["a", "b", "c"], L)
    assert r["same_label_level"] == "none" and r["same_label_thesis_id"] is None
