"""CSDL tin tuyển dụng (SQLite): schema, upsert, đóng tin hết hạn, nhật ký crawl.

Crawler và script nhập dữ liệu chỉ dùng các hàm ở đây, không tự viết SQL. Backend vẫn đọc CSV cho tới khi chuyển sang đọc từ CSDL.
Tin không bao giờ bị xóa: hết hạn thì status='closed' (giữ lịch sử cho biểu đồ xu hướng).
"""
import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from ml import config as C

DB_PATH = C.ROOT / "data/db/jobs.sqlite"
MISS_TO_CLOSE = 2          # vắng mặt từ N lần crawl thành công liên tiếp thì đóng
MIN_SEEN_RATIO = 0.5       # lần crawl thấy < 50% số tin của lần crawl thành công trước thì coi là bất thường, không đóng tin nào

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  source_job_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title_raw TEXT, title_norm TEXT, role TEXT,
  company TEXT, location TEXT, working_model TEXT, salary_text TEXT,
  description TEXT, requirements TEXT, benefits TEXT,
  posted_at TEXT, deadline TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  missed_runs INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed')),
  is_it INTEGER NOT NULL DEFAULT 1,
  UNIQUE (source, source_job_id)
);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS ix_jobs_first_seen ON jobs(first_seen);
CREATE TABLE IF NOT EXISTS job_skills (
  job_id INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  origin TEXT NOT NULL DEFAULT 'listed' CHECK (origin IN ('listed','extracted')),
  PRIMARY KEY (job_id, skill)
);
CREATE INDEX IF NOT EXISTS ix_skills_skill ON job_skills(skill);
CREATE TABLE IF NOT EXISTS crawl_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
  n_seen INTEGER DEFAULT 0, n_new INTEGER DEFAULT 0, n_closed INTEGER DEFAULT 0,
  ok INTEGER NOT NULL DEFAULT 0, note TEXT
);
CREATE TABLE IF NOT EXISTS raw_pages (
  source TEXT NOT NULL, source_job_id TEXT NOT NULL, fetched_at TEXT NOT NULL, payload TEXT,
  PRIMARY KEY (source, source_job_id, fetched_at)
);
"""

JOB_COLS = ["title_raw", "title_norm", "role", "company", "location", "working_model", "salary_text",
            "description", "requirements", "benefits", "posted_at", "deadline", "is_it"]


def connect(path=None):
    p = Path(path or DB_PATH)
    if str(p) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=120)     # nhiều crawler cùng ghi thì chờ nhau tối đa 2 phút thay vì báo "database is locked"
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def source_of(url):
    host = urlparse(url).netloc.lower().replace("www.", "")
    return host.split(".")[0] or "unknown"


def source_job_id(url):
    """Mã tin: itviec lấy phần cuối đường dẫn; careerviet lấy mã giữa '.' và '.html'; còn lại lấy đường dẫn đã bỏ query."""
    path = urlparse(url).path.rstrip("/")
    m = re.search(r"\.([0-9A-Za-z]+)\.html$", path)
    return m.group(1) if m else (path.rsplit("/", 1)[-1] or path)


def _today(today):
    return str(today or date.today())


def upsert_job(con, url, skills=(), today=None, source=None, origin="listed", sid=None, **fields):
    """Thêm tin mới hoặc cập nhật tin đã có. Trả về (job_id, is_new). Giá trị rỗng/None không ghi đè dữ liệu đã có."""
    t = _today(today)
    src, sid = source or source_of(url), sid or source_job_id(url)
    row = con.execute("SELECT job_id FROM jobs WHERE source=? AND source_job_id=?", (src, sid)).fetchone()
    vals = {k: fields[k] for k in JOB_COLS if k in fields and fields[k] not in (None, "")}
    if row is None:
        cols = ["source", "source_job_id", "url", "first_seen", "last_seen"] + list(vals)
        cur = con.execute(f"INSERT INTO jobs ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                          [src, sid, url, t, t] + list(vals.values()))
        jid, new = cur.lastrowid, True
    else:
        jid, new = row["job_id"], False
        sets = ["url=?", "last_seen=?", "missed_runs=0", "status='active'"] + [f"{k}=?" for k in vals]
        con.execute(f"UPDATE jobs SET {','.join(sets)} WHERE job_id=?", [url, t] + list(vals.values()) + [jid])
    for s in skills:
        con.execute("INSERT OR IGNORE INTO job_skills (job_id, skill, origin) VALUES (?,?,?)", (jid, str(s).strip(), origin))
    return jid, new


def start_run(con, source, now=None):
    cur = con.execute("INSERT INTO crawl_runs (source, started_at) VALUES (?,?)", (source, now or datetime.now().isoformat(timespec="seconds")))
    con.commit()
    return cur.lastrowid


def close_missing(con, run_id, source, seen_ids, today=None):
    """Gọi sau khi crawl XONG một nguồn. Trả về số tin vừa đóng. Quy tắc:
    - tin quá deadline thì đóng ngay;
    - tin active không có trong seen_ids: tăng missed_runs, đủ MISS_TO_CLOSE lần liên tiếp thì đóng;
    - nếu lần crawl thấy ít hơn MIN_SEEN_RATIO so với lần crawl thành công trước (nghi bị chặn/lỗi) thì KHÔNG đóng tin nào vì lý do vắng mặt."""
    t = _today(today)
    seen = set(seen_ids)
    active = [r["job_id"] for r in con.execute("SELECT job_id FROM jobs WHERE source=? AND status='active'", (source,))]
    closed = con.execute("UPDATE jobs SET status='closed' WHERE source=? AND status='active' AND deadline IS NOT NULL AND deadline<?", (source, t)).rowcount
    prev = con.execute("SELECT n_seen FROM crawl_runs WHERE source=? AND ok=1 AND run_id<? ORDER BY run_id DESC LIMIT 1", (source, run_id)).fetchone()
    suspicious = prev is not None and prev["n_seen"] > 0 and len(seen) < MIN_SEEN_RATIO * prev["n_seen"]
    note = None
    if suspicious:
        note = f"bất thường: lần này thấy {len(seen)} tin, lần trước {prev['n_seen']}; bỏ qua việc đóng tin vì vắng mặt"
    else:
        for jid in active:
            if jid in seen:
                continue
            con.execute("UPDATE jobs SET missed_runs=missed_runs+1 WHERE job_id=? AND status='active'", (jid,))
            closed += con.execute("UPDATE jobs SET status='closed' WHERE job_id=? AND status='active' AND missed_runs>=?", (jid, MISS_TO_CLOSE)).rowcount
    con.execute("UPDATE crawl_runs SET n_closed=?, note=COALESCE(?,note) WHERE run_id=?", (closed, note, run_id))
    con.commit()
    return closed


def finish_run(con, run_id, n_seen, n_new, ok=True, note=None, now=None):
    cur = con.execute("SELECT note FROM crawl_runs WHERE run_id=?", (run_id,)).fetchone()
    if cur and str(cur["note"] or "").startswith("bất thường"):
        ok = False                       # close_missing đã nghi lần crawl này thiếu tin: không dùng nó làm mốc so sánh cho lần sau
    con.execute("UPDATE crawl_runs SET finished_at=?, n_seen=?, n_new=?, ok=?, note=COALESCE(?,note) WHERE run_id=?",
                (now or datetime.now().isoformat(timespec="seconds"), n_seen, n_new, int(ok), note, run_id))
    con.commit()


def parse_skills(s):
    try:
        v = json.loads(s)
        return [str(x) for x in v] if isinstance(v, list) else []
    except (TypeError, ValueError):
        return [x.strip() for x in str(s or "").split(",") if x.strip()]


def prune_source(con, source, keep_job_ids):
    """Xóa hẳn các tin của một nguồn không nằm trong keep_job_ids (kể cả kỹ năng, bản chụp thô). Chỉ dùng khi thu hẹp phạm vi crawl. Trả về số tin đã xóa."""
    keep = set(keep_job_ids)
    drop = [(r["job_id"], r["source_job_id"]) for r in con.execute("SELECT job_id, source_job_id FROM jobs WHERE source=?", (source,)) if r["job_id"] not in keep]
    for jid, sid in drop:
        con.execute("DELETE FROM raw_pages WHERE source=? AND source_job_id=?", (source, sid))
        con.execute("DELETE FROM jobs WHERE job_id=?", (jid,))
    con.commit()
    return len(drop)
