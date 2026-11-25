"""Pipeline phân loại cho một nhãn (TF-IDF từ + ký tự [+ cờ từ khóa taxonomy] -> Logistic Regression)."""
import re
import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

DEFAULT_PARAMS = dict(C=4.0, class_weight="balanced", max_iter=2000)


def compile_keywords(kws):
    parts = [k.strip().lower() for k in str(kws).split("|") if k.strip()]
    return re.compile("|".join(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])" for k in parts))


class KeywordFlag(BaseEstimator, TransformerMixin):
    """1 cột: số từ khóa taxonomy khớp (chặn trên 2), nhân trọng số."""
    def __init__(self, keywords="", weight=1.0):
        self.keywords, self.weight = keywords, weight

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rx = compile_keywords(self.keywords)
        v = np.array([min(len(set(m.group(0) for m in rx.finditer(t))), 2) for t in X], dtype=float) * self.weight
        return sparse.csr_matrix(v.reshape(-1, 1))


def make_pipeline(params=None, keywords=None, kw_weight=1.0):
    p = {**DEFAULT_PARAMS, **(params or {})}
    parts = [
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
    ]
    if keywords:
        parts.append(("kw", KeywordFlag(keywords, kw_weight)))
    return Pipeline([("tfidf", FeatureUnion(parts)), ("clf", LogisticRegression(**p))])


class EmbeddingClassifier(BaseEstimator):
    """Logistic Regression trên embedding (văn bản -> vector qua Embedder, đã cache)."""
    def __init__(self, embedder=None, C=1.0):
        self.embedder, self.C = embedder, C

    def fit(self, texts, y):
        self.clf_ = LogisticRegression(C=self.C, class_weight="balanced", max_iter=2000)
        self.clf_.fit(self.embedder.encode(list(texts)), y)
        return self

    def predict_proba(self, texts):
        return self.clf_.predict_proba(self.embedder.encode(list(texts)))


def build_models(label, kwmap=None, kw_weight=2.0, parts=("tfidf", "tfidf+kw"), embedder=None, emb_C=1.0):
    """Danh sách mô hình thành phần; xác suất cuối = trung bình các thành phần."""
    out = []
    for part in parts:
        if part == "tfidf":
            out.append(make_pipeline())
        elif part == "tfidf+kw":
            out.append(make_pipeline(keywords=kwmap[label], kw_weight=kw_weight))
        elif part == "emb":
            out.append(EmbeddingClassifier(embedder, emb_C))
        else:
            raise ValueError(part)
    return out
