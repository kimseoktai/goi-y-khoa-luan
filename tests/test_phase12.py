"""Kiểm thử backend trên bộ dữ liệu nhỏ tự tạo (không đụng dữ liệu thật). Embedding dùng backend 'hash' chỉ để thử luồng."""
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

from backend.database.store import DataStore
from backend.errors import BadRequest, NotFound, Unavailable
from backend.services import catalog_service as C, matching_service as MS, novelty_service as NS, recommendation_service as RS
from ml.embedding.embedder import Embedder


def make_root(with_embeddings=True):
    root = Path(tempfile.mkdtemp())
    for d in ("data/repository", "data/processed/jobs", "data/processed/thesis", "data/processed/embeddings", "data/processed/market"):
        (root / d).mkdir(parents=True)
    pd.DataFrame(dict(topic_id=["T1", "T2", "T3"], topic_name=["AI/ML", "Web Development", "Database"], description="d", keywords="a|b",
                      examples="x", status=["active", "active", "candidate"], created_at="x", version="taxonomy_v1.1")).to_csv(root / "data/repository/technical_topics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dict(domain_id=["D1", "D2"], domain_name=["Education", "Finance & Banking"], description="d", keywords="a",
                      examples="x", status="active", created_at="x", version="taxonomy_v1.1")).to_csv(root / "data/repository/domains.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dict(skill_name=["Python", "React", "SQL"], topic_name=["AI/ML", "Web Development", "Database"], weight=1.0, status="draft")).to_csv(root / "data/repository/skill_topic_map.csv", index=False, encoding="utf-8-sig")
    J = lambda x: json.dumps(x, ensure_ascii=False)
    jobs = pd.DataFrame([
        dict(job_id=1, job_title="AI Engineer", company="A", url="u", description="python ml education", skills=J(["Python", "SQL"]), technologies=J(["Python"]), competencies=J([]),
             technical_topics=J(["AI/ML", "Database"]), technical_topic_scores=J({"AI/ML": 1.0, "Database": 0.5}), topic_evidence=J({}), domains=J(["Education"]), domain_scores=J({"Education": 1.0}), domain_evidence=J({})),
        dict(job_id=2, job_title="Frontend Dev", company="B", url="u", description="react web", skills=J(["React"]), technologies=J(["React"]), competencies=J([]),
             technical_topics=J(["Web Development"]), technical_topic_scores=J({"Web Development": 1.0}), topic_evidence=J({}), domains=J([]), domain_scores=J({}), domain_evidence=J({})),
        dict(job_id=3, job_title="Office Admin", company="C", url="u", description="paperwork", skills=J([]), technologies=J([]), competencies=J([]),
             technical_topics=J([]), technical_topic_scores=J({}), topic_evidence=J({}), domains=J([]), domain_scores=J({}), domain_evidence=J({}))])
    jobs["review_flag"] = np.nan; jobs["taxonomy_version"] = "taxonomy_v1.1"; jobs["method"] = "rules"
    titles = ["Ứng dụng học máy trong giáo dục", "Website bán hàng bằng React", "Hệ thống quản lý cơ sở dữ liệu", "Chatbot học tập thông minh", "Dự báo điểm sinh viên bằng học máy", "Ứng dụng web quản lý lớp học"]
    tt = [["AI/ML"], ["Web Development"], ["Database"], ["AI/ML"], ["AI/ML"], ["Web Development"]]
    td = [["Education"], [], [], ["Education"], ["Education"], ["Education"]]
    th = pd.DataFrame(dict(thesis_id=range(101, 107), title=titles, year=2025.0, source="s", technical_topics=[J(x) for x in tt],
                           technical_topic_scores=[J({k: 1.0 for k in x}) for x in tt], topic_confidence=1.0, domains=[J(x) for x in td],
                           domain_scores=[J({k: 1.0 for k in x}) for x in td], domain_confidence=1.0, keywords=J(["k"]), label_source="gold", in_gold=True,
                           review_flag=np.nan, taxonomy_version="taxonomy_v1.1", topic_model_version="v1.2", domain_model_version="v1.2", dataset_version="gold_v2.1"))
    jobs.to_csv(root / "data/processed/jobs/jobs_processed.csv", index=False, encoding="utf-8-sig")
    th.to_csv(root / "data/processed/thesis/thesis_processed.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dict(item=["AI/ML"], rank=1, job_count=2, share=0.5, ci_low=0.2, ci_high=0.8, n_companies=2, top_company_share=0.5, support_ok=False, concentrated=False)).to_csv(root / "data/processed/market/demand_topics.csv", index=False, encoding="utf-8-sig")
    if with_embeddings:
        emb = Embedder("x", "hash")
        d = root / "data/processed/embeddings"
        np.save(d / "jobs_hash256.npy", emb.encode((jobs.job_title + ". " + jobs.description).tolist())); pd.DataFrame(dict(id=jobs.job_id)).to_csv(d / "jobs_hash256_index.csv", index=False)
        np.save(d / "thesis_hash256.npy", emb.encode(titles)); pd.DataFrame(dict(id=th.thesis_id)).to_csv(d / "thesis_hash256_index.csv", index=False)
    return root


def store(with_embeddings=True):
    return DataStore(make_root(with_embeddings), "x", "hash")


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    return False


def test_catalog_lists_filters_and_404():
    ds = store()
    assert [t["topic_name"] for t in C.list_topics(ds, "active")] == ["AI/ML", "Web Development"]
    r = C.list_jobs(ds, topic="AI/ML"); assert r["total"] == 1 and r["items"][0]["job_id"] == 1
    assert C.list_jobs(ds, role="AI Engineer")["total"] == 1 and C.list_jobs(ds, role="AI")["total"] == 0   # role khớp đúng, không khớp một phần
    assert C.list_jobs(ds, q="frontend")["total"] == 1 and C.list_jobs(ds, limit=1)["items"].__len__() == 1
    assert C.get_job(ds, 1)["technical_topic_scores"]["AI/ML"] == 1.0
    assert C.list_thesis(ds, domain="Education")["total"] == 4 and C.get_thesis(ds, 101)["title"].startswith("Ứng dụng")
    assert raises(NotFound, C.get_job, ds, 999) and raises(NotFound, C.get_thesis, ds, 1)
    assert raises(BadRequest, C.list_jobs, ds, limit=0) and raises(BadRequest, C.market_table, ds, "nope")
    assert C.market_table(ds, "demand_topics", only_supported=True)["total"] == 0 and C.market_table(ds, "demand_topics")["total"] == 1


def test_thesis_list_sorts_by_year_and_title():
    ds = store()
    new = [t["year"] or 0 for t in C.list_thesis(ds, sort="new")["items"]]
    old = [t["year"] or 9999 for t in C.list_thesis(ds, sort="old")["items"]]
    az = [t["title"].lower() for t in C.list_thesis(ds, sort="az")["items"]]
    assert new == sorted(new, reverse=True) and old == sorted(old) and az == sorted(az)
    assert raises(BadRequest, C.list_thesis, ds, sort="lung-tung")


def test_matching_ranks_label_sharing_thesis_and_validates_weights():
    ds = store()
    r = MS.match_job(ds, 1, top_k=3)
    assert len(r["items"]) == 3 and r["items"][0]["score"] >= r["items"][-1]["score"] and r["semantic_used"]
    assert "AI/ML" in r["items"][0]["shared_topics"]
    assert raises(BadRequest, MS.match_job, ds, 1, 3, {"topic": -1}) and raises(BadRequest, MS.match_job, ds, 1, 3, {"bogus": 1})
    assert raises(BadRequest, MS.match_job, ds, 1, 0) and raises(NotFound, MS.match_job, ds, 77)
    only_topic = MS.match_job(ds, 1, 3, {"topic": 1, "domain": 0, "semantic": 0})
    assert only_topic["items"][0]["score"] == only_topic["items"][0]["topic_match"]
    assert len(MS.similar_thesis(ds, 101, 3)["items"]) == 3 and MS.similar_thesis(ds, 101, 3)["items"][0]["thesis_id"] != 101


def test_novelty_check_text_and_thesis():
    ds = store()
    r = NS.check_text(ds, "Website bán hàng bằng React", ["Web Development"], [])
    assert r["max_similarity"] > 0.99 and r["nearest_thesis"]["thesis_id"] == 102 and r["novelty_status"] in ("Duplicate", "Similar")
    assert r["combo_support"] == 2 and r["thresholds"]["source"]
    far = NS.check_text(ds, "zzzz qqqq xxxx", [], [])
    assert far["max_similarity"] < r["max_similarity"] and far["novelty_score"] >= r["novelty_score"]
    assert raises(BadRequest, NS.check_text, ds, "  ") and raises(BadRequest, NS.check_text, ds, "ok", ["Không có topic"])
    assert raises(BadRequest, NS.check_text, ds, "x" * 600) and raises(BadRequest, NS.check_text, ds, "ok", top_k=0)
    t = NS.check_thesis(ds, 101)
    assert t["thesis_id"] == 101 and t["nearest_thesis"]["thesis_id"] != 101
    n0 = r["top_neighbors"][0]                     # năm và trường để giao diện hiển thị
    assert "year" in n0 and "source" in n0 and "year" in r["nearest_thesis"] and "source" in r["nearest_thesis"]


def test_recommendation_with_and_without_embeddings():
    ds = store()
    r = RS.recommend(ds, 1, top_k=3)
    assert r["items"] and r["semantic_used"] and all(i["explanation"] and i["components"]["topic"] is not None for i in r["items"])
    assert all(set(i["direction_topics"]) <= {"AI/ML", "Database"} for i in r["items"])          # chỉ Topic của Job
    assert r["items"][0]["recommendation_score"] >= r["items"][-1]["recommendation_score"]
    empty = RS.recommend(ds, 3)
    assert empty["items"] == [] and "chưa có Technical Topic" in empty["message"]
    assert raises(BadRequest, RS.recommend, ds, 1, 5, {"topic": -1}) and raises(BadRequest, RS.recommend, ds, 1, 5, None, 2.0)
    assert raises(BadRequest, RS.recommend, ds, 1, 5, None, 0.0, "bogus") and raises(NotFound, RS.recommend, ds, 99)
    ds2 = store(with_embeddings=False)
    r2 = RS.recommend(ds2, 1, top_k=2)
    assert not r2["semantic_used"] and r2["weights"]["semantic"] == 0 and r2["items"]
    assert raises(Unavailable, NS.check_text, ds2, "abc") and raises(Unavailable, MS.match_job, ds2, 1)
    assert MS.match_job(ds2, 1, 2, use_semantic=False)["semantic_used"] is False


def test_versions_and_health_data():
    ds = store()
    v = ds.versions()
    assert v["taxonomy_version"] == "taxonomy_v1.1" and v["thesis_topic_model"] == "v1.2" and ds.has_embeddings()
    assert not store(False).has_embeddings()


def test_routes_if_fastapi_available():
    try:
        from fastapi.testclient import TestClient
        from backend.main import create_app
    except Exception:
        print("  (bỏ qua test route: chưa cài fastapi/httpx)")
        return
    c = TestClient(create_app(store()))
    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/jobs/1").status_code == 200 and c.get("/jobs/999").status_code == 404
    assert c.get("/jobs?limit=0").status_code == 422
    assert c.get("/recommendations/jobs/1?top_k=2").json()["items"]
    assert c.get("/recommendations/jobs/1?w_topic=-1").status_code == 422
    assert c.post("/novelty/check", json={"title": "Website bán hàng bằng React"}).json()["nearest_thesis"]["thesis_id"] == 102
    assert c.post("/novelty/check", json={"title": ""}).status_code == 400
    assert c.get("/matching/jobs/1").status_code == 200
