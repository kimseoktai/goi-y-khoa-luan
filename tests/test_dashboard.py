"""Kiểm thử dashboard xu hướng khóa luận: lọc, KPI, tăng trưởng, cơ cấu cộng đủ 100%, chủ đề mới nổi, lỗi tham số. Dữ liệu giả."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd                                              # noqa: E402

from backend.errors import BadRequest, NotFound                  # noqa: E402
from backend.services import dashboard_service as D              # noqa: E402
from tests.test_phase12 import raises                            # noqa: E402


def ds_of(rows):
    """rows: (năm, nguồn, [topic], [domain])"""
    t = pd.DataFrame([dict(thesis_id=i, year=r[0], source=r[1]) for i, r in enumerate(rows)])
    t["_technical_topics"], t["_domains"] = [r[2] for r in rows], [r[3] for r in rows]
    return NS(thesis=t, topics=pd.DataFrame(dict(topic_name=["AI/ML", "Web Development", "Generative AI & LLM"], status="active")),
              domains=pd.DataFrame(dict(domain_name=["Education", "Finance & Banking"], status="active")))


ROWS = ([(2023, "neu", ["Web Development"], ["Education"])] * 40 + [(2023, "neu", ["AI/ML"], ["Finance & Banking"])] * 10
        + [(2024, "neu", ["AI/ML"], ["Education"])] * 30 + [(2024, "neu", ["Generative AI & LLM"], [])] * 8 + [(2024, "neu", ["Web Development"], [])] * 12
        + [(2024, "uit", ["AI/ML"], [])] * 5 + [(2024, "neu", [], [])] * 2)


def test_kpi_and_filters():
    d = D.dashboard(ds_of(ROWS))
    assert d["kpi"]["total"] == 102 and d["kpi"]["in_range"] == 102 and d["kpi"]["years_label"] == "2023–2024"
    assert d["kpi"]["n_topics"] == 3 and d["kpi"]["n_domains"] == 2                        # bài của trường khác không tính
    one = D.dashboard(ds_of(ROWS), year_from=2024, year_to=2024)
    assert one["kpi"]["in_range"] == 52 and one["kpi"]["single_year"] and one["kpi"]["total"] == 102
    f = D.dashboard(ds_of(ROWS), domain="Education", topic="AI/ML")
    assert f["kpi"]["in_range"] == 30 and f["kpi"]["n_topics"] == 1 and [y["n"] for y in f["years"]] == [0, 30]


def test_domain_mix_sums_to_one_and_reports_unlabelled():
    d = D.dashboard(ds_of(ROWS))
    assert abs(sum(x["share"] for x in d["domain_mix"]) - 1) < 1e-9 and d["domain_mix"][0]["name"] == "Education"
    assert d["no_domain"] == 22


def test_domain_topic_pairs():
    d = D.dashboard(ds_of(ROWS))
    edu = next(x for x in d["domain_topic"] if x["domain"] == "Education")
    assert edu["count"] == 70 and {t["name"]: t["count"] for t in edu["topics"]} == {"Web Development": 40, "AI/ML": 30}
    assert [x["domain"] for x in d["domain_topic"]] == ["Education", "Finance & Banking"]


def test_growth_top5_and_emerging():
    d = D.dashboard(ds_of(ROWS))
    ml = next(x for x in d["top5"] if x["name"] == "AI/ML")
    assert ml["count"] == 40 and ml["change_pp"] > 0 and ml["common_domains"][0]["name"] == "Education"       # 2024: 30/52 so với 2023: 10/50
    em = {e["name"]: e for e in d["emerging"]}
    assert em["Generative AI & LLM"]["reason"] == "new" and em["Generative AI & LLM"]["first_year"] == 2024
    assert "Web Development" not in em                                                    # đã có từ 2023 và không tăng
    assert D.dashboard(ds_of(ROWS), year_from=2024, year_to=2024)["top5"][0]["change_pp"] is None   # một năm: không so được


def test_errors():
    raises(BadRequest, lambda: D.dashboard(ds_of(ROWS), year_from=2025, year_to=2023))
    raises(BadRequest, lambda: D.dashboard(ds_of(ROWS), view="x"))
    raises(BadRequest, lambda: D.dashboard(ds_of(ROWS), topic="Không có"))
    raises(NotFound, lambda: D.dashboard(ds_of(ROWS), source="zzz"))
