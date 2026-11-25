"""Nhóm công việc (role) hiển thị cho sinh viên. Nhóm nhỏ (ít job) được gộp vào nhóm cha; khi một nhóm đang gộp đạt ngưỡng thì thành
"đề xuất tách riêng" chờ admin duyệt. Không sửa job_title trong dữ liệu: chỉ là lớp hiển thị, quyết định lưu ở data/repository/role_groups.csv.

role_groups.csv: role, parent_role (rỗng = "Nhóm khác"), status (merged | own), reason, keep_until_count, decided_at, decided_by
  - merged: đang gộp vào parent_role. Nếu số job của role đạt ngưỡng (và vượt keep_until_count) thì xuất hiện trong danh sách chờ duyệt.
  - own: admin đã duyệt tách riêng.
  - Role không có dòng nào: giữ riêng nếu đủ ngưỡng, ngược lại vào "Nhóm khác" và hiện trong danh sách "chưa có nhóm cha".
Ngưỡng dùng cùng MIN_SUPPORT/MIN_COMPANIES với các bảng thị trường.
"""
import math
import os
import tempfile
import threading
from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd

from backend.errors import BadRequest, NotFound
from backend.services.common import jsonable
from ml.recommendation import market_demand as MD

MIN_SUPPORT, MIN_COMPANIES = MD.MIN_SUPPORT, MD.MIN_COMPANIES
OTHER = "Nhóm khác"
FILE = "data/repository/role_groups.csv"
COLS = ["role", "parent_role", "status", "reason", "keep_until_count", "decided_at", "decided_by"]
_LOCK = threading.Lock()


def _path(ds):
    return ds.root / FILE


def _read(ds):
    p = _path(ds)
    if not p.exists():
        return {}
    df = pd.read_csv(p, encoding="utf-8-sig", dtype=str).fillna("")
    return {r["role"]: r for r in df.to_dict("records") if r.get("role")}


def _write(ds, rows):
    p = _path(ds)
    p.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{c: r.get(c, "") for c in COLS} for r in rows.values()], columns=COLS)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    os.close(fd)
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, p)                                # ghi nguyên tử, không để file dở dang


def _stats(ds):
    cnt, comp = defaultdict(int), defaultdict(set)
    for t, c in zip(ds.jobs.job_title.fillna("").astype(str), ds.jobs.company.fillna("").astype(str)):
        if t:
            cnt[t] += 1; comp[t].add(c)
    return cnt, {t: len(v) for t, v in comp.items()}


def _big(cnt, ncomp, t):
    return cnt[t] >= MIN_SUPPORT and ncomp.get(t, 0) >= MIN_COMPANIES


def _keep(dec):
    try:
        return int(float(dec.get("keep_until_count") or 0))
    except ValueError:
        return 0


def _view(ds):
    """Tính nhóm hiển thị của từng role, danh sách chờ duyệt và role chưa có nhóm cha."""
    cnt, ncomp = _stats(ds)
    dec = _read(ds)
    group_of, pending, unassigned = {}, [], []
    for t in cnt:
        d, big = dec.get(t), _big(cnt, ncomp, t)
        if d and d.get("status") == "own":
            group_of[t] = t
        elif d and d.get("status") == "merged":
            group_of[t] = d.get("parent_role") or OTHER
            if big and cnt[t] > _keep(d):
                pending.append(t)
        elif big:
            group_of[t] = t
        else:
            group_of[t] = OTHER; unassigned.append(t)
    return cnt, ncomp, dec, group_of, pending, unassigned


def titles_for(ds, role):
    """Các job_title thuộc một nhóm (tên nhóm hoặc tên role). Tên lạ thì coi là khớp đúng một job_title."""
    cnt, _, _, group_of, _, _ = _view(ds)
    t = {r for r, g in group_of.items() if g == role}
    return t or {role}


def roles(ds):
    cnt, ncomp, dec, group_of, pending, unassigned = _view(ds)
    total = sum(cnt.values()) or 1
    members = defaultdict(list)
    for r, g in group_of.items():
        members[g].append(r)
    out = []
    for g, ms in members.items():
        n = sum(cnt[m] for m in ms)
        out.append(dict(name=g, job_count=n, share=round(n / total, 4), is_other=(g == OTHER),
                        children=sorted([dict(role=m, job_count=cnt[m]) for m in ms if m != g], key=lambda x: -x["job_count"])))
    out.sort(key=lambda x: (x["is_other"], -x["job_count"]))
    return jsonable(dict(total_jobs=int(sum(cnt.values())), thresholds=dict(min_support=MIN_SUPPORT, min_companies=MIN_COMPANIES), groups=out,
                         pending_count=len(pending), unassigned_count=len(unassigned)))


def admin_view(ds):
    cnt, ncomp, dec, group_of, pending, unassigned = _view(ds)
    base = roles(ds)
    own_groups = [g["name"] for g in base["groups"] if not g["is_other"]]
    pend = [dict(role=t, job_count=cnt[t], n_companies=ncomp.get(t, 0), parent_role=dec[t].get("parent_role") or OTHER, reason=dec[t].get("reason", "")) for t in sorted(pending, key=lambda x: -cnt[x])]
    merged = [dict(role=t, job_count=cnt.get(t, 0), n_companies=ncomp.get(t, 0), parent_role=d.get("parent_role") or OTHER, reason=d.get("reason", ""), decided_by=d.get("decided_by", ""))
              for t, d in dec.items() if d.get("status") == "merged" and t not in pending]
    un = [dict(role=t, job_count=cnt[t], n_companies=ncomp.get(t, 0)) for t in sorted(unassigned, key=lambda x: -cnt[x])]
    return jsonable(dict(base, parent_choices=own_groups, pending=pend, merged=sorted(merged, key=lambda x: -x["job_count"]), unassigned=un))


def decide(ds, role, action, parent=None, by="admin"):
    """action: approve_split (tách riêng), keep_merged (giữ gộp, hỏi lại khi tăng thêm 50%), merge (đặt nhóm cha; parent rỗng = Nhóm khác)."""
    cnt, ncomp, dec, group_of, pending, unassigned = _view(ds)
    if role not in cnt:
        raise NotFound(f"không có nhóm công việc '{role}' trong dữ liệu")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOCK:
        rows = _read(ds)
        cur = rows.get(role, dict(role=role, parent_role="", status="merged", reason=""))
        if action == "approve_split":
            if role not in pending:
                raise BadRequest("chỉ duyệt tách riêng được nhóm đang gộp và đã đạt ngưỡng")
            cur.update(status="own", keep_until_count="")
        elif action == "keep_merged":
            if role not in pending:
                raise BadRequest("chỉ giữ gộp được nhóm đang chờ duyệt")
            cur.update(status="merged", keep_until_count=str(math.ceil(cnt[role] * 1.5)))
        elif action == "merge":
            parent = (parent or "").strip()
            if parent == OTHER:
                parent = ""
            if parent:
                if parent == role:
                    raise BadRequest("không thể gộp một nhóm vào chính nó")
                if parent not in cnt or group_of.get(parent) != parent:
                    raise BadRequest("nhóm cha phải là một nhóm đang hiển thị riêng")
            cur.update(status="merged", parent_role=parent, keep_until_count="")
        else:
            raise BadRequest("action phải là approve_split, keep_merged hoặc merge")
        cur.update(decided_at=now, decided_by=by)
        rows[role] = cur
        _write(ds, rows)
    return admin_view(ds)
