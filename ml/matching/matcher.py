"""Phase 9 - so khớp Job -> Thesis.

Matching Score = (w_topic*TopicMatch + w_domain*DomainMatch + w_sem*SemanticSimilarity) / (tổng trọng số của các thành phần CÓ DỮ LIỆU).
- TopicMatch: cosine giữa vector điểm Technical Topic của Job và Thesis.
- DomainMatch: cosine giữa vector điểm Domain; nếu Job hoặc Thesis không có Domain thì BỎ thành phần này (không phạt), trọng số được chuẩn hóa lại.
- SemanticSimilarity: cosine embedding Job-Thesis, quy về [0,1] bằng phân vị 5%-95% của toàn bộ cặp (lưu trong metadata).
Không dùng Skill của Job để suy ra Skill của Thesis. Trọng số mặc định chỉ là giá trị khởi đầu, chưa được coi là tối ưu.
"""
import json
import numpy as np

DEFAULT_WEIGHTS = {"topic": 0.4, "domain": 0.2, "semantic": 0.4}


def score_matrix(rows, names, col):
    idx = {n: i for i, n in enumerate(names)}
    M = np.zeros((len(rows), len(names)), dtype=np.float32)
    for r, v in enumerate(rows[col]):
        for k, s in json.loads(v).items():
            if k in idx:
                M[r, idx[k]] = float(s)
    return M


def l2norm(M):
    n = np.linalg.norm(M, axis=1, keepdims=True)
    n[n == 0] = 1
    return M / n


def cosine_matrix(A, B):
    return l2norm(A) @ l2norm(B).T


def semantic_normalizer(S, lo_pct=5, hi_pct=95):
    lo, hi = np.percentile(S, [lo_pct, hi_pct])
    return float(lo), float(hi)


def combine(topic, domain, domain_ok, sem, weights):
    """Các đầu vào cùng shape (n_job, n_thesis). domain_ok: mảng bool, sem có thể None."""
    num = weights["topic"] * topic
    den = np.full_like(topic, weights["topic"], dtype=np.float32)
    num = num + np.where(domain_ok, weights["domain"] * domain, 0.0)
    den = den + np.where(domain_ok, weights["domain"], 0.0)
    if sem is not None:
        num = num + weights["semantic"] * sem
        den = den + weights["semantic"]
    return num / den


def top_k(score, k):
    k = min(k, score.shape[1])
    part = np.argpartition(-score, k - 1, axis=1)[:, :k]
    order = np.take_along_axis(score, part, 1).argsort(1)[:, ::-1]
    return np.take_along_axis(part, order, 1)


def explain(job_title, shared_t, shared_d, sem_raw, domain_ok):
    p = [f"Job '{job_title}'"]
    p.append("cùng Technical Topic: " + (", ".join(shared_t) if shared_t else "không có"))
    if domain_ok:
        p.append("cùng Domain: " + (", ".join(shared_d) if shared_d else "không có"))
    else:
        p.append("Domain: không xét (Job hoặc Thesis chưa có Domain)")
    if sem_raw is not None:
        p.append(f"độ tương đồng ngữ nghĩa {sem_raw:.2f}")
    return "; ".join(p)
