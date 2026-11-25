"""Gợi ý giảng viên hướng dẫn (GVHD) của NEU cho một đề tài, dựa trên các khóa luận GVHD đó đã hướng dẫn.

Điểm của một giảng viên (mỗi thành phần về thang 0..1):
  0.6 · kinh nghiệm cùng hướng: số khóa luận thầy/cô đã hướng dẫn thuộc chủ đề (lĩnh vực đóng góp thêm một phần nhỏ),
        lấy log rồi chia cho người nhiều nhất, để người có 14 bài không bị xếp sau người chỉ có 2 bài như khi chấm theo tỷ lệ
  0.2 · độ chuyên sâu: tỷ lệ khóa luận của thầy/cô thuộc chủ đề (phân biệt khi hai người bằng số bài)
  0.1 · còn hoạt động: năm gần nhất thầy/cô hướng dẫn khóa luận cùng hướng, tương đối so với những người còn lại
  0.1 · gần về nghĩa: trung bình 3 khóa luận gần nhất với nội dung đề tài (embedding); bỏ nếu thiếu embedding hoặc không có nội dung
Thành phần không áp dụng được thì bỏ và chia lại trọng số. Đây là gợi ý dựa trên lịch sử hướng dẫn, không phải phân công;
việc thầy/cô còn nhận hướng dẫn hay không dữ liệu không cho biết. Chỉ dùng tên giảng viên, không có thông tin sinh viên.
"""
import math

import numpy as np

from backend.errors import BadRequest, Unavailable
from backend.services.common import check_domains, check_topics

W_EXP, W_DEPTH, W_REC, W_SEM = 0.6, 0.2, 0.1, 0.1
DOM_WEIGHT = 0.25        # một khóa luận cùng lĩnh vực (nhưng khác chủ đề) tính bằng ngần này khóa luận cùng chủ đề
LEVELS = ((5, "strong"), (2, "ok"), (1, "weak"))
SOURCE = "neu"


def _index(ds):
    def build():
        t = ds.thesis
        if "_advisors" not in t:
            return {}
        src = t.source.astype(str).values if "source" in t else np.array([SOURCE] * len(t))
        out = {}
        for i, names in enumerate(t._advisors):
            if src[i] != SOURCE or not isinstance(names, list):
                continue
            for n in names:
                out.setdefault(n, []).append(i)
        return out
    return ds.cached("advisor_index", build)


def _year(ds, i):
    try:
        v = float(ds.thesis.year.iloc[i])
        return None if np.isnan(v) else int(v)
    except (TypeError, ValueError):
        return None


def _count(rows, lists, wanted):
    if not wanted:
        return 0
    return sum(1 for i in rows if set(wanted) & set(lists.iloc[i]))


def _level(k):
    for need, name in LEVELS:
        if k >= need:
            return name
    return "none"


def list_advisors(ds, q=None, limit=100):
    idx = _index(ds)
    q = (q or "").strip().lower()
    out = []
    for name, rows in idx.items():
        if q and q not in name.lower():
            continue
        yrs = [y for y in (_year(ds, i) for i in rows) if y]
        cnt = {}
        for i in rows:
            for tp in ds.thesis._technical_topics.iloc[i]:
                cnt[tp] = cnt.get(tp, 0) + 1
        out.append(dict(advisor=name, n_theses=len(rows), latest_year=max(yrs) if yrs else None,
                        top_topics=[k for k, _ in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))[:3]]))
    out.sort(key=lambda r: (-r["n_theses"], r["advisor"]))
    return dict(total=len(out), items=out[:limit])


def recommend(ds, topic=None, domains=None, text=None, top_k=5):
    if not (1 <= top_k <= 20):
        raise BadRequest("top_k phải trong khoảng 1..20")
    topics = check_topics(ds, [topic] if topic else [])
    doms = check_domains(ds, domains or [])
    text = (text or "").strip()[:1500]
    if not topics and not doms and not text:
        raise BadRequest("cần ít nhất một trong: topic, domains, text")
    idx = _index(ds)
    if not idx:
        raise Unavailable("chưa có dữ liệu giảng viên hướng dẫn; chạy scripts/inspect_neu_fields.py rồi crawl lại, hoặc scripts/import_advisors.py")
    T, D = ds.thesis._technical_topics, ds.thesis._domains
    sims, note = None, None
    if text:
        try:
            E = ds.thesis_vectors()
            sims = E @ ds.encode([text])[0]
        except Unavailable:
            note = "chưa có embedding nên chỉ xét chủ đề và lĩnh vực"
    rows = []
    for name, ids in idx.items():
        tc = _count(ids, T, topics)
        dc = _count(ids, D, doms)
        k = tc + DOM_WEIGHT * dc if topics else dc          # chỉ lĩnh vực: dc là kinh nghiệm chính
        n_rel = tc if topics else dc
        on = [i for i in ids if (set(topics) & set(T.iloc[i])) or (not topics and set(doms) & set(D.iloc[i]))]
        ys = [y for y in (_year(ds, i) for i in on) if y]
        sm = float(np.mean(np.sort(sims[ids])[::-1][:3])) if sims is not None else 0.0
        rows.append(dict(name=name, ids=ids, tc=tc, dc=dc, k=k, depth=n_rel / len(ids), last=max(ys) if ys else None, sm=max(sm, 0.0), n_rel=n_rel))
    has_rel = bool(topics or doms)
    kmax = max((r["k"] for r in rows), default=0.0)
    rel_max = max((r["n_rel"] for r in rows), default=0)        # n_rel: số bài cùng chủ đề (hoặc cùng lĩnh vực nếu chỉ chọn lĩnh vực)
    smax = max((r["sm"] for r in rows), default=0.0) or 1.0
    lasts = [r["last"] for r in rows if r["last"]]
    y0, y1 = (min(lasts), max(lasts)) if lasts else (0, 0)
    w = dict(e=W_EXP if has_rel and kmax > 0 else 0, d=W_DEPTH if has_rel and kmax > 0 else 0, r=W_REC if has_rel and kmax > 0 else 0, s=W_SEM if sims is not None else 0)
    tot = sum(w.values()) or 1.0
    res = []
    for r in rows:
        exp = math.log1p(r["k"]) / math.log1p(kmax) if kmax > 0 else 0.0
        rec = ((r["last"] - y0) / (y1 - y0) if y1 > y0 else 1.0) if r["last"] else 0.0
        sc = (w["e"] * exp + w["d"] * r["depth"] + w["r"] * rec + w["s"] * r["sm"] / smax) / tot
        if sc <= 0 or (has_rel and rel_max > 0 and r["n_rel"] == 0):          # có chủ đề/lĩnh vực: chỉ giữ người đã hướng dẫn ít nhất một bài cùng hướng
            continue
        ids = r["ids"]
        if sims is not None:
            near = sorted(ids, key=lambda i: -sims[i])[:3]
        else:
            near = sorted(ids, key=lambda i: -(_year(ds, i) or 0))[:3]
        yrs = [y for y in (_year(ds, i) for i in ids) if y]
        res.append(dict(advisor=r["name"], score=round(sc, 3), n_theses=len(ids), latest_year=max(yrs) if yrs else None,
                        n_topic=r["tc"], n_domain=r["dc"], n_related=r["n_rel"], latest_related_year=r["last"], level=_level(r["n_rel"]),
                        nearest=[dict(thesis_id=str(ds.thesis.thesis_id.iloc[i]), title=str(ds.thesis.title.iloc[i]), year=_year(ds, i)) for i in near]))
    res.sort(key=lambda r: (-r["score"], -r["n_related"], -r["n_theses"], r["advisor"]))
    top = res[:top_k]
    thin = has_rel and not any(r["n_related"] >= 2 for r in top)
    return dict(items=top, n_advisors=len(idx), topic=topics[0] if topics else None, domains=doms, semantic=sims is not None, note=note, low_data=thin,
                caveat="Gợi ý dựa trên các khóa luận thầy/cô đã hướng dẫn; không phải phân công và không cho biết thầy/cô còn nhận hướng dẫn hay không. Hãy liên hệ khoa để xác nhận."
                      + (" Hướng này có rất ít khóa luận trong dữ liệu nên kết quả chỉ mang tính tham khảo." if thin else ""))
