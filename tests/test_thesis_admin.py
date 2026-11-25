"""Kiểm thử thêm/sửa/xóa khóa luận cho quản trị: quy tắc dữ liệu, tương tác với crawl, nhãn chỉnh tay, nâng cấp CSDL cũ, tầng service."""
import sqlite3
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.errors import BadRequest, NotFound               # noqa: E402
from backend.services import thesis_admin_service as T        # noqa: E402
from ml.thesisdb import admin, clean, db, neu                  # noqa: E402
from tests.test_phase12 import raises, store                   # noqa: E402
from tests.test_thesisdb import A, B, page                     # noqa: E402

TOPICS, DOMAINS = {"AI/ML", "Web Development"}, {"Education"}


def con():
    return db.connect(":memory:")


def test_add_validates_and_blocks_duplicates():
    c = con()
    assert raises(admin.Invalid, admin.add, c, "Một")                                  # < 2 từ
    assert raises(admin.Invalid, admin.add, c, "Hệ thống bán hàng", year=1800)
    assert raises(admin.Invalid, admin.add, c, "Hệ thống bán hàng", report_url="javascript:alert(1)")
    assert raises(admin.Invalid, admin.add, c, "Hệ thống bán hàng", source="a b!")
    tid = admin.add(c, "  Hệ thống   bán hàng ", year=2025, report_url="https://x.example/a.pdf")
    r = c.execute("SELECT * FROM thesis_raw WHERE thesis_id=?", (tid,)).fetchone()
    assert r["title"] == "Hệ thống bán hàng" and r["origin"] == "manual" and r["locked"] == 1 and r["source"] == "neu" and r["source_thesis_id"].startswith("manual-")
    assert raises(admin.Invalid, admin.add, c, "hệ thống bán hàng.")                   # trùng (bỏ qua hoa thường, dấu câu cuối)
    admin.delete(c, tid)
    try:
        admin.add(c, "Hệ thống bán hàng")
        assert False
    except admin.Invalid as e:
        assert "khôi phục" in str(e)


def test_update_locks_row_and_crawl_does_not_overwrite():
    c = con()
    neu.crawl(c, html=page([A, B]), today="2026-10-01")
    tid = c.execute("SELECT thesis_id FROM thesis_raw WHERE source_thesis_id='n1'").fetchone()[0]
    assert admin.update(c, tid, title="Tiêu đề do admin sửa", year=2020, report_url="") is True
    assert admin.update(c, tid, title="Tiêu đề do admin sửa") is False                  # không đổi gì
    neu.crawl(c, html=page([A, B]), today="2026-10-02")
    r = c.execute("SELECT title, year, report_url, locked FROM thesis_raw WHERE thesis_id=?", (tid,)).fetchone()
    assert (r["title"], r["year"], r["report_url"], r["locked"]) == ("Tiêu đề do admin sửa", 2020, None, 1)
    assert raises(admin.Invalid, admin.update, c, tid, title="Phân tích dữ liệu bán hàng bằng Power BI")   # trùng khóa luận khác
    assert raises(admin.Invalid, admin.update, c, tid, nam=3)
    assert raises(admin.Missing, admin.update, c, 9999, title="Hai từ")


def test_delete_is_soft_and_survives_crawl_restore_works():
    c = con()
    neu.crawl(c, html=page([A, B]), today="2026-10-01")
    tid = c.execute("SELECT thesis_id FROM thesis_raw WHERE source_thesis_id='n2'").fetchone()[0]
    assert admin.delete(c, tid) is True and admin.delete(c, tid) is False
    for d in ("2026-10-02", "2026-10-03"):
        neu.crawl(c, html=page([A, B]), today=d)                                       # trang vẫn có B: không được tự mở lại
    assert c.execute("SELECT status, hidden FROM thesis_raw WHERE thesis_id=?", (tid,)).fetchone()[:] == ("closed", 1)
    clean.run(c)
    assert tid not in {r[0] for r in c.execute("SELECT thesis_id FROM thesis_raw WHERE status='active'")}
    assert admin.restore(c, tid) is True and admin.restore(c, tid) is False
    assert c.execute("SELECT status, hidden FROM thesis_raw WHERE thesis_id=?", (tid,)).fetchone()[:] == ("active", 0)


def test_manual_rows_are_never_closed_by_crawl():
    c = con()
    neu.crawl(c, html=page([A, B]), today="2026-10-01")
    tid = admin.add(c, "Đề tài thêm tay của khoa", year=2026)
    for d in ("2026-10-02", "2026-10-03", "2026-10-04"):
        neu.crawl(c, html=page([A, B]), today=d)
    assert c.execute("SELECT status FROM thesis_raw WHERE thesis_id=?", (tid,)).fetchone()[0] == "active"
    n = db.export_csv(c, Path(tempfile.mkdtemp()) / "o.csv")
    assert n == 3


def test_labels_override_validation_and_clear():
    c = con()
    tid = admin.add(c, "Hệ thống học tập trực tuyến")
    assert raises(admin.Invalid, admin.set_labels, c, tid, ["Không có"], [], TOPICS, DOMAINS)
    assert raises(admin.Invalid, admin.set_labels, c, tid, list(TOPICS) * 1 + ["a", "b", "c", "d"], [], TOPICS | {"a", "b", "c", "d"}, DOMAINS)
    admin.set_labels(c, tid, ["AI/ML", "AI/ML", "Web Development"], ["Education"], TOPICS, DOMAINS, "đã xem PDF")
    assert admin.overrides(c) == {tid: (["AI/ML", "Web Development"], ["Education"])}
    admin.set_labels(c, tid, [], [], TOPICS, DOMAINS)
    assert admin.overrides(c) == {}
    assert raises(admin.Missing, admin.set_labels, c, 9999, ["AI/ML"], [], TOPICS, DOMAINS)


def test_pending_counts_actions_after_last_build():
    c = con()
    tid = admin.add(c, "Đề tài thứ nhất của khoa")
    admin.update(c, tid, year=2024)
    assert admin.pending_since(c, "") == 2
    assert admin.pending_since(c, "2999-01-01T00:00:00") == 0
    assert admin.pending_since(c, "2000-01-01T00:00:00") == 2


def test_listing_filters_search_and_escape():
    c = con()
    db.import_legacy(c, [dict(thesis_id=1, title="Hệ thống 100% tự động", year=2021, source="uit"), dict(thesis_id=2, title="Ứng dụng web", year=2023, source="neu")])
    admin.add(c, "Đề tài thêm tay mới", year=2026)
    assert admin.listing(c)[0] == 3
    assert admin.listing(c, q="100%")[0] == 1 and admin.listing(c, q="%")[0] == 1       # % là ký tự thường, không phải ký tự đại diện
    assert admin.listing(c, source="neu")[0] == 2 and admin.listing(c, origin="manual")[0] == 1
    t, rows = admin.listing(c, sort="year", limit=1)
    assert t == 3 and rows[0]["year"] == 2026


def test_old_database_is_upgraded_without_losing_data():
    f = tempfile.mktemp(suffix=".sqlite")
    o = sqlite3.connect(f)
    o.executescript("""CREATE TABLE thesis_raw (thesis_id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, source_thesis_id TEXT NOT NULL, title TEXT NOT NULL, year INTEGER,
      report_url TEXT, source_code_url TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, missed_runs INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed')), origin TEXT NOT NULL DEFAULT 'crawl' CHECK (origin IN ('legacy','crawl')), UNIQUE (source, source_thesis_id));
      CREATE TABLE thesis_clean (thesis_id INTEGER PRIMARY KEY REFERENCES thesis_raw(thesis_id) ON DELETE CASCADE, title_norm TEXT, valid INTEGER NOT NULL, reason TEXT, dup_of INTEGER, rules_version TEXT, cleaned_at TEXT);
      INSERT INTO thesis_raw VALUES (7,'neu','a','Tiêu đề cũ của khóa luận',2024,NULL,NULL,'2026-10-01','2026-10-01',0,'active','legacy');
      INSERT INTO thesis_clean VALUES (7,'x',1,NULL,NULL,'v','t');""")
    o.commit(); o.close()
    c = db.connect(f)
    assert c.execute("SELECT thesis_id, title, locked, hidden FROM thesis_raw").fetchone()[:] == (7, "Tiêu đề cũ của khóa luận", 0, 0)
    assert c.execute("SELECT COUNT(*) FROM thesis_clean").fetchone()[0] == 1           # bảng con không bị xóa dây chuyền
    tid = admin.add(c, "Khóa luận thêm sau khi nâng cấp")
    assert tid == 8 and c.execute("PRAGMA foreign_key_check").fetchall() == []
    db.connect(f)                                                                      # kết nối lần hai không làm gì


def test_service_list_add_edit_labels_and_errors():
    ds = store(False)
    (ds.root / "data/db").mkdir(parents=True)
    c = db.connect(ds.root / "data/db/jobs.sqlite")
    db.import_legacy(c, [dict(thesis_id=101, title="Ứng dụng học máy trong giáo dục", year=2025, source="neu")]); c.close()
    d = T.listing(ds)
    assert d["total"] == 1 and d["items"][0]["labels"]["topics"] == ["AI/ML"] and d["items"][0]["labels"]["built"] is True and d["pending"] == 0
    assert d["topics"] == ["AI/ML", "Web Development"] and d["domains"] == ["Education", "Finance & Banking"]
    tid = T.add(ds, title="Đề tài mới của khoa", year=2026)["thesis_id"]
    assert T.listing(ds)["pending"] == 1 and raises(BadRequest, T.add, ds, title="Đề tài mới của khoa")
    T.set_labels(ds, tid, ["Web Development"], ["Education"])
    row = [r for r in T.listing(ds)["items"] if r["thesis_id"] == tid][0]
    assert row["labels"] == dict(topics=["Web Development"], domains=["Education"], label_source="manual", built=False)
    assert raises(BadRequest, T.set_labels, ds, tid, ["Nhãn lạ"], [])
    assert raises(NotFound, T.delete, ds, 424242)
    assert T.delete(ds, tid)["changed"] is True and T.listing(ds, status="closed")["total"] == 1
