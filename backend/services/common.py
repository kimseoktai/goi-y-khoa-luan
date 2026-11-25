"""Tiện ích dùng chung: chuyển kiểu numpy/NaN sang JSON, phân trang, kiểm tra tham số."""
import math
import numpy as np
import pandas as pd

from backend.errors import BadRequest, NotFound


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) or math.isinf(float(x)) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if x is pd.NA or x is pd.NaT:
        return None
    return x


def opt(row, name):
    """Giá trị tùy chọn của một dòng Job (cột chỉ có ở dữ liệu từ CSDL: posted_at, source...); thiếu/NaN thì None."""
    v = row.get(name) if hasattr(row, "get") else None
    if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() in ("", "nan", "None"):
        return None
    return str(v)


def page(items, total, limit, offset):
    return {"total": int(total), "limit": limit, "offset": offset, "items": jsonable(items)}


def check_paging(limit, offset, max_limit=200):
    if not (1 <= limit <= max_limit):
        raise BadRequest(f"limit phải trong khoảng 1..{max_limit}")
    if offset < 0:
        raise BadRequest("offset phải >= 0")


def check_topics(ds, names):
    valid = set(ds.topics.topic_name)
    bad = [n for n in names if n not in valid]
    if bad:
        raise BadRequest(f"Technical Topic không có trong taxonomy: {bad}")
    return list(dict.fromkeys(names))


def check_domains(ds, names):
    valid = set(ds.domains.domain_name)
    bad = [n for n in names if n not in valid]
    if bad:
        raise BadRequest(f"Domain không có trong taxonomy: {bad}")
    return list(dict.fromkeys(names))


def check_weights(weights, allowed):
    """weights: dict hoặc None. Trả về dict đủ khóa `allowed` (khóa thiếu lấy mặc định ở nơi gọi). Không âm và tổng > 0."""
    if not weights:
        return None
    bad = [k for k in weights if k not in allowed]
    if bad:
        raise BadRequest(f"trọng số không hợp lệ {bad}; chỉ gồm {sorted(allowed)}")
    if any((v is None) or v < 0 for v in weights.values()):
        raise BadRequest("trọng số phải >= 0")
    return {k: float(v) for k, v in weights.items()}


def job_index(ds, job_id):
    i = ds.job_pos.get(str(job_id))
    if i is None:
        raise NotFound(f"không có Job {job_id}")
    return i


def thesis_index(ds, thesis_id):
    i = ds.thesis_pos.get(str(thesis_id))
    if i is None:
        raise NotFound(f"không có Thesis {thesis_id}")
    return i
