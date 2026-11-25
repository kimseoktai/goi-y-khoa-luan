"""Lớp dữ liệu của backend (chỉ ĐỌC): nạp các CSV/JSON đã xử lý một lần, embedding nạp lười.

Chưa dùng CSDL quan hệ: dữ liệu là file phiên bản hóa trong data/processed và data/repository. Khi cần ghi (người dùng, lịch sử đề xuất)
thì thêm CSDL ở đây mà không đổi service/route. Backend không sửa dữ liệu gốc và không huấn luyện mô hình.
"""
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

from backend.database.sources import resolve_jobs
from backend.errors import Unavailable
from ml import config as C
from ml.embedding.embedder import Embedder, model_tag
from ml.matching import matcher as M
from ml.novelty import novelty as N
from ml.recommendation import pipeline as P
from ml.recommendation import recommender as R

log = logging.getLogger("backend.store")
MAX_FILL = 300                                         # thiếu tối đa bấy nhiêu id thì mã hóa bù, nhiều hơn thì bắt build lại
JOB_CHARS = 1500                                       # phải bằng --job-chars của build_embeddings.py


def read_csv(p, required=True):
    p = Path(p)
    if not p.exists():
        if required:
            raise FileNotFoundError(f"thiếu dữ liệu bắt buộc: {p}")
        return None
    return pd.read_csv(p, encoding="utf-8-sig")


class DataStore:
    def __init__(self, root=None, embedding_model=None, embedding_backend=None, jobs_source="auto"):
        self.root = Path(root or C.ROOT)
        self.embedding_model = embedding_model or C.DEFAULT_EMBED_MODEL
        self.embedding_backend = embedding_backend or "st"
        r = self.root
        src = resolve_jobs(r, jobs_source)
        self.jobs_source, self.jobs_embed_name = src["source"], src["embed_name"]
        self.jobs = read_csv(src["jobs_path"]).reset_index(drop=True)
        self.thesis = read_csv(r / "data/processed/thesis/thesis_processed.csv").reset_index(drop=True)
        self.topics = read_csv(r / "data/repository/technical_topics.csv")
        self.domains = read_csv(r / "data/repository/domains.csv")
        self.skill_map = R.build_skill_map(read_csv(r / "data/repository/skill_topic_map.csv"))
        mk = src["market_dir"]
        self.market = {n: read_csv(mk / f"{n}.csv", required=False) for n in
                       ["demand_topics", "demand_domains", "demand_skills", "demand_roles", "demand_technologies",
                        "demand_topic_domain_pairs", "supply_vs_demand_topics"]}
        self.market_summary = json.load(open(mk / "market_summary.json", encoding="utf-8")) if (mk / "market_summary.json").exists() else {}
        self.market_ctx = P.market_context(mk)
        th = r / "data/processed/novelty/thresholds.json"
        self.thresholds = json.load(open(th, encoding="utf-8")) if th.exists() else None
        # ép kiểu JSON một lần để service không phải parse lại
        for df, cols in ((self.jobs, ["technical_topics", "technical_topic_scores", "topic_evidence", "domains", "domain_scores", "domain_evidence", "skills", "technologies", "competencies"]),
                         (self.thesis, ["technical_topics", "technical_topic_scores", "domains", "domain_scores", "keywords", "advisors"])):
            for c in cols:
                if c in df:
                    df["_" + c] = df[c].map(lambda v: json.loads(v) if isinstance(v, str) and v.strip() else ([] if c in ("technical_topics", "domains", "skills", "technologies", "competencies", "keywords", "advisors") else {}))
        self.job_pos = {str(j): i for i, j in enumerate(self.jobs.job_id)}
        self.thesis_pos = {str(t): i for i, t in enumerate(self.thesis.thesis_id)}
        self._vec, self._embedder, self._cache = {}, None, {}
        self.filled = {}                                   # tên bộ embedding -> số id phải mã hóa bù (thiếu trong file)
        log.info("DataStore: %d job (nguồn %s), %d thesis, %d topic, %d domain, root=%s", len(self.jobs), self.jobs_source, len(self.thesis), len(self.topics), len(self.domains), self.root)

    # ---- embedding (nạp lười)
    @property
    def tag(self):
        return "hash256" if self.embedding_backend == "hash" else model_tag(self.embedding_model)

    def _load_vecs(self, name, ids, fill=None):
        if name in self._vec:
            return self._vec[name]
        d = self.root / "data/processed/embeddings"
        f, ix = d / f"{name}_{self.tag}.npy", d / f"{name}_{self.tag}_index.csv"
        if not f.exists() or not ix.exists():
            raise Unavailable(f"chưa có embedding '{name}' ({f.name}); chạy ml/embedding/build_embeddings.py trên máy có mạng rồi khởi động lại backend")
        have = [str(i) for i in read_csv(ix).id]
        pos = {i: k for k, i in enumerate(have)}
        miss = [i for i in ids if str(i) not in pos]
        E = M.l2norm(np.load(f))
        if not miss:
            self._vec[name] = E[[pos[str(i)] for i in ids]]
            return self._vec[name]
        # Thiếu vài id (thường là tin mới sau lần crawl): mã hóa bù ngay trong bộ nhớ thay vì tắt cả phần semantic.
        # Quá nhiều id thiếu thì bắt tạo lại embedding (mã hóa bù nhiều sẽ chậm và lệch so với bản build).
        if fill is None or len(miss) > MAX_FILL:
            raise Unavailable(f"embedding '{name}' thiếu {len(miss)} id (ví dụ {miss[:3]}); chạy: python scripts/build_site_data.py --embeddings")
        try:
            extra = np.asarray(fill(miss), dtype=np.float32)
        except Exception as e:                                                                   # chưa có mô hình/thư viện để mã hóa bù
            raise Unavailable(f"embedding '{name}' thiếu {len(miss)} id và không mã hóa bù được ({type(e).__name__}); chạy: python scripts/build_site_data.py --embeddings")
        got = {str(i): extra[k] for k, i in enumerate(miss)}
        self._vec[name] = np.stack([E[pos[str(i)]] if str(i) in pos else got[str(i)] for i in ids])
        self.filled[name] = len(miss)
        return self._vec[name]

    def _job_texts(self, miss):
        """Cùng công thức với ml/embedding/build_embeddings.py: tên vị trí + kỹ năng + 1500 ký tự mô tả."""
        want, J = {str(i) for i in miss}, self.jobs
        rows = {str(J.job_id.iloc[k]): k for k in range(len(J)) if str(J.job_id.iloc[k]) in want}
        return [f"{J.job_title.iloc[rows[str(i)]]}. Skills: {', '.join(map(str, J._skills.iloc[rows[str(i)]]))}. {str(J.description.iloc[rows[str(i)]])[:JOB_CHARS]}" for i in miss]

    def thesis_vectors(self):
        return self._load_vecs("thesis", self.thesis.thesis_id.tolist())

    def job_vectors(self):
        return self._load_vecs(self.jobs_embed_name, self.jobs.job_id.tolist(), fill=lambda miss: self.encode(self._job_texts(miss)))

    def has_embeddings(self):
        try:
            self.thesis_vectors(); self.job_vectors()
            return True
        except Unavailable:
            return False

    def encode(self, texts):
        if self._embedder is None:
            self._embedder = Embedder(self.embedding_model, self.embedding_backend).load_cache()
        return M.l2norm(np.asarray(self._embedder.encode(list(texts)), dtype=np.float32))

    # ---- các đại lượng dùng chung, tính một lần
    def cached(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def novelty_reference(self):
        """max_similarity của từng Thesis tới Thesis gần nhất khác (loại chính nó)."""
        return self.cached("nov_ref", lambda: N.self_neighbors(self.thesis_vectors(), k=1)[1][:, 0])

    def novelty_thresholds(self):
        if self.thresholds:
            return self.thresholds
        return self.cached("nov_th", lambda: N.provisional_thresholds(self.novelty_reference()))

    def thesis_label_sets(self):
        return self.cached("label_sets", lambda: [(set(t), set(d)) for t, d in zip(self.thesis._technical_topics, self.thesis._domains)])

    def versions(self):
        t, j = self.thesis, self.jobs
        first = lambda s: (s.dropna().iloc[0] if len(s.dropna()) else None)
        return dict(taxonomy_version=first(t.taxonomy_version), thesis_topic_model=first(t.topic_model_version),
                    thesis_domain_model=first(t.domain_model_version), thesis_dataset_version=first(t.dataset_version),
                    jobs_labeling_method=first(j.method), jobs_source=self.jobs_source, embedding_model=self.embedding_model, embedding_backend=self.embedding_backend,
                    novelty_thresholds_source=(self.thresholds or {}).get("source", "provisional_quantiles"),
                    default_matching_weights=M.DEFAULT_WEIGHTS, default_recommendation_weights=R.DEFAULT_WEIGHTS)
