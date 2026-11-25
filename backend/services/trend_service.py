"""Xu hướng làm khóa luận của một trường (mặc định NEU) theo từng năm: số lượng và tỷ lệ theo chủ đề kỹ thuật và lĩnh vực.

- Tỷ lệ của một nhãn trong năm = số khóa luận của năm đó có nhãn / TẤT CẢ khóa luận của năm (kể cả chưa có nhãn). Một khóa luận có thể có nhiều nhãn nên tổng các tỷ lệ có thể vượt 100%.
- Khoảng tin cậy 95% theo Wilson (cùng công thức với phần thị trường tuyển dụng, ml.recommendation.market_demand.wilson).
- Xu hướng: so tỷ lệ của năm gần nhất với tỷ lệ gộp của các năm trước; chỉ kết luận tăng hoặc giảm khi hai khoảng tin cậy không chồng nhau
  và cả hai bên đủ MIN_N khóa luận; còn lại là "ổn định" hoặc "chưa đủ dữ liệu". Đây là mô tả dữ liệu đã thu thập, không phải dự báo.
- Nhãn của khóa luận ngoài bộ Gold là do mô hình dự đoán; trả kèm tỷ lệ nhãn đã được người xác nhận để người đọc biết độ tin cậy.
"""
import numpy as np

from backend.errors import NotFound
from ml.recommendation.market_demand import wilson

MIN_N = 30            # số khóa luận tối thiểu ở mỗi bên để kết luận tăng/giảm
SMALL_YEAR = 30       # năm có ít hơn số này được gắn cờ "mẫu nhỏ"


def _trend(count_last, n_last, count_prior, n_prior):
    if n_last < MIN_N or n_prior < MIN_N:
        return "insufficient"
    lo1, hi1 = wilson(count_last, n_last)
    lo0, hi0 = wilson(count_prior, n_prior)
    if lo1 > hi0:
        return "up"
    if hi1 < lo0:
        return "down"
    return "flat"


def _block(names, lists, years_of, years, n_year):
    """names: danh sách nhãn; lists: danh sách nhãn của từng khóa luận; years_of: năm của từng khóa luận (cùng thứ tự)."""
    cnt = {nm: {y: 0 for y in years} for nm in names}
    for ls, y in zip(lists, years_of):
        for nm in set(ls):
            if nm in cnt:
                cnt[nm][y] += 1
    last, prior = years[-1], years[:-1]
    n_prior = sum(n_year[y] for y in prior)
    n_all = sum(n_year.values())
    rows = []
    for nm in names:
        by = []
        for y in years:
            c, n = cnt[nm][y], n_year[y]
            lo, hi = wilson(c, n)
            by.append(dict(year=y, count=c, share=c / n if n else 0.0, ci_low=lo, ci_high=hi))
        total = sum(cnt[nm].values())
        c_prior = sum(cnt[nm][y] for y in prior)
        s_last = cnt[nm][last] / n_year[last] if n_year[last] else 0.0
        s_prior = c_prior / n_prior if n_prior else 0.0
        rows.append(dict(name=nm, total=total, share=total / n_all if n_all else 0.0, by_year=by,
                         share_last=s_last, share_prior=s_prior, change=s_last - s_prior,
                         trend=_trend(cnt[nm][last], n_year[last], c_prior, n_prior) if prior else "insufficient"))
    return sorted(rows, key=lambda r: (-r["total"], r["name"]))


def thesis_trends(ds, source="neu", top=None):
    t = ds.thesis
    if "source" not in t:
        raise NotFound("dữ liệu khóa luận không có cột nguồn")
    sources = sorted(t.source.dropna().astype(str).unique().tolist())
    if source not in sources:
        raise NotFound(f"không có khóa luận của nguồn '{source}' (có: {', '.join(sources) or 'không có'})")
    yr = t.year.astype(float).values
    m = (t.source.astype(str).values == source) & ~np.isnan(yr)
    n_source = int((t.source.astype(str).values == source).sum())
    idx = np.flatnonzero(m)
    if len(idx) == 0:
        return dict(source=source, sources=sources, n_source=n_source, n_with_year=0, years=[], topics=[], domains=[], note="chưa có khóa luận nào của nguồn này có ghi năm")
    years_of = [int(yr[i]) for i in idx]
    years = sorted(set(years_of))
    n_year = {y: years_of.count(y) for y in years}
    tl, dl = t._technical_topics, t._domains
    topics_l, domains_l = [tl.iloc[i] for i in idx], [dl.iloc[i] for i in idx]
    topic_names = ds.topics[ds.topics.status == "active"].topic_name.tolist() if "status" in ds.topics else ds.topics.topic_name.tolist()
    domain_names = ds.domains[ds.domains.status == "active"].domain_name.tolist() if "status" in ds.domains else ds.domains.domain_name.tolist()
    unl_t = {y: sum(1 for ls, yy in zip(topics_l, years_of) if yy == y and not ls) for y in years}
    unl_d = {y: sum(1 for ls, yy in zip(domains_l, years_of) if yy == y and not ls) for y in years}
    gold = t.in_gold.astype(bool).values[idx] if "in_gold" in t else np.zeros(len(idx), bool)
    topics = _block(topic_names, topics_l, years_of, years, n_year)
    domains = _block(domain_names, domains_l, years_of, years, n_year)
    if top:
        topics, domains = topics[:top], domains[:top]
    return dict(source=source, sources=sources, n_source=n_source, n_with_year=len(idx), n_without_year=n_source - len(idx),
                years=[dict(year=y, n=n_year[y], share_of_total=n_year[y] / len(idx), small=n_year[y] < SMALL_YEAR, no_topic=unl_t[y], no_domain=unl_d[y]) for y in years],
                latest_year=years[-1], compare_years=years[:-1], min_n=MIN_N, small_year=SMALL_YEAR,
                label_quality=dict(gold=int(gold.sum()), model=int(len(idx) - gold.sum()), gold_share=float(gold.mean())),
                topics=topics, domains=domains)
