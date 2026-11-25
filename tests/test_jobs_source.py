"""Nguồn dữ liệu Jobs của backend: csv (bộ cũ) hay db (tạo từ CSDL), embedding tách tên để không ghép nhầm id."""
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from backend.database import sources
from backend.database.store import DataStore
from backend.services import role_service as R, student_service as S, catalog_service as CS
from tests.test_phase12 import make_root, raises


def _make_db_files(root):
    """Thêm bộ dữ liệu 'db' vào root: cùng nhãn như bộ csv nhưng job_id khác và có posted_at/source."""
    j = pd.read_csv(root / sources.CSV_JOBS, encoding="utf-8-sig")
    j["job_id"] = j.job_id + 5000
    j["source"] = ["topdev", "itviec", "careerviet"]
    j["posted_at"] = ["2026-10-01", "2026-10-15", None]
    j["status"] = "active"
    j.to_csv(root / sources.DB_JOBS, index=False, encoding="utf-8-sig")
    (root / sources.DB_MARKET).mkdir(parents=True)
    for f in (root / sources.CSV_MARKET).iterdir():
        shutil.copy(f, root / sources.DB_MARKET / f.name)
    (root / sources.DB_MARKET / "market_summary.json").write_text("{}", encoding="utf-8")


def test_resolve_jobs_rules():
    root = Path(tempfile.mkdtemp())
    assert sources.resolve_jobs(root, "auto")["source"] == "csv"                       # chưa có dữ liệu db
    assert raises(FileNotFoundError, sources.resolve_jobs, root, "db")
    assert raises(ValueError, sources.resolve_jobs, root, "abc")
    (root / "data/processed/jobs").mkdir(parents=True)
    (root / sources.DB_JOBS).write_text("x")
    assert sources.resolve_jobs(root, "auto")["source"] == "csv"                       # thiếu thư mục market_db thì không dùng db
    (root / sources.DB_MARKET).mkdir(parents=True)
    (root / sources.DB_MARKET / "market_summary.json").write_text("{}")
    r = sources.resolve_jobs(root, "auto")
    assert r["source"] == "db" and r["embed_name"] == "jobs_db" and sources.resolve_jobs(root, "csv")["embed_name"] == "jobs"


def test_store_uses_db_when_available_and_csv_otherwise():
    root = make_root(with_embeddings=True)
    ds = DataStore(root, "x", "hash")
    assert ds.jobs_source == "csv" and ds.jobs.job_id.tolist() == [1, 2, 3] and ds.has_embeddings()
    _make_db_files(root)
    ds = DataStore(root, "x", "hash")                                                   # auto -> db
    assert ds.jobs_source == "db" and ds.jobs.job_id.tolist() == [5001, 5002, 5003] and ds.versions()["jobs_source"] == "db"
    assert not ds.has_embeddings()                                                      # embedding 'jobs' cũ KHÔNG được dùng cho job_id mới
    assert DataStore(root, "x", "hash", "csv").jobs.job_id.tolist() == [1, 2, 3]


def test_db_job_embeddings_are_separate_and_checked():
    import numpy as np
    from ml.embedding.embedder import Embedder
    root = make_root(with_embeddings=True)
    _make_db_files(root)
    ds = DataStore(root, "x", "hash")
    emb = Embedder("x", "hash")
    d = root / "data/processed/embeddings"
    np.save(d / "jobs_db_hash256.npy", emb.encode((ds.jobs.job_title + ". " + ds.jobs.description).tolist()))
    pd.DataFrame(dict(id=ds.jobs.job_id)).to_csv(d / "jobs_db_hash256_index.csv", index=False)
    ds = DataStore(root, "x", "hash")
    assert ds.has_embeddings() and ds.job_vectors().shape[0] == 3


def test_missing_job_embeddings_are_filled_in_memory():
    import numpy as np
    from backend.database import store as ST
    from ml.embedding.embedder import Embedder
    root = make_root(with_embeddings=True)
    _make_db_files(root)
    ds = DataStore(root, "x", "hash")
    emb = Embedder("x", "hash")
    text = lambda d, k: f"{d.jobs.job_title.iloc[k]}. Skills: {', '.join(d.jobs._skills.iloc[k])}. {str(d.jobs.description.iloc[k])[:1500]}"
    texts = [text(ds, k) for k in range(3)]
    d = root / "data/processed/embeddings"
    np.save(d / "jobs_db_hash256.npy", emb.encode(texts[:2]))                             # file embedding chỉ có 2 tin đầu (tin thứ 3 là tin mới)
    pd.DataFrame(dict(id=ds.jobs.job_id[:2])).to_csv(d / "jobs_db_hash256_index.csv", index=False)
    ds = DataStore(root, "x", "hash")
    V = ds.job_vectors()
    assert ds.has_embeddings() and V.shape[0] == 3 and ds.filled == {"jobs_db": 1}
    assert np.allclose(V[2], emb.encode(texts[2:3])[0], atol=1e-5)                        # tin thiếu được mã hóa bằng đúng công thức của bản build
    assert np.allclose(np.linalg.norm(V, axis=1), 1.0, atol=1e-4)
    old = ST.MAX_FILL
    try:
        ST.MAX_FILL = 0                                                                  # thiếu nhiều hơn mức cho phép: bắt build lại
        ds2 = DataStore(root, "x", "hash")
        assert not ds2.has_embeddings() and raises(Exception, ds2.job_vectors)
    finally:
        ST.MAX_FILL = old
    ds3 = DataStore(root, "x", "hash")
    ds3.encode = lambda t: (_ for _ in ()).throw(RuntimeError("không có mô hình"))      # không mã hóa bù được: vẫn báo thiếu, không lỗi 500
    assert not ds3.has_embeddings()


def test_jobs_of_role_has_dates_newest_first_and_csv_mode_has_none():
    R.MIN_SUPPORT, R.MIN_COMPANIES = 1, 1
    root = make_root(with_embeddings=False)
    old = DataStore(root, "x", "hash")
    it = S.jobs_of_role(old, "AI Engineer")["items"][0]
    assert it["posted_at"] is None and it["source"] is None                             # bộ csv không có ngày đăng
    _make_db_files(root)
    j = pd.read_csv(root / sources.DB_JOBS, encoding="utf-8-sig")
    j["job_title"] = "AI Engineer"                                                      # cả 3 tin cùng một công việc
    j.to_csv(root / sources.DB_JOBS, index=False, encoding="utf-8-sig")
    ds = DataStore(root, "x", "hash")
    items = S.jobs_of_role(ds, "AI Engineer")["items"]
    assert [x["posted_at"] for x in items] == ["2026-10-15", "2026-10-01", None]         # mới nhất trước, chưa rõ ngày xuống cuối
    assert [x["source"] for x in items] == ["itviec", "topdev", "careerviet"]
    g = CS.get_job(ds, 5001)
    assert g["posted_at"] == "2026-10-01" and g["source"] == "topdev" and g["status"] == "active"
