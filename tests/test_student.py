"""Kiểm thử dữ liệu cho giao diện sinh viên (bộ dữ liệu nhỏ tự tạo; ngưỡng được hạ để thử). LLM giả."""
import pandas as pd

from backend.errors import BadRequest, NotFound, Unavailable
from backend.services import role_service as R, student_service as S
from ml.generation import llm_client as OC
from tests.test_phase12 import raises, store
from tests.test_ideas import fake


def setup(with_emb=False):
    R.MIN_SUPPORT, R.MIN_COMPANIES = 1, 1
    S.CORE_MIN_JOBS, S.PATH_MIN_JOBS, S.FIT_MIN_JOBS, S.DOMAIN_MIN_JOBS = 1, 1, 1, 1
    ds = store(with_emb)
    pd.DataFrame(dict(skill_name=["Python", "SQL", "React"], category=["Programming Language", "Database", "Framework / Library"])).to_csv(
        ds.root / "data/repository/skills.csv", index=False, encoding="utf-8-sig")
    return ds


def test_overview_roles_and_skill_groups():
    ds = setup()
    o = S.overview(ds)
    assert o["n_jobs"] == 3 and o["n_thesis"] == 6 and o["years"] == [2025]
    assert {r["name"] for r in o["hot_roles"]} == {"AI Engineer", "Frontend Dev", "Office Admin"}
    assert {s["name"] for s in o["top_skills"]} == {"Python", "SQL", "React"} and o["top_skills"][0]["share"] == round(1 / 3, 4)
    assert S.roles(ds)["items"][0]["hot"] is True and S.roles(ds)["max_roles"] == 3
    g = S.skill_groups(ds, min_count=1)
    assert {x["category"] for x in g["groups"]} == {"Programming Language", "Database", "Framework / Library"}
    assert all(x["skills"] for x in g["groups"]) and S.skill_groups(ds)["groups"] == []            # mặc định cần >= 3 tin


def test_generic_skill_hidden_from_picker():
    ds = setup()
    (ds.root / "data/repository/skill_generic.csv").write_text("skill_name,reason\nSQL,chung\n", encoding="utf-8")
    names = {s["name"] for g in S.skill_groups(ds, min_count=1)["groups"] for s in g["skills"]}
    assert "SQL" not in names and {"Python", "React"} <= names
    assert S.profile(ds, ["SQL"])["ignored"] == ["SQL"]            # cùng danh mục với phân tích: khái niệm chung không còn là kỹ năng chọn được


def test_profile_match_and_path():
    ds = setup()
    p = S.profile(ds, ["python", "Python", "Không có"])
    assert p["known"] == ["Python"] and p["ignored"] == ["Không có"]
    assert [(g["category"], g["skills"]) for g in p["groups"]] == [("Programming Language", ["Python"])]
    ai = next(r for r in p["roles"] if r["role"] == "AI Engineer")
    assert ai["have"] == ["Python"] and [m["name"] for m in ai["missing"]] == ["SQL"] and ai["match"] == 0.5     # 1/2 kỹ năng cốt lõi
    assert p["roles"][0]["role"] == "AI Engineer" and [x["name"] for x in p["path"]][0] in ("SQL", "React")
    assert next(x for x in p["path"] if x["name"] == "SQL")["near"] == "Python"
    assert S.profile(ds, [])["roles"][0]["match"] == 0.0
    assert raises(BadRequest, S.profile, ds, [str(i) for i in range(81)])


def test_ideas_directions_and_errors():
    ds = setup()
    r = S.ideas(ds, ["AI Engineer", "Frontend Dev"], 0, 3)
    assert r["n_jobs"] == 2 and r["total_directions"] == 3 and len(r["items"]) == 3
    ai = next(x for x in r["items"] if x["topic"] == "AI/ML")
    assert ai["fit"] == 1 and ai["fit_total"] == 2 and ai["technologies"][0] == "Python" and ai["domains"] == ["Education"]
    assert {t["thesis_id"] for t in ai["related_theses"]} == {101, 104, 105} and ai["same_topic_theses"] == 3
    assert len(S.ideas(ds, ["AI Engineer"], 1, 1)["items"]) == 1
    assert raises(BadRequest, S.ideas, ds, [], 0, 3) and raises(BadRequest, S.ideas, ds, ["a", "b", "c", "d"], 0, 3)
    assert raises(NotFound, S.ideas, ds, ["Không có"], 0, 3) and raises(BadRequest, S.ideas, ds, ["AI Engineer"], -1, 3)
    assert S.ideas(ds, ["Office Admin"], 0, 3)["items"] == [] and S.ideas(ds, ["Office Admin"], 0, 3)["message"]      # không có chủ đề -> thông báo, không lỗi


def test_idea_title_flow():
    ds = setup(True)
    ds.thresholds = dict(similar=0.9, duplicate=0.99, source="test")
    llm = fake([dict(title="Hệ thống gợi ý lộ trình học tập cá nhân hóa bằng học máy", why="ok", summary="Xây dựng mô hình gợi ý lộ trình học. Dùng dữ liệu học tập.")])
    r = S.idea_title(ds, llm, ["AI Engineer"], "AI/ML", avoid=["Một tên đã hiện"], n=1)
    assert isinstance(r["titles"][0]["tech"], list) and isinstance(r["titles"][0]["domain_labels"], list)
    assert r["titles"][0]["summary"].startswith("Xây dựng") and r["titles"][0]["novelty"]["status"] in ("Novel", "Similar")
    prompt = llm.calls[0][1]["content"]
    assert "Một tên đã hiện" in prompt and "Python" in prompt and "Ứng dụng học máy trong giáo dục" in prompt
    assert raises(BadRequest, S.idea_title, ds, llm, ["Frontend Dev"], "AI/ML")                     # chủ đề không thuộc các công việc đã chọn
    assert raises(NotFound, S.idea_title, ds, llm, ["AI Engineer"], "Không có")
    def down(msgs):
        raise OC.LLMUnavailable("tắt")
    assert raises(Unavailable, S.idea_title, ds, down, ["AI Engineer"], "AI/ML")


def test_jobs_of_role_hides_unsafe_url():
    ds = setup()
    j = S.jobs_of_role(ds, "AI Engineer", 5, 0)
    assert j["total"] == 1 and j["items"][0]["skills"] == ["Python", "SQL"] and j["items"][0]["url"] is None        # "u" không phải http(s)
    assert S._safe_url("javascript:alert(1)") is None and S._safe_url("https://a.vn/x") == "https://a.vn/x"
    assert raises(NotFound, S.jobs_of_role, ds, "Không có") and raises(BadRequest, S.jobs_of_role, ds, "AI Engineer", 0)
