"""Dữ liệu cho giao diện sinh viên: công việc đang tuyển nhiều, kỹ năng, đối chiếu kỹ năng của bạn với từng công việc, hướng đề tài theo các công việc đã chọn.

Mọi con số là đếm trực tiếp trên các tin tuyển dụng đã thu thập (ảnh chụp một thời điểm, không có xu hướng theo thời gian).
Tên đề tài và tóm tắt do LLM viết (ideas_service.generate); công nghệ, kỹ năng, đề tài đã có và mức trùng lấy từ dữ liệu.
Nhãn tiếng Việt, mô tả công việc nằm ở data/repository/student_labels.csv để sửa không cần đổi mã.
"""
from collections import Counter, defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

from backend.errors import BadRequest, NotFound
from backend.services import ideas_service, role_service
from backend.services.common import check_paging, jsonable, opt, page

LABELS_FILE = "data/repository/student_labels.csv"
SKILLS_FILE = "data/repository/skills.csv"
GENERIC_FILE = "data/repository/skill_generic.csv"   # khái niệm chung: vẫn được đếm khi phân tích nhưng không hiện làm lựa chọn cho sinh viên
MAX_ROLES = 3
MAX_SKILLS = 80
CORE_K, CORE_MIN_SHARE, CORE_MIN_JOBS = 12, 0.10, 2        # "kỹ năng cốt lõi" của một công việc: tối đa 12 kỹ năng có mặt trong ít nhất 10% tin của công việc đó
FIT_MIN_JOBS, FIT_MIN_SHARE = 2, 0.10    # một công việc "hợp" với hướng đề tài nếu có ít nhất 2 tin và 10% tin của nó thuộc chủ đề đó
DIRECTION_CAP = 9
PATH_MIN_JOBS = 3                        # kỹ năng chỉ được gợi ý học khi có trong ít nhất 3 tin của các công việc hợp nhất
DOMAIN_MIN_JOBS, DOMAIN_MIN_SHARE = 2, 0.25


# ---------- nhãn và danh mục
def _labels(ds):
    def build():
        out, p = defaultdict(dict), ds.root / LABELS_FILE
        if p.exists():
            for r in pd.read_csv(p, encoding="utf-8-sig", dtype=str).fillna("").to_dict("records"):
                out[r["kind"]][r["key"]] = (r["label_vi"] or r["key"], r["description_vi"])
        return out
    return ds.cached("student_labels", build)


def label(ds, kind, key):
    return _labels(ds)[kind].get(key, (key, ""))[0]


def labels(ds):
    """Nhãn tiếng Việt của chủ đề/lĩnh vực và các mục lọc cho Kho khóa luận (chủ đề có nhiều luận văn nhất, năm)."""
    L = _labels(ds)
    cnt = Counter(t for ts in ds.thesis._technical_topics for t in set(ts))
    topics = [dict(name=t, label=label(ds, "topic", t), count=c) for t, c in cnt.most_common()]
    years = sorted({int(y) for y in ds.thesis.year.dropna()}, reverse=True)
    return jsonable(dict(topics={k: v[0] for k, v in L["topic"].items()}, domains={k: v[0] for k, v in L["domain"].items()},
                         library=dict(topics=topics, years=years, total=len(ds.thesis))))


def _catalog(ds):
    """tên kỹ năng (đúng chữ hoa/thường trong dữ liệu) -> nhóm."""
    def build():
        p = ds.root / SKILLS_FILE
        df = pd.read_csv(p, encoding="utf-8-sig") if p.exists() else pd.DataFrame(columns=["skill_name", "category"])
        gen = _generic(ds)
        return {str(r.skill_name): str(r.category) for r in df.itertuples() if str(r.skill_name) != "nan" and str(r.skill_name).strip().lower() not in gen}
    return ds.cached("student_catalog", build)


def _sets(ds):
    return ds.cached("job_skill_sets", lambda: [set(str(x) for x in s) for s in ds.jobs._skills])


def _count(ds, idx=None):
    sets = _sets(ds)
    c = Counter()
    for i in (range(len(sets)) if idx is None else idx):
        c.update(sets[i])
    return c


def _role_names(ds):
    return {g["name"]: g for g in role_service.roles(ds)["groups"]}


def _mask(ds, role):
    return ds.jobs.job_title.fillna("").isin(role_service.titles_for(ds, role)).values


def _check_roles(ds, roles):
    roles = list(dict.fromkeys(roles or []))
    if not (1 <= len(roles) <= MAX_ROLES):
        raise BadRequest(f"hãy chọn từ 1 đến {MAX_ROLES} công việc")
    names = _role_names(ds)
    bad = [r for r in roles if r not in names or names[r]["is_other"]]
    if bad:
        raise NotFound(f"không có nhóm công việc: {', '.join(bad)}")
    return roles


def _role_card(ds, g):
    name = g["name"]
    return dict(name=name, label=label(ds, "role", name), description=_labels(ds)["role"].get(name, ("", ""))[1], job_count=g["job_count"])


# ---------- trang chủ
def overview(ds):
    n = len(ds.jobs)
    groups = [g for g in role_service.roles(ds)["groups"] if not g["is_other"]]
    hot = [_role_card(ds, g) for g in groups[:6]]
    sets = _sets(ds)
    cnt = _count(ds)
    top = cnt.most_common(8)
    pool = {s for s, _ in cnt.most_common(40)}
    pairs = Counter()
    for ss in sets:
        pairs.update(combinations(sorted(ss & pool), 2))
    years = sorted({int(y) for y in ds.thesis.year.dropna()})
    return jsonable(dict(
        n_jobs=n, n_thesis=len(ds.thesis), years=years, hot_roles=hot,
        top_skills=[dict(name=s, count=c, share=round(c / n, 4)) for s, c in top],
        skill_pairs=[dict(a=a, b=b, count=c) for (a, b), c in pairs.most_common(8)],
        note="Số liệu đếm từ các tin tuyển dụng đã thu thập, là ảnh chụp một thời điểm, chưa phải xu hướng theo tháng."))


def roles(ds):
    groups = [g for g in role_service.roles(ds)["groups"] if not g["is_other"]]
    return jsonable(dict(max_roles=MAX_ROLES, items=[dict(_role_card(ds, g), hot=i < 3) for i, g in enumerate(groups)]))


def _generic(ds):
    def build():
        p = ds.root / GENERIC_FILE
        if not p.exists():
            return set()
        df = pd.read_csv(p, encoding="utf-8-sig")
        return {str(x).strip().lower() for x in df.get("skill_name", []) if str(x) != "nan"}
    return ds.cached("student_generic", build)


def skill_groups(ds, per_group=8, max_groups=6, min_count=3):
    cat, cnt = _catalog(ds), _count(ds)
    by = defaultdict(list)
    for s, c in cnt.items():
        if c >= min_count and s in cat:
            by[cat[s]].append((s, c))
    groups = sorted(by.items(), key=lambda kv: -sum(c for _, c in kv[1]))[:max_groups]
    return jsonable(dict(max_skills=MAX_SKILLS, groups=[dict(category=k, label=label(ds, "skill_category", k),
                                                          skills=[dict(name=s, count=c) for s, c in sorted(v, key=lambda x: (-x[1], x[0]))[:per_group]]) for k, v in groups]))


# ---------- kỹ năng của tôi
def _known(ds, skills):
    cat = {k.lower(): k for k in _catalog(ds)}
    if len(skills or []) > MAX_SKILLS:
        raise BadRequest(f"tối đa {MAX_SKILLS} kỹ năng")
    known, ignored = [], []
    for s in skills or []:
        k = cat.get(str(s).strip().lower())
        (known if k else ignored).append(k or str(s))
    return list(dict.fromkeys(known)), ignored


def profile(ds, skills):
    known, ignored = _known(ds, skills)
    ks = set(known)
    sets = _sets(ds)
    out = []
    for g in role_service.roles(ds)["groups"]:
        if g["is_other"]:
            continue
        idx = np.where(_mask(ds, g["name"]))[0]
        if len(idx) == 0:
            continue
        c = _count(ds, idx)
        core = [(s, v / len(idx)) for s, v in c.most_common(CORE_K) if v / len(idx) >= CORE_MIN_SHARE and v >= CORE_MIN_JOBS]
        total = sum(sh for _, sh in core) or 1.0
        have = [s for s, _ in core if s in ks]
        miss = [dict(name=s, share=round(sh, 4)) for s, sh in core if s not in ks]
        out.append(dict(role=g["name"], label=label(ds, "role", g["name"]), job_count=len(idx),
                        match=round(sum(sh for s, sh in core if s in ks) / total, 4), have=have, missing=miss[:5]))
    out.sort(key=lambda r: (-r["match"], -r["job_count"]))
    # lộ trình: kỹ năng chưa biết, xếp theo mức xuất hiện trong tin của 3 công việc hợp nhất
    top = out[:3]
    pool = sorted({int(i) for r in top for i in np.where(_mask(ds, r["role"]))[0]})
    cnt, path = _count(ds, pool), []
    if pool:
        for s, v in cnt.most_common():
            if s in ks or v < PATH_MIN_JOBS:
                continue
            with_known = Counter()
            for i in pool:
                if s in sets[i]:
                    with_known.update(sets[i] & ks)
            near = with_known.most_common(1)
            path.append(dict(name=s, share=round(v / len(pool), 4), near=near[0][0] if near and near[0][1] >= CORE_MIN_JOBS else None))
            if len(path) == 5:
                break
    catg, by = _catalog(ds), defaultdict(list)
    for k in known:
        by[catg.get(k) or ""].append(k)
    groups = [dict(category=c, label=label(ds, "skill_category", c) if c else "Khác", skills=v)
              for c, v in sorted(by.items(), key=lambda kv: (kv[0] == "", -len(kv[1]), kv[0]))]
    return jsonable(dict(known=known, groups=groups, ignored=ignored, n_jobs=len(ds.jobs), roles=out[:6], path=path, path_roles=[r["label"] for r in top],
                         note="Mức hợp = tỷ lệ kỹ năng cốt lõi của công việc mà bạn đã có (tính trên các tin tuyển dụng đã thu thập). Là tham khảo, không phải đánh giá năng lực."))


# ---------- hướng đề tài theo các công việc đã chọn
def _pool(ds, roles):
    masks = {r: _mask(ds, r) for r in roles}
    idx = np.where(np.any(list(masks.values()), axis=0))[0]
    return masks, [int(i) for i in idx]


def _direction(ds, roles, masks, pool, topic, role_topic):
    jt = ds.jobs._technical_topics.tolist()
    jd = ds.jobs._domains.tolist()
    jobs_t = [i for i in pool if topic in jt[i]]
    dc = Counter(d for i in jobs_t for d in set(jd[i]))
    doms = [d for d, c in dc.most_common(1) if c >= DOMAIN_MIN_JOBS and c / len(jobs_t) >= DOMAIN_MIN_SHARE]
    sets = _sets(ds)
    cnt = _count(ds, jobs_t)
    mapped = [s for s, _ in cnt.most_common() if topic in ds.skill_map.get(s.strip().lower(), {})]
    techs = mapped[:6]
    for s, _ in cnt.most_common():                 # chưa đủ 3 công nghệ gắn với chủ đề thì lấy kỹ năng phổ biến nhất của các tin đó
        if len(techs) >= 3:
            break
        if s not in techs:
            techs.append(s)
    gained = [s for s, _ in cnt.most_common() if s not in techs][:4]
    ts = set(techs)
    rep = max(jobs_t, key=lambda i: (len(sets[i] & ts), -i))
    fit = sum(1 for r in roles if role_topic[r][topic] >= FIT_MIN_JOBS and role_topic[r][topic] / max(1, int(masks[r].sum())) >= FIT_MIN_SHARE)
    return jobs_t, doms, techs, gained, rep, fit


def ideas(ds, roles, offset=0, n=3):
    roles = _check_roles(ds, roles)
    if offset < 0 or not (1 <= n <= 6):
        raise BadRequest("offset phải >= 0 và n trong khoảng 1..6")
    masks, pool = _pool(ds, roles)
    jt = ds.jobs._technical_topics.tolist()
    tcount, role_topic = Counter(), {r: Counter() for r in roles}
    for i in pool:
        tcount.update(set(jt[i]))
    for r in roles:
        for i in np.where(masks[r])[0]:
            role_topic[r].update(set(jt[i]))
    names = _role_names(ds)
    cnt = _count(ds, pool)
    base = dict(roles=[_role_card(ds, names[r]) for r in roles], n_jobs=len(pool),
                top_skills=[dict(name=s, count=c, share=round(c / max(1, len(pool)), 4)) for s, c in cnt.most_common(8)],
                offset=offset)
    rank = []
    for t, c in tcount.items():
        fit = sum(1 for r in roles if role_topic[r][t] >= FIT_MIN_JOBS and role_topic[r][t] / max(1, int(masks[r].sum())) >= FIT_MIN_SHARE)
        rank.append((t, c, fit))
    rank.sort(key=lambda x: (-x[2], -x[1], x[0]))
    rank = rank[:DIRECTION_CAP]
    items = []
    for t, c, _ in rank[offset:offset + n]:
        jobs_t, doms, techs, gained, rep, fit = _direction(ds, roles, masks, pool, t, role_topic)
        rel = ideas_service.related_theses(ds, rep, [t], doms, 3)
        n_same = int((ds.thesis._technical_topics.map(lambda x: t in x)).sum())
        items.append(dict(key=t, topic=t, topic_label=label(ds, "topic", t), domains=doms, domain_labels=[label(ds, "domain", d) for d in doms],
                          n_jobs=len(jobs_t), fit=fit, fit_total=len(roles), technologies=techs, skills=gained,
                          related_theses=rel["related_theses"], same_topic_theses=n_same))
    msg = None if rank else "Các công việc này chưa có tin nào được gán chủ đề kỹ thuật nên chưa gợi ý được hướng đề tài."
    return jsonable(dict(base, total_directions=len(rank), items=items, message=msg,
                         note="Hướng đề tài lấy từ chủ đề của các tin tuyển dụng. Mức hợp = số công việc bạn chọn có ít nhất 10% tin thuộc chủ đề đó."))


def idea_title(ds, llm, roles, topic, avoid=(), n=1):
    roles = _check_roles(ds, roles)
    if not (1 <= n <= 3):
        raise BadRequest("n phải trong khoảng 1..3")
    if topic not in set(ds.topics.topic_name):
        raise NotFound(f"không có chủ đề '{topic}'")
    masks, pool = _pool(ds, roles)
    jt = ds.jobs._technical_topics.tolist()
    role_topic = {r: Counter(t for i in np.where(masks[r])[0] for t in set(jt[i])) for r in roles}
    if not any(topic in jt[i] for i in pool):
        raise BadRequest("chủ đề này không thuộc hướng của các công việc đã chọn")
    jobs_t, doms, techs, gained, rep, fit = _direction(ds, roles, masks, pool, topic, role_topic)
    ref = [r["title"] for r in ideas_service.related_theses(ds, rep, [topic], doms, 5)["related_theses"]]
    names = ", ".join(label(ds, "role", r) for r in roles)
    need = f"sinh viên Công nghệ thông tin muốn làm khóa luận cho các vị trí: {names}"
    avoid = [str(a)[:250] for a in list(avoid or [])[:8]]
    rj = ds.jobs.iloc[rep]
    out, dropped, has_emb = ideas_service.generate(ds, llm, need, [topic], doms, techs + gained[:2], ref, n, avoid=avoid, context=dict(job_title=rj.job_title, excerpt=opt(rj, "description")))
    for x in out:
        x["domain_labels"] = [label(ds, "domain", d) for d in x["domains"]]
    return jsonable(dict(titles=out, dropped_duplicates=dropped, novelty_checked=has_emb, notes=ideas_service.NOTES))


# ---------- tin tuyển dụng thật
def _safe_url(u):
    u = str(u or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else None


def jobs_of_role(ds, role, limit=10, offset=0):
    check_paging(limit, offset, 50)
    names = _role_names(ds)
    if role not in names:
        raise NotFound(f"không có nhóm công việc '{role}'")
    idx = np.where(_mask(ds, role))[0]
    if "posted_at" in ds.jobs.columns:                       # dữ liệu từ CSDL: tin mới đăng lên trước (tin chưa rõ ngày xuống cuối)
        pa = ds.jobs.posted_at.fillna("").astype(str).values
        idx = np.array(sorted(idx, key=lambda i: pa[i], reverse=True), dtype=int)
    items = []
    for i in idx[offset:offset + limit]:
        r = ds.jobs.iloc[int(i)]
        items.append(dict(job_id=r.job_id, title=r.job_title, company=r.company, url=_safe_url(r.url), skills=[str(s) for s in r._skills],
                          posted_at=opt(r, "posted_at"), source=opt(r, "source")))
    return dict(page(items, len(idx), limit, offset), role=role, role_label=label(ds, "role", role),
                note="Tin lấy từ dữ liệu đã thu thập, có thể đã hết hạn tuyển.")
