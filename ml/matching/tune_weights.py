"""Tinh chỉnh trọng số Matching bằng đánh giá thủ công (nDCG@5 trên các cặp đã được chấm, leave-one-job-out).
Chỉ khuyến nghị đổi trọng số khi cải thiện trên job bị giữ lại đủ rõ so với trọng số mặc định."""
import argparse, itertools, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                      # noqa: E402
from ml.matching import matcher as M            # noqa: E402

GAIN = {"relevant": 2, "partially relevant": 1, "partial": 1, "not relevant": 0, "no": 0, "yes": 2}


def read_csv_any(p):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(p, encoding=enc)
        except UnicodeDecodeError:
            continue


def pair_scores(df, w):
    s = w["topic"] * df.topic_match.values
    d = w["topic"] * np.ones(len(df))
    ok = df.domain_ok.values
    s = s + np.where(ok, w["domain"] * df.domain_match.values, 0); d = d + np.where(ok, w["domain"], 0)
    if "semantic_norm" in df and df.semantic_norm.notna().all() and w["semantic"] > 0:
        s = s + w["semantic"] * df.semantic_norm.values; d = d + w["semantic"]
    return s / d


def ndcg_at_k(scores, gains, k=5):
    order = np.argsort(-scores, kind="stable")[:k]
    disc = 1 / np.log2(np.arange(2, len(order) + 2))
    dcg = float((gains[order] * disc).sum())
    ideal = np.sort(gains)[::-1][:k]
    idcg = float((ideal * disc[:len(ideal)]).sum())
    return dcg / idcg if idcg > 0 else np.nan


def mean_ndcg(df, w, k=5):
    v = [ndcg_at_k(pair_scores(g, w), g.gain.values.astype(float), k) for _, g in df.groupby("job_id")]
    return float(np.nanmean(v)) if len(v) else float("nan")


def grid(step=0.1):
    n = int(round(1 / step)); out = []
    for a, b in itertools.product(range(n + 1), repeat=2):
        if a + b <= n:
            out.append({"topic": a * step, "domain": b * step, "semantic": (n - a - b) * step})
    return out


def loo(df, weights, k=5):
    jobs = df.job_id.unique(); res = []
    for j in jobs:
        tr, te = df[df.job_id != j], df[df.job_id == j]
        best = max(weights, key=lambda w: mean_ndcg(tr, w, k))
        res.append(ndcg_at_k(pair_scores(te, best), te.gain.values.astype(float), k))
    return float(np.nanmean(res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeled", required=True, help="matching_eval_sample.csv đã điền cột relevance")
    ap.add_argument("--key", default=str(C.EVAL_DIR / "matching_eval_key.csv"))
    ap.add_argument("--out", default=str(C.EVAL_DIR / "matching_weight_tuning.csv"))
    a = ap.parse_args()
    lab = read_csv_any(a.labeled)[["pair_id", "relevance"]]
    lab["gain"] = lab.relevance.fillna("").astype(str).str.strip().str.lower().map(GAIN)
    key = read_csv_any(a.key)
    df = key.merge(lab.dropna(subset=["gain"]), on="pair_id")
    has_sem = df.semantic_norm.notna().all()
    ws = grid(0.1) if has_sem else [w for w in grid(0.1) if w["semantic"] == 0]
    rows = [dict(w_topic=w["topic"], w_domain=w["domain"], w_semantic=w["semantic"], ndcg5=round(mean_ndcg(df, w), 4)) for w in ws]
    res = pd.DataFrame(rows).sort_values("ndcg5", ascending=False)
    res.to_csv(a.out, index=False, encoding="utf-8-sig")
    base = {"topic": 0.4, "domain": 0.2, "semantic": 0.4 if has_sem else 0.0}
    ref = {"mặc định": base, "chỉ topic": {"topic": 1, "domain": 0, "semantic": 0}}
    if has_sem:
        ref["chỉ semantic"] = {"topic": 0, "domain": 0, "semantic": 1}
    print(f"cặp đã chấm={len(df)}, job={df.job_id.nunique()}, có semantic={has_sem}")
    for n, w in ref.items():
        print(f"  nDCG@5 {n}: {mean_ndcg(df, w):.3f}")
    cv = loo(df, ws)
    print(f"  nDCG@5 quy trình tinh chỉnh (leave-one-job-out): {cv:.3f}")
    print("  top 3 trọng số trong mẫu:\n", res.head(3).to_string(index=False))
    gain = cv - mean_ndcg(df, base)
    print("KẾT LUẬN:", "có bằng chứng nên đổi trọng số" if gain >= 0.02 else "chưa đủ bằng chứng để đổi trọng số mặc định", f"(chênh {gain:+.3f})")


if __name__ == "__main__":
    main()
