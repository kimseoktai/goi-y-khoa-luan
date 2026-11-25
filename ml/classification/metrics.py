"""Metric multi-label tính trên các cặp (bản ghi, nhãn) đã được dùng/che đúng cách."""
import numpy as np
import pandas as pd


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def per_label(pairs: pd.DataFrame, thr: float) -> pd.DataFrame:
    rows = []
    for lab, g in pairs.groupby("label"):
        pred = g.p >= thr
        tp = int((pred & (g.y == 1)).sum()); fp = int((pred & (g.y == 0)).sum()); fn = int((~pred & (g.y == 1)).sum())
        p, r, f = prf(tp, fp, fn)
        rows.append(dict(label=lab, precision=round(p, 3), recall=round(r, 3), f1=round(f, 3),
                         support=int((g.y == 1).sum()), n_rows=len(g)))
    return pd.DataFrame(rows)


def overall(pairs: pd.DataFrame, thr: float) -> dict:
    pred = pairs.p >= thr
    y = pairs.y == 1
    tp = int((pred & y).sum()); fp = int((pred & ~y).sum()); fn = int((~pred & y).sum())
    mp, mr, mf = prf(tp, fp, fn)
    macro = per_label(pairs, thr).f1.mean()
    ham = float((pred != y).mean())
    jac = []
    for _, g in pairs.assign(pred=pred, yy=y).groupby("row"):
        inter = int((g.pred & g.yy).sum()); union = int((g.pred | g.yy).sum())
        jac.append(1.0 if union == 0 else inter / union)
    return dict(precision=round(mp, 4), recall=round(mr, 4), micro_f1=round(mf, 4), macro_f1=round(float(macro), 4),
                jaccard=round(float(np.mean(jac)), 4), hamming_loss=round(ham, 4), n_pairs=len(pairs))
