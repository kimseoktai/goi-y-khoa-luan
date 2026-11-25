"""Kiểm thử route FastAPI trên dữ liệu nhỏ tự tạo (cần: pip install fastapi httpx). Không cần server chạy, không đụng dữ liệu thật.
  python -c "import sys; sys.path.insert(0,'.'); import tests.test_api_routes as m; [getattr(m,n)() for n in dir(m) if n.startswith('test_')]; print('xong')"
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient                       # noqa: E402

from backend.main import create_app                             # noqa: E402
from backend.settings import Settings                           # noqa: E402
from tests.test_phase12 import store                            # noqa: E402


def client(with_embeddings=True, **kw):
    return TestClient(create_app(store(with_embeddings), Settings()), **kw)


def test_system_and_docs():
    c = client()
    h = c.get("/health").json()
    assert h["status"] == "ok" and h["jobs"] == 3 and h["thesis"] == 6 and h["embeddings"] is True
    assert c.get("/meta/versions").json()["taxonomy_version"] == "taxonomy_v1.1"
    paths = c.get("/openapi.json").json()["paths"]
    assert "/recommendations/jobs/{job_id}" in paths and "/novelty/check" in paths and c.get("/docs").status_code == 200


def test_catalog_validation_codes():
    c = client()
    assert c.get("/jobs?limit=0").status_code == 422 and c.get("/jobs?limit=999").status_code == 422 and c.get("/jobs?offset=-1").status_code == 422
    assert c.get("/jobs?topic=AI/ML").json()["total"] == 1
    assert c.get("/jobs/1").json()["job_title"] == "AI Engineer" and c.get("/jobs/999").status_code == 404
    assert c.get("/thesis/101").status_code == 200 and c.get("/thesis/1").status_code == 404
    assert c.get("/market/demand_topics").json()["total"] == 1 and c.get("/market/bogus").status_code == 400
    assert c.get("/taxonomy/topics?status=candidate").json()[0]["topic_name"] == "Database"


def test_matching_and_similar():
    c = client()
    r = c.get("/matching/jobs/1?top_k=3").json()
    assert len(r["items"]) == 3 and r["items"][0]["score"] >= r["items"][2]["score"]
    assert c.get("/matching/jobs/1?w_topic=-1").status_code == 422 and c.get("/matching/jobs/99").status_code == 404
    assert c.get("/thesis/101/similar?top_k=2").json()["items"][0]["thesis_id"] != 101
    assert c.get("/thesis/101/novelty").json()["novelty_status"] in ("Novel", "Similar", "Duplicate")


def test_novelty_post_cases():
    c = client()
    ok = c.post("/novelty/check", json={"title": "Website bán hàng bằng React", "topics": ["Web Development"], "top_k": 2})
    assert ok.status_code == 200 and ok.json()["nearest_thesis"]["thesis_id"] == 102 and ok.json()["combo_support"] == 2
    assert c.post("/novelty/check", json={"title": "  "}).status_code == 400
    assert c.post("/novelty/check", json={"title": "ok", "topics": ["Sai"]}).status_code == 400
    assert c.post("/novelty/check", json={"title": "x" * 600}).status_code == 400
    assert c.post("/novelty/check", json={}).status_code == 422 and c.post("/novelty/check", json={"title": "a", "top_k": 99}).status_code == 422


def test_recommendations_cases():
    c = client()
    r = c.get("/recommendations/jobs/1?top_k=3").json()
    assert r["items"] and all(set(i["direction_topics"]) <= {"AI/ML", "Database"} for i in r["items"])
    assert c.get("/recommendations/jobs/3").json()["items"] == []
    for q in ("w_topic=-1", "mmr=2", "novelty_mode=bogus", "top_k=0"):
        assert c.get("/recommendations/jobs/1?" + q).status_code == 422
    assert c.get("/recommendations/jobs/99").status_code == 404
    only = c.get("/recommendations/jobs/1?w_topic=1&w_job_relevance=0&w_domain=0&w_semantic=0&w_novelty=0").json()["items"]
    assert all(abs(i["recommendation_score"] - i["components"]["topic"]) < 1e-3 for i in only)


def test_503_without_embeddings_and_graceful_degradation():
    c = client(with_embeddings=False)
    assert c.get("/health").json()["embeddings"] is False
    assert c.post("/novelty/check", json={"title": "abc"}).status_code == 503 and c.get("/matching/jobs/1").status_code == 503
    assert c.get("/matching/jobs/1?use_semantic=false").status_code == 200
    r = c.get("/recommendations/jobs/1").json()
    assert r["semantic_used"] is False and r["items"]


def test_unhandled_error_is_hidden_and_cors_present():
    import backend.routes.analysis as A
    c = client(raise_server_exceptions=False)
    orig = A.recommendation_service.recommend
    A.recommendation_service.recommend = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bí mật nội bộ"))
    try:
        r = c.get("/recommendations/jobs/1")
    finally:
        A.recommendation_service.recommend = orig
    assert r.status_code == 500 and "bí mật nội bộ" not in r.text
    assert c.get("/health", headers={"Origin": "http://localhost:5173"}).headers.get("access-control-allow-origin")


def test_overview_route():
    c = TestClient(create_app(store()))
    r = c.get("/overview")
    assert r.status_code == 200 and r.json()["kpis"]["n_jobs"] == 3 and r.json()["topics"]
    assert c.get("/overview?n_topics=0").status_code == 422


def test_admin_roles_auth():
    from backend.services import role_service as R
    R.MIN_SUPPORT, R.MIN_COMPANIES = 1, 1
    off = client(False)
    assert off.get("/roles").status_code == 200
    assert off.get("/admin/roles").status_code == 403                      # chưa đặt REC_ADMIN_TOKEN: tắt hẳn
    on = TestClient(create_app(store(False), Settings(admin_token="s3")))
    assert on.get("/admin/roles").status_code == 401 and on.get("/admin/roles", headers={"X-Admin-Token": "sai"}).status_code == 401
    H = {"X-Admin-Token": "s3"}
    assert on.get("/admin/roles", headers=H).status_code == 200
    assert on.post("/admin/roles/decision", json={"role": "Frontend Dev", "action": "merge", "parent": "AI Engineer"}).status_code == 401
    r = on.post("/admin/roles/decision", headers=H, json={"role": "Frontend Dev", "action": "merge", "parent": "AI Engineer"})
    assert r.status_code == 200 and len(r.json()["pending"]) == 1
    assert on.post("/admin/roles/decision", headers=H, json={"role": "Frontend Dev", "action": "x"}).status_code == 400


def test_direction_routes():
    c = TestClient(create_app(store(True), Settings(gemini_api_key="", llm_timeout=2)))
    r = c.post("/recommendations/jobs/1/related", json={"topics": ["AI/ML"], "domains": ["Education"]})
    assert r.status_code == 200 and r.json()["technologies"] == ["Python"] and len(r.json()["related_theses"]) == 3
    assert c.post("/recommendations/jobs/1/related", json={"topics": []}).status_code == 422
    assert c.post("/recommendations/jobs/1/related", json={"topics": ["Không có"]}).status_code == 400
    assert c.post("/recommendations/jobs/999/related", json={"topics": ["AI/ML"]}).status_code == 404
    t = c.post("/recommendations/jobs/1/titles", json={"topics": ["AI/ML"]})                  # chưa có khóa Gemini: báo rõ, không lỗi 500
    assert t.status_code == 503 and "Gemini" in t.json()["detail"]
    assert c.post("/recommendations/jobs/1/titles", json={"topics": ["AI/ML"], "n": 9}).status_code == 422


def test_student_routes():
    from tests.test_student import setup
    ds = setup(True)
    c = TestClient(create_app(ds, Settings(gemini_api_key="", llm_timeout=2)))
    assert c.get("/student/overview").json()["n_jobs"] == 3
    assert c.get("/student/roles").json()["items"][0]["name"] and c.get("/student/skills").status_code == 200 and "topics" in c.get("/student/labels").json()
    p = c.post("/student/profile", json=dict(skills=["Python"])).json()
    assert p["known"] == ["Python"] and p["roles"][0]["match"] >= 0
    r = c.post("/student/ideas", json=dict(roles=["AI Engineer"], n=2)).json()
    assert len(r["items"]) == 2 and r["items"][0]["technologies"]
    assert c.post("/student/ideas", json=dict(roles=[])).status_code == 422 and c.post("/student/ideas", json=dict(roles=["Không có"])).status_code == 404
    assert c.post("/student/ideas", json=dict(roles=["a", "b", "c", "d"])).status_code == 422
    t = c.post("/student/ideas/title", json=dict(roles=["AI Engineer"], topic="AI/ML"))
    assert t.status_code == 503                                  # không có khóa Gemini trong môi trường kiểm thử: báo rõ, không lỗi 500
    assert c.get("/student/jobs?role=AI Engineer").json()["total"] == 1 and c.get("/student/jobs?role=Không có").status_code == 404
    assert c.get("/student/jobs").status_code == 422
