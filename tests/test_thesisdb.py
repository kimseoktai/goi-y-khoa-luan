"""Kiểm thử đường ống khóa luận NEU: đọc trang, thêm/đóng/mở lại, nhận bản cũ, làm sạch, xuất CSV. Dữ liệu và tên đều là giả."""
import json

import pandas as pd
import pytest

from ml.jobsdb import db as jobsdb
from ml.thesisdb import clean, db, neu


def page(items, has_more=False, extra=None):
    results = [dict(id=i, tenChuyenDe=t, nam=y, fileBaoCao=f, sourceCode=s, hoTen="Nguyễn Văn A", maSV="123", **(extra or {})) for i, t, y, f, s in items]
    obj = {"object": "list", "results": results, "has_more": has_more}
    payload = '7:["$","$L11",null,{"res":' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + '}]\n'
    esc = json.dumps(payload, ensure_ascii=False)[1:-1]
    half = len(esc) // 2
    while esc[half - 1] == "\\":              # không cắt giữa dãy thoát
        half += 1
    return f'<html><script>self.__next_f.push([1,"{esc[:half]}"])</script><script>self.__next_f.push([1,"{esc[half:]}"])</script></html>'


A = ("n1", "Xây dựng hệ thống quản lý thư viện", 2023, "/files/a.pdf", None)
B = ("n2", "Phân tích dữ liệu bán hàng bằng Power BI", 2024, "https://s3.example/b.pdf", "https://git.example/b")
C = ("n3", "Ứng dụng học máy dự đoán giá nhà", 2024, None, None)



@pytest.fixture
def con():
    return db.connect(":memory:")


def test_parse_drops_personal_and_joins_chunks():
    recs, more = neu.parse(page([A, B]))
    assert more is False and [r["sid"] for r in recs] == ["n1", "n2"]
    assert recs[0]["report_url"] == "https://fit.neu.edu.vn/files/a.pdf"
    assert recs[1]["source_code_url"] == "https://git.example/b"
    assert not any("Nguyễn" in json.dumps(r, ensure_ascii=False) or "123" in r.values() for r in recs)


def test_parse_errors():
    with pytest.raises(neu.ParseError):
        neu.parse("<html>không có gì</html>")
    with pytest.raises(neu.ParseError):
        neu.parse(page([]))


def test_fetch_refuses_api():
    with pytest.raises(ValueError):
        neu.fetch("https://fit.neu.edu.vn/api/theses")
    with pytest.raises(ValueError):
        neu.fetch("https://example.com/theses")


def test_crawl_adds_idempotent_and_keeps_links(con):
    r = neu.crawl(con, html=page([A, B]), today="2026-10-01")
    assert (r["seen"], r["new"], r["closed"], r["complete"]) == (2, 2, 0, True)
    r = neu.crawl(con, html=page([A, B]), today="2026-10-02")
    assert r["new"] == 0 and con.execute("SELECT COUNT(*) FROM thesis_raw").fetchone()[0] == 2
    # giá trị rỗng không ghi đè đường dẫn đã có
    neu.crawl(con, html=page([("n2", B[1], 2024, None, None), A]), today="2026-10-03")
    assert con.execute("SELECT report_url FROM thesis_raw WHERE source_thesis_id='n2'").fetchone()[0] == "https://s3.example/b.pdf"


def test_close_after_two_runs_and_reopen(con):
    neu.crawl(con, html=page([A, B, C]), today="2026-10-01")
    neu.crawl(con, html=page([A, B]), today="2026-10-02")
    st = lambda: con.execute("SELECT status FROM thesis_raw WHERE source_thesis_id='n3'").fetchone()[0]
    assert st() == "active"                       # mới vắng 1 lần
    assert neu.crawl(con, html=page([A, B]), today="2026-10-03")["closed"] == 1 and st() == "closed"
    neu.crawl(con, html=page([A, B, C]), today="2026-10-04")
    assert st() == "active"                       # quay lại thì mở lại


def test_suspicious_run_closes_nothing(con):
    many = [(f"x{i}", f"Đề tài số {i} về hệ thống thông tin", 2022, None, None) for i in range(10)]
    neu.crawl(con, html=page(many), today="2026-10-01")
    for d in ("2026-10-02", "2026-10-03", "2026-10-04"):
        r = neu.crawl(con, html=page(many[:2]), today=d)
        assert r["closed"] == 0
    assert con.execute("SELECT COUNT(*) FROM thesis_raw WHERE status='active'").fetchone()[0] == 10


def test_has_more_closes_nothing(con):
    neu.crawl(con, html=page([A, B]), today="2026-10-01")
    for d in ("2026-10-02", "2026-10-03"):
        r = neu.crawl(con, html=page([A], has_more=True), today=d)
        assert not r["complete"] and r["closed"] == 0
    assert con.execute("SELECT COUNT(*) FROM thesis_raw WHERE status='closed'").fetchone()[0] == 0


def test_parse_failure_is_logged_and_closes_nothing(con):
    neu.crawl(con, html=page([A, B]), today="2026-10-01")
    with pytest.raises(neu.ParseError):
        neu.crawl(con, html="<html></html>", today="2026-10-02")
    assert con.execute("SELECT ok FROM crawl_runs WHERE source=? ORDER BY run_id DESC LIMIT 1", (neu.RUN_SOURCE,)).fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM thesis_raw WHERE status='active'").fetchone()[0] == 2


def test_legacy_import_keeps_ids_and_neu_crawl_adopts(con):
    rows = [dict(thesis_id=7, title=A[1], year=2023, source="neu"), dict(thesis_id=9, title="Một đề tài của trường khác", year=2020, source="uit")]
    assert db.import_legacy(con, rows) == 2
    assert db.import_legacy(con, rows) == 0       # chạy lại không tạo bản trùng
    r = neu.crawl(con, html=page([A, B]), today="2026-10-01")
    assert r["new"] == 1                          # chỉ B là mới; A được nhận
    got = con.execute("SELECT thesis_id, source_thesis_id, report_url, origin FROM thesis_raw WHERE title=?", (A[1],)).fetchone()
    assert (got[0], got[1], got[3]) == (7, "n1", "legacy") and got[2].endswith("/files/a.pdf")
    assert con.execute("SELECT thesis_id FROM thesis_raw WHERE source_thesis_id='n2'").fetchone()[0] > 9     # id mới nối tiếp, không đụng id cũ
    # trường khác (uit) không bị lần crawl NEU đóng
    for d in ("2026-10-02", "2026-10-03"):
        neu.crawl(con, html=page([A, B]), today=d)
    assert con.execute("SELECT status FROM thesis_raw WHERE thesis_id=9").fetchone()[0] == "active"


def test_clean_and_export_order(con, tmp_path):
    db.import_legacy(con, [dict(thesis_id=3, title="Hệ thống quản lý sinh viên", year=2021, source="uit"),
                           dict(thesis_id=1, title="Nghiên cứu mạng nơ-ron tích chập", year=2022, source="uit"),
                           dict(thesis_id=2, title="Ngắn", year=2022, source="uit")])
    neu.crawl(con, html=page([A, ("n9", "hệ thống quản lý sinh viên.", 2025, None, None)]), today="2026-10-01")
    st = clean.run(con)
    assert st["invalid"] == 1 and st["dup"] == 1
    out = tmp_path / "t.csv"
    n = db.export_csv(con, out)
    df = pd.read_csv(out, encoding="utf-8-sig")
    assert n == len(df) == 3 and list(df.thesis_id) == sorted(df.thesis_id)
    assert {"report_url", "source_code_url"} <= set(df.columns) and 2 not in set(df.thesis_id)
    assert "hệ thống quản lý sinh viên." not in set(df.title.str.lower())    # bản trùng của khóa luận mới bị loại, bản cũ giữ


def test_link_only_http():
    import numpy as np
    from backend.services import catalog_service as S
    row = pd.Series(dict(report_url="https://x/y.pdf", source_code_url=np.nan, bad="javascript:alert(1)"))
    assert S._link(row, "report_url") == "https://x/y.pdf"
    assert S._link(row, "source_code_url") is None and S._link(row, "bad") is None and S._link(row, "khong_co") is None
