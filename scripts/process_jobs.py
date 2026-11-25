"""Phase 7 - xử lý Jobs: Technologies + Technical Topics + Domains + tham chiếu Embedding (quy tắc có bằng chứng, không train).

  python scripts/process_jobs.py --embedding-model intfloat/multilingual-e5-base
"""
import argparse, json, logging, sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                   # noqa: E402
from ml.classification.job_labeling import label_jobs, load_company_domains   # noqa: E402
from ml.embedding.embedder import model_tag                  # noqa: E402

log = logging.getLogger("process_jobs")
R = C.ROOT / "data/repository"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(C.JOBS))
    ap.add_argument("--embedding-model", default=None)
    ap.add_argument("--embedding-name", default="jobs", help="tên bộ embedding Jobs ( 'jobs_db' cho dữ liệu từ CSDL)")
    ap.add_argument("--min-skill-weight", type=float, default=1.5, help="tổng trọng số skill tối thiểu để gán topic (rules_v1.3: hạ từ 2.0 xuống 1.5)")
    ap.add_argument("--min-desc-hits", type=int, default=2)
    ap.add_argument("--min-repeat", type=int, default=3, help="một từ khóa lặp từ N lần trong mô tả cũng đủ gán Domain")
    ap.add_argument("--out", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--summary", default=str(C.ROOT / "data/processed/jobs/jobs_label_summary.csv"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
    jobs = rd(a.jobs); topics, domains = rd(C.TOPICS), rd(C.DOMAINS)
    company_domains = load_company_domains(R / "company_domains.csv")
    lab = label_jobs(jobs, topics, domains, rd(R / "skill_topic_map.csv"), rd(R / "job_role_topic_map.csv"),
                     rd(R / "skill_category_roles.csv"), rd(R / "skill_role_overrides.csv"), rd(R / "skills.csv"),
                     a.min_skill_weight, 3.0, a.min_desc_hits, rd(R / "domain_job_exclusions.csv"),
                     rd(R / "job_domain_extra_keywords.csv"), a.min_repeat,
                     domain_min_hits=({r.domain_name: int(r.min_hits) for r in rd(R / "domain_min_hits.csv").itertuples()} if (R / "domain_min_hits.csv").exists() else None),
                     company_domains=company_domains)
    out = pd.concat([jobs.reset_index(drop=True), lab], axis=1)
    n_tab = int(out.domain_evidence.str.contains("company_table").sum())
    log.info("lĩnh vực theo bảng công ty (company_domains.csv): %d tin (%d công ty trong bảng)", n_tab, len(company_domains))
    emb_ref = ""
    if a.embedding_model:
        tag = model_tag(a.embedding_model)
        f, idx = C.EMBED_DIR / f"{a.embedding_name}_{tag}.npy", C.EMBED_DIR / f"{a.embedding_name}_{tag}_index.csv"
        if not f.exists() or not idx.exists():
            raise SystemExit(f"thiếu {f.name}; chạy ml/embedding/build_embeddings.py trước")
        if np.load(f, mmap_mode="r").shape[0] != len(jobs) or rd(idx).id.tolist() != jobs.job_id.tolist():
            raise SystemExit("embedding Jobs không khớp thứ tự/số dòng jobs_clean.csv; tạo lại embedding")
        emb_ref = f"embeddings/{f.name}"
    out["embedding_file"] = emb_ref
    out["taxonomy_version"] = topics.version.iloc[0]
    out["method"] = f"rules(role+skill>={a.min_skill_weight}; domain company|desc>={a.min_desc_hits} or repeat>={a.min_repeat}; exclusions+extra)"
    out["processed_at"] = datetime.now().isoformat(timespec="seconds")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    rows = []
    for kind, col, names in [("technical_topic", "technical_topics", topics.topic_name), ("domain", "domains", domains.domain_name),
                             ("technology", "technologies", pd.Series(sorted({s for v in out.technologies for s in json.loads(v)})))]:
        lists = out[col].map(json.loads)
        for n in names:
            m = lists.map(lambda l: n in l)
            st = topics.set_index("topic_name").status.get(n) if kind == "technical_topic" else (domains.set_index("domain_name").status.get(n) if kind == "domain" else "")
            rows.append(dict(type=kind, label=n, taxonomy_status=st, job_count=int(m.sum()), pct=round(100 * m.mean(), 1)))
    pd.DataFrame(rows).to_csv(a.summary, index=False, encoding="utf-8-sig")
    log.info("jobs=%d | không topic=%d | không domain=%d | đã lưu %s", len(out), (out.technical_topics == "[]").sum(), (out.domains == "[]").sum(), a.out)


if __name__ == "__main__":
    main()
