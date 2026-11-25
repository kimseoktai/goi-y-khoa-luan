"""Novelty (Phase 10): so một tiêu đề/ý tưởng hoặc một Thesis với kho Thesis. Dùng lại ml.novelty."""
import numpy as np

from backend.errors import BadRequest
from backend.services.common import check_domains, check_topics, jsonable, thesis_index
from ml.novelty import novelty as N

NOTE = ("Ngưỡng Duplicate/Similar hiệu chỉnh từ nhãn tay trên cặp tiêu đề-tiêu đề (mẫu nhỏ, trong mẫu). "
        "Similar là nhãn dễ nhầm nhất; dùng như gợi ý xem lại, không phải kết luận.")


def _meta(ds, j):
    """Năm và nguồn (trường) của một Thesis, để giao diện hiển thị cạnh tiêu đề."""
    y = ds.thesis.year.iloc[j]
    return dict(year=None if np.isnan(float(y)) else int(y), source=ds.thesis.source.iloc[j])


def _result(ds, sims, idx, th, extra=None):
    ms = float(sims[0])
    ref = ds.novelty_reference()
    t = ds.thesis
    out = dict(max_similarity=round(ms, 4), nearest_thesis=dict(thesis_id=t.thesis_id[idx[0]], title=t.title[idx[0]], **_meta(ds, idx[0])),
               novelty_score=round(float(N.novelty_score(ms, ref)), 3), novelty_status=str(N.status(ms, th)),
               top_neighbors=[dict(thesis_id=t.thesis_id[j], title=t.title[j], similarity=round(float(s), 4), **_meta(ds, j)) for j, s in zip(idx, sims)],
               thresholds=dict(similar=th.get("similar"), duplicate=th.get("duplicate"), source=th.get("source")), note=NOTE)
    if th.get("duplicate") is None:
        out["note"] += " Chưa đặt được ngưỡng Duplicate (ít nhãn Duplicate) nên chỉ trả Novel/Similar."
    out.update(extra or {})
    return jsonable(out)


def check_text(ds, title, topics=None, domains=None, top_k=5, max_chars=500):
    title = (title or "").strip()
    if not title:
        raise BadRequest("title không được rỗng")
    if len(title) > max_chars:
        raise BadRequest(f"title tối đa {max_chars} ký tự")
    if not (1 <= top_k <= 20):
        raise BadRequest("top_k phải trong khoảng 1..20")
    topics, domains = check_topics(ds, topics or []), check_domains(ds, domains or [])
    E = ds.thesis_vectors()                       # có thể ném Unavailable
    q = ds.encode([title])[0]
    s = E @ q
    idx = np.argsort(-s, kind="stable")[:top_k]
    extra = {}
    if topics:
        extra["combo_support"] = N.combo_support(ds.thesis_label_sets(), topics, domains)
        extra["combo_note"] = "số Thesis đã có đủ các Technical Topic (và Domain) này; 0 nghĩa là tổ hợp chưa có Thesis nào"
    return _result(ds, s[idx], idx, ds.novelty_thresholds(), extra)


def check_thesis(ds, thesis_id, top_k=5):
    """Novelty của một Thesis đã có so với phần còn lại của kho (loại chính nó theo chỉ số)."""
    if not (1 <= top_k <= 20):
        raise BadRequest("top_k phải trong khoảng 1..20")
    i = thesis_index(ds, thesis_id)
    E = ds.thesis_vectors()
    s = E @ E[i]; s[i] = -np.inf
    idx = np.argsort(-s, kind="stable")[:top_k]
    return _result(ds, s[idx], idx, ds.novelty_thresholds(), dict(thesis_id=ds.thesis.thesis_id[i], title=ds.thesis.title[i]))
