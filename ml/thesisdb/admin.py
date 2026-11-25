"""Thêm, sửa, xóa (mềm), khôi phục đề tài khóa luận và chỉnh nhãn tay, cho trang quản trị. Không phụ thuộc FastAPI nên kiểm thử được riêng.

- Mọi thay đổi ghi vào thesis_raw + thesis_admin_log; dữ liệu website chỉ đổi sau khi chạy lại scripts/build_thesis_data.py.
- Xóa là đóng (status='closed', hidden=1): không mất dữ liệu, crawl không tự mở lại. Khôi phục đưa về active.
- Bản ghi quản trị viên sửa hoặc thêm bị khóa (locked=1): crawl không ghi đè nội dung; bản thêm tay (origin='manual') không bị crawl đóng.
- Nhãn chỉnh tay lưu ở thesis_label_override và được áp lên kết quả của mô hình khi dựng dữ liệu.
"""
import json
import uuid
from datetime import date, datetime

from ml.thesisdb import advisors as adv, db

MAX_TITLE = 300
SORT = {"newest": "r.thesis_id DESC", "oldest": "r.thesis_id ASC", "year": "r.year DESC, r.thesis_id DESC", "title": "r.title COLLATE NOCASE ASC"}


class Invalid(ValueError):
    """Dữ liệu nhập không hợp lệ; thông báo hiển thị thẳng cho người dùng."""


class Missing(LookupError):
    """Không có khóa luận này."""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _log(con, thesis_id, action, detail=None):
    con.execute("INSERT INTO thesis_admin_log (thesis_id, action, detail, at) VALUES (?,?,?,?)",
                (thesis_id, action, json.dumps(detail, ensure_ascii=False) if detail is not None else None, _now()))


def _title(v):
    t = " ".join(str(v or "").split())
    if len(t.split()) < 2:
        raise Invalid("Tiêu đề cần ít nhất 2 từ.")
    if len(t) > MAX_TITLE:
        raise Invalid(f"Tiêu đề dài quá {MAX_TITLE} ký tự.")
    return t


def _year(v):
    if v in (None, ""):
        return None
    y = db._year(v)
    if y is None:
        raise Invalid(f"Năm phải nằm trong khoảng 1990 đến {date.today().year + 1}.")
    return y


def _url(v, what):
    v = (v or "").strip()
    if not v:
        return None
    if not v.startswith(("https://", "http://")) or " " in v or len(v) > 2000:
        raise Invalid(f"Đường dẫn {what} phải bắt đầu bằng http:// hoặc https:// và không chứa khoảng trắng.")
    return v


def _source(v):
    v = (v or "neu").strip().lower()
    if not v or len(v) > 30 or not all(c.isalnum() or c in "_-" for c in v):
        raise Invalid("Nguồn chỉ gồm chữ, số, dấu gạch dưới hoặc gạch ngang (ví dụ: neu).")
    return v


def _row(con, thesis_id):
    r = con.execute("SELECT * FROM thesis_raw WHERE thesis_id=?", (int(thesis_id),)).fetchone()
    if r is None:
        raise Missing(f"không có khóa luận {thesis_id}")
    return r


def _dup(con, title, exclude=None):
    k = db.title_key(title)
    for r in con.execute("SELECT thesis_id, title, status, hidden FROM thesis_raw"):
        if r["thesis_id"] != exclude and db.title_key(r["title"]) == k:
            return r
    return None


def _dup_error(r):
    if r["status"] == "closed" or r["hidden"]:
        return Invalid(f"Đã có khóa luận cùng tiêu đề (mã {r['thesis_id']}) nhưng đang bị đóng; hãy khôi phục nó thay vì thêm mới.")
    return Invalid(f"Đã có khóa luận cùng tiêu đề (mã {r['thesis_id']}).")


def add(con, title, year=None, source="neu", report_url=None, source_code_url=None, today=None, advisors=None):
    title, year, source = _title(title), _year(year), _source(source)
    ru, su = _url(report_url, "báo cáo"), _url(source_code_url, "mã nguồn")
    d = _dup(con, title)
    if d is not None:
        raise _dup_error(d)
    t = str(today or date.today())
    cur = con.execute("INSERT INTO thesis_raw (source, source_thesis_id, title, year, report_url, source_code_url, first_seen, last_seen, origin, locked) "
                      "VALUES (?,?,?,?,?,?,?,?,'manual',1)", (source, "manual-" + uuid.uuid4().hex[:12], title, year, ru, su, t, t))
    tid = cur.lastrowid
    db.set_advisors(con, tid, advisors)
    _log(con, tid, "add", dict(title=title, year=year, source=source, advisors=db.advisors_of(con, tid)))
    con.commit()
    return tid


FIELDS = ("title", "year", "source", "report_url", "source_code_url", "advisors")


def update(con, thesis_id, **fields):
    """Chỉ sửa những trường được truyền. Trường để rỗng (chuỗi trống) sẽ xóa giá trị (với năm và đường dẫn)."""
    r = _row(con, thesis_id)
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise Invalid("Không sửa được trường: " + ", ".join(sorted(unknown)))
    new = {}
    if "title" in fields:
        new["title"] = _title(fields["title"])
        d = _dup(con, new["title"], exclude=r["thesis_id"])
        if d is not None:
            raise _dup_error(d)
    if "year" in fields:
        new["year"] = _year(fields["year"])
    if "source" in fields:
        new["source"] = _source(fields["source"])
    if "report_url" in fields:
        new["report_url"] = _url(fields["report_url"], "báo cáo")
    if "source_code_url" in fields:
        new["source_code_url"] = _url(fields["source_code_url"], "mã nguồn")
    changed = {k: v for k, v in new.items() if r[k] != v}
    new_adv = None
    if "advisors" in fields:
        new_adv = adv.split_names(fields["advisors"])
        if new_adv == db.advisors_of(con, r["thesis_id"]):
            new_adv = None
    if not changed and new_adv is None:
        return False
    log = {k: [r[k], v] for k, v in changed.items()}
    if changed:
        sets = ",".join(f"{k}=?" for k in changed)
        con.execute(f"UPDATE thesis_raw SET {sets} WHERE thesis_id=?", list(changed.values()) + [r["thesis_id"]])
    if new_adv is not None:
        log["advisors"] = [db.advisors_of(con, r["thesis_id"]), new_adv]
        con.execute("DELETE FROM thesis_advisor WHERE thesis_id=?", (r["thesis_id"],))
        db.set_advisors(con, r["thesis_id"], new_adv)
    con.execute("UPDATE thesis_raw SET locked=1 WHERE thesis_id=?", (r["thesis_id"],))
    _log(con, r["thesis_id"], "update", log)
    con.commit()
    return True


def delete(con, thesis_id):
    r = _row(con, thesis_id)
    if r["status"] == "closed" and r["hidden"]:
        return False
    con.execute("UPDATE thesis_raw SET status='closed', hidden=1 WHERE thesis_id=?", (r["thesis_id"],))
    _log(con, r["thesis_id"], "delete", dict(title=r["title"]))
    con.commit()
    return True


def restore(con, thesis_id):
    r = _row(con, thesis_id)
    if r["status"] == "active" and not r["hidden"]:
        return False
    d = _dup(con, r["title"], exclude=r["thesis_id"])
    if d is not None and d["status"] == "active":
        raise Invalid(f"Đã có khóa luận cùng tiêu đề đang hiệu lực (mã {d['thesis_id']}); không khôi phục để tránh trùng.")
    con.execute("UPDATE thesis_raw SET status='active', hidden=0, missed_runs=0 WHERE thesis_id=?", (r["thesis_id"],))
    _log(con, r["thesis_id"], "restore", dict(title=r["title"]))
    con.commit()
    return True


def set_labels(con, thesis_id, topics, domains, valid_topics, valid_domains, note=None):
    """Đặt nhãn tay. topics/domains: danh sách tên nhãn. Rỗng cả hai nghĩa là xóa nhãn tay (trở về nhãn của mô hình)."""
    _row(con, thesis_id)
    topics, domains = list(dict.fromkeys(topics or [])), list(dict.fromkeys(domains or []))
    bad = [x for x in topics if x not in valid_topics] + [x for x in domains if x not in valid_domains]
    if bad:
        raise Invalid("Nhãn không có trong danh sách: " + ", ".join(bad))
    if len(topics) > 4 or len(domains) > 3:
        raise Invalid("Tối đa 4 chủ đề kỹ thuật và 3 lĩnh vực cho mỗi khóa luận.")
    if not topics and not domains:
        con.execute("DELETE FROM thesis_label_override WHERE thesis_id=?", (int(thesis_id),))
        _log(con, thesis_id, "labels_clear")
    else:
        con.execute("INSERT INTO thesis_label_override (thesis_id, technical_topics, domains, note, updated_at) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(thesis_id) DO UPDATE SET technical_topics=excluded.technical_topics, domains=excluded.domains, note=excluded.note, updated_at=excluded.updated_at",
                    (int(thesis_id), json.dumps(topics, ensure_ascii=False), json.dumps(domains, ensure_ascii=False), note, _now()))
        _log(con, thesis_id, "labels", dict(topics=topics, domains=domains))
    con.commit()


def overrides(con):
    """{thesis_id: (danh sách chủ đề, danh sách lĩnh vực)} cho bước dựng dữ liệu."""
    return {r["thesis_id"]: (json.loads(r["technical_topics"]), json.loads(r["domains"])) for r in con.execute("SELECT * FROM thesis_label_override")}


def pending_since(con, since):
    """Số thao tác quản trị sau thời điểm `since` (chuỗi ISO) tức chưa được dựng vào dữ liệu website. since rỗng: đếm tất cả."""
    return con.execute("SELECT COUNT(*) FROM thesis_admin_log WHERE at > ?", (since or "",)).fetchone()[0]


def listing(con, q="", status="", source="", origin="", sort="newest", limit=25, offset=0):
    where, args = [], []
    if q:
        where.append("r.title LIKE ? ESCAPE '\\'")
        args.append("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if status in ("active", "closed"):
        where.append("r.status=?"); args.append(status)
    if source:
        where.append("r.source=?"); args.append(source)
    if origin in ("legacy", "crawl", "manual"):
        where.append("r.origin=?"); args.append(origin)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = con.execute("SELECT COUNT(*) FROM thesis_raw r" + w, args).fetchone()[0]
    rows = con.execute("SELECT r.thesis_id, r.source, r.title, r.year, r.report_url, r.source_code_url, r.status, r.origin, r.locked, r.hidden, r.last_seen, "
                       "(o.thesis_id IS NOT NULL) AS has_override FROM thesis_raw r LEFT JOIN thesis_label_override o USING(thesis_id)" + w +
                       f" ORDER BY {SORT.get(sort, SORT['newest'])} LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
    out = [dict(r) for r in rows]
    for r in out:
        r["advisors"] = db.advisors_of(con, r["thesis_id"])
    return total, out


def sources(con):
    return [r[0] for r in con.execute("SELECT DISTINCT source FROM thesis_raw ORDER BY source")]
