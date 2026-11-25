from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.database.store import DataStore
from backend.routes.deps import get_store, llm_from, weights_from
from backend.services import ideas_service, matching_service, novelty_service, recommendation_service

router = APIRouter(tags=["analysis"])


class DirectionRequest(BaseModel):
    topics: List[str] = Field(..., min_length=1, description="Technical Topic của hướng đề tài (tên trong taxonomy)")
    domains: List[str] = Field(default_factory=list)
    n: int = Field(3, ge=1, le=5, description="Số tên đề tài muốn nhận (chỉ dùng cho /titles)")


class NoveltyRequest(BaseModel):
    title: str = Field(..., description="Tiêu đề/ý tưởng cần kiểm tra")
    topics: List[str] = Field(default_factory=list, description="Technical Topic (tên trong taxonomy), tùy chọn, để tính combo_support")
    domains: List[str] = Field(default_factory=list)
    top_k: int = Field(5, ge=1, le=20)


@router.get("/matching/jobs/{job_id}")
def match_job(job_id: str, top_k: int = Query(10, ge=1, le=100), use_semantic: bool = True,
              w_topic: Optional[float] = Query(None, ge=0), w_domain: Optional[float] = Query(None, ge=0),
              w_semantic: Optional[float] = Query(None, ge=0), ds: DataStore = Depends(get_store)):
    """Top Thesis phù hợp với một Job (Topic + Domain + Semantic), kèm giải thích."""
    w = weights_from(["topic", "domain", "semantic"], [w_topic, w_domain, w_semantic])
    return matching_service.match_job(ds, job_id, top_k, w, use_semantic)


@router.get("/thesis/{thesis_id}/similar")
def similar(thesis_id: str, top_k: int = Query(10, ge=1, le=100), ds: DataStore = Depends(get_store)):
    return matching_service.similar_thesis(ds, thesis_id, top_k)


@router.get("/thesis/{thesis_id}/novelty")
def thesis_novelty(thesis_id: str, top_k: int = Query(5, ge=1, le=20), ds: DataStore = Depends(get_store)):
    return novelty_service.check_thesis(ds, thesis_id, top_k)


@router.post("/novelty/check")
def novelty_check(body: NoveltyRequest, request: Request, ds: DataStore = Depends(get_store)):
    """Kiểm tra mức độ mới của một tiêu đề so với kho Thesis (Novel / Similar / Duplicate)."""
    return novelty_service.check_text(ds, body.title, body.topics, body.domains, body.top_k, request.app.state.settings.max_text_chars)


@router.get("/recommendations/jobs/{job_id}")
def recommend(job_id: str, top_k: int = Query(5, ge=1, le=20), mmr: float = Query(0.0, ge=0, le=1),
              novelty_mode: str = Query("label", pattern="^(label|semantic)$"),
              w_job_relevance: Optional[float] = Query(None, ge=0), w_topic: Optional[float] = Query(None, ge=0),
              w_domain: Optional[float] = Query(None, ge=0), w_semantic: Optional[float] = Query(None, ge=0),
              w_novelty: Optional[float] = Query(None, ge=0), ds: DataStore = Depends(get_store)):
    """Top Thesis Direction cho một Job, kèm điểm thành phần và giải thích (Job, kỹ năng, Topic, Domain, nhu cầu thị trường, Thesis gần nhất, novelty)."""
    w = weights_from(["job_relevance", "topic", "domain", "semantic", "novelty"], [w_job_relevance, w_topic, w_domain, w_semantic, w_novelty])
    return recommendation_service.recommend(ds, job_id, top_k, w, mmr, novelty_mode)


@router.post("/recommendations/jobs/{job_id}/related")
def direction_related(job_id: str, body: DirectionRequest, ds: DataStore = Depends(get_store)):
    """Công nghệ nên dùng (từ kỹ năng của Job) và luận văn đã có cùng chủ đề để tham khảo. Không cần gọi LLM."""
    return ideas_service.related(ds, job_id, body.topics, body.domains)


@router.post("/recommendations/jobs/{job_id}/titles")
def direction_titles(job_id: str, body: DirectionRequest, request: Request, ds: DataStore = Depends(get_store)):
    """Tên đề tài do LLM (Gemini) viết cho một hướng; mỗi tên được kiểm tra trùng với kho luận văn, tên trùng bị bỏ."""
    llm = llm_from(request)
    return ideas_service.titles(ds, llm, job_id, body.topics, body.domains, body.n)
