"""Tạo file để NGƯỜI kiểm tra thủ công kết quả gán nhãn Job (50 job, phân tầng theo vai trò).
Điền 4 cột cuối rồi gửi lại: topics_check (yes/partial/no), topics_missing, domains_check (yes/partial/no), domains_missing."""
import argparse, json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--exclude", default=None, help="CSV mẫu cũ (cột job_id) cần loại để có mẫu mới độc lập")
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--out", default=str(C.EVAL_DIR / "jobs_validation_sample.csv"))
    a = ap.parse_args()
    j = pd.read_csv(a.jobs, encoding="utf-8-sig")
    if a.exclude:
        for enc in ("utf-8-sig", "cp1252"):
            try:
                old = pd.read_csv(a.exclude, encoding=enc, usecols=["job_id"]); break
            except UnicodeDecodeError:
                continue
        j = j[~j.job_id.isin(old.job_id)]
    first = j.groupby("job_title", group_keys=False).sample(1, random_state=a.seed)       # mỗi vai trò 1 job
    rest = j[~j.job_id.isin(first.job_id)].sample(max(0, a.n - len(first)), random_state=a.seed)
    s = pd.concat([first, rest]).sort_values("job_id")
    out = pd.DataFrame({
        "job_id": s.job_id, "job_title": s.job_title, "company": s.company,
        "skills": s.skills.map(lambda v: ", ".join(json.loads(v)[:15])),
        "description_excerpt": s.description.str.replace(r"\s+", " ", regex=True).str.slice(0, 350),
        "predicted_topics": s.technical_topics.map(lambda v: ", ".join(json.loads(v))),
        "topic_evidence": s.topic_evidence.map(lambda v: "; ".join(f"{t}: role={e['role']} skills={','.join(e['skills'][:4])}" for t, e in json.loads(v).items())),
        "predicted_domains": s.domains.map(lambda v: ", ".join(json.loads(v))),
        "domain_evidence": s.domain_evidence.map(lambda v: "; ".join(f"{d}: {','.join(e['company'] + e['description'])}" for d, e in json.loads(v).items())),
        "topics_check": "", "topics_missing": "", "domains_check": "", "domains_missing": ""})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(len(out), "job ->", a.out)


if __name__ == "__main__":
    main()
