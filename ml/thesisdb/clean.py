"""Tầng sạch cho khóa luận: chuẩn hóa tiêu đề, kiểm tra hợp lệ, đánh dấu bản trùng. Dựng lại hoàn toàn từ thesis_raw mỗi lần chạy."""
import re
import unicodedata
from datetime import datetime

from ml.thesisdb import db


def norm_title(title):
    t = unicodedata.normalize("NFC", str(title or ""))
    return re.sub(r"\s+", " ", t).strip()


def run(con, now=None):
    """Trả về thống kê. Bản 'legacy' không bao giờ bị coi là trùng (giữ nguyên bộ dữ liệu đã gán nhãn);
    bản mới (crawl) trùng tiêu đề với bản khác đang hiệu lực thì ghi dup_of trỏ về bản cũ nhất."""
    now = now or datetime.now().isoformat(timespec="seconds")
    rows = con.execute("SELECT thesis_id, title, status, origin FROM thesis_raw ORDER BY thesis_id").fetchall()
    first = {}
    for r in rows:
        if r["status"] == "active":
            first.setdefault(db.title_key(r["title"]), r["thesis_id"])
    con.execute("DELETE FROM thesis_clean")
    st = dict(total=len(rows), valid=0, invalid=0, dup=0)
    for r in rows:
        tn = norm_title(r["title"])
        valid, reason, dup = 1, None, None
        if len(tn.split()) < 2:
            valid, reason = 0, "title_too_short"
        k = db.title_key(tn)
        if valid and r["status"] == "active" and r["origin"] == "crawl" and first.get(k, r["thesis_id"]) != r["thesis_id"]:
            dup, reason = first[k], "duplicate_title"
        con.execute("INSERT INTO thesis_clean (thesis_id, title_norm, valid, reason, dup_of, rules_version, cleaned_at) VALUES (?,?,?,?,?,?,?)",
                    (r["thesis_id"], tn, valid, reason, dup, db.RULES_VERSION, now))
        st["valid" if valid else "invalid"] += 1
        st["dup"] += dup is not None
    con.commit()
    return st
