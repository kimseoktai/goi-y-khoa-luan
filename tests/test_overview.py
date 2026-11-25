"""Kiểm thử /overview trên bộ dữ liệu nhỏ tự tạo (dùng lại make_root của test_phase12).
  python -c "import sys; sys.path.insert(0,'.'); import tests.test_overview as m; [getattr(m,n)() for n in dir(m) if n.startswith('test_')]; print('xong')"
"""
from backend.services import overview_service as O
from tests.test_phase12 import store


def test_overview_counts_and_shares():
    r = O.overview(store())
    k = r["kpis"]
    assert (k["n_jobs"], k["n_thesis"], k["n_topics"], k["n_domains"]) == (3, 6, 3, 2)
    assert k["jobs_with_topic"] == 2 and k["jobs_with_domain"] == 1 and k["thesis_with_year"] == 6
    t = {x["name"]: x for x in r["topics"]}
    assert t["AI/ML"]["job_count"] == 1 and t["AI/ML"]["thesis_count"] == 3
    assert abs(t["AI/ML"]["job_share"] - 1 / 3) < 1e-3 and abs(t["AI/ML"]["thesis_share"] - 0.5) < 1e-3
    assert 0 <= t["AI/ML"]["job_ci_low"] <= t["AI/ML"]["job_share"] <= t["AI/ML"]["job_ci_high"] <= 1
    assert t["AI/ML"]["support_ok"] is False            # 1 job < 10: không đủ bằng chứng
    assert r["denominators"]["domains_jobs"] == 1 and r["denominators"]["domains_thesis"] == 4


def test_overview_domains_use_labelled_denominator_and_pairs():
    r = O.overview(store())
    d = {x["name"]: x for x in r["domains"]}
    assert d["Education"]["job_count"] == 1 and d["Education"]["job_share"] == 1.0      # 1/1 job đã có Domain
    assert d["Education"]["thesis_count"] == 4 and d["Education"]["thesis_share"] == 1.0
    cells = {(c["topic"], c["domain"]): c for c in r["pairs"]["cells"]}
    assert cells[("AI/ML", "Education")]["job_count"] == 1 and cells[("AI/ML", "Education")]["thesis_count"] == 3
    assert "Web Development" in r["pairs"]["topics"] or "AI/ML" in r["pairs"]["topics"]


def test_overview_thesis_by_year_and_notes():
    r = O.overview(store())
    y = r["thesis_by_year"]
    assert y["years"] == [2025] and y["total"] == [6] and y["by_topic"]["AI/ML"] == [3] and y["n_with_year"] == 6
    assert any("ngày đăng" in n for n in r["notes"])


def test_overview_without_embeddings_still_works():
    r = O.overview(store(with_embeddings=False))
    assert r["kpis"]["n_jobs"] == 3 and len(r["topics"]) == 3
