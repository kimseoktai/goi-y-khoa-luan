"""Quản trị khóa luận: danh sách, thêm, sửa, xóa mềm, khôi phục, chỉnh nhãn tay. Logic nằm ở ml.thesisdb.admin; ở đây chỉ nối với DataStore và đổi lỗi sang lỗi HTTP."""
import json
from pathlib import Path

from backend.errors import BadRequest, NotFound
from ml.thesisdb import admin, db

STATE = "data/processed/thesis/.thesis_build_state.json"


def _con(ds):
    return db.connect(Path(ds.root) / "data/db/jobs.sqlite")


def _wrap(fn, *a, **k):
    try:
        return fn(*a, **k)
    except admin.Invalid as e:
        raise BadRequest(str(e))
    except admin.Missing as e:
        raise NotFound(str(e))


def _built_at(ds):
    p = Path(ds.root) / STATE
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("built_at", "")
    except (OSError, ValueError):
        return ""


def _names(ds, df, col):
    d = df[df.status == "active"] if "status" in df else df
    return d[col].tolist()


def _labels(ds, tid, override):
    """Nhãn đang hiển thị trên website (từ dữ liệu đã dựng) hoặc nhãn chỉnh tay đang chờ dựng."""
    if override is not None:
        return dict(topics=override[0], domains=override[1], label_source="manual", built=False)
    i = ds.thesis_pos.get(str(tid))
    if i is None:
        return dict(topics=[], domains=[], label_source=None, built=False)
    return dict(topics=ds.thesis._technical_topics.iloc[i], domains=ds.thesis._domains.iloc[i], label_source=str(ds.thesis.label_source.iloc[i]), built=True)


def listing(ds, q="", status="", source="", origin="", sort="newest", limit=25, offset=0):
    con = _con(ds)
    try:
        total, rows = admin.listing(con, q.strip(), status, source, origin, sort, limit, offset)
        ov = admin.overrides(con)
        for r in rows:
            r["labels"] = _labels(ds, r["thesis_id"], ov.get(r["thesis_id"]))
        return dict(total=total, items=rows, sources=admin.sources(con), pending=admin.pending_since(con, _built_at(ds)),
                    topics=_names(ds, ds.topics, "topic_name"), domains=_names(ds, ds.domains, "domain_name"))
    finally:
        con.close()


def add(ds, **f):
    con = _con(ds)
    try:
        return dict(ok=True, thesis_id=_wrap(admin.add, con, **f))
    finally:
        con.close()


def update(ds, thesis_id, fields):
    con = _con(ds)
    try:
        return dict(ok=True, changed=_wrap(admin.update, con, thesis_id, **fields))
    finally:
        con.close()


def delete(ds, thesis_id):
    con = _con(ds)
    try:
        return dict(ok=True, changed=_wrap(admin.delete, con, thesis_id))
    finally:
        con.close()


def restore(ds, thesis_id):
    con = _con(ds)
    try:
        return dict(ok=True, changed=_wrap(admin.restore, con, thesis_id))
    finally:
        con.close()


def set_labels(ds, thesis_id, topics, domains, note=None):
    con = _con(ds)
    try:
        _wrap(admin.set_labels, con, thesis_id, topics, domains, set(ds.topics.topic_name), set(ds.domains.domain_name), note)
        return dict(ok=True)
    finally:
        con.close()
