"""Tổng quan cho trang chủ và màn "Job so với luận văn". Chỉ đếm nhãn đã có và gọi lại ml.recommendation.market_demand
(Wilson 95%, supply_vs_demand); không có công thức mới. Dữ liệu Job không có ngày đăng nên không có xu hướng theo thời gian;
Thesis có cột năm nên trả thêm số Thesis theo năm (chỉ phía nguồn cung)."""
from collections import Counter, defaultdict

import numpy as np

from backend.services.common import jsonable
from ml.recommendation import market_demand as MD

MIN_SUPPORT, MIN_COMPANIES = MD.MIN_SUPPORT, MD.MIN_COMPANIES


def _measurable(ds):
    """Topic nào Job đo được (có quy tắc gán). Lấy từ bảng Phase 8 nếu có; không có thì coi mọi Topic đều đo được."""
    sv = ds.market.get("supply_vs_demand_topics")
    if sv is None or "measurable_in_jobs" not in sv:
        return None
    return set(sv[sv.measurable_in_jobs.astype(bool)].topic)


def _rows(job_lists, thesis_lists, companies, names, measurable=None):
    if not job_lists or not thesis_lists:
        return []
    df = MD.supply_vs_demand(job_lists, thesis_lists, names, measurable)
    comp = defaultdict(set)
    for items, c in zip(job_lists, companies):
        for it in set(items):
            comp[it].add(c)
    out = []
    for r in df.to_dict("records"):
        n = len(comp[r["topic"]])
        out.append(dict(name=r["topic"], job_count=r["job_count"], job_share=r["job_share"], job_ci_low=r["job_ci_low"], job_ci_high=r["job_ci_high"],
                        thesis_count=r["thesis_count"], thesis_share=r["thesis_share"], thesis_ci_low=r["thesis_ci_low"], thesis_ci_high=r["thesis_ci_high"],
                        gap=r["gap"], gap_status=r["gap_status"], measurable=bool(r["measurable_in_jobs"]), n_companies=n,
                        support_ok=bool(r["job_count"] >= MIN_SUPPORT and n >= MIN_COMPANIES)))
    return out


def _pairs(ds, topics, domains, n_topics, n_domains):
    jt, jd, tt, td = ds.jobs._technical_topics, ds.jobs._domains, ds.thesis._technical_topics, ds.thesis._domains
    jc, tc = Counter(), Counter()
    for ts, dm in zip(jt, jd):
        for t in set(ts):
            for d in set(dm):
                jc[(t, d)] += 1
    for ts, dm in zip(tt, td):
        for t in set(ts):
            for d in set(dm):
                tc[(t, d)] += 1
    top_t = [r["name"] for r in sorted((r for r in topics if r["measurable"]), key=lambda r: -r["job_count"])[:n_topics]]
    top_d = [r["name"] for r in sorted(domains, key=lambda r: -r["job_count"])[:n_domains]]
    cells = [dict(topic=t, domain=d, job_count=jc[(t, d)], thesis_count=tc[(t, d)]) for t in top_t for d in top_d]
    return dict(topics=top_t, domains=top_d, cells=cells)


def _thesis_by_year(ds, topic_names):
    yr = ds.thesis.year
    ok = ~np.isnan(yr.values.astype(float))
    years = sorted({int(y) for y in yr.values[ok]})
    total = Counter(int(y) for y in yr.values[ok])
    by_topic = {t: Counter() for t in topic_names}
    for y, ts in zip(yr.values, ds.thesis._technical_topics):
        if np.isnan(float(y)):
            continue
        for t in set(ts):
            if t in by_topic:
                by_topic[t][int(y)] += 1
    return dict(years=years, total=[total[y] for y in years], by_topic={t: [c[y] for y in years] for t, c in by_topic.items()},
                n_with_year=int(ok.sum()), n_thesis=int(len(yr)))


def overview(ds, n_topics=6, n_domains=5):
    j, t = ds.jobs, ds.thesis
    companies = j.company.fillna("").tolist()
    topic_names = ds.topics.topic_name.tolist()
    domain_names = ds.domains.domain_name.tolist()

    topics = _rows(list(j._technical_topics), list(t._technical_topics), companies, topic_names, _measurable(ds))
    # Domain: mẫu số là các Job/Thesis đã xác định được Domain (Domain rỗng là hợp lệ, không phải "không có nhu cầu")
    jm = [i for i, d in enumerate(j._domains) if d]
    tm = [d for d in t._domains if d]
    domains = _rows([j._domains[i] for i in jm], tm, [companies[i] for i in jm], domain_names)

    kpis = dict(n_jobs=len(j), n_thesis=len(t), n_topics=len(topic_names), n_domains=len(domain_names),
                jobs_with_topic=int(sum(1 for x in j._technical_topics if x)), jobs_with_domain=len(jm),
                thesis_with_domain=len(tm), thesis_with_year=int((~np.isnan(t.year.values.astype(float))).sum()))
    return jsonable(dict(
        kpis=kpis, topics=topics, domains=domains,
        pairs=_pairs(ds, topics, domains, n_topics, n_domains),
        thesis_by_year=_thesis_by_year(ds, [r["name"] for r in topics]),
        thresholds=dict(min_support=MIN_SUPPORT, min_companies=MIN_COMPANIES),
        denominators=dict(topics_jobs=len(j), topics_thesis=len(t), domains_jobs=len(jm), domains_thesis=len(tm)),
        notes=["Tỷ lệ Topic tính trên tất cả Job và tất cả Thesis; tỷ lệ Domain chỉ tính trên Job và Thesis đã xác định được Domain.",
               "Dữ liệu Job không có ngày đăng nên không có xu hướng theo thời gian. Thesis có năm nên có số Thesis theo năm (chỉ phía nguồn cung).",
               "gap_status dựa trên khoảng tin cậy Wilson 95%; Topic 'not_measurable_from_jobs' chưa có quy tắc gán cho Job nên 0 Job không có nghĩa là không có nhu cầu."]))
