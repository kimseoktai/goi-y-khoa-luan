"""Tài khoản theo mã sinh viên: danh sách mã được phép vào (do quản trị nhập), phiên đăng nhập và hồ sơ lưu theo từng mã.
Lưu ở data/db/accounts.sqlite (tách khỏi jobs.sqlite để các lần dựng lại dữ liệu không xóa mất hồ sơ sinh viên).
Sinh viên chỉ cần mã đúng định dạng (tự được tạo ở lần đăng nhập đầu); mã admin phải có sẵn trong CSDL và nhập thêm mã quản trị (REC_ADMIN_TOKEN)."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from backend.errors import BadRequest, NotFound, Unauthorized

ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,24}$")
STUDENT_ID_PATTERN = r"^11\d{6}$"          # mã sinh viên hợp lệ: 8 chữ số, luôn bắt đầu bằng 11 (ví dụ 11236197); mã đúng định dạng được tự tạo khi đăng nhập lần đầu
FORMAT_HINT = "Mã sinh viên gồm 8 chữ số và bắt đầu bằng 11 (ví dụ 11236197)."
ROLES = ("student", "admin")
SESSION_DAYS = 30
STATE_MAX = 200_000                 # byte, đủ cho hàng trăm đề tài đã lưu
RANGE_MAX = 5000                    # tối đa số mã sinh ra từ một dãy a-b
SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
  student_id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT 'student',
  created_at REAL NOT NULL, last_login REAL);
CREATE TABLE IF NOT EXISTS student_state (
  student_id TEXT PRIMARY KEY REFERENCES students(student_id) ON DELETE CASCADE, state_json TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
  created_at REAL NOT NULL, expires_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sessions_student ON sessions(student_id);
"""


def _con(root):
    p = Path(root) / "data/db/accounts.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def norm_id(s):
    return str(s or "").strip().upper()


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- nhập danh sách mã ----------
def parse_ids(text, default_role="student"):
    """Mỗi dòng: `mã`, `mã,tên`, `mã,tên,vai trò` hoặc dãy `11200001-11200050` (cùng độ dài, tăng dần).
    Trả về (danh sách (mã, tên, vai trò), danh sách dòng lỗi)."""
    if default_role not in ROLES:
        raise BadRequest("vai trò phải là student hoặc admin")
    rows, bad, seen = [], [], set()
    for ln, raw in enumerate(re.split(r"[\r\n;]+", str(text or "")), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"[,\t]", line)]
        ident, name = parts[0], (parts[1] if len(parts) > 1 else "")
        role = parts[2].lower() if len(parts) > 2 and parts[2] else default_role
        if role not in ROLES:
            bad.append("dòng %d: vai trò '%s' không hợp lệ" % (ln, parts[2])); continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", ident)
        if m:
            a, b = m.group(1), m.group(2)
            if len(a) != len(b) or int(a) > int(b) or int(b) - int(a) + 1 > RANGE_MAX:
                bad.append("dòng %d: dãy '%s' không hợp lệ (cùng độ dài, tăng dần, tối đa %d mã)" % (ln, ident, RANGE_MAX)); continue
            ids = [str(i).zfill(len(a)) for i in range(int(a), int(b) + 1)]
            name = ""                                          # dãy không có tên riêng
        else:
            ids = [norm_id(ident)]
        for i in ids:
            if not ID_RE.match(i):
                bad.append("dòng %d: mã '%s' không hợp lệ (3-24 ký tự chữ, số, . _ -)" % (ln, i)); break
            if i in seen:
                continue
            seen.add(i)
            rows.append((i, name[:120], role))
    return rows, bad[:20]


def import_students(root, text, default_role="student"):
    rows, bad = parse_ids(text, default_role)
    if not rows and not bad:
        raise BadRequest("chưa có mã nào để nhập")
    now = time.time()
    added = updated = 0
    with closing(_con(root)) as con, con:
        for i, name, role in rows:
            cur = con.execute("SELECT name, role FROM students WHERE student_id=?", (i,)).fetchone()
            if cur is None:
                con.execute("INSERT INTO students(student_id,name,role,created_at) VALUES(?,?,?,?)", (i, name, role, now)); added += 1
            else:
                new_name = name or cur["name"]
                if new_name != cur["name"] or role != cur["role"]:
                    con.execute("UPDATE students SET name=?, role=? WHERE student_id=?", (new_name, role, i)); updated += 1
    return {"added": added, "updated": updated, "unchanged": len(rows) - added - updated, "invalid": bad}


def list_students(root, q="", role="", limit=50, offset=0):
    where, args = [], []
    if q:
        where.append("(s.student_id LIKE ? OR s.name LIKE ?)"); args += ["%" + q.strip().upper() + "%", "%" + q.strip() + "%"]
    if role in ROLES:
        where.append("s.role=?"); args.append(role)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    with closing(_con(root)) as con:
        total = con.execute("SELECT COUNT(*) FROM students s" + w, args).fetchone()[0]
        by_role = {r["role"]: r["n"] for r in con.execute("SELECT role, COUNT(*) n FROM students GROUP BY role")}
        rows = con.execute("SELECT s.student_id, s.name, s.role, s.last_login, st.state_json, st.updated_at FROM students s LEFT JOIN student_state st USING(student_id)"
                           + w + " ORDER BY s.student_id LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
    items = []
    for r in rows:
        n_saved = n_skills = 0
        if r["state_json"]:
            try:
                d = json.loads(r["state_json"]); n_saved = len(d.get("saved") or []); n_skills = len(d.get("skills") or [])
            except ValueError:
                pass
        items.append({"student_id": r["student_id"], "name": r["name"], "role": r["role"], "last_login": r["last_login"], "saved": n_saved, "skills": n_skills})
    return {"total": total, "by_role": by_role, "items": items}


def _other_admins(con, sid):
    return con.execute("SELECT COUNT(*) FROM students WHERE role='admin' AND student_id<>?", (sid,)).fetchone()[0]


def save_student(root, student_id, name="", role="student", create=False):
    """Thêm một sinh viên (create=True) hoặc sửa tên và quyền của mã đã có. Sửa thì ghi đúng giá trị gửi lên, kể cả xóa tên."""
    sid = norm_id(student_id)
    if not ID_RE.match(sid):
        raise BadRequest("mã không hợp lệ: 3 đến 24 ký tự gồm chữ, số, dấu chấm, gạch ngang hoặc gạch dưới")
    if role not in ROLES:
        raise BadRequest("quyền không hợp lệ")
    name = " ".join(str(name or "").split())[:80]
    with closing(_con(root)) as con, con:
        cur = con.execute("SELECT role FROM students WHERE student_id=?", (sid,)).fetchone()
        if create:
            if cur is not None:
                raise BadRequest("mã này đã có trong danh sách")
            con.execute("INSERT INTO students(student_id,name,role,created_at) VALUES(?,?,?,?)", (sid, name, role, time.time()))
        else:
            if cur is None:
                raise NotFound("không có mã sinh viên này")
            if cur["role"] == "admin" and role != "admin" and _other_admins(con, sid) == 0:
                raise BadRequest("đây là quản trị viên cuối cùng, không thể hạ quyền")
            con.execute("UPDATE students SET name=?, role=? WHERE student_id=?", (name, role, sid))
            if cur["role"] != role:
                con.execute("DELETE FROM sessions WHERE student_id=?", (sid,))        # đổi quyền thì bắt đăng nhập lại để quyền mới có hiệu lực
    return {"student_id": sid, "name": name, "role": role, "created": bool(create)}


def delete_student(root, student_id):
    with closing(_con(root)) as con, con:
        row = con.execute("SELECT role FROM students WHERE student_id=?", (norm_id(student_id),)).fetchone()
        if row and row["role"] == "admin" and _other_admins(con, norm_id(student_id)) == 0:
            raise BadRequest("đây là quản trị viên cuối cùng, không thể xóa")
        n = con.execute("DELETE FROM students WHERE student_id=?", (norm_id(student_id),)).rowcount
    if not n:
        raise NotFound("không có mã sinh viên này")
    return {"deleted": norm_id(student_id)}


# ---------- đăng nhập, phiên ----------
def login(root, admin_token, student_id, secret="", pattern=STUDENT_ID_PATTERN):
    sid = norm_id(student_id)
    if not ID_RE.match(sid):
        raise BadRequest(FORMAT_HINT)
    with closing(_con(root)) as con, con:
        row = con.execute("SELECT student_id, name, role FROM students WHERE student_id=?", (sid,)).fetchone()
        if row is None:
            if not re.fullmatch(pattern or STUDENT_ID_PATTERN, sid):
                raise Unauthorized(FORMAT_HINT)                               # không phải mã sinh viên đúng định dạng và cũng không phải mã quản trị có sẵn
            con.execute("INSERT INTO students(student_id,name,role,created_at) VALUES(?,?,?,?)", (sid, "", "student", time.time()))
            row = {"student_id": sid, "name": "", "role": "student"}
        token = secrets.token_urlsafe(32)
        now = time.time()
        con.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        con.execute("INSERT INTO sessions(token_hash,student_id,created_at,expires_at) VALUES(?,?,?,?)", (_hash(token), sid, now, now + SESSION_DAYS * 86400))
        con.execute("UPDATE students SET last_login=? WHERE student_id=?", (now, sid))
    return {"status": "ok", "token": token, "student": {"student_id": row["student_id"], "name": row["name"], "role": row["role"]}}


def session(root, token):
    if not token:
        raise Unauthorized("Bạn chưa đăng nhập.")
    with closing(_con(root)) as con:
        row = con.execute("SELECT s.student_id, s.name, s.role, x.expires_at FROM sessions x JOIN students s USING(student_id) WHERE x.token_hash=?", (_hash(token),)).fetchone()
    if row is None or row["expires_at"] < time.time():
        raise Unauthorized("Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.")
    return {"student_id": row["student_id"], "name": row["name"], "role": row["role"]}


def logout(root, token):
    if token:
        with closing(_con(root)) as con, con:
            con.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(token),))
    return {"ok": True}


# ---------- hồ sơ theo mã ----------
def get_state(root, student_id):
    with closing(_con(root)) as con:
        row = con.execute("SELECT state_json, updated_at FROM student_state WHERE student_id=?", (student_id,)).fetchone()
    if row is None:
        return {"state": None, "updated_at": None}
    try:
        return {"state": json.loads(row["state_json"]), "updated_at": row["updated_at"]}
    except ValueError:
        return {"state": None, "updated_at": row["updated_at"]}


def save_state(root, student_id, state):
    if not isinstance(state, dict):
        raise BadRequest("hồ sơ phải là một đối tượng JSON")
    keep = {k: state[k] for k in ("welcomed", "skills", "roles", "saved") if k in state}        # chỉ giữ các trường app dùng
    raw = json.dumps(keep, ensure_ascii=False)
    if len(raw.encode("utf-8")) > STATE_MAX:
        raise BadRequest("hồ sơ quá lớn (tối đa %d KB)" % (STATE_MAX // 1000))
    now = time.time()
    with closing(_con(root)) as con, con:
        con.execute("INSERT INTO student_state(student_id,state_json,updated_at) VALUES(?,?,?) ON CONFLICT(student_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
                    (student_id, raw, now))
    return {"updated_at": now}
