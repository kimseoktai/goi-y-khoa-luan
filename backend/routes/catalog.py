from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.database.store import DataStore
from backend.routes.deps import get_store
from backend.services import catalog_service as S, advisor_service, dashboard_service, overview_service, trend_service

router = APIRouter(tags=["catalog"])


@router.get("/taxonomy/topics")
def topics(status: Optional[str] = Query(None, description="active | candidate | draft"), ds: DataStore = Depends(get_store)):
    return S.list_topics(ds, status)


@router.get("/taxonomy/domains")
def domains(status: Optional[str] = Query(None), ds: DataStore = Depends(get_store)):
    return S.list_domains(ds, status)


@router.get("/jobs")
def jobs(q: Optional[str] = None, topic: Optional[str] = None, domain: Optional[str] = None,
         role: Optional[str] = Query(None, description="khớp đúng job_title (vai trò), ví dụ 'AI/ML Engineer'"),
         limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0), ds: DataStore = Depends(get_store)):
    return S.list_jobs(ds, q, topic, domain, limit, offset, role)


@router.get("/jobs/{job_id}")
def job(job_id: str, ds: DataStore = Depends(get_store)):
    return S.get_job(ds, job_id)


@router.get("/thesis")
def thesis_list(q: Optional[str] = None, topic: Optional[str] = None, domain: Optional[str] = None, year: Optional[int] = None, source: Optional[str] = None,
                limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0), sort: str = Query("new", description="new | old | az"), ds: DataStore = Depends(get_store)):
    return S.list_thesis(ds, q, topic, domain, year, limit, offset, source, sort)


@router.get("/thesis/{thesis_id}")
def thesis_one(thesis_id: str, ds: DataStore = Depends(get_store)):
    return S.get_thesis(ds, thesis_id)


@router.get("/overview")
def overview(n_topics: int = Query(6, ge=1, le=20), n_domains: int = Query(5, ge=1, le=17), ds: DataStore = Depends(get_store)):
    """Tổng quan Job so với Thesis: tỷ lệ theo Topic/Domain kèm khoảng tin cậy, ô Topic x Domain, Thesis theo năm. Dùng cho trang chủ và màn so sánh."""
    return overview_service.overview(ds, n_topics, n_domains)


@router.get("/trends/thesis")
def thesis_trends(source: str = Query("neu", description="mã nguồn (trường), mặc định neu"), top: Optional[int] = Query(None, ge=1, le=50), ds: DataStore = Depends(get_store)):
    """Xu hướng khóa luận của một trường theo từng năm: số lượng, tỷ lệ theo chủ đề và lĩnh vực (khoảng tin cậy Wilson), chủ đề tăng hoặc giảm."""
    return trend_service.thesis_trends(ds, source, top)


@router.get("/market/summary")
def market_summary(ds: DataStore = Depends(get_store)):
    return S.market_summary(ds)


@router.get("/market/{table}")
def market_table(table: str, limit: int = Query(50, ge=1, le=500), only_supported: bool = False, ds: DataStore = Depends(get_store)):
    """table: demand_topics | demand_domains | demand_skills | demand_roles | demand_technologies | demand_topic_domain_pairs | supply_vs_demand_topics"""
    return S.market_table(ds, table, limit, only_supported)


@router.get("/advisors")
def advisors_list(q: Optional[str] = None, limit: int = Query(100, ge=1, le=500), ds: DataStore = Depends(get_store)):
    return advisor_service.list_advisors(ds, q, limit)


@router.get("/dashboard/thesis")
def dashboard_thesis(source: str = "neu", year_from: Optional[int] = None, year_to: Optional[int] = None, domain: Optional[str] = None,
                     topic: Optional[str] = None, view: str = Query("domain", description="domain | topic"), ds: DataStore = Depends(get_store)):
    return dashboard_service.dashboard(ds, source, year_from, year_to, domain, topic, view)
