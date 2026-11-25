"""Phase 8 - phân tích nhu cầu thị trường từ Jobs (chỉ thống kê, có khoảng tin cậy và cờ đủ bằng chứng).

Không gọi một Skill/Topic là "hot" chỉ dựa trên vài bản ghi: mỗi mục có count, share, khoảng tin cậy Wilson 95%,
số công ty khác nhau và cờ support_ok (đủ số job và đủ số công ty). Dữ liệu không có ngày đăng nên không phân tích xu hướng theo thời gian.
"""
import json
import math
from collections import Counter, defaultdict
import pandas as pd

MIN_SUPPORT = 10      # số job tối thiểu để coi là đủ bằng chứng (heuristic, chỉnh được)
MIN_COMPANIES = 3     # số công ty khác nhau tối thiểu
CONCENTRATED = 0.5    # cờ nếu một công ty chiếm > 50% số job của mục


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def demand_table(items_per_job, companies, min_support=MIN_SUPPORT, min_companies=MIN_COMPANIES):
    n = len(items_per_job)
    jobs_of, comp_of = defaultdict(int), defaultdict(Counter)
    for items, comp in zip(items_per_job, companies):
        for it in set(items):
            jobs_of[it] += 1
            comp_of[it][comp] += 1
    rows = []
    for it, k in jobs_of.items():
        lo, hi = wilson(k, n)
        top = comp_of[it].most_common(1)[0][1] / k
        rows.append(dict(item=it, job_count=k, share=round(k / n, 4), ci_low=round(lo, 4), ci_high=round(hi, 4),
                         n_companies=len(comp_of[it]), top_company_share=round(top, 3),
                         support_ok=bool(k >= min_support and len(comp_of[it]) >= min_companies),
                         concentrated=bool(top > CONCENTRATED and k >= min_support)))
    df = pd.DataFrame(rows).sort_values(["job_count", "item"], ascending=[False, True]).reset_index(drop=True)
    df.insert(1, "rank", range(1, len(df) + 1))
    return df


def fractional_domain_table(domain_scores_per_job, companies):
    """Mỗi job đóng góp tổng 1 điểm, chia theo điểm của các Domain (tránh đếm trùng job nhiều Domain)."""
    frac, jobs_of, comp = defaultdict(float), defaultdict(int), defaultdict(set)
    with_dom = 0
    for sc, c in zip(domain_scores_per_job, companies):
        if not sc:
            continue
        with_dom += 1
        tot = sum(sc.values())
        for d, v in sc.items():
            frac[d] += v / tot; jobs_of[d] += 1; comp[d].add(c)
    rows = [dict(item=d, weighted_jobs=round(frac[d], 2), job_count=jobs_of[d], share_of_labelled=round(frac[d] / with_dom, 4),
                 n_companies=len(comp[d]), support_ok=bool(jobs_of[d] >= MIN_SUPPORT and len(comp[d]) >= MIN_COMPANIES))
            for d in frac]
    df = pd.DataFrame(rows).sort_values("weighted_jobs", ascending=False).reset_index(drop=True)
    return df, with_dom


def pair_table(topics_per_job, domains_per_job, companies, min_count=5):
    n = len(topics_per_job)
    cnt, comp = Counter(), defaultdict(set)
    for ts, ds, c in zip(topics_per_job, domains_per_job, companies):
        for t in set(ts):
            for d in set(ds):
                cnt[(t, d)] += 1; comp[(t, d)].add(c)
    rows = [dict(topic=t, domain=d, job_count=k, share_of_all_jobs=round(k / n, 4), n_companies=len(comp[(t, d)]),
                 support_ok=bool(k >= MIN_SUPPORT and len(comp[(t, d)]) >= MIN_COMPANIES))
            for (t, d), k in cnt.items() if k >= min_count]
    return pd.DataFrame(rows).sort_values("job_count", ascending=False).reset_index(drop=True)


def supply_vs_demand(job_topics, thesis_topics, all_topics, measurable=None):
    nj, nt = len(job_topics), len(thesis_topics)
    jc = Counter(t for l in job_topics for t in set(l)); tc = Counter(t for l in thesis_topics for t in set(l))
    rows = []
    for t in all_topics:
        jl, jh = wilson(jc[t], nj); tl, th = wilson(tc[t], nt)
        js, ts = jc[t] / nj, tc[t] / nt
        clear = "demand_exceeds_supply" if jl > th else ("supply_exceeds_demand" if tl > jh else "no_clear_gap")
        if measurable is not None and t not in measurable:
            clear = "not_measurable_from_jobs"      # topic không có quy tắc gán cho Job -> 0 job là chưa đo được, không phải không có nhu cầu
        rows.append(dict(topic=t, job_count=jc[t], job_share=round(js, 4), job_ci_low=round(jl, 4), job_ci_high=round(jh, 4),
                         thesis_count=tc[t], thesis_share=round(ts, 4), thesis_ci_low=round(tl, 4), thesis_ci_high=round(th, 4),
                         gap=round(js - ts, 4), measurable_in_jobs=(measurable is None or t in measurable), gap_status=clear))
    return pd.DataFrame(rows).sort_values("gap", ascending=False).reset_index(drop=True)
