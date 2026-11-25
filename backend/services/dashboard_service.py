"""Dashboard tổng quan xu hướng khóa luận của một trường (mặc định NEU): bộ lọc, KPI, xu hướng theo năm, cơ cấu, top 5 và chủ đề mới nổi.

Quy ước (giao diện cũng nói rõ cho người đọc):
- Mọi con số đều tính trên cùng một lát cắt: nguồn + khoảng năm + lĩnh vực + chủ đề đã chọn. Bộ lọc lĩnh vực/chủ đề giữ khóa luận CÓ nhãn đó.
- Tăng trưởng của một nhãn = tỷ lệ của nó trong năm cuối của khoảng so với tỷ lệ gộp của các năm trước đó trong khoảng; khoảng chỉ có một năm thì không so được.
  Kết luận tăng/giảm dùng cùng luật với trend_service (khoảng tin cậy Wilson không chồng nhau và mỗi bên đủ MIN_N khóa luận), còn lại là ổn định hoặc chưa đủ dữ liệu.
- Cơ cấu lĩnh vực là tỷ trọng theo số lần gắn nhãn (một khóa luận có thể có nhiều lĩnh vực), nên cộng lại đúng 100%; bài chưa có lĩnh vực được báo riêng.
- Chủ đề mới nổi: năm bắt đầu xuất hiện là năm đầu tiên chủ đề có từ 2 khóa luận (tính trên toàn bộ dữ liệu của nguồn, không theo bộ lọc năm); được liệt kê khi mới xuất hiện trong 2 năm gần nhất,
  hoặc đang tăng rõ, hoặc tỷ lệ năm cuối gấp từ 1,5 lần giai đoạn trước với ít nhất 5 bài. Là mô tả dữ liệu đã thu thập, không phải dự báo.
"""
import numpy as np

from backend.errors import BadRequest, NotFound
from backend.services.common import check_domains, check_topics
from backend.services.trend_service import MIN_N, SMALL_YEAR, _trend
from ml.recommendation.market_demand import wilson

TOP_SERIES = 5
PIE_MAX = 7
EMERGE_MIN_FIRST = 2        # số khóa luận tối thiểu để tính là "đã xuất hiện"
EMERGE_MIN_RECENT = 5
EMERGE_RATIO = 1.5


def _names(df, col):
    d = df[df.status == "active"] if "status" in df else df
    return d[col].tolist()


def _growth(c_last, n_last, c_prior, n_prior):
    s_last = c_last / n_last if n_last else 0.0
    s_prior = c_prior / n_prior if n_prior else None
    if s_prior is None:
        return dict(share_last=s_last, share_prior=None, change_pp=None, change_rel=None)
    rel = (s_last / s_prior - 1) if s_prior > 0 else None
    return dict(share_last=s_last, share_prior=s_prior, change_pp=s_last - s_prior, change_rel=rel)


def dashboard(ds, source="neu", year_from=None, year_to=None, domain=None, topic=None, view="domain"):
    if view not in ("domain", "topic"):
        raise BadRequest("view phải là domain hoặc topic")
    t = ds.thesis
    if "source" not in t:
        raise NotFound("dữ liệu khóa luận không có cột nguồn")
    sources = sorted(t.source.dropna().astype(str).unique().tolist())
    if source not in sources:
        raise NotFound(f"không có khóa luận của nguồn '{source}' (có: {', '.join(sources) or 'không có'})")
    topic_names, domain_names = _names(ds.topics, "topic_name"), _names(ds.domains, "domain_name")
    if topic:
        check_topics(ds, [topic])
    if domain:
        check_domains(ds, [domain])
    src = t.source.astype(str).values == source
    yr = t.year.astype(float).values
    has_year = src & ~np.isnan(yr)
    all_idx = np.flatnonzero(has_year)
    if len(all_idx) == 0:
        return dict(source=source, sources=sources, n_source=int(src.sum()), years=[], note="chưa có khóa luận nào của nguồn này có ghi năm")
    all_years = sorted({int(yr[i]) for i in all_idx})
    y0 = year_from if year_from is not None else all_years[0]
    y1 = year_to if year_to is not None else all_years[-1]
    if y0 > y1:
        raise BadRequest("year_from không được lớn hơn year_to")
    T, D = t._technical_topics, t._domains
    sel = [int(i) for i in all_idx if y0 <= int(yr[i]) <= y1 and (not domain or domain in D.iloc[i]) and (not topic or topic in T.iloc[i])]
    years = [y for y in all_years if y0 <= y <= y1]
    n_year = {y: 0 for y in years}
    for i in sel:
        n_year[int(yr[i])] += 1
    last, prior = (years[-1], years[:-1]) if years else (None, [])
    n_last = n_year.get(last, 0)
    n_prior = sum(n_year[y] for y in prior)

    def count_by_year(names, lists_of):
        cnt = {nm: {y: 0 for y in years} for nm in names}
        for i in sel:
            for nm in set(lists_of.iloc[i]):
                if nm in cnt:
                    cnt[nm][int(yr[i])] += 1
        return cnt

    tc, dc = count_by_year(topic_names, T), count_by_year(domain_names, D)

    def row(nm, cnt):
        by = [cnt[nm][y] for y in years]
        c_last, c_prior = cnt[nm].get(last, 0), sum(cnt[nm][y] for y in prior)
        g = _growth(c_last, n_last, c_prior, n_prior)
        tr = _trend(c_last, n_last, c_prior, n_prior) if prior else "insufficient"
        ci = [list(wilson(c, n_year[y])) if n_year[y] else [0.0, 0.0] for c, y in zip(by, years)]
        return dict(name=nm, total=sum(by), by_year=by, ci=ci, trend=tr, **g)

    trows = sorted((row(n, tc) for n in topic_names if sum(tc[n].values())), key=lambda r: (-r["total"], r["name"]))
    drows = sorted((row(n, dc) for n in domain_names if sum(dc[n].values())), key=lambda r: (-r["total"], r["name"]))

    # xu hướng theo năm: tổng + các nhãn hàng đầu của chiều được chọn
    lines = trows[:TOP_SERIES] if view == "topic" else drows[:TOP_SERIES]

    # cơ cấu lĩnh vực: theo số lần gắn nhãn, gom phần đuôi vào "Khác"
    tot_d = sum(r["total"] for r in drows)
    pie = [dict(name=r["name"], count=r["total"], share=r["total"] / tot_d if tot_d else 0.0) for r in drows[:PIE_MAX]]
    rest = sum(r["total"] for r in drows[PIE_MAX:])
    if rest:
        pie.append(dict(name="Khác", count=rest, share=rest / tot_d, other=True, n_labels=len(drows) - PIE_MAX))
    no_domain = sum(1 for i in sel if not D.iloc[i])
    no_topic = sum(1 for i in sel if not T.iloc[i])
    gold = int(t.in_gold.astype(bool).values[sel].sum()) if "in_gold" in t and sel else 0
    bars = [dict(name=r["name"], count=r["total"], share=r["total"] / len(sel) if sel else 0.0) for r in trows[:8]]

    # lĩnh vực x chủ đề: số khóa luận có cả hai nhãn (cho treemap và ma trận)
    pair = {}
    for i in sel:
        for dm in set(D.iloc[i]):
            row = pair.setdefault(dm, {})
            tps = set(T.iloc[i]) or {None}
            for tp in tps:
                row[tp] = row.get(tp, 0) + 1
    domain_topic = [dict(domain=r["name"], count=r["total"], topics=[dict(name=tp, count=c) for tp, c in sorted(pair.get(r["name"], {}).items(), key=lambda x: (-x[1], str(x[0])))])
                    for r in drows]

    # top 5 chủ đề: số bài, tăng trưởng, lĩnh vực hay gặp nhất
    top5 = []
    for r in trows[:5]:
        dcount = {}
        for i in sel:
            if r["name"] in T.iloc[i]:
                for d in set(D.iloc[i]):
                    dcount[d] = dcount.get(d, 0) + 1
        dom = sorted(dcount.items(), key=lambda x: (-x[1], x[0]))[:2]
        top5.append(dict(name=r["name"], count=r["total"], share_last=r["share_last"], share_prior=r["share_prior"], change_pp=r["change_pp"],
                         change_rel=r["change_rel"], trend=r["trend"], common_domains=[dict(name=n, count=c, share=c / r["total"]) for n, c in dom]))

    # chủ đề mới nổi
    all_topic_years = {}
    for i in all_idx:
        if domain and domain not in D.iloc[i]:
            continue
        for nm in set(T.iloc[i]):
            all_topic_years.setdefault(nm, []).append(int(yr[i]))
    latest_all = all_years[-1]
    cand = {str(r.topic_name): str(getattr(r, "status", "active")) for r in ds.topics.itertuples()}
    emerging = []
    for r in trows:
        ys = sorted(all_topic_years.get(r["name"], []))
        n_ys = {y: ys.count(y) for y in set(ys)}
        first = next((y for y in sorted(n_ys) if n_ys[y] >= EMERGE_MIN_FIRST), None)
        if first is None:
            continue
        recent = sum(r["by_year"][k] for k, y in enumerate(years) if y >= (last or 0) - 1)
        new = first >= latest_all - 1 and first > all_years[0]            # có ngay từ năm đầu của dữ liệu thì không thể gọi là mới
        fast = r["trend"] == "up" or (r["share_prior"] and r["share_last"] >= EMERGE_RATIO * r["share_prior"] and r["by_year"][-1] >= EMERGE_MIN_RECENT)
        if not (new or fast) or recent == 0:
            continue
        emerging.append(dict(name=r["name"], first_year=first, recent_count=recent, total=r["total"], trend=r["trend"], share_last=r["share_last"],
                             share_prior=r["share_prior"], change_pp=r["change_pp"], change_rel=r["change_rel"], reason="new" if new else "fast",
                             status=cand.get(r["name"], "active")))
    emerging.sort(key=lambda r: (r["reason"] != "new", -(r["change_pp"] or 0), -r["recent_count"], r["name"]))

    return dict(
        source=source, sources=sources, n_source=int(src.sum()),
        filters=dict(years=all_years, domains=domain_names, topics=topic_names, year_from=y0, year_to=y1, domain=domain, topic=topic, view=view),
        kpi=dict(total=len(all_idx), in_range=len(sel), years_label=f"{y0}" if y0 == y1 else f"{y0}–{y1}", single_year=y0 == y1,
                 n_domains=len(drows), n_topics=len(trows), n_domains_all=len(domain_names), n_topics_all=len(topic_names)),
        years=[dict(year=y, n=n_year[y], small=n_year[y] < SMALL_YEAR) for y in years],
        latest_year=last, compare_years=prior, min_n=MIN_N, small_year=SMALL_YEAR,
        series=dict(view=view, lines=lines),
        domain_mix=pie, domain_topic=domain_topic, no_domain=no_domain, no_topic=no_topic, label_quality=dict(gold=gold, model=len(sel) - gold, gold_share=gold / len(sel) if sel else 0.0), topic_bars=bars, top5=top5, emerging=emerging, topics=trows, domains=drows,
    )
