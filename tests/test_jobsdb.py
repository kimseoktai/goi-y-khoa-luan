from ml.jobsdb import db


def con():
    return db.connect(":memory:")


def test_source_ids():
    assert db.source_of("https://itviec.com/it-jobs/x-1234") == "itviec"
    assert db.source_job_id("https://itviec.com/it-jobs/x-1234") == "x-1234"
    assert db.source_job_id("https://careerviet.vn/vi/tim-viec-lam/abc.35C8127B.html") == "35C8127B"


def test_upsert_no_duplicate_and_keeps_data():
    c = con()
    j, new = db.upsert_job(c, "https://itviec.com/it-jobs/a-1", skills=["Python"], today="2026-10-01", title_raw="A", company="X")
    assert new
    j2, new2 = db.upsert_job(c, "https://itviec.com/it-jobs/a-1", skills=["Python", "SQL"], today="2026-10-08", salary_text="1000$", company="")
    assert j == j2 and not new2
    r = c.execute("SELECT * FROM jobs").fetchone()
    assert (r["first_seen"], r["last_seen"], r["company"], r["salary_text"]) == ("2026-10-01", "2026-10-08", "X", "1000$")
    assert c.execute("SELECT COUNT(*) FROM job_skills").fetchone()[0] == 2


def _seed(c, n, src="itviec"):
    return [db.upsert_job(c, f"https://{src}.com/it-jobs/j-{i}", today="2026-10-01")[0] for i in range(n)]


def test_close_after_two_missed_runs_and_reopen():
    c = con()
    ids = _seed(c, 4)
    for d in ("2026-10-08", "2026-10-15"):
        run = db.start_run(c, "itviec")
        db.close_missing(c, run, "itviec", ids[:3], today=d)
    st = {r["job_id"]: r["status"] for r in c.execute("SELECT job_id, status FROM jobs")}
    assert st[ids[3]] == "closed" and all(st[i] == "active" for i in ids[:3])
    j, _ = db.upsert_job(c, "https://itviec.com/it-jobs/j-3", today="2026-10-22")
    assert c.execute("SELECT status, missed_runs FROM jobs WHERE job_id=?", (j,)).fetchone()[:] == ("active", 0)


def test_suspicious_run_closes_nothing():
    c = con()
    ids = _seed(c, 10)
    r0 = db.start_run(c, "itviec")
    db.finish_run(c, r0, n_seen=10, n_new=10, ok=True)           # lần trước thấy 10 tin
    for _ in range(3):
        run = db.start_run(c, "itviec")
        assert db.close_missing(c, run, "itviec", ids[:2], today="2026-10-08") == 0   # lần này chỉ thấy 2
    assert c.execute("SELECT COUNT(*) FROM jobs WHERE status='closed'").fetchone()[0] == 0
    assert "bất thường" in c.execute("SELECT note FROM crawl_runs ORDER BY run_id DESC").fetchone()[0]


def test_suspicious_run_is_not_used_as_next_baseline():
    c = con()
    ids = _seed(c, 10)
    r0 = db.start_run(c, "itviec"); db.finish_run(c, r0, n_seen=10, n_new=10, ok=True)
    r1 = db.start_run(c, "itviec")
    db.close_missing(c, r1, "itviec", ids[:2], today="2026-10-08")                        # thấy 2/10: bất thường
    db.finish_run(c, r1, n_seen=2, n_new=0, ok=True)
    assert c.execute("SELECT ok FROM crawl_runs WHERE run_id=?", (r1,)).fetchone()[0] == 0
    r2 = db.start_run(c, "itviec")                                                         # vẫn thấy 2: phải còn bị coi là bất thường so với mốc 10
    assert db.close_missing(c, r2, "itviec", ids[:2], today="2026-10-09") == 0
    assert c.execute("SELECT COUNT(*) FROM jobs WHERE status='closed'").fetchone()[0] == 0


def test_old_stale_rows_still_close_when_run_is_normal():
    c = con()
    ids = _seed(c, 10)                                            # 10 tin cũ, chỉ 3 tin còn sống; không có lần crawl trước để so sánh
    for d in ("2026-10-08", "2026-10-15"):
        run = db.start_run(c, "itviec")
        db.close_missing(c, run, "itviec", ids[:3], today=d)
        db.finish_run(c, run, n_seen=3, n_new=0, ok=True)
    assert c.execute("SELECT COUNT(*) FROM jobs WHERE status='closed'").fetchone()[0] == 7


def test_deadline_closes_immediately():
    c = con()
    j, _ = db.upsert_job(c, "https://itviec.com/it-jobs/d-1", today="2026-10-01", deadline="2026-10-05")
    run = db.start_run(c, "itviec")
    db.close_missing(c, run, "itviec", [j], today="2026-10-10")
    assert c.execute("SELECT status FROM jobs").fetchone()[0] == "closed"


def test_parse_skills():
    assert db.parse_skills('["A", "B"]') == ["A", "B"] and db.parse_skills("A, B") == ["A", "B"] and db.parse_skills("") == []


ITEM = {"id": 2138248, "title": "C/C++ Software Developer", "content": "<p>About&nbsp;us</p><ul><li>Linux</li></ul>", "responsibilities": "<ul><li>Design &amp; build</li></ul>",
        "requirements_arr": [], "benefits_v2": [{"name": "", "description": "<ul><li>Salary: 10,000,000 VND</li></ul>"}], "company": {"display_name": "RemotePeople"},
        "skills_arr": ["Linux", "C/C++"], "addresses": {"address_region_array": ["Thành phố Hà Nội", "Thành phố Hà Nội"]}, "is_salary_visible": False,
        "salary": {"min_filter": 10000000, "max_filter": 60000000, "currency": "VND", "is_negotiable": "0"}, "job_types_str": "Trực tiếp",
        "published": {"date": "15-10-2026"}, "expires": {"date": "14-11-2026"}, "detail_url": "https://topdev.vn/detail-jobs/c-c-software-developer-remotepeople-2138248?src=x"}


def test_topdev_record():
    from ml.jobsdb import topdev
    r = topdev.to_record(ITEM)
    f = r["fields"]
    assert (r["sid"], r["url"], r["skills"]) == ("2138248", "https://topdev.vn/detail-jobs/c-c-software-developer-remotepeople-2138248", ["Linux", "C/C++"])
    assert (f["company"], f["location"], f["posted_at"], f["deadline"], f["salary_text"]) == ("RemotePeople", "Thành phố Hà Nội", "2026-10-15", "2026-11-14", "")
    assert "About us" in f["description"] and "- Linux" in f["description"] and "Design & build" in f["description"]
    assert topdev.iso_date({"date": "bad"}) is None
    assert topdev.salary_text({**ITEM, "is_salary_visible": True}) == "10,000,000 - 60,000,000 VND"


def test_topdev_ingest_and_close():
    from ml.jobsdb import topdev
    c = con()
    mk = lambda i: {**ITEM, "id": i, "title": f"Dev {i}", "detail_url": f"https://topdev.vn/detail-jobs/dev-{i}"}
    ids, new = topdev.ingest_items(c, [mk(1), mk(2), mk(3)], today="2026-10-01")
    assert new == 3 and c.execute("SELECT COUNT(*) FROM raw_pages").fetchone()[0] == 3
    r = c.execute("SELECT * FROM jobs WHERE source_job_id='1'").fetchone()
    assert (r["title_raw"], r["deadline"], r["status"]) == ("Dev 1", "2026-11-14", "active")
    assert {x[0] for x in c.execute("SELECT skill FROM job_skills WHERE job_id=?", (ids[0],))} == {"Linux", "C/C++"}
    for d in ("2026-10-08", "2026-10-15"):                  # tin 3 biến mất 2 lần crawl liên tiếp
        run = db.start_run(c, "topdev")
        seen, n = topdev.ingest_items(c, [mk(1), mk(2)], today=d)
        assert n == 0
        db.close_missing(c, run, "topdev", seen, today=d)
    assert c.execute("SELECT status FROM jobs WHERE source_job_id='3'").fetchone()[0] == "closed"
    assert c.execute("SELECT COUNT(*) FROM raw_pages").fetchone()[0] == 3     # chỉ lưu nguyên bản của tin mới


def test_topdev_bad_item_is_skipped():
    from ml.jobsdb import topdev
    c = con()
    good = {**ITEM, "id": 7, "detail_url": "https://topdev.vn/detail-jobs/g-7"}
    odd = {**ITEM, "id": 8, "detail_url": "https://topdev.vn/detail-jobs/o-8", "addresses": {"address_region_array": [None, "Hà Nội"]}, "benefits_v2": [None], "requirements_arr": [None]}
    bad = {"id": 9, "detail_url": "https://topdev.vn/detail-jobs/b-9", "skills_arr": 5}
    errs = []
    ids, new = topdev.ingest_items(c, [good, odd, bad], today="2026-10-01", errors=errs)
    assert new == 2 and len(errs) == 1 and "9" in errs[0]
    assert c.execute("SELECT location FROM jobs WHERE source_job_id='8'").fetchone()[0] == "Hà Nội"


def test_prune_source():
    c = con()
    ids = _seed(c, 4, "topdev")
    other = _seed(c, 1, "itviec")
    db.upsert_job(c, "https://topdev.vn/it-jobs/j-0", skills=["Python"], today="2026-10-01")
    assert db.prune_source(c, "topdev", ids[:2]) == 2
    left = {r[0] for r in c.execute("SELECT job_id FROM jobs")}
    assert left == set(ids[:2]) | set(other)
    assert c.execute("SELECT COUNT(*) FROM job_skills").fetchone()[0] in (0, 1)


# ---------- ITviec / CareerViet ----------
import json as _json
from pathlib import Path as _P

FX = _json.loads((_P(__file__).parent / "fixtures" / "job_samples.json").read_text(encoding="utf-8"))


def _ld_page(ld, single=True):
    q = "'" if single else '"'
    return f"<html><head><title>x</title></head><body><script type={q}application/ld+json{q}>\n{_json.dumps(ld, ensure_ascii=False)}\n</script></body></html>"


def test_itviec_parse_detail_and_list():
    from ml.jobsdb import htmlsites as H
    d = H.ITviec.parse_detail(_ld_page(FX["itviec_ld"]), "https://itviec.com/it-jobs/a-0658")
    f = d["fields"]
    assert d["skills"] == ["Cloud", "DevOps", "English"]
    assert (f["company"], f["location"], f["posted_at"], f["deadline"]) == ("Cloud Ace", "Hà Nội", "2026-10-08", "2026-11-12")
    assert f["description"].startswith("Top 3 Reasons") and "salary_text" not in f
    html = ('<a href="https://itviec.com/it-jobs/senior-dev-abc-0658?lab_feature=preview_jd_page">x</a><a href="/companies/abc?lab_feature=preview_jd_page">c</a>'
            '<a href="/it-jobs/qa-tester-xyz-3508?lab_feature=preview_jd_page">y</a><a href="/it-jobs/senior-dev-abc-0658?lab_feature=preview_jd_page">dup</a>')
    assert H.ITviec.parse_list(html) == ["https://itviec.com/it-jobs/senior-dev-abc-0658", "https://itviec.com/it-jobs/qa-tester-xyz-3508"]


def test_careerviet_parse_detail_and_list():
    from ml.jobsdb import htmlsites as H
    d = H.CareerViet.parse_detail(_ld_page(FX["careerviet_ld"], single=False), "u")
    f = d["fields"]
    assert (f["title_raw"], f["location"], f["posted_at"], f["deadline"], f["salary_text"]) == ("IP Network Engineer", "Hà Nội", "2026-10-18", "2026-11-15", "Cạnh tranh")
    assert d["skills"] == [] and "COMPANY" in f["description"]
    html = "<title>Tuyển dụng 583 việc làm CNTT</title>Tuyển dụng 4003 việc làm " + "".join(f'<a href="{p}">j</a>' for p in FX["careerviet_list_links"]) + \
           '<a href="/vi/talentcommunity/bai-viet.35A52D7D.html">blog</a>'
    assert H.CareerViet.total(html) == 583 and len(H.CareerViet.parse_list(html)) == 3
    assert H.CareerViet.parse_list(html)[0] == "https://careerviet.vn" + FX["careerviet_list_links"][0]


class _FakeSite:
    NAME = "fake"
    GROUPS = ["g"]
    PAGES = {1: ["https://fake.vn/j/a-0001", "https://fake.vn/j/b-0002"], 2: ["https://fake.vn/j/c-0003"], 3: []}

    @staticmethod
    def list_url(g, p):
        return f"list/{g}/{p}"

    @staticmethod
    def parse_list(html):
        return _json.loads(html)

    @staticmethod
    def total(html):
        return None

    @staticmethod
    def parse_detail(html, url):
        if "BAD" in html:
            raise ValueError("hỏng")
        return dict(skills=["Python"], raw={"u": url}, fields=dict(title_raw="T " + url, description="d", posted_at="2026-10-01", deadline="2026-12-01"))


def _fetch_for(pages, detail="OK"):
    def fetch(u):
        if u.startswith("list/"):
            return _json.dumps(pages.get(int(u.rsplit("/", 1)[1]), []))
        return detail
    return fetch


def test_crawl_runner_new_touch_close():
    from ml.jobsdb import htmlsites as H
    c = con()
    r = H.crawl(c, _FakeSite, fetch=_fetch_for(_FakeSite.PAGES), today="2026-10-01", sleep=None, log=lambda *_: None)
    assert (r["listed"], r["new"], r["fetched"], r["complete"]) == (3, 3, 3, True)
    assert c.execute("SELECT COUNT(*) FROM raw_pages").fetchone()[0] == 3
    # lần 2: tin đã đủ thông tin thì không tải chi tiết nữa, chỉ cập nhật last_seen
    r = H.crawl(c, _FakeSite, fetch=_fetch_for(_FakeSite.PAGES, detail="BAD"), today="2026-10-08", sleep=None, log=lambda *_: None)
    assert (r["new"], r["fetched"], r["errors"], r["complete"]) == (0, 0, [], True)
    assert c.execute("SELECT last_seen FROM jobs WHERE source_job_id='a-0001'").fetchone()[0] == "2026-10-08"
    # tin c biến mất 2 lần liên tiếp thì đóng
    pages = {1: _FakeSite.PAGES[1]}
    for d in ("2026-10-15", "2026-10-22"):
        H.crawl(c, _FakeSite, fetch=_fetch_for(pages), today=d, sleep=None, log=lambda *_: None)
    assert c.execute("SELECT status FROM jobs WHERE source_job_id='c-0003'").fetchone()[0] == "closed"


def test_crawl_runner_errors_block_closing_and_backfill():
    from ml.jobsdb import htmlsites as H
    c = con()
    db.upsert_job(c, "https://fake.vn/j/old-0009", source="fake", today="2026-09-01")      # tin cũ chưa có ngày đăng
    r = H.crawl(c, _FakeSite, fetch=_fetch_for(_FakeSite.PAGES, detail="BAD"), today="2026-10-01", sleep=None, log=lambda *_: None)
    assert r["complete"] is False and len(r["errors"]) == 3 and r["closed"] == 0 and r["new"] == 0
    assert c.execute("SELECT COUNT(*) FROM jobs WHERE source='fake'").fetchone()[0] == 1          # tin mới lỗi thì không ghi dở
    r = H.crawl(c, _FakeSite, fetch=_fetch_for({1: ["https://fake.vn/j/old-0009"]}), today="2026-10-08", sleep=None, log=lambda *_: None)
    assert r["fetched"] == 1 and r["complete"] and c.execute("SELECT posted_at FROM jobs WHERE source_job_id='old-0009'").fetchone()[0] == "2026-10-01"


def test_crawl_runner_max_details_never_closes():
    from ml.jobsdb import htmlsites as H
    c = con()
    r = H.crawl(c, _FakeSite, fetch=_fetch_for(_FakeSite.PAGES), today="2026-10-01", max_details=1, sleep=None, log=lambda *_: None)
    assert r["new"] == 1 and r["complete"] is False and "max-details" in r["note"]


def test_two_connections_can_write_in_turn(tmp_path=None):
    import tempfile, os
    d = tempfile.mkdtemp()
    path = os.path.join(d, "t.sqlite")
    a, b = db.connect(path), db.connect(path)
    db.upsert_job(a, "https://x.vn/j/a-0001", source="x", today="2026-10-01")
    a.commit()
    db.upsert_job(b, "https://x.vn/j/b-0002", source="x", today="2026-10-01")
    b.commit()
    assert a.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2


def test_crawl_runner_unreadable_pages_tolerated_when_few():
    from ml.jobsdb import htmlsites as H

    class Site(_FakeSite):
        @staticmethod
        def parse_detail(html, url):
            if url.endswith("-0100"):
                raise H.NoJobPosting("không thấy khối JobPosting trong trang")
            return _FakeSite.parse_detail(html, url)
    n = 100
    pages = {1: [f"https://fake.vn/j/x-{i:04d}" for i in range(1, n + 1)]}
    c = con()
    r = H.crawl(c, Site, fetch=_fetch_for(pages), today="2026-10-01", sleep=None, log=lambda *_: None)
    assert r["complete"] is True and r["errors"] == [] and r["new"] == n - 1 and "không đọc được" in r["note"]
    c2 = con()                                                      # 1 trên 10 tin không đọc được thì quá nhiều: không tính là đủ
    small = {1: pages[1][-10:]}
    r = H.crawl(c2, Site, fetch=_fetch_for(small), today="2026-10-01", sleep=None, log=lambda *_: None)
    assert r["complete"] is False
