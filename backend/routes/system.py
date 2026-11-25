from fastapi import APIRouter, Depends

from backend.database.store import DataStore
from backend.routes.deps import get_store
from backend.services.common import jsonable

router = APIRouter(tags=["system"])


@router.get("/health")
def health(ds: DataStore = Depends(get_store)):
    """Kiểm tra sống và dữ liệu đã nạp. embeddings=false thì các endpoint cần semantic trả 503 kèm hướng dẫn."""
    return {"status": "ok", "jobs": len(ds.jobs), "jobs_source": ds.jobs_source, "thesis": len(ds.thesis), "topics": len(ds.topics), "domains": len(ds.domains),
            "embeddings": ds.has_embeddings(), "embeddings_filled": ds.filled, "novelty_thresholds": (ds.thresholds or {}).get("source", "provisional_quantiles")}


@router.get("/meta/versions")
def versions(ds: DataStore = Depends(get_store)):
    """Phiên bản taxonomy, mô hình, dữ liệu, trọng số mặc định và nguồn ngưỡng novelty."""
    return jsonable(ds.versions())
