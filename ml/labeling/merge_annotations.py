"""Phase 3 - gộp kết quả gán nhãn vào Gold (v2.0).

1) Chấp nhận suggested_topics/suggested_domains đã được duyệt -> gộp vào nhãn chính.
2) Gộp quyết định yes/no trong gold_annotation_done.csv thành bản ghi Gold mới.
   Bản ghi mới chỉ được kiểm tra với các nhãn trong hàng đợi, nên đánh dấu 'annotated_partial'
   và ghi `verified_labels` để lúc train có thể che (mask) các nhãn chưa kiểm tra.
Không sửa file gốc. Khoá ghép dùng thesis_id + label_id (không phụ thuộc encoding của title).
"""
import argparse, json, logging
import pandas as pd

log = logging.getLogger("merge_annotations")


def read_decisions(path):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python",
                               usecols=["label_type", "label_id", "thesis_id", "decision"])
        except UnicodeDecodeError:
            continue
    raise ValueError("Không đọc được encoding của file annotation")


def merge(gold, queue, done, thesis, topics, domains):
    gold = gold.copy()
    for c in ["technical_topics", "domains", "suggested_topics", "suggested_domains"]:
        gold[c] = gold[c].map(json.loads)
    # 1) chấp nhận gợi ý đã duyệt
    gold["added_topics"] = gold.suggested_topics
    gold["added_domains"] = gold.suggested_domains
    gold["technical_topics"] = [sorted(set(a) | set(b)) for a, b in zip(gold.technical_topics, gold.suggested_topics)]
    gold["domains"] = [sorted(set(a) | set(b)) for a, b in zip(gold.domains, gold.suggested_domains)]
    gold = gold.drop(columns=["suggested_topics", "suggested_domains"])
    gold["verified_labels"] = "all"
    gold["label_status"] = gold.technical_topics.map(lambda l: "labelled" if l else "needs_review")

    # 2) gộp annotation
    m = queue.merge(done, on=["label_type", "label_id", "thesis_id"], how="left", validate="one_to_one",
                    suffixes=("", "_done"))
    m["dec"] = m.decision_done.fillna("").astype(str).str.strip().str.lower()
    bad = set(m.dec) - {"yes", "no", ""}
    if bad:
        raise ValueError(f"Giá trị decision không hợp lệ: {bad}")
    m = m[m.dec != ""]
    th = thesis.set_index("thesis_id")
    next_id = int(gold.gold_id.max()) + 1
    new = []
    for tid, grp in m.groupby("thesis_id"):
        yes, no = grp[grp.dec == "yes"], grp[grp.dec == "no"]
        if tid not in th.index:
            raise ValueError(f"thesis_id không tồn tại: {tid}")
        if yes.empty:
            continue
        new.append(dict(
            gold_id=next_id, title=th.loc[tid, "title"], source=th.loc[tid, "source"],
            technical_topics=sorted(set(yes[yes.label_type == "technical_topic"].label_name)),
            domains=sorted(set(yes[yes.label_type == "domain"].label_name)),
            added_topics=[], added_domains=[],
            verified_labels=json.dumps(sorted(set(grp.label_name)), ensure_ascii=False),
            label_status="annotated_partial", review_flag="", thesis_id=int(tid)))
        next_id += 1
    new = pd.DataFrame(new)
    out = pd.concat([gold, new], ignore_index=True)
    out["thesis_id"] = out.thesis_id.astype("Int64")
    for c in ["technical_topics", "domains", "added_topics", "added_domains"]:
        out[c] = out[c].map(lambda l: json.dumps(l, ensure_ascii=False))
    cols = ["gold_id", "title", "source", "technical_topics", "domains", "added_topics", "added_domains",
            "label_status", "verified_labels", "review_flag", "thesis_id"]
    return out[cols]


def verified_negatives(queue, done, gold_titles, thesis):
    """Thesis chỉ có quyết định 'no' không thành bản ghi Gold, nhưng là ví dụ âm đã được kiểm chứng
    cho đúng nhãn đó. Lưu riêng để lúc train dùng (che các nhãn còn lại)."""
    m = queue.merge(done, on=["label_type", "label_id", "thesis_id"], how="left", suffixes=("", "_done"))
    m["dec"] = m.decision_done.fillna("").astype(str).str.strip().str.lower()
    yes_ids = set(m[m.dec == "yes"].thesis_id)
    neg = m[(m.dec == "no") & ~m.thesis_id.isin(yes_ids)]
    neg = neg.merge(thesis[["thesis_id", "title"]].rename(columns={"title": "title_ok"}), on="thesis_id")
    neg = neg[~neg.title_ok.str.lower().str.strip().isin(gold_titles)]
    return neg[["thesis_id", "title_ok", "label_type", "label_name"]].rename(columns={"title_ok": "title"})


def apply_overrides(out, ov):
    """Áp dụng quyết định thủ công (thêm nhãn) rồi cập nhật label_status."""
    out = out.copy()
    for r in ov.itertuples():
        i = out.index[out.gold_id == r.gold_id]
        if len(i) != 1:
            raise ValueError(f"gold_id không tồn tại: {r.gold_id}")
        col = "technical_topics" if r.label_type == "technical_topic" else "domains"
        cur = set(json.loads(out.at[i[0], col]))
        out.at[i[0], col] = json.dumps(sorted(cur | {r.label_name}), ensure_ascii=False)
    full = out.verified_labels == "all"
    has_topic = out.technical_topics.map(lambda v: len(json.loads(v)) > 0)
    out.loc[full & has_topic & (out.label_status == "needs_review"), "label_status"] = "labelled"
    return out


def apply_additions(out, add, thesis):
    """Thêm bản ghi Gold annotated_partial từ gold_additions.csv (thesis chưa có trong Gold).
    Mỗi dòng: thesis_id + nhãn dương duy nhất đã kiểm tra."""
    out = out.copy()
    th = thesis.set_index("thesis_id")
    titles = set(out.title.str.lower().str.strip())
    next_id = int(out.gold_id.max()) + 1
    rows = []
    for tid, grp in add.groupby("thesis_id"):
        if tid not in th.index:
            raise ValueError(f"thesis_id không tồn tại: {tid}")
        title = th.loc[tid, "title"]
        if title.lower().strip() in titles:
            raise ValueError(f"Thesis {tid} đã có trong Gold")
        tt = sorted(set(grp[grp.label_type == "technical_topic"].label_name))
        dm = sorted(set(grp[grp.label_type == "domain"].label_name))
        rows.append(dict(gold_id=next_id, title=title, source=th.loc[tid, "source"],
                         technical_topics=json.dumps(tt, ensure_ascii=False),
                         domains=json.dumps(dm, ensure_ascii=False),
                         added_topics="[]", added_domains="[]", label_status="annotated_partial",
                         verified_labels=json.dumps(sorted(set(grp.label_name)), ensure_ascii=False),
                         review_flag="", thesis_id=int(tid)))
        next_id += 1
    out = pd.concat([out, pd.DataFrame(rows)], ignore_index=True)
    out["thesis_id"] = out.thesis_id.astype("Int64")
    return out


def label_report(out, topics, domains, min_support=15):
    rows = []
    for kind, df, col, namec in [("technical_topic", topics, "technical_topics", "topic_name"),
                                 ("domain", domains, "domains", "domain_name")]:
        for name in df[namec]:
            has = out[col].map(lambda v: name in json.loads(v))
            full = int((has & (out.verified_labels == "all")).sum())
            part = int((has & (out.verified_labels != "all")).sum())
            status = df.loc[df[namec] == name, "status"].iloc[0]
            total = full + part
            rows.append(dict(type=kind, label=name, taxonomy_status=status, support_full=full,
                             support_partial=part, total=total,
                             training_eligible=bool(status == "active" and total >= min_support)))
    return pd.DataFrame(rows).sort_values(["type", "total"], ascending=[True, False])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gold", default="data/processed/gold/gold_dataset_clean_v2.0-draft.csv")
    p.add_argument("--queue", default="data/processed/gold/gold_annotation_queue.csv")
    p.add_argument("--done", required=True)
    p.add_argument("--thesis", required=True)
    p.add_argument("--topics", default="data/repository/technical_topics.csv")
    p.add_argument("--domains", default="data/repository/domains.csv")
    p.add_argument("--output", default="data/processed/gold/gold_dataset_clean.csv")
    p.add_argument("--overrides", default="data/processed/gold/manual_label_overrides.csv")
    p.add_argument("--min-support", type=int, default=15, help="số mẫu tối thiểu để nhãn đủ điều kiện train")
    p.add_argument("--additions", default="data/processed/gold/gold_additions.csv")
    p.add_argument("--negatives-out", default="data/processed/gold/gold_verified_negatives.csv")
    p.add_argument("--report", default="data/processed/gold/gold_label_report.csv")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rd = lambda f: pd.read_csv(f, encoding="utf-8-sig")
    topics, domains = rd(a.topics), rd(a.domains)
    out = merge(rd(a.gold), rd(a.queue), read_decisions(a.done), rd(a.thesis), topics, domains)
    out = apply_overrides(out, rd(a.overrides))
    out = apply_additions(out, rd(a.additions), rd(a.thesis))
    out.to_csv(a.output, index=False, encoding="utf-8-sig")
    neg = verified_negatives(rd(a.queue), read_decisions(a.done), set(out.title.str.lower().str.strip()), rd(a.thesis))
    neg.to_csv(a.negatives_out, index=False, encoding="utf-8-sig")
    log.info("verified negatives=%d", len(neg))
    rep = label_report(out, topics, domains, a.min_support)
    rep.to_csv(a.report, index=False, encoding="utf-8-sig")
    log.info("gold rows=%d (partial=%d)", len(out), (out.label_status == "annotated_partial").sum())
    print(rep.to_string(index=False))


if __name__ == "__main__":
    main()
