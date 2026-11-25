"""Từ một hướng đề tài (Topic + Domain) của một Job: công nghệ nên dùng, đề tài đã có để tham khảo, và tên đề tài do LLM viết (Phase 14).
LLM chỉ viết tên; công nghệ lấy từ kỹ năng của Job, đề tài liên quan và mức trùng lấy từ dữ liệu của hệ thống."""
import numpy as np

from backend.errors import BadRequest, Unavailable
from backend.services import novelty_service
from backend.services.common import check_domains, check_topics, job_index, jsonable, opt
from ml.generation import title_prompt as TP
from ml.generation.llm_client import LLMBadOutput, LLMUnavailable

EXTRA = 1                      # sinh dư vài tên để còn bỏ tên trùng


def _direction(ds, topics, domains):
    topics = check_topics(ds, topics or [])
    if not topics:
        raise BadRequest("topics không được rỗng")
    return topics, check_domains(ds, domains or [])


def technologies(ds, i, topics, k=8):
    """Công nghệ/kỹ năng của Job có liên quan tới các Topic của hướng (theo bảng kỹ năng-chủ đề)."""
    j, ts, out = ds.jobs.iloc[i], set(topics), []
    for s in list(j._technologies) + list(j._skills):
        m = ds.skill_map.get(str(s).strip().lower(), {})
        if any(t in ts for t in m) and s not in out:
            out.append(s)
    return out[:k]


def related_theses(ds, i, topics, domains, k=5):
    """Luận văn đã có cùng chủ đề (ưu tiên cùng lĩnh vực), xếp theo độ giống với Job nếu có embedding, không thì theo số nhãn trùng."""
    t, ts, dm = ds.thesis, set(topics), set(domains)
    rows = []
    for p, (tt, dd) in enumerate(zip(t._technical_topics, t._domains)):
        st, sd = ts & set(tt), dm & set(dd)
        if st:
            rows.append((p, sorted(st), sorted(sd)))
    sims = None
    try:
        sims = ds.thesis_vectors() @ ds.job_vectors()[i]
    except Unavailable:
        pass
    key = (lambda r: (-len(r[2]), -float(sims[r[0]]))) if sims is not None else (lambda r: (-len(r[2]), -len(r[1]), r[0]))
    rows.sort(key=key)
    out = []
    for p, st, sd in rows[:k]:
        y = t.year.iloc[p]
        out.append(dict(thesis_id=t.thesis_id[p], title=t.title[p], year=None if np.isnan(float(y)) else int(y), source=t.source.iloc[p],
                        similarity=None if sims is None else round(float(sims[p]), 4), shared_topics=st, shared_domains=sd))
    return jsonable(dict(technologies=technologies(ds, i, topics), related_theses=out, total_same_topic=len(rows), similarity_note=None if sims is not None else "Chưa có embedding nên xếp theo số nhãn trùng."))


def related(ds, job_id, topics, domains, k=5):
    if not (1 <= k <= 10):
        raise BadRequest("k phải trong khoảng 1..10")
    topics, domains = _direction(ds, topics, domains)
    return related_theses(ds, job_index(ds, job_id), topics, domains, k)


def generate(ds, llm, need, topics, domains, techs, examples, n, avoid=(), context=None):
    """Phần dùng chung: gọi LLM viết tên và tóm tắt, kiểm tra trùng với kho luận văn, bỏ tên trùng. llm(messages) -> dict JSON."""
    all_t = ds.topics[ds.topics.status == "active"].topic_name.tolist()
    all_d = ds.domains[ds.domains.status == "active"].domain_name.tolist()
    msgs = TP.build_messages(need, topics, domains, techs, examples, n + EXTRA, all_t, all_d, avoid=avoid, context=context)
    cands = []
    for _ in range(2):                                      # thử lại một lần nếu mô hình trả JSON hỏng
        try:
            cands = TP.parse_titles(llm(msgs), all_t, all_d, topics, domains, allowed_tech=techs)
        except LLMUnavailable as e:
            raise Unavailable(str(e))
        except LLMBadOutput:
            cands = []
        if cands:
            break
    if not cands:
        raise Unavailable("mô hình trả về kết quả không đọc được; hãy thử lại")
    try:
        ds.thesis_vectors(); has_emb = True
    except Unavailable:
        has_emb = False
    out, dropped = [], 0
    for c in cands:
        nov = None
        if has_emb:
            r = novelty_service.check_text(ds, c["title"], topics, domains, top_k=3)
            if r["novelty_status"] == "Duplicate":
                dropped += 1
                continue
            nov = dict(status=r["novelty_status"], max_similarity=r["max_similarity"], novelty_score=r["novelty_score"], nearest=r["top_neighbors"][0], combo_support=r.get("combo_support"))
        out.append(dict(title=c["title"], why=c["why"], summary=c.get("summary", ""), tech=c["tech"], domains=c["domains"], novelty=nov))
    out.sort(key=lambda x: 0 if (x["novelty"] or {}).get("status") == "Novel" else 1)       # sort ổn định: Mới lên trước
    return out[:n], dropped, has_emb


NOTES = ["Tên đề tài và phần tóm tắt do mô hình ngôn ngữ viết, hãy xem như gợi ý để chỉnh sửa. Chủ đề và lĩnh vực là của hướng bạn đang xem.",
         "Mức trùng chỉ so với kho luận văn hiện có, không phải mọi đề tài đã tồn tại."]


def titles(ds, llm, job_id, topics, domains, n=3):
    """llm(messages) -> dict JSON (gọi Gemini); tiêm từ ngoài để kiểm thử."""
    if not (1 <= n <= 5):
        raise BadRequest("n phải trong khoảng 1..5")
    topics, domains = _direction(ds, topics, domains)
    i = job_index(ds, job_id)
    job = ds.jobs.iloc[i]
    techs = technologies(ds, i, topics)
    ref = related_theses(ds, i, topics, domains, 5)["related_theses"]
    need = f"sinh viên cần một đề tài khóa luận gắn với vị trí tuyển dụng \"{job.job_title}\"" + (f" (kỹ năng: {', '.join(job._skills[:8])})" if job._skills else "")
    out, dropped, has_emb = generate(ds, llm, need, topics, domains, techs, [r["title"] for r in ref], n, context=dict(job_title=job.job_title, excerpt=opt(job, "description")))
    return jsonable(dict(titles=out, technologies=techs, dropped_duplicates=dropped, novelty_checked=has_emb, notes=NOTES))
