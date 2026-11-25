import json
import pandas as pd

gold = pd.read_csv("data/processed/gold/gold_dataset_clean.csv", encoding="utf-8-sig")
topics = pd.read_csv("data/repository/technical_topics.csv", encoding="utf-8-sig")
domains = pd.read_csv("data/repository/domains.csv", encoding="utf-8-sig")
thesis = pd.read_csv("data/processed/thesis/thesis_clean.csv", encoding="utf-8-sig") \
    if __import__("os").path.exists("data/processed/thesis/thesis_clean.csv") else None


def test_gold_basic():
    assert len(gold) == 586
    assert not gold.gold_id.duplicated().any()
    assert not gold.title.str.lower().str.strip().duplicated().any()
    assert not gold.title.isna().any()


def test_labels_in_repository_and_separated():
    tn, dn = set(topics.topic_name), set(domains.domain_name)
    assert not tn & dn, "Technical Topic và Domain không được trùng tên"
    for v in gold.technical_topics: assert set(json.loads(v)) <= tn
    for v in gold.domains: assert set(json.loads(v)) <= dn


def test_partial_records_declare_verified_scope():
    part = gold[gold.label_status == "annotated_partial"]
    assert len(part) == 275
    for v in part.verified_labels:
        assert len(json.loads(v)) >= 1
    assert (gold[gold.label_status != "annotated_partial"].verified_labels == "all").all()


def test_unlabelled_full_rows_are_flagged_not_deleted():
    full = gold[gold.verified_labels == "all"]
    empty = full[full.technical_topics.map(lambda v: len(json.loads(v)) == 0)]
    assert (empty.label_status == "needs_review").all()
