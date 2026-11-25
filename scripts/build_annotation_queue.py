"""Phase 3 - tạo hàng đợi gán nhãn cho các nhãn Gold chưa đủ mẫu.

Lấy title Thesis (chưa nằm trong Gold) khớp keywords của nhãn thiếu mẫu.
Đây chỉ là danh sách ĐỂ NGƯỜI GÁN NHÃN xem, cột decision để trống.
"""
import argparse, json, re
import pandas as pd
from taxonomy_evidence import compile_kw


def n_kw(title, kws):
    t = title.lower()
    return sum(bool(re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", t)) for k in kws)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--thesis", required=True)
    p.add_argument("--gold", default="data/processed/gold/gold_dataset_clean.csv")
    p.add_argument("--topics", default="data/repository/technical_topics.csv")
    p.add_argument("--domains", default="data/repository/domains.csv")
    p.add_argument("--min-support", type=int, default=15, help="nhãn có ít hơn số mẫu Gold này thì vào hàng đợi")
    p.add_argument("--per-label", type=int, default=30)
    p.add_argument("--out", default="data/processed/gold/gold_annotation_queue.csv")
    a = p.parse_args()
    t = pd.read_csv(a.thesis, encoding="utf-8-sig")
    g = pd.read_csv(a.gold, encoding="utf-8-sig")
    gt = set(g.title.str.lower().str.strip())
    pool = t[~t.title.str.lower().str.strip().isin(gt)]
    rows = []
    for kind, path, col, namec, idc in [("technical_topic", a.topics, "technical_topics", "topic_name", "topic_id"),
                                       ("domain", a.domains, "domains", "domain_name", "domain_id")]:
        sup = pd.Series([x for l in g[col].map(json.loads) for x in l]).value_counts()
        for r in pd.read_csv(path, encoding="utf-8-sig").itertuples():
            name = getattr(r, namec)
            if sup.get(name, 0) >= a.min_support:
                continue
            kws = [k for k in r.keywords.split("|") if k]
            rx = compile_kw(r.keywords)
            m = pool[pool.title.str.lower().map(lambda s: bool(rx.search(s)))].copy()
            m["score"] = m.title.map(lambda s: n_kw(s, kws))
            m = m.sort_values("score", ascending=False).head(a.per_label)
            for x in m.itertuples():
                rows.append(dict(label_type=kind, label_id=getattr(r, idc), label_name=name,
                                 current_gold_support=int(sup.get(name, 0)), thesis_id=x.thesis_id,
                                 title=x.title, source=x.source, keyword_score=x.score, decision=""))
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(out.groupby(["label_type", "label_name"]).size().to_string())
    print("tổng dòng:", len(out), "| thesis duy nhất:", out.thesis_id.nunique())


if __name__ == "__main__":
    main()
