"""Phase 11 - đánh giá đề xuất và tinh chỉnh trọng số từ mẫu chấm tay.
  python ml\\recommendation\\tune_rec_weights.py --labeled data\\evaluation\\recommendation_eval_sample.csv
Báo cáo: Top-1/3/5 (precision chặt = chỉ Relevant, nới = Relevant+Partially; hit@k), nDCG@5, tỉ lệ Novel do người chấm,
AUC của novelty_score so với nhãn Novel, đa dạng (diversity) của Top-5. Mọi chỉ số tính TRONG BỂ đã chấm, không phải toàn bộ ứng viên.
Chỉ khuyên đổi trọng số khi nDCG@5 leave-one-job-out tăng >= 0.02 so với mặc định.
"""
import argparse, itertools, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                      # noqa: E402
from ml.recommendation import recommender as R  # noqa: E402


def read_any(p):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(p, encoding=enc)
        except UnicodeDecodeError:
            continue


def auc(score, label):
    s, y = np.asarray(score, float), np.asarray(label, int)
    ok = ~np.isnan(s); s, y = s[ok], y[ok]
    if y.sum() == 0 or y.sum() == len(y):
        return np.nan
    r = pd.Series(s).rank().values
    return float((r[y == 1].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (len(y) - y.sum())))


def grid(comps, step=0.1):
    n = int(round(1 / step)); out = []
    for combo in itertools.product(range(n + 1), repeat=len(comps)):
        if sum(combo) == n:
            out.append({c: v * step for c, v in zip(comps, combo)})
    return out


def job_metrics(g, w, k=5):
    s = np.nan_to_num(R.score(g, w), nan=-1.0)
    gains = g.gain.values.astype(float); order = np.argsort(-s, kind="stable")
    m = dict(ndcg5=R.ndcg_at_k(s, gains, 5))
    for kk in (1, 3, 5):
        top = gains[order[:kk]]
        m[f"p@{kk}_strict"] = float((top == 2).mean()); m[f"p@{kk}_lenient"] = float((top >= 1).mean()); m[f"hit@{kk}"] = float((top == 2).any())
    if "novel_flag" in g:
        m["novel_rate@5"] = float(g.novel_flag.values[order[:5]].mean())
    m["diversity@5"] = R.diversity([set(g.topics.values[i]) | set(g.domains.values[i]) for i in order[:5]])
    return m


def evaluate(df, w):
    rows = [job_metrics(g, w) for _, g in df.groupby("job_id")]
    return pd.DataFrame(rows).mean(numeric_only=True)


def loo(df, weights):
    res = []
    for j in df.job_id.unique():
        tr, te = df[df.job_id != j], df[df.job_id == j]
        best = max(weights, key=lambda w: evaluate(tr, w)["ndcg5"])
        res.append(job_metrics(te, best)["ndcg5"])
    return float(np.nanmean(res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeled", required=True)
    ap.add_argument("--key", default=str(C.EVAL_DIR / "recommendation_eval_key.csv"))
    ap.add_argument("--novelty-mode", default="label", choices=["label", "semantic"], help="label: c_novelty = 1/(1+combo_support) tính lại từ key (mặc định); semantic: dùng c_novelty trong key")
    ap.add_argument("--out", default=str(C.EVAL_DIR / "recommendation_weight_tuning.csv"))
    a = ap.parse_args()
    lab, key = read_any(a.labeled), read_any(a.key)
    lab["gain"] = lab.relevance.fillna("").astype(str).str.strip().str.lower().map(R.GAIN)
    lab["novel_flag"] = lab.novel.fillna("").astype(str).str.strip().str.lower().map({"novel": 1, "not novel": 0})
    df = key.merge(lab[["rec_id", "gain", "novel_flag"]].dropna(subset=["gain"]), on="rec_id")
    df["topics"] = df.topics.fillna("").map(lambda s: tuple(x for x in s.split(" | ") if x))
    df["domains"] = df.domains.fillna("").map(lambda s: tuple(x for x in s.split(" | ") if x))
    if a.novelty_mode == "label" and "combo_support" in df and df.combo_support.notna().all():
        df["c_novelty_semantic"] = df["c_novelty"]
        df["c_novelty"] = 1.0 / (1.0 + df.combo_support.astype(float))
        print("Novelty = 1/(1+combo_support) (mode label); novelty ngữ nghĩa cũ giữ để so sánh")
    comps = [c for c in R.COMPONENTS if f"c_{c}" in df and df[f"c_{c}"].notna().any()]
    print(f"hướng đã chấm={len(df)}, job={df.job_id.nunique()}, thành phần có dữ liệu={comps}")
    print("phân bố relevance:", lab.relevance.value_counts().to_dict(), "| novel:", lab.novel.value_counts().to_dict())
    base = {c: R.DEFAULT_WEIGHTS[c] if c in comps else 0.0 for c in R.COMPONENTS}
    print("\nChỉ số trong bể đã chấm (trung bình theo job):")
    refs = {"mặc định": base, **{f"chỉ {c}": {x: float(x == c) for x in R.COMPONENTS} for c in comps}}
    table = pd.DataFrame({n: evaluate(df, w) for n, w in refs.items()}).T
    print(table.round(3).to_string())
    if df.novel_flag.notna().any() and "novelty" in comps:
        d = df.dropna(subset=["novel_flag"])
        print(f"\nAUC của c_novelty đang dùng so với nhãn Novel của người chấm: {auc(d.c_novelty, d.novel_flag):.3f} (0.5 = ngẫu nhiên), n={len(d)}")
        if "c_novelty_semantic" in d:
            print(f"AUC của novelty ngữ nghĩa: {auc(d.c_novelty_semantic, d.novel_flag):.3f}")
        if "combo_support" in d:
            print(f"AUC của 1/(1+combo_support) so với nhãn Novel: {auc(1 / (1 + d.combo_support.astype(float)), d.novel_flag):.3f}")
    ws = grid(comps, 0.1)
    res = pd.DataFrame([dict(**w, ndcg5=round(evaluate(df, w)["ndcg5"], 4)) for w in ws]).sort_values("ndcg5", ascending=False)
    res.to_csv(a.out, index=False, encoding="utf-8-sig")
    cv = loo(df, ws); b = evaluate(df, base)["ndcg5"]
    print(f"\nnDCG@5 mặc định (trọng số chưa tune): {b:.3f}")
    print(f"nDCG@5 quy trình tinh chỉnh (leave-one-job-out): {cv:.3f}")
    print("top 3 trọng số trong mẫu:\n", res.head(3).to_string(index=False))
    print("KẾT LUẬN:", "có bằng chứng nên đổi trọng số" if cv - b >= 0.02 else "chưa đủ bằng chứng để đổi trọng số mặc định", f"(chênh {cv - b:+.3f})")


if __name__ == "__main__":
    main()
