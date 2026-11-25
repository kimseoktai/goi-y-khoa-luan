"""Phase 5 - phân tích lỗi: dự đoán out-of-fold cho từng nhãn, liệt kê FN/FP và nghi vấn nhãn sai.
Chỉ đọc dữ liệu/mô hình cấu hình, KHÔNG ghi đè mô hình đã lưu.
"""
import argparse, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                                   # noqa: E402
from ml.classification import dataset as D                   # noqa: E402
from ml.classification.train import cross_validate, KIND     # noqa: E402


def oof_pairs(kind_key, parts=("tfidf", "tfidf+kw"), embedder=None):
    kind, repo_path, id_col, name_col, _ = KIND[kind_key]
    gold = D.load_gold(C.GOLD)
    neg = pd.read_csv(C.GOLD_NEGATIVES, encoding="utf-8-sig")
    report = pd.read_csv(C.GOLD_REPORT, encoding="utf-8-sig")
    repo = pd.read_csv(repo_path, encoding="utf-8-sig")
    covered = D.covered_names(pd.read_csv(C.LABEL_MAP, encoding="utf-8-sig"), repo, id_col, name_col)
    frames = {l: D.build_label_frame(gold, neg, l, kind, covered) for l in D.eligible_labels(report, kind)}
    pairs, _ = cross_validate(frames, 5, dict(zip(repo[name_col], repo.keywords)), tuple(parts), embedder)
    return pairs, frames, covered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["topic", "domain"], required=True)
    ap.add_argument("--thr", type=float, required=True)
    ap.add_argument("--parts", default="tfidf,tfidf+kw")
    ap.add_argument("--embedding-model", default=None)
    ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    ap.add_argument("--tag", default="", help="hậu tố tên file kết quả")
    ap.add_argument("--out", default=str(C.EVAL_DIR))
    a = ap.parse_args()
    from ml.embedding.embedder import Embedder
    parts = [x.strip() for x in a.parts.split(",") if x.strip()]
    emb = Embedder(a.embedding_model, a.embedding_backend).load_cache() if "emb" in parts else None
    pairs, frames, covered = oof_pairs(a.kind, parts, emb)
    pairs["pred"] = pairs.p >= a.thr
    issues = []
    for r in pairs.itertuples():
        if r.y == 1 and r.p < 0.15:
            issues.append((a.kind, r.label, r.row, "gán dương nhưng mô hình rất không chắc (có thể gán nhầm)", round(r.p, 2)))
        if r.y == 0 and r.p > 0.85:
            why = "âm đã kiểm chứng nhưng mô hình rất chắc là dương" if r.prov == "verified" else "âm giả định, mô hình rất chắc là dương (có thể thiếu nhãn)"
            issues.append((a.kind, r.label, r.row, why, round(r.p, 2)))
    iss = pd.DataFrame(issues, columns=["kind", "label", "title_norm", "reason", "p"])
    Path(a.out).mkdir(parents=True, exist_ok=True)
    iss.to_csv(Path(a.out) / f"label_issues_{a.kind}{'_' + a.tag if a.tag else ''}.csv", index=False, encoding="utf-8-sig")
    pairs.to_csv(Path(a.out) / f"oof_predictions_{a.kind}{'_' + a.tag if a.tag else ''}.csv", index=False, encoding="utf-8-sig")
    print("nghi vấn nhãn:", len(iss), iss.reason.value_counts().to_dict())


if __name__ == "__main__":
    main()
