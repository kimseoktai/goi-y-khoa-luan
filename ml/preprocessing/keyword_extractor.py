"""Trích từ khóa cho title: cụm từ đặc trưng (TF-IDF, loại cụm quá phổ biến theo thống kê, không dùng stopword hard-code)."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class KeywordExtractor:
    def __init__(self, ngram_range=(1, 2), min_df=3, max_df=0.10):
        self.vec = TfidfVectorizer(ngram_range=ngram_range, min_df=min_df, max_df=max_df, sublinear_tf=True)

    def fit(self, texts):
        self.vec.fit(texts)
        self.terms = np.array(self.vec.get_feature_names_out())
        return self

    def top_terms(self, texts, k=3, exclude=None):
        X = self.vec.transform(texts)
        out = []
        exclude = exclude or [[] for _ in range(X.shape[0])]
        for i in range(X.shape[0]):
            row = X.getrow(i)
            if row.nnz == 0:
                out.append([]); continue
            idx = row.indices[np.argsort(-row.data)]
            chosen = []
            for j in idx:                                   # bỏ cụm nằm trong cụm đã chọn (tránh lặp)
                t = self.terms[j]
                if any(t in e or e in t for e in exclude[i]):      # đã có trong từ khóa taxonomy
                    continue
                if not any(t in c or c in t for c in chosen):
                    chosen.append(t)
                if len(chosen) == k:
                    break
            out.append(chosen)
        return out
