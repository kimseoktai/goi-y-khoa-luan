"""Kiểm thử GVHD: tách tên, lưu từ crawl và từ admin, không lấy tên sinh viên, gợi ý theo chủ đề/lĩnh vực/nghĩa. Dữ liệu và tên đều là giả."""
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from backend.errors import BadRequest, Unavailable
from backend.services import advisor_service as AV
from ml.thesisdb import admin, advisors, db, neu
from tests.test_thesisdb import page


def test_split_and_clean_names():
    assert advisors.split_names("TS. Nguyễn Văn An; ThS Trần Thị Bình") == ["Nguyễn Văn An", "Trần Thị Bình"]
    assert advisors.split_names([{"name": "PGS.TS. Lê Văn C"}, "an"]) == ["Lê Văn C"]          # tên một từ bị bỏ
    assert advisors.split_names(None) == [] and advisors.split_names("") == []
    assert advisors.key("Nguyễn Đức") == advisors.key("nguyen duc")


def test_parse_takes_advisor_but_never_student_field():
    item = [("n1", "Hệ thống quản lý thư viện", 2023, None, None)]
    recs, _ = neu.parse(page(item, extra={"GVHD": "TS. Phạm Văn D"}))                       # tên trường thật của trang NEU
    assert recs[0]["advisors"] == ["Phạm Văn D"]
    old = neu.ADVISOR_KEY
    neu.ADVISOR_KEY = None                                                                  # chế độ tự dò
    try:
        assert neu.parse(page(item, extra={"giangVienHuongDan": "TS. Phạm Văn D"}))[0][0]["advisors"] == ["Phạm Văn D"]
        assert neu.parse(page(item, extra={"tenSinhVien": "Nguyễn Văn E"}))[0][0]["advisors"] == []
    finally:
        neu.ADVISOR_KEY = old


def test_upsert_keeps_advisors_unless_locked_or_empty():
    con = db.connect(":memory:")
    db.upsert_thesis(con, "neu", "n1", "Hệ thống quản lý thư viện", 2023, advisors=["Phạm Văn D"])
    row = con.execute("SELECT thesis_id FROM thesis_raw WHERE source_thesis_id='n1'").fetchone()
    assert db.advisors_of(con, row["thesis_id"]) == ["Phạm Văn D"]
    db.upsert_thesis(con, "neu", "n1", "Hệ thống quản lý thư viện", 2023, advisors=[])          # trang không còn GVHD: giữ bản cũ
    assert db.advisors_of(con, row["thesis_id"]) == ["Phạm Văn D"]
    db.upsert_thesis(con, "neu", "n1", "Hệ thống quản lý thư viện", 2023, advisors=["Lê Văn C"])
    assert db.advisors_of(con, row["thesis_id"]) == ["Lê Văn C"]
    admin.update(con, row["thesis_id"], advisors="Trần Thị B; Võ Văn F")
    db.upsert_thesis(con, "neu", "n1", "Hệ thống quản lý thư viện", 2023, advisors=["Lê Văn C"])   # đã khóa: crawl không ghi đè
    assert db.advisors_of(con, row["thesis_id"]) == ["Trần Thị B", "Võ Văn F"]
    out = pd.read_csv(_export(con))
    assert json.loads(out.loc[out.thesis_id == row["thesis_id"], "advisors"].iloc[0]) == ["Trần Thị B", "Võ Văn F"]


def _export(con):
    import tempfile, os
    p = os.path.join(tempfile.mkdtemp(), "t.csv")
    db.export_csv(con, p)
    return p


def test_admin_add_with_advisors_and_clear():
    con = db.connect(":memory:")
    tid = admin.add(con, "Ứng dụng học máy dự đoán giá nhà", 2024, advisors="TS. Nguyễn Văn An")
    assert db.advisors_of(con, tid) == ["Nguyễn Văn An"]
    assert admin.update(con, tid, advisors="") is True and db.advisors_of(con, tid) == []
    assert admin.update(con, tid, advisors="") is False


def ds_of():
    ml_, web = "AI/ML", "Web Development"
    rows = [  # (nguồn, năm, topics, domains, GVHD)
        ("neu", 2022, [ml_], ["Education"], ["An"]), ("neu", 2023, [ml_], [], ["An"]), ("neu", 2024, [ml_], ["Education"], ["An"]),
        ("neu", 2024, [web], [], ["Bình"]), ("neu", 2023, [ml_], [], ["Bình"]), ("neu", 2024, [web], [], ["Bình"]),
        ("neu", 2024, [ml_], [], ["Chi"]), ("uit", 2024, [ml_], [], ["Dũng"]), ("neu", 2024, [web], [], []),
    ]
    t = pd.DataFrame(dict(thesis_id=[f"t{i}" for i in range(len(rows))], title=[f"Đề tài {i}" for i in range(len(rows))], year=[r[1] for r in rows], source=[r[0] for r in rows]))
    t["_technical_topics"], t["_domains"], t["_advisors"] = [r[2] for r in rows], [r[3] for r in rows], [r[4] for r in rows]
    cache = {}
    E = np.eye(len(rows), dtype=np.float32)
    ds = NS(thesis=t, topics=pd.DataFrame(dict(topic_name=["AI/ML", "Web Development"])), domains=pd.DataFrame(dict(domain_name=["Education"])),
            cached=lambda k, f: cache.setdefault(k, f()), thesis_vectors=lambda: E, encode=lambda xs: np.array([E[0]]))
    return ds


def test_index_is_neu_only_and_listing():
    d = AV.list_advisors(ds_of())
    assert [r["advisor"] for r in d["items"]] == ["An", "Bình", "Chi"]                       # Dũng thuộc trường khác
    assert d["items"][0]["n_theses"] == 3 and d["items"][0]["latest_year"] == 2024 and d["items"][0]["top_topics"] == ["AI/ML"]
    assert AV.list_advisors(ds_of(), q="bình")["total"] == 1


def test_recommend_by_topic_prefers_more_matching_theses():
    r = AV.recommend(ds_of(), topic="AI/ML")
    assert [x["advisor"] for x in r["items"]][:2] == ["An", "Chi"] or r["items"][0]["advisor"] == "An"
    assert r["items"][0]["advisor"] == "An" and r["items"][0]["n_topic"] == 3 and r["semantic"] is False
    assert "không phải phân công" in r["caveat"]
    names = [x["advisor"] for x in r["items"]]
    assert "Dũng" not in names and len(r["items"][0]["nearest"]) == 3


def test_recommend_semantic_and_domain():
    r = AV.recommend(ds_of(), topic="Web Development", text="một đề tài")                    # vector gần nhất là t0 (của An)
    assert r["semantic"] is True and r["items"][0]["advisor"] in ("Bình", "An")
    r2 = AV.recommend(ds_of(), domains=["Education"])
    assert r2["items"][0]["advisor"] == "An" and r2["items"][0]["n_domain"] == 2


def test_recommend_errors():
    with pytest.raises(BadRequest):
        AV.recommend(ds_of())
    with pytest.raises(BadRequest):
        AV.recommend(ds_of(), topic="Không có")
    with pytest.raises(BadRequest):
        AV.recommend(ds_of(), topic="AI/ML", top_k=0)
    ds = ds_of(); ds.thesis["_advisors"] = [[] for _ in range(len(ds.thesis))]
    with pytest.raises(Unavailable):
        AV.recommend(ds, topic="AI/ML")


def _ds_rows(rows):
    t = pd.DataFrame(dict(thesis_id=[f"t{i}" for i in range(len(rows))], title=[f"Đề tài {i}" for i in range(len(rows))], year=[r[0] for r in rows], source=["neu"] * len(rows)))
    t["_technical_topics"], t["_domains"], t["_advisors"] = [r[1] for r in rows], [[] for _ in rows], [r[2] for r in rows]
    cache = {}
    return NS(thesis=t, topics=pd.DataFrame(dict(topic_name=["AI/ML", "Web Development"])), domains=pd.DataFrame(dict(domain_name=["Education"])),
              cached=lambda k, f: cache.setdefault(k, f()), thesis_vectors=lambda: np.eye(len(rows), dtype=np.float32), encode=lambda xs: np.array([np.eye(len(rows))[0]]))


def test_more_experience_beats_small_perfect_share():
    ml_, web = ["AI/ML"], ["Web Development"]
    rows = [(2024, ml_, ["Lâm"])] * 2 + [(2023, ml_, ["Minh"])] * 14 + [(2022, web, ["Minh"])] * 22        # Lâm 2/2 (100%), Minh 14/36 (39%)
    r = AV.recommend(_ds_rows(rows), topic="AI/ML")
    assert [x["advisor"] for x in r["items"]] == ["Minh", "Lâm"]
    assert r["items"][0]["n_related"] == 14 and r["items"][0]["level"] == "strong" and r["items"][1]["level"] == "ok"
    assert r["low_data"] is False


def test_thin_topic_is_flagged():
    rows = [(2024, ["AI/ML"], ["Lâm"]), (2023, ["Web Development"], ["Minh"])]
    r = AV.recommend(_ds_rows(rows), topic="AI/ML")
    assert r["low_data"] is True and "rất ít khóa luận" in r["caveat"] and r["items"][0]["level"] == "weak"


def test_advisor_without_same_topic_thesis_is_excluded_even_with_semantic():
    rows = [(2024, ["AI/ML"], ["Lâm"]), (2023, ["Web Development"], ["Minh"]), (2022, ["Web Development"], ["Nam"])]
    r = AV.recommend(_ds_rows(rows), topic="AI/ML", text="một đề tài")             # có embedding nhưng Minh và Nam không có bài AI/ML
    assert r["semantic"] is True and [x["advisor"] for x in r["items"]] == ["Lâm"]


def test_same_domain_but_other_topic_is_excluded_when_topic_given():
    rows = [(2024, ["AI/ML"], ["Lâm"]), (2023, ["Web Development"], ["Minh"])]
    ds = _ds_rows(rows); ds.thesis["_domains"] = [["Education"], ["Education"]]
    r = AV.recommend(ds, topic="AI/ML", domains=["Education"])                  # Minh cùng lĩnh vực nhưng không có bài AI/ML
    assert [x["advisor"] for x in r["items"]] == ["Lâm"]
