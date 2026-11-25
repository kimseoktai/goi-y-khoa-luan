"""Phase 11 - tạo mẫu để CHẤM TAY chất lượng đề xuất (và để tinh chỉnh trọng số).
  python scripts\\make_recommendation_eval_sample.py
Đọc data/processed/recommendation/candidates_all.csv (do recommend_directions.py tạo). Mỗi Job lấy một "bể" hướng gồm: Top của điểm mặc định,
Top theo từng thành phần riêng lẻ và 1 hướng ngẫu nhiên, để việc tinh chỉnh không thiên về trọng số mặc định.
Cột closest_thesis_same_labels là Thesis gần nhất trong số các Thesis cùng nhãn (match_level=partial_labels nghĩa là chưa có Thesis nào đủ nhãn). Điền 2 cột: relevance (Relevant / Partially Relevant / Not Relevant) và novel (Novel / Not Novel). Điểm số được ẩn ở file key.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                      # noqa: E402
from ml.recommendation import recommender as R  # noqa: E402

rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
OUT = C.ROOT / "data/processed/recommendation"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(OUT / "candidates_all.csv"))
    ap.add_argument("--jobs", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--n-jobs", type=int, default=12)
    ap.add_argument("--min-candidates", type=int, default=6)
    ap.add_argument("--prefill", help="file đã chấm trước đó: giữ relevance, chuyển novel cũ sang novel_prev để chấm lại novel với Thesis mới hiển thị")
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--out-dir", default=str(C.EVAL_DIR))
    a = ap.parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    cand, jobs = rd(a.candidates), rd(a.jobs)
    cand["topics_t"] = cand.topics.fillna("").map(lambda s: tuple(x for x in s.split(" | ") if x))
    cand["domains_t"] = cand.domains.fillna("").map(lambda s: tuple(x for x in s.split(" | ") if x))
    cand["topics"], cand["domains"] = cand.topics_t, cand.domains_t
    rng = np.random.default_rng(a.seed)
    sizes = cand.groupby("job_id").size()
    ok = sizes[sizes >= a.min_candidates].index.tolist()
    first = {j: cand[cand.job_id == j].topics.iloc[0][0] for j in ok}
    groups = {}
    for j in ok:
        groups.setdefault(first[j], []).append(j)
    for g in groups.values():
        rng.shuffle(g)
    chosen = []
    while len(chosen) < min(a.n_jobs, len(ok)):                       # luân phiên giữa các Topic chính để mẫu đa dạng
        for t in sorted(groups):
            if groups[t] and len(chosen) < a.n_jobs:
                chosen.append(groups[t].pop())
    jinfo = jobs.set_index("job_id")
    lab, key = [], []
    have = {c: f"c_{c}" in cand and cand[f"c_{c}"].notna().any() for c in R.COMPONENTS}
    for j in chosen:
        g = cand[cand.job_id == j].reset_index(drop=True)
        src = {}
        def add(i, s):
            src.setdefault(i, []).append(s)
        for rk, i in enumerate(R.rank(g, None, 3)):
            add(i, f"default@{rk + 1}")
        for c in R.COMPONENTS:
            if have[c]:
                col = g[f"c_{c}"].fillna(-1).values
                for i in np.argsort(-col, kind="stable")[:2]:
                    add(int(i), f"{c}_only")
        rest = [i for i in range(len(g)) if i not in src]
        if rest:
            add(int(rng.choice(rest)), "random_control")
        default_rank = {i: r for r, i in enumerate(R.rank(g, None, len(g)), 1)}
        order = list(src); rng.shuffle(order)
        jr = jinfo.loc[j] if j in jinfo.index else None
        skills = ", ".join(json.loads(jr.skills)[:10]) if jr is not None and isinstance(jr.skills, str) else ""
        for i in order:
            r = g.iloc[i]; rid = f"{j}-{r.cand_id.split('-')[-1]}"
            lab.append(dict(rec_id=rid, job_id=j, job_title=r.job_title, company=r.company, job_skills=skills,
                            job_topics=" | ".join(json.loads(jr.technical_topics)) if jr is not None else "",
                            job_domains=" | ".join(json.loads(jr.domains)) if jr is not None else "",
                            direction_topics=" + ".join(r.topics), direction_domains=" + ".join(r.domains),
                            suggested_technologies=", ".join(json.loads(r.suggested_technologies)),
                            closest_thesis_same_labels=r.get("same_label_thesis_title", r.get("nearest_thesis_title", "")), match_level=r.get("same_label_level", ""),
                            relevance="", novel="", note=""))
            key.append(dict(rec_id=rid, job_id=j, cand_id=r.cand_id, topics=r.topics_t if False else " | ".join(r.topics), domains=" | ".join(r.domains),
                            **{f"c_{c}": r.get(f"c_{c}", np.nan) for c in R.COMPONENTS}, nearest_similarity=r.get("nearest_similarity", np.nan),
                            combo_support=r.get("combo_support", np.nan), default_rank=default_rank[i], sources="|".join(src[i])))
    lab = pd.DataFrame(lab)
    if a.prefill:
        prev = rd(a.prefill)[["rec_id", "relevance", "novel"]].rename(columns={"novel": "novel_prev"})
        lab = lab.drop(columns=["relevance"]).merge(prev[["rec_id", "relevance", "novel_prev"]], on="rec_id", how="left")
        lab["relevance"] = lab.relevance.fillna("")
        print(f"đã giữ relevance cho {(lab.relevance != '').sum()}/{len(lab)} hướng; hãy chấm lại cột novel")
    lab.to_csv(out / "recommendation_eval_sample.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(key).to_csv(out / "recommendation_eval_key.csv", index=False, encoding="utf-8-sig")
    print(f"{len(chosen)} job, {len(lab)} hướng cần chấm -> {out / 'recommendation_eval_sample.csv'}")


if __name__ == "__main__":
    main()
