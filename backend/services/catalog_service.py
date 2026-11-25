"""Danh mục: taxonomy, Job, Thesis, thị trường. Chỉ đọc và lọc; không có logic ML."""
import numpy as np

from backend.errors import BadRequest, NotFound
from backend.services.common import check_paging, jsonable, job_index, opt, page, thesis_index

TAXO_COLS_T = ["topic_id", "topic_name", "description", "keywords", "status", "version"]
TAXO_COLS_D = ["domain_id", "domain_name", "description", "keywords", "status", "version"]


def _taxo(df, cols, status):
    d = df if not status else df[df.status == status]
    out = d[cols].to_dict("records")
    for r in out:
        r["keywords"] = [k for k in str(r["keywords"]).split("|") if k]
    return jsonable(out)


def list_topics(ds, status=None):
    return _taxo(ds.topics, TAXO_COLS_T, status)


def list_domains(ds, status=None):
    return _taxo(ds.domains, TAXO_COLS_D, status)


def _job_summary(ds, i):
    r = ds.jobs.iloc[i]
    return dict(job_id=r.job_id, job_title=r.job_title, company=r.company, technical_topics=r._technical_topics,
                domains=r._domains, n_skills=len(r._skills))


def list_jobs(ds, q=None, topic=None, domain=None, limit=20, offset=0, role=None):
    """role: tên nhóm công việc (gồm các nhóm nhỏ đã gộp vào) hoặc đúng một job_title; q: tìm theo chữ trong tên vị trí hoặc công ty."""
    check_paging(limit, offset)
    m = np.ones(len(ds.jobs), dtype=bool)
    if role:
        from backend.services import role_service
        m &= ds.jobs.job_title.fillna("").isin(role_service.titles_for(ds, role)).values   # role là tên nhóm (gồm các nhóm đã gộp) hoặc một job_title
    if q:
        ql = q.lower()
        m &= ds.jobs.job_title.fillna("").str.lower().str.contains(ql, regex=False).values | ds.jobs.company.fillna("").str.lower().str.contains(ql, regex=False).values
    if topic:
        m &= np.array([topic in t for t in ds.jobs._technical_topics])
    if domain:
        m &= np.array([domain in d for d in ds.jobs._domains])
    idx = np.where(m)[0]
    return page([_job_summary(ds, i) for i in idx[offset:offset + limit]], len(idx), limit, offset)


def get_job(ds, job_id):
    r = ds.jobs.iloc[job_index(ds, job_id)]
    return jsonable(dict(
        job_id=r.job_id, job_title=r.job_title, company=r.company, url=r.url, description=r.description,
        skills=r._skills, technologies=r._technologies, competencies=r._competencies,
        technical_topics=r._technical_topics, technical_topic_scores=r._technical_topic_scores, topic_evidence=r._topic_evidence,
        domains=r._domains, domain_scores=r._domain_scores, domain_evidence=r._domain_evidence,
        review_flag=None if str(r.review_flag) == "nan" else r.review_flag,
        posted_at=opt(r, "posted_at"), deadline=opt(r, "deadline"), source=opt(r, "source"), status=opt(r, "status"),
        taxonomy_version=r.taxonomy_version, labeling_method=r.method))


def _link(r, col):
    """Đường dẫn do trang nguồn cung cấp (dữ liệu crawl): chỉ nhận http/https, còn lại bỏ."""
    v = r.get(col)
    return v if isinstance(v, str) and v.startswith(("https://", "http://")) else None


def _thesis_summary(ds, i):
    r = ds.thesis.iloc[i]
    return dict(thesis_id=r.thesis_id, title=r.title, year=None if np.isnan(r.year) else int(r.year), source=r.source,
                technical_topics=r._technical_topics, domains=r._domains, report_url=_link(r, "report_url"))


def list_thesis(ds, q=None, topic=None, domain=None, year=None, limit=20, offset=0, source=None, sort="new"):
    check_paging(limit, offset)
    if sort not in ("new", "old", "az"):
        raise BadRequest("sort phải là new, old hoặc az")
    m = np.ones(len(ds.thesis), dtype=bool)
    if q:
        m &= ds.thesis.title.fillna("").str.lower().str.contains(q.lower(), regex=False).values
    if topic:
        m &= np.array([topic in t for t in ds.thesis._technical_topics])
    if domain:
        m &= np.array([domain in d for d in ds.thesis._domains])
    if year is not None:
        m &= (ds.thesis.year == year).values
    if source and "source" in ds.thesis:
        m &= (ds.thesis.source.astype(str).values == source)
    idx = np.where(m)[0]
    yr = ds.thesis.year.values[idx].astype(float)
    if sort == "old":                                                   # cũ nhất trước (thiếu năm xếp cuối)
        idx = idx[np.argsort(np.where(np.isnan(yr), 1e9, yr), kind="stable")]
    elif sort == "az":
        idx = idx[np.argsort(np.array([str(ds.thesis.title.values[i] or "").lower() for i in idx], dtype=object), kind="stable")]
    else:
        idx = idx[np.argsort(-np.nan_to_num(yr, nan=-1), kind="stable")]   # năm mới nhất trước, giữ nguyên thứ tự cũ trong cùng năm
    return page([_thesis_summary(ds, i) for i in idx[offset:offset + limit]], len(idx), limit, offset)


def get_thesis(ds, thesis_id):
    r = ds.thesis.iloc[thesis_index(ds, thesis_id)]
    return jsonable(dict(
        thesis_id=r.thesis_id, title=r.title, year=None if np.isnan(r.year) else int(r.year), source=r.source,
        report_url=_link(r, "report_url"), source_code_url=_link(r, "source_code_url"),
        technical_topics=r._technical_topics, technical_topic_scores=r._technical_topic_scores, topic_confidence=r.topic_confidence,
        domains=r._domains, domain_scores=r._domain_scores, domain_confidence=r.domain_confidence,
        keywords=r._keywords, label_source=r.label_source, in_gold=bool(r.in_gold),
        review_flag=None if str(r.review_flag) == "nan" else r.review_flag,
        taxonomy_version=r.taxonomy_version, topic_model_version=r.topic_model_version, domain_model_version=r.domain_model_version))


MARKET_TABLES = ["demand_topics", "demand_domains", "demand_skills", "demand_roles", "demand_technologies",
                 "demand_topic_domain_pairs", "supply_vs_demand_topics"]


def market_table(ds, name, limit=50, only_supported=False):
    if name not in MARKET_TABLES:
        raise BadRequest(f"bảng không hợp lệ; chọn một trong {MARKET_TABLES}")
    df = ds.market.get(name)
    if df is None:
        raise NotFound(f"chưa có bảng {name}; chạy scripts/analyze_market.py")
    if only_supported and "support_ok" in df:
        df = df[df.support_ok]
    return jsonable(dict(table=name, total=len(df), items=df.head(limit).to_dict("records"),
                         note="support_ok=False nghĩa là ít job/công ty, chỉ đọc như gợi ý, không kết luận xu hướng. Dữ liệu không có ngày đăng nên không có xu hướng theo thời gian."))


def market_summary(ds):
    return jsonable(ds.market_summary)
