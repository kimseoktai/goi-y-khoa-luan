"""Phase 10 - phát hiện mức độ MỚI (novelty) của một Thesis/hướng đề tài so với kho Thesis hiện có.

Hai tín hiệu tách riêng (không trộn thành một số để khỏi che giấu thông tin):
1) Ngữ nghĩa: max_similarity = cosine embedding lớn nhất tới Thesis đã có (loại chính nó khi đánh giá Thesis trong kho).
   novelty_score = tỉ lệ Thesis trong kho mà độ giống với láng giềng gần nhất của CHÍNH chúng cao hơn max_similarity của ứng viên
   (0 = giống hơn mọi Thesis đang có; 1 = xa kho hơn mọi Thesis đang có). Thang này là thực nghiệm, không hard-code.
2) Không gian nhãn: combo_support = số Thesis đã có đủ các Topic (và Domain nếu có) của ứng viên; 0 = tổ hợp chưa ai làm.
Ngưỡng Duplicate/Similar: tạm tính từ phân phối (provisional) rồi thay bằng ngưỡng hiệu chỉnh từ nhãn tay (fit_thresholds).
"""
import numpy as np

PROVISIONAL_QUANTILES = {"similar": 0.50, "duplicate": 0.95}   # chỉ là điểm khởi đầu, KHÔNG phải kết luận


def self_neighbors(E, k=5):
    """Láng giềng gần nhất trong cùng kho, loại chính nó theo CHỈ SỐ (không theo độ giống). E đã chuẩn hóa L2."""
    S = E @ E.T
    np.fill_diagonal(S, -np.inf)
    k = min(k, E.shape[0] - 1)
    idx = np.argsort(-S, axis=1, kind="stable")[:, :k]
    return idx, np.take_along_axis(S, idx, axis=1)


def query_neighbors(Q, E, k=5):
    S = Q @ E.T
    idx = np.argsort(-S, axis=1, kind="stable")[:, :k]
    return idx, np.take_along_axis(S, idx, axis=1)


def novelty_score(max_sim, ref):
    """ref: max_similarity của các Thesis trong kho (leave-self-out). Trả về tỉ lệ ref > max_sim."""
    ref = np.sort(np.asarray(ref, dtype=float))
    pos = np.searchsorted(ref, np.asarray(max_sim, dtype=float), side="right")
    return 1.0 - pos / len(ref)


def provisional_thresholds(ref):
    return {"similar": float(np.quantile(ref, PROVISIONAL_QUANTILES["similar"])),
            "duplicate": float(np.quantile(ref, PROVISIONAL_QUANTILES["duplicate"])),
            "source": "provisional_quantiles", "n_labeled": 0}


def status(max_sim, th):
    m = np.asarray(max_sim, dtype=float)
    td = th.get("duplicate")
    base = np.where(m >= th["similar"], "Similar", "Novel")
    return base if td is None else np.where(m >= td, "Duplicate", base)


def combo_support(label_sets, topics, domains=()):
    """label_sets: list[(set_topic, set_domain)] của kho. Đếm Thesis chứa đủ topics và domains yêu cầu."""
    topics, domains = set(topics), set(domains)
    return int(sum(1 for t, d in label_sets if topics <= t and domains <= d))


def fit_thresholds(sims, labels, min_duplicate=5):
    """Chọn (similar, duplicate) tối đa hóa balanced accuracy trên nhãn tay Duplicate/Similar/Different.
    Trả về dict ngưỡng + chỉ số. Ngưỡng nằm giữa hai giá trị liền kề để ổn định hơn."""
    sims = np.asarray(sims, dtype=float); labels = np.asarray(labels)
    cls = ["Different", "Similar", "Duplicate"]
    present = [c for c in cls if (labels == c).any()]
    if len(present) < 2:
        raise ValueError("cần ít nhất 2 loại nhãn để hiệu chỉnh ngưỡng")
    u = np.unique(sims)
    cand = np.concatenate([[u[0] - 1e-6], (u[:-1] + u[1:]) / 2, [u[-1] + 1e-6]])
    best = None
    for i, ts in enumerate(cand):
        for td in cand[i:]:
            pred = np.where(sims >= td, "Duplicate", np.where(sims >= ts, "Similar", "Different"))
            rec = [float((pred[labels == c] == c).mean()) for c in present]
            ba = float(np.mean(rec))
            key = (ba, -(td - ts))                      # hòa thì ưu tiên vùng Similar hẹp hơn
            if best is None or key > best[0]:
                best = (key, ts, td, ba, dict(zip(present, rec)))
    _, ts, td, ba, rec = best
    n_dup = int((labels == "Duplicate").sum())
    if n_dup < min_duplicate:                # quá ít ví dụ Duplicate: ngưỡng Duplicate sẽ chỉ là nhiễu
        return {"similar": float(fit_thresholds(sims[labels != "Duplicate"], np.where(labels[labels != "Duplicate"] == "Different", "Different", "Similar"), min_duplicate)["similar"]) if len(present) > 2 and (labels == "Different").any() else float(ts),
                "duplicate": None, "source": "fitted_from_manual_labels",
                "n_labeled": int(len(sims)), "class_counts": {c: int((labels == c).sum()) for c in present},
                "warning": f"chỉ có {n_dup} cặp Duplicate (<{min_duplicate}) nên chưa đặt ngưỡng Duplicate; chấm thêm cặp giống cao (--extra-sample)"}
    return {"similar": float(ts), "duplicate": float(td), "balanced_accuracy": ba, "recall_by_class": rec,
            "source": "fitted_from_manual_labels", "n_labeled": int(len(sims)),
            "class_counts": {c: int((labels == c).sum()) for c in present}}
