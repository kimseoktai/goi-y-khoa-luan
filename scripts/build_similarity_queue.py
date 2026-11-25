"""Hàng đợi bổ sung mẫu cho MỘT nhãn thiếu mẫu, dùng từ khóa mở rộng + độ tương đồng TF-IDF
với các mẫu dương hiện có (giảm thiên lệch chỉ-khớp-từ-khóa). Chỉ để người gán nhãn duyệt.
Loại các Thesis đã nằm trong Gold hoặc đã từng nằm trong hàng đợi trước.
"""
import argparse, json, re, glob
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--thesis", required=True)
    p.add_argument("--gold", default="data/processed/gold/gold_dataset_clean.csv")
    p.add_argument("--prior-queues", default="data/processed/gold/gold_annotation_queue*.csv")
    p.add_argument("--label-name", required=True)
    p.add_argument("--label-type", default="technical_topic", choices=["technical_topic", "domain"])
    p.add_argument("--label-id", required=True)
    p.add_argument("--strong-regex", required=True, help="regex ưu tiên cao (chữ thường)")
    p.add_argument("--broad-regex", required=True, help="regex rộng để lấy ứng viên")
    p.add_argument("--recheck-thesis-ids", default="", help="thesis_id cần xem lại, phân tách bằng dấu phẩy")
    p.add_argument("--strong-only", action="store_true", help="chỉ giữ ứng viên khớp strong-regex (bỏ ứng viên chỉ giống về chuỗi ký tự)")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--min-sim", type=float, default=0.25)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    t = pd.read_csv(a.thesis, encoding="utf-8-sig")
    g = pd.read_csv(a.gold, encoding="utf-8-sig")
    col = "technical_topics" if a.label_type == "technical_topic" else "domains"
    pos = g[g[col].map(lambda v: a.label_name in json.loads(v))].title
    seen_titles = set(g.title.str.lower().str.strip())
    seen_ids = set()
    for f in glob.glob(a.prior_queues):
        seen_ids |= set(pd.read_csv(f, encoding="utf-8-sig").thesis_id)
    pool = t[~t.title.str.lower().str.strip().isin(seen_titles) & ~t.thesis_id.isin(seen_ids)].copy()

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit(t.title)
    pool["sim"] = (vec.transform(pool.title) @ vec.transform(pos).T).toarray().max(1)
    low = pool.title.str.lower()
    pool["strong"] = low.str.contains(a.strong_regex, regex=True)
    pool["broad"] = low.str.contains(a.broad_regex, regex=True)
    sel = pool.strong if a.strong_only else (pool.broad | (pool.sim >= a.min_sim))
    c = pool[sel].sort_values(["strong", "sim"], ascending=False).head(a.top)

    rows = []
    for x in c.itertuples():
        rows.append(dict(label_type=a.label_type, label_id=a.label_id, label_name=a.label_name,
                         current_gold_support=len(pos), thesis_id=x.thesis_id, title=x.title, source=x.source,
                         keyword_score=int(x.strong), current_decision="", decision="", group="new_candidate"))
    # xem lại nhãn đã gán
    rid = [int(i) for i in a.recheck_thesis_ids.split(",") if i.strip()]
    titles_pos = set(pos.str.lower().str.strip())
    for x in t[t.thesis_id.isin(rid)].itertuples():
        cur = "yes" if x.title.lower().strip() in titles_pos else "no"
        rows.append(dict(label_type=a.label_type, label_id=a.label_id, label_name=a.label_name,
                         current_gold_support=len(pos), thesis_id=x.thesis_id, title=x.title, source=x.source,
                         keyword_score=0, current_decision=cur, decision="", group="recheck"))
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(out.group.value_counts().to_dict(), "->", a.out)


if __name__ == "__main__":
    main()
