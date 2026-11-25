"""Kiểm thử trang quản trị: xác thực, chạy lệnh nền + log, duyệt bảng công ty, chỉ số (dữ liệu nhỏ tự tạo)."""
import sqlite3
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd                                              # noqa: E402
try:
    from fastapi.testclient import TestClient                    # noqa: E402
    from backend.main import create_app                          # noqa: E402
except ImportError:                                              # chưa cài fastapi: chỉ chạy các test tầng service
    TestClient = create_app = None
from backend.services import admin_service as A                  # noqa: E402
from backend.settings import Settings                            # noqa: E402
from tests.test_phase12 import store                             # noqa: E402

H = {"X-Admin-Token": "tok"}


def make_ds():
    ds = store(False)
    (ds.root / "data/repository/company_domains.csv").write_text(
        "company_key,company_example,domain,status,source,note\n"
        "acme bank,ACME Bank,Finance & Banking,draft,claude_knowledge,ngân hàng\n"
        "lop hoc,Lớp Học Vui,Education,review,gemini,\n", encoding="utf-8-sig")
    return ds


def make(token="tok"):
    ds = make_ds()
    return TestClient(create_app(ds, Settings(root=str(ds.root), admin_token=token))), ds


def test_auth():
    if TestClient is None:
        return                                                  # cần fastapi; xem các test_service_* chạy mà không cần
    c, _ = make("")
    assert c.get("/admin/overview").status_code == 403           # chưa đặt mã: tắt hẳn
    c, _ = make()
    assert c.get("/admin/overview").status_code == 401 and c.get("/admin/overview", headers={"X-Admin-Token": "sai"}).status_code == 401
    assert c.get("/admin/overview", headers=H).status_code == 200


def test_overview_with_and_without_db():
    if TestClient is None:
        return                                                  # cần fastapi; xem các test_service_* chạy mà không cần
    c, ds = make()
    d = c.get("/admin/overview", headers=H).json()
    assert d["db"] is None and d["coverage"]["jobs"] == 3 and d["coverage"]["with_domain"] == 1 and d["coverage"]["with_topic"] == 2
    assert d["company_table"] == {"total": 2, "by_status": {"draft": 1, "review": 1}}
    p = ds.root / "data/db"; p.mkdir(parents=True)
    con = sqlite3.connect(p / "jobs.sqlite")
    con.executescript("CREATE TABLE jobs (source TEXT, status TEXT, first_seen TEXT, last_seen TEXT, is_it INTEGER);"
                      "CREATE TABLE crawl_runs (run_id INTEGER PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT, n_seen INT, n_new INT, n_closed INT, ok INT, note TEXT);"
                      "INSERT INTO jobs VALUES ('topdev','active',date('now'),date('now'),1),('topdev','closed','2020-01-01','2020-01-02',1),('itviec','active',date('now'),date('now'),1);"
                      "INSERT INTO crawl_runs (source, started_at, n_seen, n_new, ok) VALUES ('topdev','2026-10-19 02:00',100,5,1);")
    con.commit(); con.close()
    d = c.get("/admin/overview", headers=H).json()["db"]
    src = {r["source"]: r for r in d["by_source"]}
    assert src["topdev"]["total"] == 2 and src["topdev"]["active"] == 1 and src["itviec"]["new_7d"] == 1
    assert d["daily_new"][-1]["n"] == 2 and d["recent_batches"][0]["n_new"] == 5


def test_companies_list_decide_add():
    if TestClient is None:
        return                                                  # cần fastapi; xem các test_service_* chạy mà không cần
    c, ds = make()
    r = c.get("/admin/companies", headers=H).json()
    assert r["total"] == 2 and "Finance & Banking" in r["domains"]
    assert c.get("/admin/companies?status=review", headers=H).json()["items"][0]["company_key"] == "lop hoc"
    assert c.get("/admin/companies?q=acme", headers=H).json()["total"] == 1
    assert c.post("/admin/companies/decision", headers=H, json={"company_key": "lop hoc", "status": "rejected"}).json()["row"]["status"] == "rejected"
    row = c.post("/admin/companies/decision", headers=H, json={"company_key": "acme bank", "domain": "Education"}).json()["row"]
    assert row["domain"] == "Education" and row["status"] == "approved"               # đổi lĩnh vực = đã duyệt
    assert c.post("/admin/companies/decision", headers=H, json={"company_key": "acme bank", "domain": "Không có"}).status_code == 400
    assert c.post("/admin/companies/decision", headers=H, json={"company_key": "acme bank", "status": "xoá"}).status_code == 400
    assert c.post("/admin/companies/decision", headers=H, json={"company_key": "zzz", "status": "draft"}).status_code == 404
    assert c.post("/admin/companies/add", headers=H, json={"company": "Công ty TNHH Beta Edu", "domain": "Education"}).status_code == 200
    assert c.post("/admin/companies/add", headers=H, json={"company": "Beta Edu", "domain": "Education"}).status_code == 400   # trùng sau khi chuẩn hóa
    df = pd.read_csv(ds.root / A.COMPANY_FILE, encoding="utf-8-sig")
    assert len(df) == 3 and df.set_index("company_key").loc["lop hoc", "status"] == "rejected"
    from ml.classification.job_labeling import load_company_domains          # file ghi ra vẫn đọc được bằng bộ gán nhãn
    got = load_company_domains(ds.root / A.COMPANY_FILE)
    assert got == {"acme bank": ["Education"], "beta edu": ["Education"]}


def test_run_task_log_and_safety():
    if TestClient is None:
        return                                                  # cần fastapi; xem các test_service_* chạy mà không cần
    c, ds = make()
    A.TASKS["echo"] = ("Thử", ["-c", "import time; print('xin chao'); time.sleep(0.3)"])
    try:
        assert c.post("/admin/run", headers=H, json={"task": "rm -rf"}).status_code == 400            # không nằm trong danh sách
        s = c.post("/admin/run", headers=H, json={"task": "echo"}).json()
        assert s["running"] and c.post("/admin/run", headers=H, json={"task": "echo"}).status_code == 400     # chỉ một lệnh tại một thời điểm
        for _ in range(50):
            s = c.get("/admin/run/status", headers=H).json()
            if not s["running"]:
                break
            time.sleep(0.1)
        assert s["code"] == 0 and "xin chao" in s["tail"] and "[exit 0]" in s["tail"]
        logs = c.get("/admin/logs", headers=H).json()["items"]
        assert logs[0]["name"] == s["log"] and logs[0]["ok"] is True
        assert "xin chao" in c.get("/admin/logs/" + s["log"], headers=H).json()["text"]
        assert c.get("/admin/logs/..%2Fsecret.log", headers=H).status_code in (400, 404)
        assert c.get("/admin/logs/khong_co.log", headers=H).status_code == 404
        assert c.get("/admin/logs/a.txt", headers=H).status_code == 400
        s = c.post("/admin/run", headers=H, json={"task": "echo"}).json()
        assert c.post("/admin/run/stop", headers=H).json()["running"] in (True, False)
        for _ in range(50):
            if not c.get("/admin/run/status", headers=H).json()["running"]:
                break
            time.sleep(0.1)
        assert c.post("/admin/run/stop", headers=H).status_code == 400                                  # không còn gì để dừng
    finally:
        A.TASKS.pop("echo", None)


def test_reload():
    if TestClient is None:
        return                                                  # cần fastapi; xem các test_service_* chạy mà không cần
    c, ds = make()
    r = c.post("/admin/reload", headers=H).json()
    assert r["ok"] and r["jobs"] == 3


def test_service_companies_and_overview():
    from backend.errors import BadRequest, NotFound
    ds = make_ds()
    o = A.overview(ds)
    assert o["db"] is None and o["coverage"]["jobs"] == 3 and o["coverage"]["with_domain"] == 1 and o["company_table"] == {"total": 2, "by_status": {"draft": 1, "review": 1}}
    assert A.list_companies(ds, "review")["items"][0]["company_key"] == "lop hoc" and A.list_companies(ds, q="acme")["total"] == 1
    assert A.decide_company(ds, "lop hoc", status="rejected")["row"]["status"] == "rejected"
    r = A.decide_company(ds, "acme bank", domain="Education")["row"]
    assert r["domain"] == "Education" and r["status"] == "approved"
    for kw, exc in ((dict(domain="Không có"), BadRequest), (dict(status="xoá"), BadRequest)):
        try:
            A.decide_company(ds, "acme bank", **kw); assert False
        except exc:
            pass
    try:
        A.decide_company(ds, "zzz", status="draft"); assert False
    except NotFound:
        pass
    A.add_company(ds, "Công ty TNHH Beta Edu", "Education")
    try:
        A.add_company(ds, "Beta Edu", "Education"); assert False
    except BadRequest:
        pass
    from ml.classification.job_labeling import load_company_domains
    assert load_company_domains(ds.root / A.COMPANY_FILE) == {"acme bank": ["Education"], "beta edu": ["Education"]}


def test_service_db_metrics():
    ds = make_ds()
    p = ds.root / "data/db"; p.mkdir(parents=True)
    con = sqlite3.connect(p / "jobs.sqlite")
    con.executescript("CREATE TABLE jobs (source TEXT, status TEXT, first_seen TEXT, last_seen TEXT, is_it INTEGER);"
                      "CREATE TABLE crawl_runs (run_id INTEGER PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT, n_seen INT, n_new INT, n_closed INT, ok INT, note TEXT);"
                      "INSERT INTO jobs VALUES ('topdev','active',date('now'),date('now'),1),('topdev','closed','2020-01-01','2020-01-02',1),('itviec','active',date('now'),date('now'),1);"
                      "INSERT INTO crawl_runs (source, started_at, n_seen, n_new, ok) VALUES ('topdev','2026-10-19 02:00',100,5,1);")
    con.commit(); con.close()
    d = A.overview(ds)["db"]
    src = {r["source"]: r for r in d["by_source"]}
    assert src["topdev"]["total"] == 2 and src["topdev"]["active"] == 1 and src["itviec"]["new_7d"] == 1
    assert d["daily_new"][-1]["n"] == 2 and d["recent_batches"][0]["n_new"] == 5


def test_group_runs_into_batches():
    r = lambda src, t, seen, new, ok=1: dict(source=src, started_at=t, finished_at=t, n_seen=seen, n_new=new, n_closed=0, ok=ok, note="")
    runs = [r("topdev", "2026-10-21T14:28:16", 0, 0, 0),                                                              # mới nhất, riêng một lần, lỗi
            r("careerviet", "2026-10-19T11:59:44", 563, 0), r("itviec", "2026-10-19T11:57:19", 640, 8), r("topdev", "2026-10-19T11:57:04", 131, 3),
            r("careerviet", "2026-10-19T00:39:24", 583, 0), r("itviec", "2026-10-19T00:37:24", 632, 0), r("topdev", "2026-10-19T00:37:12", 128, 0)]
    b = A.group_runs(runs)
    assert [len(x["runs"]) for x in b] == [1, 3, 3] and b[0]["ok"] is False and b[1]["ok"] is True
    assert [x["source"] for x in b[1]["runs"]] == ["topdev", "itviec", "careerviet"] and b[1]["n_new"] == 11 and b[1]["n_seen"] == 1334
    assert len(A.group_runs(runs, max_batches=2)) == 2 and A.group_runs([]) == []


def test_service_runner_and_logs():
    from backend.errors import BadRequest, NotFound
    ds = make_ds()
    A.TASKS["echo"] = ("Thử", ["-c", "import time; print('xin chao'); time.sleep(0.4)"])
    try:
        r = A.Runner(ds.root)
        for bad in ("rm -rf", None):
            try:
                r.start(bad); assert False
            except BadRequest:
                pass
        assert r.start("echo")["running"]
        try:
            r.start("echo"); assert False                                           # chỉ một lệnh tại một thời điểm
        except BadRequest:
            pass
        for _ in range(60):
            s = r.status()
            if not s["running"]:
                break
            time.sleep(0.1)
        time.sleep(0.2)
        s = r.status()
        assert s["code"] == 0 and "xin chao" in s["tail"] and "[exit 0]" in s["tail"]
        logs = A.list_logs(ds.root)
        assert logs[0]["name"] == s["log"] and logs[0]["ok"] is True
        assert "xin chao" in A.read_log(ds.root, s["log"])
        for bad in ("../x.log", "a.txt", "", "a/b.log"):
            try:
                A.read_log(ds.root, bad); assert False
            except BadRequest:
                pass
        try:
            A.read_log(ds.root, "khong_co.log"); assert False
        except NotFound:
            pass
        r.start("echo"); r.stop()
        for _ in range(60):
            if not r.running():
                break
            time.sleep(0.1)
        time.sleep(0.2)
        assert not r.running() and "(đã dừng)" in r.status()["tail"]
        try:
            r.stop(); assert False
        except BadRequest:
            pass
    finally:
        A.TASKS.pop("echo", None)


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)

