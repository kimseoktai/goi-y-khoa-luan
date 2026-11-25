"""Tính ma trận thành phần điểm Job x Thesis (dùng chung cho match, tạo mẫu đánh giá và tinh chỉnh trọng số)."""
import json
import logging
import numpy as np
import pandas as pd

from ml import config as C
from ml.embedding.embedder import model_tag
from ml.matching import matcher as M

log = logging.getLogger("matching")


def load_embeddings(jobs, thesis, model, backend):
    tag = "hash256" if backend == "hash" else model_tag(model)
    out = {}
    for name, df, idc in [("jobs", jobs, "job_id"), ("thesis", thesis, "thesis_id")]:
        f, idx = C.EMBED_DIR / f"{name}_{tag}.npy", C.EMBED_DIR / f"{name}_{tag}_index.csv"
        if not f.exists() or not idx.exists():
            raise SystemExit(f"thiếu {f.name}; chạy ml/embedding/build_embeddings.py trước")
        E = np.load(f)
        if E.shape[0] != len(df) or pd.read_csv(idx).id.tolist() != df[idc].tolist():
            raise SystemExit(f"embedding {name} không khớp thứ tự/số dòng; tạo lại embedding")
        out[name] = M.l2norm(E)
    return out["jobs"], out["thesis"]


def build_components(jobs, thesis, topics, domains, embedding_model=None, embedding_backend="st"):
    Jt = M.score_matrix(jobs, topics.topic_name.tolist(), "technical_topic_scores")
    Tt = M.score_matrix(thesis, topics.topic_name.tolist(), "technical_topic_scores")
    Jd = M.score_matrix(jobs, domains.domain_name.tolist(), "domain_scores")
    Td = M.score_matrix(thesis, domains.domain_name.tolist(), "domain_scores")
    comp = dict(topic=M.cosine_matrix(Jt, Tt), domain=M.cosine_matrix(Jd, Td),
                domain_ok=(Jd.sum(1) > 0)[:, None] & (Td.sum(1) > 0)[None, :], sem_raw=None, sem=None, lo=None, hi=None)
    if embedding_model:
        Ej, Et = load_embeddings(jobs, thesis, embedding_model, embedding_backend)
        S = Ej @ Et.T
        lo, hi = M.semantic_normalizer(S)
        comp.update(sem_raw=S, sem=np.clip((S - lo) / max(hi - lo, 1e-9), 0, 1), lo=lo, hi=hi)
    return comp
