"""Phase 11 - Recommendation Engine: Job -> Thesis Direction (không dùng LLM).

Thesis Direction = (tập Technical Topic, tập Domain, công nghệ gợi ý). Hướng được SINH từ chính Job (tổ hợp 1-2 Topic hàng đầu
của Job, kèm Domain của Job hoặc không Domain), rồi chấm điểm bằng 5 thành phần theo Master Requirement:
  Recommendation Score = (w1*JobRelevance + w2*TopicMatch + w3*DomainMatch + w4*SemanticRelevance + w5*Novelty) / tổng trọng số CÓ DỮ LIỆU
- JobRelevance: tỉ lệ khối lượng Skill của Job (qua skill_topic_map) được các Topic của hướng bao phủ.
- TopicMatch: cosine giữa vector Topic của hướng (0/1) và vector điểm Topic của Job.
- DomainMatch: cosine Domain; BỎ thành phần nếu Job hoặc hướng không có Domain (không phạt).
- SemanticRelevance: cosine embedding(văn bản hướng, Job), quy về [0,1] bằng phân vị 5%-95% của các cặp (Job, hướng) đã sinh.
- Novelty (mặc định, mode "label"): 1/(1+combo_support), combo_support = số Thesis đã có đủ Topic (và Domain) của hướng. 1.0 = chưa Thesis nào làm,
  0.5 = đúng 1 Thesis. Dạng hàm là heuristic đơn giản (chưa tối ưu). Chọn mode này vì khi chấm tay, novelty ngữ nghĩa (embedding của MÔ TẢ nhãn so với tiêu đề
  Thesis) gần như không dự đoán được nhãn Novel (AUC ~0.50, hai lần chấm), còn combo_support đạt AUC ~0.71 trên cả hai lần chấm (mẫu nhỏ, 83 hướng / 12 Job).
  Novelty ngữ nghĩa (mode "semantic") vẫn được lưu ở cột c_novelty_semantic để đối chiếu. Không dùng ngưỡng Duplicate/Similar của Phase 10 vì ngưỡng đó hiệu chỉnh cho cặp tiêu đề-tiêu đề.
Trọng số mặc định chỉ là điểm khởi đầu, chưa được coi là tối ưu (xem ml/recommendation/tune_rec_weights.py).
"""
import itertools
import json
import numpy as np
import pandas as pd

from ml.matching import matcher as M
from ml.novelty import novelty as N

DEFAULT_WEIGHTS = {"job_relevance": 0.25, "topic": 0.20, "domain": 0.10, "semantic": 0.25, "novelty": 0.20}
COMPONENTS = list(DEFAULT_WEIGHTS)
GAP_VI = {"demand_exceeds_supply": "nhu cầu Job lớn hơn nguồn cung Thesis", "supply_exceeds_demand": "Thesis nhiều hơn nhu cầu Job",
          "no_clear_gap": "chưa thấy chênh lệch rõ giữa Job và Thesis"}
GAIN = {"relevant": 2, "partially relevant": 1, "not relevant": 0}


def direction_text(topics, domains):
    return "Thesis direction: " + " + ".join(topics) + (" in " + " + ".join(domains) if domains else "")


def build_skill_map(df):
    out = {}
    for s, t, w in zip(df.skill_name, df.topic_name, df.weight):
        out.setdefault(str(s).strip().lower(), {})[t] = out.get(str(s).strip().lower(), {}).get(t, 0.0) + float(w)
    return out


def gen_candidates(topic_scores, domain_scores, max_topics=3, max_size=2, max_domains=2):
    top = [t for t, _ in sorted(topic_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:max_topics]]
    doms = [d for d, _ in sorted(domain_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:max_domains]]
    tsets = [tuple(sorted(c)) for r in range(1, min(max_size, len(top)) + 1) for c in itertools.combinations(top, r)]
    return [(ts, dm) for ts in tsets for dm in [()] + [(d,) for d in doms]]


def job_relevance(skills, skill_map, topics):
    tot = cov = 0.0
    covered = {}
    for s in skills:
        m = skill_map.get(str(s).strip().lower())
        if not m:
            continue
        tot += sum(m.values())
        c = sum(m.get(t, 0.0) for t in topics)
        cov += c
        if c > 0:
            covered[s] = c
    tech = [s for s, _ in sorted(covered.items(), key=lambda kv: -kv[1])][:6]
    return (cov / tot if tot > 0 else np.nan), tech


def topic_match(vec, topics):
    nv = np.sqrt(sum(v * v for v in vec.values()))
    return sum(vec.get(t, 0.0) for t in topics) / (np.sqrt(len(topics)) * nv) if nv > 0 else np.nan


def domain_match(vec, domains):
    if not vec or not domains:
        return np.nan
    nv = np.sqrt(sum(v * v for v in vec.values()))
    return sum(vec.get(d, 0.0) for d in domains) / (np.sqrt(len(domains)) * nv)


def build_candidates(jobs, skill_map, **kw):
    rows = []
    for _, j in jobs.iterrows():
        ts, ds = json.loads(j.technical_topic_scores), json.loads(j.domain_scores)
        skills = json.loads(j.skills) if isinstance(j.skills, str) else []
        for k, (topics, domains) in enumerate(gen_candidates(ts, ds, **kw)):
            jr, tech = job_relevance(skills, skill_map, topics)
            rows.append(dict(job_id=j.job_id, job_title=j.job_title, company=j.company, cand_id=f"{j.job_id}-{k}",
                             topics=topics, domains=domains, direction_text=direction_text(topics, domains),
                             suggested_technologies=json.dumps(tech, ensure_ascii=False),
                             c_job_relevance=jr, c_topic=topic_match(ts, topics), c_domain=domain_match(ds, domains)))
    return pd.DataFrame(rows)


def closest_same_label(topics, domains, dvec, thesis_E, thesis_ids, thesis_titles, label_sets):
    """Thesis gần nhất TRONG SỐ các Thesis cùng nhãn với hướng (đủ Topic và Domain). Nếu không có: lấy nhóm Thesis trùng nhiều nhãn nhất.
    Embedding mô tả nhãn chung chung nên Thesis gần nhất toàn kho hay là vài Thesis 'hub' không liên quan; lọc theo nhãn cho giải thích có nghĩa."""
    tset, dset = set(topics), set(domains)
    full = [i for i, (a, b) in enumerate(label_sets) if tset <= a and dset <= b]
    level, tier = "same_labels", full
    if not full:
        ov = np.array([len(tset & a) / len(tset) + (len(dset & b) / len(dset) if dset else 0.0) for a, b in label_sets])
        if len(ov) and ov.max() > 0:
            level, tier = "partial_labels", list(np.where(ov == ov.max())[0])
        else:
            level, tier = "none", []
    if not len(tier):
        return dict(same_label_thesis_id=None, same_label_thesis_title=None, same_label_similarity=np.nan, same_label_level=level)
    sims = thesis_E[tier] @ dvec
    j = tier[int(np.argmax(sims))]
    return dict(same_label_thesis_id=thesis_ids[j], same_label_thesis_title=thesis_titles[j], same_label_similarity=float(sims.max()), same_label_level=level)


def add_semantic_and_novelty(df, job_vecs, dir_vecs, thesis_E, thesis_ids, thesis_titles, label_sets, novelty_mode="label"):
    """job_vecs: {job_id: vec}; dir_vecs: {text: vec}; tất cả đã chuẩn hóa L2."""
    texts = list(dict.fromkeys(df.direction_text))
    D = np.vstack([dir_vecs[t] for t in texts])
    idx, sims = N.query_neighbors(D, thesis_E, k=3)
    ref = sims[:, 0]
    info = {t: dict(nearest_thesis_id=thesis_ids[idx[i, 0]], nearest_thesis_title=thesis_titles[idx[i, 0]],
                    nearest_similarity=float(sims[i, 0]), novelty=float(N.novelty_score(sims[i, 0], ref)),
                    neighbors=json.dumps([[thesis_ids[j], round(float(s), 4)] for j, s in zip(idx[i], sims[i])]))
            for i, t in enumerate(texts)}
    raw = np.array([float(job_vecs[str(j)] @ dir_vecs[t]) for j, t in zip(df.job_id, df.direction_text)])
    lo, hi = M.semantic_normalizer(raw)
    out = df.copy()
    out["sem_raw"] = raw
    out["c_semantic"] = np.clip((raw - lo) / max(hi - lo, 1e-9), 0, 1)
    for k in ("nearest_thesis_id", "nearest_thesis_title", "nearest_similarity", "neighbors"):
        out[k] = [info[t][k] for t in out.direction_text]
    out["c_novelty_semantic"] = [info[t]["novelty"] for t in out.direction_text]
    cache, sl, sup = {}, {}, []
    for tp, dm, t in zip(out.topics, out.domains, out.direction_text):
        if (tp, dm) not in cache:
            cache[(tp, dm)] = N.combo_support(label_sets, tp, dm)
            sl[(tp, dm)] = closest_same_label(tp, dm, dir_vecs[t], thesis_E, thesis_ids, thesis_titles, label_sets)
        sup.append(cache[(tp, dm)])
    out["combo_support"] = sup
    out["c_novelty_label"] = 1.0 / (1.0 + out.combo_support.astype(float))
    out["c_novelty"] = out["c_novelty_label"] if novelty_mode == "label" else out["c_novelty_semantic"]
    for k in ("same_label_thesis_id", "same_label_thesis_title", "same_label_similarity", "same_label_level"):
        out[k] = [sl[(tp, dm)][k] for tp, dm in zip(out.topics, out.domains)]
    out.attrs["semantic_norm"] = dict(lo=lo, hi=hi, novelty_mode=novelty_mode)
    return out


def score(df, w=None):
    w = w or DEFAULT_WEIGHTS
    num = np.zeros(len(df)); den = np.zeros(len(df))
    for c in COMPONENTS:
        col = f"c_{c}"
        if col not in df or w.get(c, 0) == 0:
            continue
        v = df[col].values.astype(float); ok = ~np.isnan(v)
        num += np.where(ok, w[c] * np.nan_to_num(v), 0.0); den += np.where(ok, w[c], 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 0.0


def rank(g, w=None, k=5, mmr=0.0):
    """g: các hướng của MỘT job. mmr=0 -> xếp thuần theo điểm; mmr>0 -> trừ phạt trùng lặp nhãn với hướng đã chọn (MMR)."""
    s = score(g, w); s = np.nan_to_num(s, nan=-1.0)
    order = list(np.argsort(-s, kind="stable"))
    if mmr <= 0:
        return order[:k]
    labs = [set(t) | set(d) for t, d in zip(g.topics, g.domains)]
    chosen = [order[0]]
    while len(chosen) < min(k, len(order)):
        rest = [i for i in order if i not in chosen]
        chosen.append(max(rest, key=lambda i: (1 - mmr) * s[i] - mmr * max(jaccard(labs[i], labs[c]) for c in chosen)))
    return chosen


def ndcg_at_k(scores, gains, k=5):
    order = np.argsort(-scores, kind="stable")[:k]
    disc = 1 / np.log2(np.arange(2, len(order) + 2))
    dcg = float((gains[order] * disc).sum())
    ideal = np.sort(gains)[::-1][:k]
    idcg = float((ideal * disc[:len(ideal)]).sum())
    return dcg / idcg if idcg > 0 else np.nan


def diversity(label_sets):
    """1 - độ giống Jaccard trung bình giữa các cặp hướng trong Top-k (0 = giống hệt nhau, 1 = không chung nhãn)."""
    if len(label_sets) < 2:
        return np.nan
    p = [jaccard(a, b) for a, b in itertools.combinations(label_sets, 2)]
    return 1 - float(np.mean(p))


def explain(r, job_topic_scores, market):
    """r: một dòng hướng; market: dict các bảng thị trường đã nạp (có thể rỗng)."""
    topics, domains = list(r.topics), list(r.domains)
    tech = json.loads(r.suggested_technologies)
    p = [f"Job '{r.job_title}' ({r.company}). Hướng đề xuất: {' + '.join(topics)}" + (f" trong lĩnh vực {', '.join(domains)}." if domains else " (không gắn Domain cụ thể vì Job không nêu rõ).")]
    if tech:
        p.append("Kỹ năng/công nghệ của Job liên quan: " + ", ".join(tech) + ".")
    p.append("Topic của Job: " + ", ".join(f"{t} ({v:.2f})" for t, v in sorted(job_topic_scores.items(), key=lambda kv: -kv[1])) + ".")
    dt = market.get("topics", {})
    for t in topics:
        m = dt.get(t)
        if m:
            p.append(f"Nhu cầu {t}: {m['share']:.0%} số Job (95% CI {m['ci_low']:.0%}-{m['ci_high']:.0%}), "
                     + ("đủ bằng chứng" if m["support_ok"] else "ÍT bằng chứng") + f"; so với Thesis: {GAP_VI.get(m.get('gap_status'), m.get('gap_status', 'n/a'))}.")
    for d in domains:
        m = market.get("domains", {}).get(d)
        if m:
            p.append(f"Nhu cầu Domain {d}: {m['share']:.0%} số Job có Domain" + ("" if m["support_ok"] else " (ít bằng chứng)") + ".")
    if "same_label_thesis_title" in r and isinstance(r.same_label_thesis_title, str):
        lv = {"same_labels": "Thesis gần nhất cùng nhãn", "partial_labels": "Thesis gần nhất trùng một phần nhãn (chưa có Thesis nào đủ nhãn)"}[r.same_label_level]
        p.append(f"{lv}: '{r.same_label_thesis_title}' (độ giống {r.same_label_similarity:.3f}); "
                 + ("chưa có Thesis nào mang đủ các nhãn này" if r.combo_support == 0 else f"{int(r.combo_support)} Thesis đã có đủ các nhãn này")
                 + f"; độ mới theo nhãn {r.c_novelty_label:.2f}, theo ngữ nghĩa {r.c_novelty_semantic:.2f}.")
    elif "nearest_thesis_title" in r and isinstance(r.nearest_thesis_title, str):
        p.append(f"Thesis gần nhất: '{r.nearest_thesis_title}' (độ giống {r.nearest_similarity:.3f}).")
    p.append("Điểm thành phần: " + ", ".join(f"{c}={getattr(r, 'c_' + c):.2f}" for c in COMPONENTS if f"c_{c}" in r and not pd.isna(getattr(r, f"c_{c}"))) + ".")
    return " ".join(p)
