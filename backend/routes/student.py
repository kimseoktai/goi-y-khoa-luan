from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.database.store import DataStore
from backend.routes.deps import get_store, llm_from
from backend.services import advisor_service as AV, student_service as S

router = APIRouter(prefix="/student", tags=["student"])


class ProfileRequest(BaseModel):
    skills: List[str] = Field(default_factory=list, description="Kỹ năng bạn đã biết (tên trong danh mục kỹ năng)")


class IdeasRequest(BaseModel):
    roles: List[str] = Field(..., min_length=1, max_length=3, description="1 đến 3 nhóm công việc đã chọn")
    offset: int = Field(0, ge=0)
    n: int = Field(3, ge=1, le=6)


class IdeaTitleRequest(BaseModel):
    roles: List[str] = Field(..., min_length=1, max_length=3)
    topic: str
    avoid: List[str] = Field(default_factory=list, description="Tên đề tài đã hiện, để mô hình viết tên khác")
    n: int = Field(1, ge=1, le=3)


class AdvisorRequest(BaseModel):
    topic: Optional[str] = Field(None, description="Technical Topic của đề tài")
    domains: List[str] = Field(default_factory=list, max_length=3)
    text: Optional[str] = Field(None, max_length=1500, description="Tên và tóm tắt đề tài, để so độ gần về nghĩa")
    top_k: int = Field(5, ge=1, le=20)


@router.post("/advisors")
def advisors(body: AdvisorRequest, ds: DataStore = Depends(get_store)):
    """Gợi ý giảng viên hướng dẫn NEU phù hợp với đề tài (dựa trên khóa luận đã hướng dẫn)."""
    return AV.recommend(ds, body.topic, body.domains, body.text, body.top_k)


@router.get("/overview")
def overview(ds: DataStore = Depends(get_store)):
    """Trang chủ: công việc đang tuyển nhiều, kỹ năng phổ biến, cặp kỹ năng hay đi cùng nhau."""
    return S.overview(ds)


@router.get("/roles")
def roles(ds: DataStore = Depends(get_store)):
    """Danh sách công việc cho cửa sổ chọn (tên tiếng Việt, mô tả, nhãn hot)."""
    return S.roles(ds)


@router.get("/skills")
def skills(ds: DataStore = Depends(get_store)):
    """Kỹ năng gom theo nhóm cho màn 'Bạn đã biết những gì rồi'."""
    return S.skill_groups(ds)


@router.get("/labels")
def labels(ds: DataStore = Depends(get_store)):
    return S.labels(ds)


@router.post("/profile")
def profile(body: ProfileRequest, ds: DataStore = Depends(get_store)):
    """Đối chiếu kỹ năng của bạn với từng công việc và gợi ý nên học gì tiếp. Không lưu gì phía máy chủ."""
    return S.profile(ds, body.skills)


@router.post("/ideas")
def ideas(body: IdeasRequest, ds: DataStore = Depends(get_store)):
    """Hướng đề tài theo các công việc đã chọn (công nghệ, kỹ năng, đề tài đã có). Không cần LLM."""
    return S.ideas(ds, body.roles, body.offset, body.n)


@router.post("/ideas/title")
def idea_title(body: IdeaTitleRequest, request: Request, ds: DataStore = Depends(get_store)):
    """Tên đề tài và tóm tắt do LLM viết cho một hướng; đã kiểm tra trùng với kho luận văn."""
    return S.idea_title(ds, llm_from(request), body.roles, body.topic, body.avoid, body.n)


@router.get("/jobs")
def jobs(role: str, limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0), ds: DataStore = Depends(get_store)):
    """Tin tuyển dụng thật của một nhóm công việc."""
    return S.jobs_of_role(ds, role, limit, offset)
