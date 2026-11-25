"""Áp mô hình đã train lên danh sách văn bản (KHÔNG train). Trả về bảng nhãn + điểm + cờ cần xem lại."""
import json
import pandas as pd

from ml.classification.predict import predict
from ml.classification.model import compile_keywords


def label_texts(titles, topic_bundle, domain_bundle, topics_repo, domains_repo, low_margin=0.15):
    pt, pd_ = predict(titles, topic_bundle), predict(titles, domain_bundle)
    kw = {r.topic_name: compile_keywords(r.keywords) for r in topics_repo.itertuples()}
    kw.update({r.domain_name: compile_keywords(r.keywords) for r in domains_repo.itertuples()})
    rows = []
    for t, a, b in zip(titles, pt, pd_):
        tl = t.lower()
        matched = []
        for lab, _ in a["labels"] + b["labels"]:
            for m in kw[lab].finditer(tl):
                if m.group(0) not in matched:
                    matched.append(m.group(0))
        flags = []
        if not a["labels"]:
            flags.append("no_technical_topic")
        elif max(p for _, p in a["labels"]) < topic_bundle["threshold"] + low_margin:
            flags.append("low_confidence_topic")
        if b["labels"] and max(p for _, p in b["labels"]) < domain_bundle["threshold"] + low_margin:
            flags.append("low_confidence_domain")
        rows.append(dict(
            technical_topics=json.dumps([l for l, _ in a["labels"]], ensure_ascii=False),
            technical_topic_scores=json.dumps(dict(a["labels"]), ensure_ascii=False),
            topic_confidence=max([p for _, p in a["labels"]], default=None),
            top_topic_candidates=json.dumps(a["top_candidates"], ensure_ascii=False),
            domains=json.dumps([l for l, _ in b["labels"]], ensure_ascii=False),
            domain_scores=json.dumps(dict(b["labels"]), ensure_ascii=False),
            domain_confidence=max([p for _, p in b["labels"]], default=None),
            taxonomy_keywords=json.dumps(matched, ensure_ascii=False),
            review_flag="|".join(flags)))
    return pd.DataFrame(rows)


def merge_gold_labels(out, gold):
    """Thesis nằm trong Gold: ưu tiên nhãn đã kiểm chứng của người gán (điểm 1.0).
    Bản ghi 'all': dùng đúng nhãn Gold. Bản ghi annotated_partial: nhãn Gold + dự đoán mô hình cho các nhãn chưa kiểm tra.
    Thesis ngoài Gold: giữ nguyên dự đoán mô hình. Cột label_source ghi rõ nguồn."""
    from ml.classification.dataset import norm_text
    g = gold.assign(key=gold.title.map(norm_text)).drop_duplicates("key").set_index("key")
    out = out.copy()
    out["label_source"] = "model"
    for i, r in out.iterrows():
        k = norm_text(r.title)
        if k not in g.index:
            continue
        gr = g.loc[k]
        gt, gd = json.loads(gr.technical_topics), json.loads(gr.domains)
        ver = None if gr.verified_labels == "all" else set(json.loads(gr.verified_labels))
        ts, ds = {l: 1.0 for l in gt}, {l: 1.0 for l in gd}
        if ver is not None:                                    # bổ sung dự đoán cho nhãn chưa được kiểm tra
            for l, p in json.loads(r.technical_topic_scores).items():
                if l not in ver and l not in ts: ts[l] = p
            for l, p in json.loads(r.domain_scores).items():
                if l not in ver and l not in ds: ds[l] = p
        out.at[i, "label_source"] = "gold" if ver is None else "gold+model"
        out.at[i, "technical_topics"] = json.dumps(list(ts), ensure_ascii=False)
        out.at[i, "technical_topic_scores"] = json.dumps(ts, ensure_ascii=False)
        out.at[i, "topic_confidence"] = max(ts.values(), default=None)
        out.at[i, "domains"] = json.dumps(list(ds), ensure_ascii=False)
        out.at[i, "domain_scores"] = json.dumps(ds, ensure_ascii=False)
        out.at[i, "domain_confidence"] = max(ds.values(), default=None)
        flags = ["no_technical_topic"] if not ts else []
        out.at[i, "review_flag"] = "|".join(flags)
    return out
