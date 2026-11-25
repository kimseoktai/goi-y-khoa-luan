"""Huấn luyện + đánh giá (5-fold CV) bộ phân loại Technical Topic hoặc Domain. Chỉ TRAIN, không predict.

Mỗi nhãn một mô hình nhị phân; mỗi nhãn chỉ dùng các bản ghi đã được kiểm tra cho nhãn đó (xem dataset.py).
Taxonomy đọc từ data/repository, nhãn đủ điều kiện đọc từ gold_label_report.csv.
"""
import argparse, json, logging, uuid
from datetime import date, datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                                  # noqa: E402
from ml.classification import dataset as D, metrics as M   # noqa: E402
from ml.classification.model import make_pipeline, DEFAULT_PARAMS, build_models as _bm  # noqa: E402
from ml.embedding.embedder import Embedder  # noqa: E402

log = logging.getLogger("train")
KIND = {"topic": ("technical_topic", C.TOPICS, "topic_id", "topic_name", "thesis_topic_clf"),
        "domain": ("domain", C.DOMAINS, "domain_id", "domain_name", "thesis_domain_clf")}


KW_WEIGHT = 2.0   # trọng số cờ từ khóa taxonomy (so sánh trong tune.py)


def build_models(label, kwmap, parts, embedder):
    return _bm(label, kwmap, KW_WEIGHT, parts, embedder)


def cross_validate(frames, folds, kwmap=None, parts=("tfidf", "tfidf+kw"), embedder=None):
    rows, skipped = [], []
    for lab, df in frames.items():
        npos = int(df.y.sum())
        if npos < folds or (len(df) - npos) < folds:
            skipped.append((lab, npos)); continue
        skf = StratifiedKFold(folds, shuffle=True, random_state=C.SEED)
        oof = np.zeros(len(df))
        for tr, te in skf.split(df.text, df.y):
            ms = [m.fit(df.text.iloc[tr], df.y.iloc[tr]) for m in build_models(lab, kwmap, parts, embedder)]
            oof[te] = np.mean([m.predict_proba(df.text.iloc[te])[:, 1] for m in ms], axis=0)
        rows.append(pd.DataFrame(dict(row=df.text, label=lab, y=df.y, p=oof, prov=df.provenance)))
    return pd.concat(rows, ignore_index=True), skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["topic", "domain"], required=True)
    ap.add_argument("--model-version", default="v1.1")
    ap.add_argument("--embedding-model", default=None, help="tên mô hình embedding (đã chạy build_embeddings); bỏ trống = không dùng")
    ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    ap.add_argument("--parts", default=None, help="thành phần blend, phân tách bằng dấu phẩy: tfidf,tfidf+kw,emb (mặc định suy ra từ các cờ khác)")
    ap.add_argument("--no-keywords", action="store_true", help="tắt cờ từ khóa (tái hiện v1.0)")
    ap.add_argument("--dataset-version", default="gold_v2.1")
    ap.add_argument("--taxonomy-version", default="taxonomy_v1.1")
    ap.add_argument("--folds", type=int, default=5)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    kind, repo_path, id_col, name_col, model_name = KIND[a.kind]

    gold = D.load_gold(C.GOLD)
    neg = pd.read_csv(C.GOLD_NEGATIVES, encoding="utf-8-sig")
    report = pd.read_csv(C.GOLD_REPORT, encoding="utf-8-sig")
    repo = pd.read_csv(repo_path, encoding="utf-8-sig")
    covered = D.covered_names(pd.read_csv(C.LABEL_MAP, encoding="utf-8-sig"), repo, id_col, name_col)
    labels = D.eligible_labels(report, kind)
    frames = {l: D.build_label_frame(gold, neg, l, kind, covered) for l in labels}
    log.info("%s: %d nhãn đủ điều kiện train", a.kind, len(labels))

    kwmap = None if a.no_keywords else dict(zip(repo[name_col], repo.keywords))
    parts = ["tfidf"] + ([] if a.no_keywords else ["tfidf+kw"])
    if a.embedding_model:
        parts.append("emb")
    if a.parts:
        parts = [x.strip() for x in a.parts.split(",") if x.strip()]
    if "tfidf+kw" in parts and a.no_keywords:
        raise SystemExit("--parts có tfidf+kw nhưng lại dùng --no-keywords")
    if "emb" in parts and not a.embedding_model:
        raise SystemExit("--parts có emb nhưng thiếu --embedding-model")
    embedder = None
    if "emb" in parts:
        embedder = Embedder(a.embedding_model, a.embedding_backend).load_cache()
        embedder.encode(pd.concat([f.text for f in frames.values()]).tolist(), allow_model=False)   # báo lỗi sớm nếu thiếu cache
    pairs, skipped = cross_validate(frames, a.folds, kwmap, tuple(parts), embedder)
    for lab, n in skipped:
        log.warning("bỏ qua %s (chỉ %d mẫu dương, ít hơn %d fold)", lab, n, a.folds)
    sweep = {round(t, 2): M.overall(pairs, t)["micro_f1"] for t in np.arange(0.30, 0.71, 0.05)}
    best = max(sweep, key=lambda t: (sweep[t], -abs(t - 0.5)))
    thr = best
    log.info("sweep micro-F1 theo ngưỡng toàn cục: %s -> chọn %.2f", sweep, thr)

    res = M.overall(pairs, thr)
    res_05 = M.overall(pairs, 0.5)
    ver = pairs[pairs.prov == "verified"]
    res_ver = M.overall(ver, thr)
    pl = M.per_label(pairs, thr)
    prov = pd.DataFrame([dict(label=l, n_pos=int(f.y.sum()), n_neg_verified=int(((f.y == 0) & (f.provenance == "verified")).sum()),
                              n_neg_assumed=int(((f.y == 0) & (f.provenance == "assumed")).sum())) for l, f in frames.items()])
    pl = pl.merge(prov, on="label", how="outer")
    pl["status"] = np.where(pl.f1.isna(), "not_evaluated", "evaluated")

    # huấn luyện lần cuối trên toàn bộ dữ liệu khả dụng của từng nhãn
    models = {l: [m.fit(f.text, f.y) for m in build_models(l, kwmap, tuple(parts), embedder)] for l, f in frames.items() if l not in {s[0] for s in skipped}}
    bundle = dict(kind=a.kind, model_name=model_name, model_version=a.model_version, dataset_version=a.dataset_version,
                  taxonomy_version=a.taxonomy_version, threshold=float(thr), params={**DEFAULT_PARAMS, "kw_weight": KW_WEIGHT if "tfidf+kw" in parts else None, "blend": len(parts) > 1, "parts": parts, "embedding_model": a.embedding_model}, labels=list(models),
                  trained_at=datetime.now().isoformat(timespec="seconds"), models=models)
    out_dir = C.MODEL_DIRS[a.kind]; out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{model_name}_{a.model_version}.joblib"
    joblib.dump(bundle, path)

    C.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    pl.to_csv(C.EVAL_DIR / f"per_label_{model_name}_{a.model_version}.csv", index=False, encoding="utf-8-sig")
    hist = C.EVAL_DIR / "evaluation_history.csv"
    row = dict(evaluation_id=uuid.uuid4().hex[:8], model_name=model_name, model_version=a.model_version,
               dataset_version=a.dataset_version, taxonomy_version=a.taxonomy_version, training_date=date.today().isoformat(),
               validation_method=f"{a.folds}-fold stratified CV theo từng nhãn", parameters=json.dumps({**DEFAULT_PARAMS, "threshold": thr, "kw_weight": KW_WEIGHT if "tfidf+kw" in parts else None, "blend": len(parts) > 1, "parts": parts, "embedding_model": a.embedding_model}),
               precision=res["precision"], recall=res["recall"], micro_f1=res["micro_f1"], macro_f1=res["macro_f1"],
               jaccard=res["jaccard"], hamming_loss=res["hamming_loss"], micro_f1_thr_0_5=res_05["micro_f1"],
               micro_f1_verified_only=res_ver["micro_f1"], dataset_size=len(gold), number_of_labels=len(models))
    old = pd.read_csv(hist, encoding="utf-8-sig") if hist.exists() else pd.DataFrame()
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(hist, index=False, encoding="utf-8-sig")
    print(json.dumps(row, ensure_ascii=False, indent=1))
    print(pl.sort_values("f1").to_string(index=False))
    log.info("đã lưu %s", path)


if __name__ == "__main__":
    main()
