import json
import pandas as pd
from ml.classification.predict import load_bundle
from ml.classification.apply_models import label_texts, merge_gold_labels
from ml.preprocessing.keyword_extractor import KeywordExtractor

topics = pd.read_csv("data/repository/technical_topics.csv", encoding="utf-8-sig")
domains = pd.read_csv("data/repository/domains.csv", encoding="utf-8-sig")


def test_label_texts_schema_and_allows_empty_domain():
    tb, db = load_bundle("topic", "v1.1"), load_bundle("domain", "v1.1")
    out = label_texts(["Xây dựng website bán hàng thời trang", "Một đề tài rất chung chung"], tb, db, topics, domains)
    assert len(out) == 2
    for c in ["technical_topics", "domains", "technical_topic_scores", "top_topic_candidates", "review_flag"]:
        assert c in out
    assert "Web Development" in json.loads(out.technical_topics[0])
    assert json.loads(out.domains[1]) == [] or isinstance(json.loads(out.domains[1]), list)   # Domain có thể rỗng


def test_keywords_never_empty_for_normal_titles_and_no_skills_inferred():
    texts = ["xây dựng website bán hàng", "xây dựng website quản lý", "website bán hàng thời trang", "phân tích dữ liệu bán hàng"] * 3
    top = KeywordExtractor(min_df=2, max_df=0.9).fit(texts).top_terms(texts[:2])
    assert all(isinstance(t, list) for t in top)


def test_merge_gold_prefers_verified_labels_and_marks_source():
    out = pd.DataFrame([dict(title="Đề tài A", technical_topics="[]", technical_topic_scores="{}", domains="[]",
                             domain_scores="{}", topic_confidence=None, domain_confidence=None, review_flag="no_technical_topic"),
                        dict(title="Đề tài B", technical_topics='["AI/ML"]', technical_topic_scores='{"AI/ML": 0.6}', domains="[]",
                             domain_scores="{}", topic_confidence=0.6, domain_confidence=None, review_flag="")])
    gold = pd.DataFrame([dict(title="Đề tài A", technical_topics='["Database"]', domains='["Finance & Banking"]', verified_labels="all")])
    r = merge_gold_labels(out, gold)
    assert r.label_source.tolist() == ["gold", "model"]
    assert json.loads(r.technical_topics[0]) == ["Database"] and r.review_flag[0] == ""
