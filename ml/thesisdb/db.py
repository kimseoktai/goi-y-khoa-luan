"""Bảng khóa luận trong CSDL: thesis_raw (thô), thesis_clean (sạch). Dùng chung kết nối, crawl_runs và quy tắc đóng tin với tin tuyển dụng.

Nguyên tắc giống phía tuyển dụng:
- khóa tự nhiên (source, source_thesis_id): chạy lại không tạo bản trùng, giá trị rỗng không ghi đè;
- khóa luận biến mất khỏi nguồn thì đóng (status='closed') sau MISS_TO_CLOSE lần crawl đầy đủ liên tiếp, KHÔNG xóa; đã đóng thì không đưa vào dữ liệu phục vụ;
- lần crawl bất thường (thấy ít hơn MIN_SEEN_RATIO so với lần trước) thì không đóng gì.
Không lưu họ tên, mã sinh viên, giảng viên: không cần cho phân tích.
"""
import hashlib
import re
import unicodedata
from datetime import date

from ml.jobsdb import db as jobsdb
from ml.thesisdb import advisors as adv

MISS_TO_CLOSE = jobsdb.MISS_TO_CLOSE
MIN_SEEN_RATIO = jobsdb.MIN_SEEN_RATIO
RULES_VERSION = "thesis_clean_v1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS thesis_raw (
  thesis_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  source_thesis_id TEXT NOT NULL,
  title TEXT NOT NULL,
  year INTEGER,
  report_url TEXT, source_code_url TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  missed_runs INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed')),
  origin TEXT NOT NULL DEFAULT 'crawl' CHECK (origin IN ('legacy','crawl','manual')),
  locked INTEGER NOT NULL DEFAULT 0,
  hidden INTEGER NOT NULL DEFAULT 0,
  UNIQUE (source, source_thesis_id)
);
CREATE INDEX IF NOT EXISTS ix_thesis_status ON thesis_raw(status);
CREATE TABLE IF NOT EXISTS thesis_clean (
  thesis_id INTEGER PRIMARY KEY REFERENCES thesis_raw(thesis_id) ON DELETE CASCADE,
  title_norm TEXT, valid INTEGER NOT NULL, reason TEXT, dup_of INTEGER,
  rules_version TEXT, cleaned_at TEXT
);
-- nhãn do người xác nhận/chỉnh tay: được áp lên kết quả gắn nhãn của mô hình, và là nguồn nhãn tin cậy cho lần huấn luyện lại
CREATE TABLE IF NOT EXISTS thesis_label_override (
  thesis_id INTEGER PRIMARY KEY REFERENCES thesis_raw(thesis_id) ON DELETE CASCADE,
  technical_topics TEXT NOT NULL, domains TEXT NOT NULL, note TEXT, updated_at TEXT NOT NULL
);
-- giảng viên hướng dẫn (chỉ tên GVHD, không có tên hay mã sinh viên)
CREATE TABLE IF NOT EXISTS thesis_advisor (
  thesis_id INTEGER NOT NULL REFERENCES thesis_raw(thesis_id) ON DELETE CASCADE,
  advisor TEXT NOT NULL,
  PRIMARY KEY (thesis_id, advisor)
);
-- nhật ký thao tác của quản trị viên (thêm, sửa, xóa, khôi phục, đổi nhãn)
CREATE TABLE IF NOT EXISTS thesis_admin_log (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  thesis_id INTEGER, action TEXT NOT NULL, detail TEXT, at TEXT NOT NULL
);
"""

COLS_V1 = "thesis_id, source, source_thesis_id, title, year, report_url, source_code_url, first_seen, last_seen, missed_runs, status, origin"


def _migrate(con):
    """CSDL tạo từ bản đầu: thêm origin='manual' (cần dựng lại bảng vì SQLite không sửa được CHECK) và cột locked, hidden. Dữ liệu giữ nguyên."""
    sql = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='thesis_raw'").fetchone()[0]
    if "'manual'" in sql and "locked" in sql:
        return
    con.commit()
    con.execute("PRAGMA foreign_keys=OFF")                  # nếu không, DROP bảng cha sẽ xóa dây chuyền thesis_clean
    try:
        con.execute("BEGIN")
        # thứ tự theo hướng dẫn của SQLite: tạo bảng mới, chép, xóa bảng cũ, rồi đổi tên; đổi tên bảng cũ trước sẽ làm khóa ngoại của bảng con trỏ nhầm
        new = SCHEMA.split("CREATE INDEX")[0].replace("CREATE TABLE IF NOT EXISTS thesis_raw", "CREATE TABLE thesis_raw_new")
        con.execute(new)
        con.execute(f"INSERT INTO thesis_raw_new ({COLS_V1}) SELECT {COLS_V1} FROM thesis_raw")
        con.execute("DROP TABLE thesis_raw")
        con.execute("ALTER TABLE thesis_raw_new RENAME TO thesis_raw")
        con.execute("CREATE INDEX IF NOT EXISTS ix_thesis_status ON thesis_raw(status)")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")


def connect(path=None):
    con = jobsdb.connect(path)
    existed = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='thesis_raw'").fetchone()
    con.executescript(SCHEMA)
    if existed:
        _migrate(con)
    return con


def title_key(title):
    """Khóa so khớp tiêu đề: NFC, chữ thường, gộp khoảng trắng, bỏ dấu câu ở hai đầu."""
    t = unicodedata.normalize("NFC", str(title or "")).lower()
    return re.sub(r"\s+", " ", t).strip(" \t\r\n.,;:-–—\"'“”‘’")


def legacy_id(source, title):
    return "legacy-" + hashlib.sha1(f"{source}|{title_key(title)}".encode("utf-8")).hexdigest()[:12]


def _today(today):
    return str(today or date.today())


def _year(v):
    try:
        y = int(float(v))
    except (TypeError, ValueError):
        return None
    return y if 1990 <= y <= date.today().year + 1 else None


def upsert_thesis(con, source, sid, title, year=None, report_url=None, source_code_url=None, today=None, origin="crawl", thesis_id=None, advisors=None):
    """Thêm khóa luận mới hoặc cập nhật cái đã có. Trả về (thesis_id, is_new, title_changed).
    Nếu chưa có theo (source, sid) nhưng có bản 'legacy' cùng tiêu đề thì nhận bản đó (gắn sid thật) thay vì tạo bản trùng."""
    t = _today(today)
    title = unicodedata.normalize("NFC", str(title or "")).strip()
    if not title:
        raise ValueError("tiêu đề rỗng")
    vals = {"year": _year(year), "report_url": report_url or None, "source_code_url": source_code_url or None}
    vals = {k: v for k, v in vals.items() if v is not None}
    row = con.execute("SELECT thesis_id, title FROM thesis_raw WHERE source=? AND source_thesis_id=?", (source, sid)).fetchone()
    if row is None:
        for r in con.execute("SELECT thesis_id, title FROM thesis_raw WHERE source=? AND source_thesis_id LIKE 'legacy-%'", (source,)):
            if title_key(r["title"]) == title_key(title):
                row = r
                con.execute("UPDATE thesis_raw SET source_thesis_id=? WHERE thesis_id=?", (sid, r["thesis_id"]))
                break
    if row is None:
        cols = ["source", "source_thesis_id", "title", "first_seen", "last_seen", "origin"] + list(vals)
        args = [source, sid, title, t, t, origin] + list(vals.values())
        if thesis_id is not None:
            cols.insert(0, "thesis_id"); args.insert(0, int(thesis_id))
        cur = con.execute(f"INSERT INTO thesis_raw ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", args)
        tid = cur.lastrowid if thesis_id is None else int(thesis_id)
        set_advisors(con, tid, advisors)
        return tid, True, False
    st = con.execute("SELECT locked, hidden FROM thesis_raw WHERE thesis_id=?", (row["thesis_id"],)).fetchone()
    if st["locked"]:                       # quản trị viên đã sửa tay: crawl chỉ báo "còn thấy", không ghi đè nội dung
        con.execute("UPDATE thesis_raw SET last_seen=?, missed_runs=0 WHERE thesis_id=?", (t, row["thesis_id"]))
        return row["thesis_id"], False, False
    set_advisors(con, row["thesis_id"], advisors)
    changed = row["title"] != title
    sets = ["title=?", "last_seen=?", "missed_runs=0"] + ([] if st["hidden"] else ["status='active'"]) + [f"{k}=?" for k in vals]   # đã bị quản trị xóa thì không tự mở lại
    con.execute(f"UPDATE thesis_raw SET {','.join(sets)} WHERE thesis_id=?", [title, t] + list(vals.values()) + [row["thesis_id"]])
    return row["thesis_id"], False, changed


def set_advisors(con, thesis_id, names):
    """Ghi GVHD của một khóa luận. names rỗng/None thì giữ nguyên (trang nguồn không cung cấp thì không xóa dữ liệu có sẵn)."""
    names = adv.split_names(names)
    if not names:
        return False
    con.execute("DELETE FROM thesis_advisor WHERE thesis_id=?", (int(thesis_id),))
    con.executemany("INSERT INTO thesis_advisor (thesis_id, advisor) VALUES (?,?)", [(int(thesis_id), n) for n in names])
    return True


def advisors_of(con, thesis_id):
    return [r[0] for r in con.execute("SELECT advisor FROM thesis_advisor WHERE thesis_id=? ORDER BY advisor", (int(thesis_id),))]


def close_missing(con, run_id, run_source, source, seen_ids):
    """Gọi sau khi crawl XONG và ĐỦ danh sách. seen_ids = tập thesis_id đã thấy. Trả về số khóa luận vừa đóng."""
    seen = set(seen_ids)
    active = [r["thesis_id"] for r in con.execute("SELECT thesis_id FROM thesis_raw WHERE source=? AND status='active' AND origin!='manual'", (source,))]
    prev = con.execute("SELECT n_seen FROM crawl_runs WHERE source=? AND ok=1 AND run_id<? ORDER BY run_id DESC LIMIT 1", (run_source, run_id)).fetchone()
    suspicious = prev is not None and prev["n_seen"] > 0 and len(seen) < MIN_SEEN_RATIO * prev["n_seen"]
    closed, note = 0, None
    if suspicious:
        note = f"bất thường: lần này thấy {len(seen)} khóa luận, lần trước {prev['n_seen']}; bỏ qua việc đóng"
    else:
        for tid in active:
            if tid in seen:
                continue
            con.execute("UPDATE thesis_raw SET missed_runs=missed_runs+1 WHERE thesis_id=? AND status='active'", (tid,))
            closed += con.execute("UPDATE thesis_raw SET status='closed' WHERE thesis_id=? AND status='active' AND missed_runs>=?", (tid, MISS_TO_CLOSE)).rowcount
    con.execute("UPDATE crawl_runs SET n_closed=?, note=COALESCE(?,note), ok=CASE WHEN ? THEN 0 ELSE ok END WHERE run_id=?",
                (closed, note, int(suspicious), run_id))
    con.commit()
    return closed


def import_legacy(con, rows, sid_by_title=None, today=None):
    """Nhập khóa luận có sẵn (giữ NGUYÊN thesis_id để khớp embedding, Gold và nhãn đã duyệt).
    rows: iterable dict {thesis_id, title, year, source}. sid_by_title: {(source, title_key): mã nguồn} (ví dụ mã Notion của NEU). Trả về số dòng mới."""
    sid_by_title = sid_by_title or {}
    n = 0
    for r in rows:
        src, title = str(r["source"]), r["title"]
        sid = sid_by_title.get((src, title_key(title))) or legacy_id(src, title)
        _, new, _ = upsert_thesis(con, src, sid, title, year=r.get("year"), today=today, origin="legacy", thesis_id=r["thesis_id"])
        n += new
    con.commit()
    return n


def export_csv(con, out):
    """Xuất khóa luận đang hiệu lực, hợp lệ, không trùng, sắp theo thesis_id (đầu vào của embedding và process_thesis). Trả về số dòng."""
    import pandas as pd
    df = pd.read_sql_query(
        "SELECT r.thesis_id, COALESCE(c.title_norm, r.title) AS title, r.year, r.source, r.report_url, r.source_code_url "
        "FROM thesis_raw r LEFT JOIN thesis_clean c USING(thesis_id) "
        "WHERE r.status='active' AND COALESCE(c.valid,1)=1 AND c.dup_of IS NULL ORDER BY r.thesis_id", con)
    import json
    by = {}
    for r in con.execute("SELECT thesis_id, advisor FROM thesis_advisor ORDER BY advisor"):
        by.setdefault(r["thesis_id"], []).append(r["advisor"])
    df["advisors"] = [json.dumps(by.get(t, []), ensure_ascii=False) for t in df.thesis_id]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)
