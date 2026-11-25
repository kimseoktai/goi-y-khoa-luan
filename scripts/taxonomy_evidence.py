"""Phase 2 - thống kê bằng chứng cho taxonomy đề xuất (chỉ đọc, không gán nhãn chính thức).

Đọc technical_topics.csv / domains.csv (cột keywords) rồi đếm số bản ghi Thesis, Job, Gold khớp.
Với nhãn Gold cũ đã có ánh xạ, tính precision/recall của bộ keywords so với nhãn Gold
để biết keywords có đáng tin hay không. Đây là kiểm tra thô, chưa phải classifier.
"""
import argparse, json, re
from pathlib import Path
import pandas as pd


def compile_kw(kws: str):
    parts = [k.strip().lower() for k in str(kws).split("|") if k.strip()]
    return re.compile("|".join(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])" for k in parts))


def hits(series: pd.Series, rx) -> pd.Series:
    return series.str.lower().fillna("").map(lambda s: bool(rx.search(s)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topics", default="data/repository/technical_topics.csv")
    p.add_argument("--domains", default="data/repository/domains.csv")
    p.add_argument("--thesis", required=True)
    p.add_argument("--jobs", default="data/processed/jobs/jobs_clean.csv")
    p.add_argument("--gold", required=True)
    p.add_argument("--map", default="data/processed/taxonomy/old_to_new_label_map.csv")
    p.add_argument("--out", default="data/processed/taxonomy/taxonomy_evidence.csv")
    a = p.parse_args()

    t = pd.read_csv(a.thesis, encoding="utf-8-sig")
    j = pd.read_csv(a.jobs, encoding="utf-8-sig")
    g = pd.read_csv(a.gold, encoding="utf-8-sig")
    m = pd.read_csv(a.map, encoding="utf-8-sig")
    g["lab"] = g.topics.map(json.loads)
    jtext = j.job_title + " " + j.skills.fillna("") + " " + j.description
    jts = j.job_title + " " + j.skills.fillna("")   # chỉ title + skills: ít nhiễu hơn description
    rows = []
    for kind, path, idc, namec in [("technical_topic", a.topics, "topic_id", "topic_name"),
                                   ("domain", a.domains, "domain_id", "domain_name")]:
        for r in pd.read_csv(path, encoding="utf-8-sig").itertuples():
            rx = compile_kw(r.keywords)
            th, jb, gd = hits(t.title, rx), hits(jtext, rx), hits(g.title, rx)
            jt = hits(jts, rx)
            old = m[(m.new_id == getattr(r, idc))].old_label.tolist()
            sup = g.lab.map(lambda l: any(o in l for o in old)) if old else None
            row = dict(type=kind, id=getattr(r, idc), name=getattr(r, namec), status=r.status,
                       thesis_hits=int(th.sum()), thesis_pct=round(th.mean() * 100, 1),
                       job_hits_desc=int(jb.sum()), job_pct_desc=round(jb.mean() * 100, 1),
                       job_hits_title_skills=int(jt.sum()), job_pct_title_skills=round(jt.mean() * 100, 1),
                       gold_label_support=int(sup.sum()) if sup is not None else 0,
                       kw_precision_vs_gold=None, kw_recall_vs_gold=None)
            if sup is not None and sup.sum() > 0:
                tp = int((gd & sup).sum())
                row["kw_precision_vs_gold"] = round(tp / max(int(gd.sum()), 1), 2)
                row["kw_recall_vs_gold"] = round(tp / int(sup.sum()), 2)
            rows.append(row)
    out = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
