"""Dựng dữ liệu train cho từng nhãn, có che (mask) nhãn chưa được kiểm tra.

Quy tắc dùng mẫu cho nhãn L:
  - bản ghi 'all' (Gold gốc): dùng. Âm là 'verified' nếu L thuộc taxonomy cũ, ngược lại 'assumed'
    (người gán nhãn gốc chưa từng xét nhãn mới -> chỉ là giả định đóng).
  - bản ghi annotated_partial: chỉ dùng nếu L nằm trong verified_labels.
  - gold_verified_negatives: ví dụ âm đã kiểm chứng cho đúng nhãn đó.
"""
import json
import re
import unicodedata
import pandas as pd


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s)).lower()
    return re.sub(r"\s+", " ", s).strip()


def load_gold(path):
    g = pd.read_csv(path, encoding="utf-8-sig")
    g["tt"] = g.technical_topics.map(json.loads)
    g["dm"] = g.domains.map(json.loads)
    g["verified"] = g.verified_labels.map(lambda v: None if v == "all" else set(json.loads(v)))
    return g


def covered_names(label_map, repo, id_col, name_col):
    """Nhãn mới mà người gán nhãn Gold gốc (taxonomy cũ) đã thực sự xét."""
    ids = set(label_map.new_id)
    return set(repo[repo[id_col].isin(ids)][name_col])


def eligible_labels(report, kind):
    r = report[(report.type == kind) & (report.training_eligible)]
    return r.label.tolist()


def build_label_frame(gold, negatives, label, kind, covered):
    col = "tt" if kind == "technical_topic" else "dm"
    rows = []
    for r in gold.itertuples():
        pos = label in getattr(r, col)
        if r.verified is None:
            prov = "verified" if (pos or label in covered) else "assumed"
            rows.append((r.title, int(pos), prov, "full"))
        elif label in r.verified:
            rows.append((r.title, int(pos), "verified", "partial"))
    neg = negatives[(negatives.label_type == kind) & (negatives.label_name == label)]
    for r in neg.itertuples():
        rows.append((r.title, 0, "verified", "negative_only"))
    df = pd.DataFrame(rows, columns=["title", "y", "provenance", "origin"])
    df["text"] = df.title.map(norm_text)
    return df.drop_duplicates("text").reset_index(drop=True)
