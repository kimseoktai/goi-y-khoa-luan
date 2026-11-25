"""Kiểm thử nhóm công việc gộp + duyệt (bộ dữ liệu nhỏ tự tạo, ngưỡng được chỉnh để thử)."""
from backend.errors import BadRequest, NotFound
from backend.services import catalog_service as C, role_service as R
from tests.test_phase12 import raises, store


def setup(support, comps=1):
    R.MIN_SUPPORT, R.MIN_COMPANIES = support, comps
    return store(False)


def test_small_roles_go_to_other_and_unassigned():
    ds = setup(2)                                   # cả 3 role chỉ có 1 job: đều dưới ngưỡng
    r = R.roles(ds)
    assert [g["name"] for g in r["groups"]] == [R.OTHER] and r["groups"][0]["job_count"] == 3
    assert r["pending_count"] == 0 and r["unassigned_count"] == 3


def test_merge_and_filter_by_group():
    ds = setup(1)                                   # đủ ngưỡng: mỗi role là một nhóm
    assert {g["name"] for g in R.roles(ds)["groups"]} == {"AI Engineer", "Frontend Dev", "Office Admin"}
    R.decide(ds, "Frontend Dev", "merge", "AI Engineer")
    # đã gộp nhưng đang đủ ngưỡng nên chờ duyệt
    assert R.roles(ds)["pending_count"] == 1
    assert C.list_jobs(ds, role="AI Engineer")["total"] == 2 and C.list_jobs(ds, role="Frontend Dev")["total"] == 1


def test_approve_keep_and_errors():
    ds = setup(1)
    R.decide(ds, "Frontend Dev", "merge", "AI Engineer")
    a = R.decide(ds, "Frontend Dev", "keep_merged")
    assert a["pending"] == [] and len(a["merged"]) == 1          # giữ gộp: hết chờ duyệt
    R.decide(ds, "Frontend Dev", "merge", "AI Engineer")
    a = R.decide(ds, "Frontend Dev", "approve_split")
    assert a["pending"] == [] and C.list_jobs(ds, role="Frontend Dev")["total"] == 1 and C.list_jobs(ds, role="AI Engineer")["total"] == 1
    assert raises(BadRequest, R.decide, ds, "Frontend Dev", "approve_split")        # không còn chờ duyệt
    assert raises(BadRequest, R.decide, ds, "Office Admin", "merge", "Office Admin")
    assert raises(BadRequest, R.decide, ds, "Office Admin", "merge", "Không có")
    assert raises(BadRequest, R.decide, ds, "Office Admin", "xoá")
    assert raises(NotFound, R.decide, ds, "Không có", "merge", "AI Engineer")


def test_persisted_file():
    ds = setup(1)
    R.decide(ds, "Office Admin", "merge", "")
    import pandas as pd
    df = pd.read_csv(ds.root / R.FILE, dtype=str).fillna("")
    assert df.loc[0, "role"] == "Office Admin" and df.loc[0, "parent_role"] == "" and df.loc[0, "decided_at"]
    assert R.roles(ds)["groups"][-1]["name"] == R.OTHER


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
