"""Phase 8 - phân tích nhu cầu thị trường từ jobs_processed.csv và so với nguồn cung Thesis (thesis_processed.csv)."""
import argparse, json, logging, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                                # noqa: E402
from ml.recommendation import market_demand as M                          # noqa: E402

log = logging.getLogger("market")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(C.ROOT / "data/processed/jobs/jobs_processed.csv"))
    ap.add_argument("--thesis", default=str(C.ROOT / "data/processed/thesis/thesis_processed.csv"))
    ap.add_argument("--out-dir", default=str(C.ROOT / "data/processed/market"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
    j, t, topics = rd(a.jobs), rd(a.thesis), rd(C.TOPICS)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    comp = j.company.tolist()
    L = lambda col: j[col].map(json.loads).tolist()

    M.demand_table([[r] for r in j.job_title], comp).to_csv(out / "demand_roles.csv", index=False, encoding="utf-8-sig")
    M.demand_table(L("skills"), comp).to_csv(out / "demand_skills.csv", index=False, encoding="utf-8-sig")
    M.demand_table(L("technologies"), comp).to_csv(out / "demand_technologies.csv", index=False, encoding="utf-8-sig")
    topic_df = M.demand_table(L("technical_topics"), comp); topic_df.to_csv(out / "demand_topics.csv", index=False, encoding="utf-8-sig")
    dom_df, with_dom = M.fractional_domain_table(L("domain_scores"), comp)
    dom_df.to_csv(out / "demand_domains.csv", index=False, encoding="utf-8-sig")
    M.pair_table(L("technical_topics"), L("domains"), comp).to_csv(out / "demand_topic_domain_pairs.csv", index=False, encoding="utf-8-sig")
    R = C.ROOT / "data/repository"
    measurable = set(rd(R / "skill_topic_map.csv").topic_name) | set(rd(R / "job_role_topic_map.csv").topic_name)
    sv = M.supply_vs_demand(L("technical_topics"), t.technical_topics.map(json.loads).tolist(), topics.topic_name.tolist(), measurable)
    sv.to_csv(out / "supply_vs_demand_topics.csv", index=False, encoding="utf-8-sig")

    top = j.company.value_counts()
    summary = dict(n_jobs=len(j), n_companies=int(j.company.nunique()), top_company=top.index[0], top_company_jobs=int(top.iloc[0]),
                   companies_unknown=int((j.company == "Unknown").sum()), top5_company_share=round(float(top.head(5).sum() / len(j)), 3),
                   jobs_with_domain=int(with_dom), jobs_without_domain=int(len(j) - with_dom), n_thesis=len(t),
                   min_support=M.MIN_SUPPORT, min_companies=M.MIN_COMPANIES, trend_analysis="không thực hiện: dữ liệu không có ngày đăng")
    (out / "market_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("đã lưu vào %s", out)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
