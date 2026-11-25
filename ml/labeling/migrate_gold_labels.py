"""Phase 3 - re-label Gold theo taxonomy v1.0.

- technical_topics / domains: chỉ lấy từ ánh xạ xác định old_to_new_label_map.csv (chắc chắn).
- suggested_*: gợi ý từ keywords (CHƯA phải nhãn), kèm review_flag để người duyệt.
Không sửa file Gold gốc. Taxonomy đọc từ data/repository, không hard-code.
"""
import argparse, json, logging
from pathlib import Path
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from taxonomy_evidence import compile_kw, hits  # noqa: E402

log = logging.getLogger("migrate_gold")


def migrate(gold, tmap, topics, domains):
    gold = gold.copy()
    gold["old"] = gold.topics.map(json.loads)
    tname = dict(zip(topics.topic_id, topics.topic_name))
    dname = dict(zip(domains.domain_id, domains.domain_name))
    lookup = {r.old_label: (r.new_type, r.new_id, r.action) for r in tmap.itertuples()}
    unknown = {l for ls in gold.old for l in ls} - set(lookup)
    if unknown:
        raise ValueError(f"Nhãn cũ chưa có ánh xạ: {sorted(unknown)}")

    def split(ls):
        tp, dm = [], []
        for l in ls:
            typ, nid, _ = lookup[l]
            (tp if typ == "technical_topic" else dm).append(nid)
        return sorted(set(tp)), sorted(set(dm))
    sp = gold.old.map(split)
    gold["tt_ids"], gold["dm_ids"] = sp.map(lambda x: x[0]), sp.map(lambda x: x[1])

    # gợi ý từ keywords
    tx = {r.topic_id: compile_kw(r.keywords) for r in topics.itertuples() if r.status == "active"}
    dx = {r.domain_id: compile_kw(r.keywords) for r in domains.itertuples() if r.status == "active"}
    th = {k: hits(gold.title, rx) for k, rx in tx.items()}
    dh = {k: hits(gold.title, rx) for k, rx in dx.items()}
    gold["sug_tt"] = [[k for k in th if th[k].iloc[i] and k not in gold.tt_ids.iloc[i]] for i in range(len(gold))]
    gold["sug_dm"] = [[k for k in dh if dh[k].iloc[i] and k not in gold.dm_ids.iloc[i]] for i in range(len(gold))]

    def flag(r):
        f = []
        if not r.tt_ids: f.append("no_technical_topic")
        if any(lookup[l][2] == "split" for l in r.old): f.append("information_management_split")
        if r.sug_tt: f.append("suggested_topic")
        if r.sug_dm: f.append("suggested_domain")
        return "|".join(f)
    gold["review_flag"] = gold.apply(flag, axis=1)

    out = pd.DataFrame({
        "gold_id": gold.gold_id, "title": gold.title, "source": gold.source,
        "technical_topics": gold.tt_ids.map(lambda l: json.dumps([tname[i] for i in l], ensure_ascii=False)),
        "domains": gold.dm_ids.map(lambda l: json.dumps([dname[i] for i in l], ensure_ascii=False)),
        "suggested_topics": gold.sug_tt.map(lambda l: json.dumps([tname[i] for i in l], ensure_ascii=False)),
        "suggested_domains": gold.sug_dm.map(lambda l: json.dumps([dname[i] for i in l], ensure_ascii=False)),
        "review_flag": gold.review_flag,
        "label_status": gold.review_flag.map(lambda f: "needs_review" if ("no_technical_topic" in f or "split" in f) else "migrated"),
    })
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gold", default="data/processed/gold/gold_dataset_clean_v1.0.csv")
    p.add_argument("--map", default="data/processed/taxonomy/old_to_new_label_map.csv")
    p.add_argument("--topics", default="data/repository/technical_topics.csv")
    p.add_argument("--domains", default="data/repository/domains.csv")
    p.add_argument("--output", default="data/processed/gold/gold_dataset_clean.csv")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = migrate(pd.read_csv(a.gold, encoding="utf-8-sig"), pd.read_csv(a.map, encoding="utf-8-sig"),
                  pd.read_csv(a.topics, encoding="utf-8-sig"), pd.read_csv(a.domains, encoding="utf-8-sig"))
    out.to_csv(a.output, index=False, encoding="utf-8-sig")
    log.info("rows=%d needs_review=%d", len(out), (out.label_status == "needs_review").sum())


if __name__ == "__main__":
    main()
