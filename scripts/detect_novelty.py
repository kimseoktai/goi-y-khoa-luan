"""Phase 10 - phát hiện novelty.

Chạy trên máy có embedding (đã tạo bằng ml/embedding/build_embeddings.py):
  1) Phân tích toàn kho + tạo mẫu hiệu chỉnh ngưỡng:
     python scripts\\detect_novelty.py --embedding-model intfloat/multilingual-e5-base
  2) Chấm novelty cho ý tưởng mới (CSV: candidate_id,title,topics,domains; nhiều nhãn cách nhau bằng |):
     python scripts\\detect_novelty.py --embedding-model intfloat/multilingual-e5-base --candidates ideas.csv
  3) Hoặc một tiêu đề: ... --query "Hệ thống phát hiện gian lận thẻ bằng GNN" --topics "AI/ML" --domains "Finance & Banking"
Ngưỡng: dùng data/processed/novelty/thresholds.json nếu có (hiệu chỉnh từ nhãn tay), nếu không dùng ngưỡng TẠM từ phân phối.
"""
import argparse, json, logging, sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                    # noqa: E402
from ml.embedding.embedder import Embedder, model_tag         # noqa: E402
from ml.matching import matcher as M                          # noqa: E402
from ml.novelty import novelty as N                           # noqa: E402

log = logging.getLogger("novelty")
OUT = C.ROOT / "data/processed/novelty"
rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")


def load_thesis_embeddings(thesis, model, backend):
    tag = "hash256" if backend == "hash" else model_tag(model)
    f, idx = C.EMBED_DIR / f"thesis_{tag}.npy", C.EMBED_DIR / f"thesis_{tag}_index.csv"
    if not f.exists() or not idx.exists():
        raise SystemExit(f"thiếu {f.name}; chạy ml/embedding/build_embeddings.py trước")
    E, ids = M.l2norm(np.load(f)), rd(idx).id.tolist()
    pos = {i: k for k, i in enumerate(ids)}
    miss = [i for i in thesis.thesis_id if i not in pos]
    if miss:
        raise SystemExit(f"{len(miss)} thesis_id không có embedding (ví dụ {miss[:3]}); tạo lại embedding")
    return E[[pos[i] for i in thesis.thesis_id]]


def sets_of(row_topics, row_domains):
    return set(json.loads(row_topics)), set(json.loads(row_domains))


def calibration_sample(thesis, E, idx, sims, n_bins=6, per_bin=10, seed=C.SEED):
    """Cặp Thesis-Thesis phân tầng theo độ giống (láng giềng hạng 1..5) để người dùng chấm Duplicate/Similar/Different.
    Độ giống được ẩn trong file chấm (nằm ở file key) để nhãn không bị ảnh hưởng."""
    rng = np.random.default_rng(seed)
    pairs = {(min(i, int(j)), max(i, int(j))): float(s) for i in range(len(idx)) for j, s in zip(idx[i], sims[i])}
    keys = list(pairs); v = np.array([pairs[k] for k in keys])
    edges = np.quantile(v, np.linspace(0, 1, n_bins + 1)); edges[-1] += 1e-9
    rows = []
    for b in range(n_bins):
        pool = [k for k, s in zip(keys, v) if edges[b] <= s < edges[b + 1]]
        for k in rng.choice(len(pool), size=min(per_bin, len(pool)), replace=False):
            rows.append(pool[k])
    rng.shuffle(rows)
    lab, key = [], []
    for n, (a, b) in enumerate(rows, 1):
        pid = f"N{n:03d}"
        lab.append(dict(pair_id=pid, thesis_id_a=thesis.thesis_id[a], title_a=thesis.title[a],
                        thesis_id_b=thesis.thesis_id[b], title_b=thesis.title[b], label="", note=""))
        key.append(dict(pair_id=pid, similarity=round(pairs[(a, b)], 4)))
    return pd.DataFrame(lab), pd.DataFrame(key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thesis", default=str(C.ROOT / "data/processed/thesis/thesis_processed.csv"))
    ap.add_argument("--embedding-model", default=C.DEFAULT_EMBED_MODEL)
    ap.add_argument("--embedding-backend", default="st", choices=["st", "hash"])
    ap.add_argument("--thresholds", default=str(OUT / "thresholds.json"))
    ap.add_argument("--candidates"); ap.add_argument("--query"); ap.add_argument("--topics", default=""); ap.add_argument("--domains", default="")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--extra-sample", action="store_true", help="tạo thêm 40 cặp giống cao (top 10%%) để chấm bổ sung nhãn Duplicate")
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    thesis = rd(a.thesis).reset_index(drop=True)
    E = load_thesis_embeddings(thesis, a.embedding_model, a.embedding_backend)
    idx, sims = N.self_neighbors(E, k=5)
    ref = sims[:, 0]
    if Path(a.thresholds).exists():
        th = json.load(open(a.thresholds, encoding="utf-8")); log.info("dùng ngưỡng đã hiệu chỉnh: %s", a.thresholds)
    else:
        th = N.provisional_thresholds(ref)
        log.warning("CHƯA có thresholds.json: dùng ngưỡng TẠM từ phân phối (similar=%.3f, duplicate=%.3f). Hãy chấm mẫu hiệu chỉnh rồi chạy calibrate_novelty.py", th["similar"], th["duplicate"])

    if a.extra_sample:
        done = set()
        sp0 = out / "novelty_calibration_sample.csv"
        if sp0.exists():
            q = rd(sp0); done = {tuple(sorted(p)) for p in zip(q.thesis_id_a, q.thesis_id_b)}
        pos = {t: i for i, t in enumerate(thesis.thesis_id)}
        pairs = {}
        for i in range(len(idx)):
            for j, s_ in zip(idx[i], sims[i]):
                pairs[(min(i, int(j)), max(i, int(j)))] = float(s_)
        cut = np.quantile(list(pairs.values()), 0.90)
        pool = [k for k, v in pairs.items() if v >= cut and tuple(sorted((int(thesis.thesis_id[k[0]]), int(thesis.thesis_id[k[1]])))) not in done]
        rng = np.random.default_rng(C.SEED + 1)
        pick = [pool[i] for i in rng.choice(len(pool), size=min(40, len(pool)), replace=False)]
        lab = pd.DataFrame([dict(pair_id=f"X{n:03d}", thesis_id_a=thesis.thesis_id[x], title_a=thesis.title[x], thesis_id_b=thesis.thesis_id[y], title_b=thesis.title[y], label="", note="") for n, (x, y) in enumerate(pick, 1)])
        key = pd.DataFrame([dict(pair_id=f"X{n:03d}", similarity=round(pairs[k], 4)) for n, k in enumerate(pick, 1)])
        lab.to_csv(out / "novelty_calibration_extra_sample.csv", index=False, encoding="utf-8-sig"); key.to_csv(out / "novelty_calibration_extra_key.csv", index=False, encoding="utf-8-sig")
        print(f"đã tạo {len(lab)} cặp giống cao (similarity >= {cut:.4f}) trong {out}"); return

    if a.candidates or a.query:
        if a.candidates:
            cand = rd(a.candidates)
        else:
            cand = pd.DataFrame([dict(candidate_id="q1", title=a.query, topics=a.topics, domains=a.domains)])
        cand = cand.fillna("")
        emb = Embedder(a.embedding_model, a.embedding_backend).load_cache()
        Q = M.l2norm(emb.encode(cand.title.tolist()))
        qi, qs = N.query_neighbors(Q, E, k=a.top_k)
        labels = [sets_of(t, d) for t, d in zip(thesis.technical_topics, thesis.domains)]
        sp = lambda s: [x.strip() for x in str(s).split("|") if x.strip()]
        rows = []
        for r, c in cand.iterrows():
            ms = float(qs[r, 0]); tp, dm = sp(c.get("topics", "")), sp(c.get("domains", ""))
            rows.append(dict(
                candidate_id=c.candidate_id, title=c.title, max_similarity=round(ms, 4),
                nearest_thesis_id=int(thesis.thesis_id[qi[r, 0]]), nearest_thesis_title=thesis.title[qi[r, 0]],
                novelty_score=round(float(N.novelty_score(ms, ref)), 3), novelty_status=str(N.status(ms, th)),
                top_neighbors=json.dumps([[int(thesis.thesis_id[j]), round(float(s), 4)] for j, s in zip(qi[r], qs[r])]),
                combo_support=N.combo_support(labels, tp, dm) if tp else "",
                combo_note=("" if not tp else ("tổ hợp Topic+Domain chưa có Thesis nào" if N.combo_support(labels, tp, dm) == 0 else "")),
                threshold_source=th["source"]))
        res = pd.DataFrame(rows); res.to_csv(out / "candidate_novelty.csv", index=False, encoding="utf-8-sig")
        print(res[["candidate_id", "title", "max_similarity", "novelty_score", "novelty_status", "combo_support", "nearest_thesis_title"]].to_string(index=False))
        return

    st = N.status(ref, th)
    res = pd.DataFrame(dict(
        thesis_id=thesis.thesis_id, title=thesis.title, max_similarity=ref.round(4),
        nearest_thesis_id=thesis.thesis_id.values[idx[:, 0]], nearest_thesis_title=thesis.title.values[idx[:, 0]],
        novelty_score=N.novelty_score(ref, ref).round(3), novelty_status=st, threshold_source=th["source"]))
    res.to_csv(out / "thesis_novelty.csv", index=False, encoding="utf-8-sig")
    dup = res[res.novelty_status == "Duplicate"].copy()
    dup["pair"] = [tuple(sorted(p)) for p in zip(dup.thesis_id, dup.nearest_thesis_id)]
    dup.drop_duplicates("pair").drop(columns="pair").sort_values("max_similarity", ascending=False).to_csv(out / "near_duplicates.csv", index=False, encoding="utf-8-sig")
    lab, key = calibration_sample(thesis, E, idx, sims)
    lab.to_csv(out / "novelty_calibration_sample.csv", index=False, encoding="utf-8-sig"); key.to_csv(out / "novelty_calibration_key.csv", index=False, encoding="utf-8-sig")
    summ = dict(n_thesis=len(thesis), embedding_model=a.embedding_model, backend=a.embedding_backend, thresholds=th,
                nn_similarity_quantiles={f"p{int(q*100)}": round(float(np.quantile(ref, q)), 4) for q in (.05, .25, .5, .75, .9, .95, .99)},
                status_counts={k: int(v) for k, v in res.novelty_status.value_counts().items()}, created=datetime.now().isoformat(timespec="seconds"),
                note=("Ngưỡng tạm chỉ là phân vị của phân phối; cần nhãn tay (novelty_calibration_sample.csv) để hiệu chỉnh." if th["source"] == "provisional_quantiles" else "Ngưỡng hiệu chỉnh từ nhãn tay (in-sample, mẫu nhỏ); tỉ lệ Duplicate/Similar/Novel trên kho khác tỉ lệ trong mẫu vì mẫu được phân tầng."))
    json.dump(summ, open(out / "novelty_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
