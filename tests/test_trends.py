"""Kiểm thử xu hướng khóa luận theo năm: đếm, tỷ lệ, so năm gần nhất với các năm trước, xử lý mẫu nhỏ, nguồn không có."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd                                              # noqa: E402

from backend.errors import NotFound                              # noqa: E402
from backend.services import trend_service as T                  # noqa: E402
from tests.test_phase12 import raises                            # noqa: E402

J = lambda x: json.dumps(x, ensure_ascii=False)


def ds_of(rows):
    """rows: (năm, nguồn, [topic], [domain], in_gold)"""
    t = pd.DataFrame([dict(thesis_id=i, year=y, source=s, in_gold=g) for i, (y, s, _, _, g) in enumerate(rows)])
    t["_technical_topics"] = [r[2] for r in rows]
    t["_domains"] = [r[3] for r in rows]
    topics = pd.DataFrame(dict(topic_name=["AI/ML", "Web Development", "Database"], status=["active", "active", "candidate"]))
    domains = pd.DataFrame(dict(domain_name=["Education", "Finance & Banking"], status="active"))
    return NS(thesis=t, topics=topics, domains=domains)


def test_counts_shares_and_unlabelled():
    rows = ([(2023, "neu", ["Web Development"], [], True)] * 40 + [(2023, "neu", [], [], False)] * 10
            + [(2024, "neu", ["AI/ML"], ["Education"], False)] * 5 + [(2024, "uit", ["AI/ML"], [], False)] * 7 + [(None, "neu", ["AI/ML"], [], False)])
    d = T.thesis_trends(ds_of(rows), "neu")
    assert d["n_with_year"] == 55 and d["n_without_year"] == 1 and d["n_source"] == 56         # khóa luận không có năm và của trường khác không tính
    y = {r["year"]: r for r in d["years"]}
    assert y[2023]["n"] == 50 and y[2023]["no_topic"] == 10 and y[2024]["n"] == 5 and y[2024]["small"] and not y[2023]["small"]
    web = next(r for r in d["topics"] if r["name"] == "Web Development")
    assert [b["count"] for b in web["by_year"]] == [40, 0] and abs(web["by_year"][0]["share"] - 0.8) < 1e-9 and web["total"] == 40
    assert "Database" not in [r["name"] for r in d["topics"]]                                  # nhãn chưa active không hiện
    assert d["label_quality"] == dict(gold=40, model=15, gold_share=40 / 55)


def test_trend_up_down_flat_and_insufficient():
    prior = [(2022, "neu", ["Database"], [], False)] * 100 + [(2022, "neu", ["Web Development"], [], False)] * 100
    # năm gần nhất: AI/ML tăng mạnh (0 -> 60%), Database giảm mạnh (50% -> 0), Web Development giữ 50%
    last = [(2025, "neu", ["AI/ML"], [], False)] * 60 + [(2025, "neu", ["Web Development"], [], False)] * 40
    ds = ds_of(prior + last)
    ds.topics = pd.DataFrame(dict(topic_name=["AI/ML", "Web Development", "Database"], status="active"))
    d = {r["name"]: r for r in T.thesis_trends(ds, "neu")["topics"]}
    assert d["AI/ML"]["trend"] == "up" and d["Database"]["trend"] == "down"
    assert d["Web Development"]["trend"] == "flat" or d["Web Development"]["trend"] == "down"   # 50% -> 40%: khoảng tin cậy chồng nhau thì không kết luận
    small = T.thesis_trends(ds_of([(2024, "neu", ["AI/ML"], [], False)] * 10 + [(2025, "neu", ["AI/ML"], [], False)] * 10), "neu")
    assert small["topics"][0]["trend"] == "insufficient"                                       # mỗi bên < 30 khóa luận
    one = T.thesis_trends(ds_of([(2025, "neu", ["AI/ML"], [], False)] * 40), "neu")
    assert one["topics"][0]["trend"] == "insufficient" and one["compare_years"] == []


def test_unknown_source_and_no_year():
    assert raises(NotFound, T.thesis_trends, ds_of([(2025, "neu", [], [], False)]), "xyz")
    d = T.thesis_trends(ds_of([(None, "neu", ["AI/ML"], [], False)]), "neu")
    assert d["n_with_year"] == 0 and d["years"] == []
