"""Dự đoán bằng mô hình đã train (KHÔNG train lại). Đầu vào: danh sách title; đầu ra: nhãn + xác suất."""
import argparse, json, sys
import numpy as np
from pathlib import Path
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml import config as C                      # noqa: E402
from ml.classification.dataset import norm_text  # noqa: E402


def load_bundle(kind, version="v1.1"):
    name = {"topic": "thesis_topic_clf", "domain": "thesis_domain_clf"}[kind]
    return joblib.load(C.MODEL_DIRS[kind] / f"{name}_{version}.joblib")


def _compat(m, depth=0):
    """Mô hình lưu bằng scikit-learn >=1.8 không còn thuộc tính multi_class; bản 1.7 vẫn đọc nó khi predict_proba.
    Bổ sung mặc định "auto" để chạy được trên 1.7 (kết quả không đổi với bộ phân loại nhị phân)."""
    if m is None or depth > 4:
        return m
    if type(m).__name__ == "LogisticRegression" and not hasattr(m, "multi_class"):
        m.multi_class = "auto"
    subs = [st for _, st in getattr(m, "steps", [])] + [getattr(m, "clf_", None), getattr(m, "clf", None)]
    for sub in subs:
        if sub is not None and sub is not m:
            _compat(sub, depth + 1)
    return m


def predict(titles, bundle, top_k=None):
    # bundle dùng embedding: các thành phần EmbeddingClassifier giữ Embedder (cache + tên mô hình);
    # văn bản mới sẽ được encode bằng mô hình (cần sentence-transformers và mô hình đã tải).
    texts = [norm_text(t) for t in titles]
    def proba(ms):
        ms = ms if isinstance(ms, list) else [ms]          # tương thích bundle v1.0
        return np.mean([_compat(m).predict_proba(texts)[:, 1] for m in ms], axis=0)
    probs = {l: proba(ms) for l, ms in bundle["models"].items()}
    out = []
    for i in range(len(texts)):
        scored = sorted(((l, float(probs[l][i])) for l in probs), key=lambda x: -x[1])
        hit = [(l, round(p, 3)) for l, p in scored if p >= bundle["threshold"]]
        out.append(dict(labels=hit[:top_k] if top_k else hit,
                        top_candidates=[(l, round(p, 3)) for l, p in scored[:3]]))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("titles", nargs="+")
    ap.add_argument("--version", default="v1.1")
    a = ap.parse_args()
    tb, db = load_bundle("topic", a.version), load_bundle("domain", a.version)
    for t, rt, rd in zip(a.titles, predict(a.titles, tb), predict(a.titles, db)):
        print(json.dumps(dict(title=t, technical_topics=rt["labels"], domains=rd["labels"],
                              confidence_note="xác suất chưa được hiệu chuẩn"), ensure_ascii=False))
