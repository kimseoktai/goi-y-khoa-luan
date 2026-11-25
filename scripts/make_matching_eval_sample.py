"""Tạo mẫu đánh giá thủ công Job -> Thesis (pooling từ nhiều cách xếp hạng, ẩn điểm để tránh thiên lệch).

Người đánh giá chỉ điền cột `relevance` trong matching_eval_sample.csv: Relevant / Partially Relevant / Not Relevant.
Điểm thành phần nằm ở matching_eval_key.csv (không cần mở), dùng để tinh chỉnh trọng số.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                   # noqa: E402
from ml.matching import matcher as M                         # noqa: E402
from ml.matching.components import build_components         # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--thesis", default=str(C.ROOT / "data/processed/thesis/thesis_processed.csv"))
    ap.add_argument("--embedding-model", default=None); ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    ap.add_argument("--n-jobs", type=int, default=12); ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--out-dir", default=str(C.EVAL_DIR))
    a = ap.parse_args()
    rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
    jobs, thesis, topics, domains = rd(a.jobs), rd(a.thesis), rd(C.TOPICS), rd(C.DOMAINS)
    comp = build_components(jobs, thesis, topics, domains, a.embedding_model, a.embedding_backend)
    W = dict(M.DEFAULT_WEIGHTS)
    if comp["sem"] is None:
        W["semantic"] = 0.0
    default = M.combine(comp["topic"], comp["domain"], comp["domain_ok"], comp["sem"], W)
    rng = np.random.default_rng(a.seed)

    eligible = jobs[jobs.technical_topics != "[]"]
    first = eligible.groupby("job_title", group_keys=False).sample(1, random_state=a.seed)
    chosen = pd.concat([first.sample(min(len(first), a.n_jobs), random_state=a.seed)]).job_id.tolist()
    rows, key = [], []
    for jid in chosen:
        i = int(jobs.index[jobs.job_id == jid][0]); pool = {}
        def add(idx, src):
            for j in idx:
                pool.setdefault(int(j), []).append(src)
        add(M.top_k(default[i:i + 1], 4)[0], "default")
        add(M.top_k(comp["topic"][i:i + 1], 2)[0], "topic_only")
        if comp["sem"] is not None:
            add(M.top_k(comp["sem"][i:i + 1], 2)[0], "semantic_only")
        far = np.argsort(-default[i])[200:]
        add(rng.choice(far, 1), "random_control")
        order = list(pool); rng.shuffle(order)
        j0 = jobs.loc[i]
        for j in order:
            pid = f"{jid}-{int(thesis.thesis_id[j])}"
            rows.append(dict(pair_id=pid, job_id=jid, job_title=j0.job_title, company=j0.company,
                             job_skills=", ".join(json.loads(j0.skills)[:12]),
                             job_description_excerpt=" ".join(str(j0.description).split())[:300],
                             job_topics=", ".join(json.loads(j0.technical_topics)), job_domains=", ".join(json.loads(j0.domains)),
                             thesis_id=int(thesis.thesis_id[j]), thesis_title=thesis.title[j],
                             thesis_topics=", ".join(json.loads(thesis.technical_topics[j])), thesis_domains=", ".join(json.loads(thesis.domains[j])),
                             relevance="", note=""))
            key.append(dict(pair_id=pid, job_id=jid, thesis_id=int(thesis.thesis_id[j]), topic_match=float(comp["topic"][i, j]),
                            domain_match=float(comp["domain"][i, j]), domain_ok=bool(comp["domain_ok"][i, j]),
                            semantic_norm=None if comp["sem"] is None else float(comp["sem"][i, j]),
                            semantic_raw=None if comp["sem_raw"] is None else float(comp["sem_raw"][i, j]),
                            default_rank=int((default[i] > default[i, j]).sum() + 1), sources="|".join(pool[j])))
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "matching_eval_sample.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(key).to_csv(out / "matching_eval_key.csv", index=False, encoding="utf-8-sig")
    print(len(rows), "cặp,", len(chosen), "job ->", out / "matching_eval_sample.csv")


if __name__ == "__main__":
    main()
