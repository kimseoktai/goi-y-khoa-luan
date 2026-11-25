"""Phase 7 - gán Technical Topic / Domain / Technologies cho Job bằng quy tắc minh bạch (có bằng chứng kèm theo).

Technical Topic: (a) vai trò trong job_title -> topic (job_role_topic_map.csv), (b) skill -> topic (skill_topic_map.csv).
Domain: từ khóa của domains.csv xuất hiện trong tên công ty hoặc >= min_desc_hits từ khác nhau trong mô tả.
Không hard-code taxonomy/skill trong code. Mọi ánh xạ đọc từ data/repository.
"""
import json
import re
import unicodedata
import pandas as pd

from ml.classification.model import compile_keywords


_COMPANY_NOISE = re.compile(r"\b(cong ty|tap doan|co phan|tnhh|trach nhiem huu han|mot thanh vien|mtv|jsc|joint stock|company|co|ltd|limited|corp|corporation|inc|pte|vietnam|viet nam|vn|chi nhanh)\b")


def company_key(name):
    """Khóa so khớp tên công ty: bỏ dấu, bỏ ký tự lạ và các từ loại hình doanh nghiệp (Công ty TNHH, Co., Ltd, Vietnam...)."""
    s = unicodedata.normalize("NFD", str(name or "").lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = _COMPANY_NOISE.sub(" ", re.sub(r"[^a-z0-9 ]", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def load_company_domains(path):
    """Đọc bảng công ty -> lĩnh vực (company_domains.csv): {company_key: [domain,...]}.
    Bỏ dòng status=rejected hoặc review (chờ người duyệt); domain '-' hoặc trống nghĩa là "lĩnh vực tùy vị trí" nên không ép (vẫn dùng từ khóa); nhiều lĩnh vực ngăn bằng '|'."""
    from pathlib import Path
    if not Path(path).exists():
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig").fillna("")
    out = {}
    for r in df.itertuples():
        doms = [d.strip() for d in str(r.domain).split("|") if d.strip() and d.strip() != "-"]
        if doms and str(r.status).strip().lower() not in ("rejected", "review"):
            out[company_key(r.company_example)] = doms
    return out


def _distinct_hits(rx, text):
    return sorted({m.group(0) for m in rx.finditer(text.lower())})


def _stem_count(hits):
    """Số từ khóa khác nhau sau khi gộp số nhiều (payment/payments tính là một)."""
    return len({re.sub(r"(?:es|s)$", "", h) if re.fullmatch(r"[a-z]+", h) and len(h) > 4 else h for h in hits})


def _counts(rx, text):
    from collections import Counter
    return Counter(m.group(0) for m in rx.finditer(text.lower()))


def _compile(kws, company=False):
    """Từ khóa ASCII cho phép số nhiều (payment -> payments). Với tên công ty, từ khóa >=4 ký tự khớp cả khi dính liền
    trong thương hiệu (bank -> Techcombank)."""
    parts = []
    for k in [k.strip().lower() for k in kws if k.strip()]:
        ascii_word = re.fullmatch(r"[a-z]+", k) is not None
        if company and ascii_word and len(k) >= 4:
            parts.append(re.escape(k))
        elif ascii_word:
            plural = r"(?:s|es)?" if len(k) >= 4 else ""      # từ viết tắt ngắn (hr) không nhận số nhiều: tránh 'HRS' -> HR
            parts.append(r"(?<![a-z0-9])" + re.escape(k) + plural + r"(?![a-z0-9])")
        else:
            parts.append(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])")
    return re.compile("|".join(parts))


def label_jobs(jobs, topics, domains, skill_topic, role_topic, cat_roles, role_over, skills_repo,
               min_skill_weight=2.0, skill_full_weight=3.0, min_desc_hits=2, domain_exclusions=None, domain_extra=None, min_repeat=3,
               topic_statuses=("active", "candidate"), domain_min_hits=None, company_domains=None):
    """domain_min_hits: {domain: số từ khóa mô tả khác nhau tối thiểu} áp dụng khi tên công ty KHÔNG khớp (bù cho lĩnh vực hay bị nhắc chung chung)."""
    domain_min_hits = domain_min_hits or {}
    company_domains = company_domains or {}      # {company_key: [domain,...]}: lĩnh vực CỦA CÔNG TY tuyển (bảng công ty); công ty có trong bảng thì chỉ dùng bảng này
    # Gán nhãn bằng quy tắc không cần huấn luyện nên được dùng cả topic candidate (để thống kê nhu cầu); trạng thái nằm ở taxonomy
    active_t = set(topics[topics.status.isin(topic_statuses)].topic_name)
    st = skill_topic[skill_topic.topic_name.isin(active_t)]
    skill_map = {}
    for r in st.itertuples():
        skill_map.setdefault(r.skill_name, []).append((r.topic_name, r.weight))
    topic_total = st.groupby("topic_name").weight.sum().to_dict()   # tổng trọng số skill của mỗi topic
    role_map = {}
    for r in role_topic[role_topic.topic_name.isin(active_t)].itertuples():
        role_map.setdefault(r.job_role, []).append(r.topic_name)
    cat_role = dict(zip(cat_roles.category, cat_roles.role))
    skill_cat = dict(zip(skills_repo.skill_name, skills_repo.category))
    over = dict(zip(role_over.skill_name, role_over.role))
    excl = {}
    if domain_exclusions is not None:
        for r in domain_exclusions.itertuples():
            excl.setdefault(r.domain_name, set()).add(r.keyword.lower())

    extra = {}
    if domain_extra is not None:
        for r in domain_extra.itertuples():
            extra.setdefault(r.domain_name, []).append(r.keyword)

    def kw_list(r):
        kws = [k for k in r.keywords.split("|") if k] + extra.get(r.domain_name, [])
        return [k for k in kws if k.lower() not in excl.get(r.domain_name, set())]
    act = list(domains[domains.status == "active"].itertuples())
    drx = {r.domain_name: _compile(kw_list(r)) for r in act}
    crx = {r.domain_name: _compile(kw_list(r), company=True) for r in act}

    rows = []
    for j in jobs.itertuples():
        skills = json.loads(j.skills)
        # --- Technologies vs competencies
        tech, comp = [], []
        for s in skills:
            role = over.get(s) or cat_role.get(skill_cat.get(s), "competency")
            (tech if role == "technology" else comp).append(s)
        # --- Technical topics
        score, ev = {}, {}
        for t in role_map.get(j.job_title, []):
            score[t] = 1.0
            ev[t] = {"role": j.job_title, "skills": []}
        wsum = {}
        sk_by_t = {}
        for s in skills:
            for t, w in skill_map.get(s, []):
                wsum[t] = wsum.get(t, 0) + w
                sk_by_t.setdefault(t, []).append(s)
        for t, w in wsum.items():
            if t in score:
                ev[t]["skills"] = sk_by_t[t]
            elif w >= min(min_skill_weight, topic_total.get(t, min_skill_weight)):   # topic chỉ có 1 skill (NLP, CV, Blockchain) cần đủ skill đó
                score[t] = round(min(1.0, w / skill_full_weight), 2)
                ev[t] = {"role": None, "skills": sk_by_t[t]}
        topics_sorted = sorted(score, key=lambda t: -score[t])
        # --- Domains
        dscore, dev = {}, {}
        forced = [d for d in company_domains.get(company_key(j.company), []) if d in drx]
        for d in forced:
            dscore[d] = 1.0; dev[d] = {"company_table": True, "company": [], "description": []}
        for d, rx in ([] if forced else drx.items()):
            ch = _distinct_hits(crx[d], j.company)
            cnt = _counts(rx, j.description)
            dh = sorted(cnt)
            if ch:
                dscore[d] = 1.0; dev[d] = {"company": ch, "description": dh}
            elif d in domain_min_hits and _stem_count(dh) < domain_min_hits[d]:
                continue
            elif len(dh) >= min_desc_hits or (cnt and max(cnt.values()) >= min_repeat):
                dscore[d] = round(min(1.0, max(len(dh) / 3, max(cnt.values()) / 5)), 2); dev[d] = {"company": [], "description": dh}
        doms_sorted = sorted(dscore, key=lambda d: -dscore[d])
        flags = []
        if not topics_sorted: flags.append("no_technical_topic")
        rows.append(dict(
            technologies=json.dumps(tech, ensure_ascii=False), competencies=json.dumps(comp, ensure_ascii=False),
            technical_topics=json.dumps(topics_sorted, ensure_ascii=False),
            technical_topic_scores=json.dumps({t: score[t] for t in topics_sorted}, ensure_ascii=False),
            topic_evidence=json.dumps(ev, ensure_ascii=False),
            domains=json.dumps(doms_sorted, ensure_ascii=False),
            domain_scores=json.dumps({d: dscore[d] for d in doms_sorted}, ensure_ascii=False),
            domain_evidence=json.dumps(dev, ensure_ascii=False),
            review_flag="|".join(flags)))
    return pd.DataFrame(rows)
