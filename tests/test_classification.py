import json
import pandas as pd
from ml.classification import dataset as D, metrics as M
from ml.classification.predict import load_bundle, predict


def test_mask_partial_rows_only_use_verified_labels():
    g = pd.DataFrame([
        dict(title="a", tt=["X"], dm=[], verified=None),
        dict(title="b", tt=["Y"], dm=[], verified={"Y"}),
    ])
    neg = pd.DataFrame(columns=["label_type", "label_name", "title"])
    fx = D.build_label_frame(g, neg, "X", "technical_topic", covered=set())
    assert fx.title.tolist() == ["a"], "dòng partial không xét nhãn X phải bị che"
    fy = D.build_label_frame(g, neg, "Y", "technical_topic", covered=set())
    assert set(fy.title) == {"a", "b"} and fy.set_index("title").loc["a", "provenance"] == "assumed"


def test_metrics_perfect_and_empty():
    pairs = pd.DataFrame(dict(row=["a", "a", "b"], label=["X", "Y", "X"], y=[1, 0, 0], p=[0.9, 0.1, 0.2]))
    r = M.overall(pairs, 0.5)
    assert r["micro_f1"] == 1.0 and r["hamming_loss"] == 0.0 and r["jaccard"] == 1.0


def test_bundle_metadata_and_predict_schema():
    for kind in ("topic", "domain"):
        b = load_bundle(kind)
        assert b["taxonomy_version"] and b["dataset_version"] and b["model_version"]
        out = predict(["Xây dựng chatbot tư vấn khách hàng ngân hàng sử dụng LLM"], b)
        assert set(out[0]) == {"labels", "top_candidates"}
        topics = pd.read_csv("data/repository/technical_topics.csv", encoding="utf-8-sig").topic_name
        domains = pd.read_csv("data/repository/domains.csv", encoding="utf-8-sig").domain_name
        assert set(b["labels"]) <= set(topics if kind == "topic" else domains)
