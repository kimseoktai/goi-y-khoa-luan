"""Phase 5 - so sánh các cấu hình cải thiện bằng repeated stratified 5-fold CV (cùng fold cho mọi cấu hình).
Không lưu mô hình. Chỉ số 'human' = chỉ các nhãn mà người gán nhãn Gold gốc thực sự xét (ít vòng tròn hơn).
"""
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                                   # noqa: E402
from ml.classification import dataset as D, metrics as M     # noqa: E402
from ml.classification.model import build_models             # noqa: E402
from ml.embedding.embedder import Embedder                   # noqa: E402
from ml.classification.train import KIND                     # noqa: E402

CONFIGS = {   # parts: danh sách thành phần được lấy trung bình xác suất
    "v1.0 (tfidf)": dict(parts=("tfidf",)),
    "v1.1 (tfidf+kw)": dict(parts=("tfidf", "tfidf+kw")),
    "emb only": dict(parts=("emb",), emb_C=1.0),
    "emb only C10": dict(parts=("emb",), emb_C=10.0),
    "tfidf+emb": dict(parts=("tfidf", "emb"), emb_C=1.0),
    "v1.1+emb": dict(parts=("tfidf", "tfidf+kw", "emb"), emb_C=1.0),
    "v1.1+emb C10": dict(parts=("tfidf", "tfidf+kw", "emb"), emb_C=10.0),
    "kw+emb": dict(parts=("tfidf+kw", "emb"), emb_C=1.0),
}


def run(frames, kwmap, cfg, repeats, embedder=None, folds=5):
    rows = []
    for lab, df in frames.items():
        texts = df.text
        for rep in range(repeats):
            oof = np.zeros(len(df))
            for tr, te in StratifiedKFold(folds, shuffle=True, random_state=C.SEED + rep).split(texts, df.y):
                ms = [m.fit(texts.iloc[tr], df.y.iloc[tr])
                      for m in build_models(lab, kwmap, 2.0, cfg["parts"], embedder, cfg.get("emb_C", 1.0))]
                oof[te] = np.mean([m.predict_proba(texts.iloc[te])[:, 1] for m in ms], axis=0)
            rows.append(pd.DataFrame(dict(row=df.text, label=lab, y=df.y, p=oof, prov=df.provenance, rep=rep)))
    return pd.concat(rows, ignore_index=True)


def score(pairs, human_labels):
    out = {}
    for name, sub in [("all", pairs), ("human", pairs[pairs.label.isin(human_labels)])]:
        res = []
        for rep, g in sub.groupby("rep"):
            best = max(np.arange(0.3, 0.71, 0.05), key=lambda t: M.overall(g, t)["micro_f1"])
            r = M.overall(g, best); res.append((r["micro_f1"], r["macro_f1"], best))
        a = np.array(res)
        out[f"{name}_micro"], out[f"{name}_macro"] = a[:, 0].mean().round(4), a[:, 1].mean().round(4)
        out[f"{name}_macro_sd"] = a[:, 1].std().round(4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["topic", "domain"], required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--embedding-model", default=None)
    ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    a = ap.parse_args()
    kind, repo_path, id_col, name_col, _ = KIND[a.kind]
    gold = D.load_gold(C.GOLD); neg = pd.read_csv(C.GOLD_NEGATIVES, encoding="utf-8-sig")
    report = pd.read_csv(C.GOLD_REPORT, encoding="utf-8-sig"); repo = pd.read_csv(repo_path, encoding="utf-8-sig")
    covered = D.covered_names(pd.read_csv(C.LABEL_MAP, encoding="utf-8-sig"), repo, id_col, name_col)
    labels = D.eligible_labels(report, kind)
    frames = {l: D.build_label_frame(gold, neg, l, kind, covered) for l in labels}
    kwmap = dict(zip(repo[name_col], repo.keywords))
    human = [l for l in labels if l in covered]
    embedder = None
    if a.embedding_model:
        embedder = Embedder(a.embedding_model, a.embedding_backend).load_cache()
        embedder.encode(pd.concat([f.text for f in frames.values()]).tolist(), allow_model=False)
    rows = []
    for name, cfg in CONFIGS.items():
        if "emb" in cfg["parts"] and embedder is None:
            continue
        pairs = run(frames, kwmap, cfg, a.repeats, embedder)
        rows.append(dict(config=name, **score(pairs, human)))
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows); res.insert(0, "kind", a.kind)
    C.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    res.insert(1, "embedding_model", a.embedding_model or "")
    res.to_csv(C.EVAL_DIR / f"tuning_{a.kind}_{(a.embedding_model or 'noemb').replace('/', '_')}.csv", index=False, encoding="utf-8-sig")
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
