from typing import Optional, Union

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.database.store import DataStore
from backend.routes.deps import get_store, require_admin
from backend.services import admin_service as A, thesis_admin_service as T

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])   # mọi route cần header X-Admin-Token


class RunBody(BaseModel):
    task: str = Field(..., description="crawl_all | crawl_thesis | build_thesis | build_site | embeddings | tests")


class CompanyDecision(BaseModel):
    company_key: str
    status: Optional[str] = Field(None, description="draft | review | approved | rejected")
    domain: Optional[str] = Field(None, description="tên lĩnh vực; nhiều lĩnh vực ngăn bằng '|'; '-' = tùy vị trí")


class CompanyNew(BaseModel):
    company: str
    domain: str
    note: str = ""


class ThesisNew(BaseModel):
    title: str
    year: Optional[int] = None
    source: str = "neu"
    report_url: Optional[str] = None
    source_code_url: Optional[str] = None
    advisors: Optional[str] = Field(None, description="giảng viên hướng dẫn, nhiều người cách nhau bằng dấu chấm phẩy")


class ThesisEdit(BaseModel):
    thesis_id: int
    title: Optional[str] = None
    year: Union[int, str, None] = Field(None, description="rỗng = xóa năm")
    source: Optional[str] = None
    report_url: Optional[str] = Field(None, description="rỗng = xóa đường dẫn")
    source_code_url: Optional[str] = None
    advisors: Optional[str] = Field(None, description="rỗng = xóa GVHD")


class ThesisId(BaseModel):
    thesis_id: int


class ThesisLabels(BaseModel):
    thesis_id: int
    topics: list[str] = []
    domains: list[str] = []
    note: Optional[str] = None


def runner(request: Request) -> A.Runner:
    app = request.app
    if not hasattr(app.state, "runner"):
        app.state.runner = A.Runner(app.state.store.root)
    return app.state.runner


@router.get("/overview")
def overview(ds: DataStore = Depends(get_store)):
    """Chỉ số dữ liệu: số tin theo nguồn/ngày, lần crawl gần nhất, độ phủ nhãn, trạng thái lịch tuần."""
    return A.overview(ds)


@router.get("/tasks")
def tasks(r: A.Runner = Depends(runner)):
    return {"tasks": [{"id": k, "label": v[0]} for k, v in A.TASKS.items()], "status": r.status()}


@router.post("/run")
def run(body: RunBody, r: A.Runner = Depends(runner)):
    return r.start(body.task)


@router.post("/run/stop")
def stop(r: A.Runner = Depends(runner)):
    return r.stop()


@router.get("/run/status")
def run_status(tail: int = Query(200, ge=1, le=2000), r: A.Runner = Depends(runner)):
    return r.status(tail)


@router.get("/logs")
def logs(ds: DataStore = Depends(get_store)):
    return {"items": A.list_logs(ds.root)}


@router.get("/logs/{name}")
def log(name: str, tail: int = Query(300, ge=1, le=2000), ds: DataStore = Depends(get_store)):
    return {"name": name, "text": A.read_log(ds.root, name, tail)}


@router.post("/reload")
def reload(request: Request):
    """Nạp lại dữ liệu website sau khi dựng xong."""
    return A.reload_store(request.app)


@router.get("/companies")
def companies(status: str = "", q: str = "", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), ds: DataStore = Depends(get_store)):
    return A.list_companies(ds, status, q, limit, offset)


@router.post("/companies/decision")
def company_decision(body: CompanyDecision, ds: DataStore = Depends(get_store)):
    return A.decide_company(ds, body.company_key, body.status, body.domain)


@router.post("/companies/add")
def company_add(body: CompanyNew, ds: DataStore = Depends(get_store)):
    return A.add_company(ds, body.company, body.domain, body.note)


@router.get("/thesis")
def thesis_list(q: str = "", status: str = "", source: str = "", origin: str = "", sort: str = "newest", limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0),
                ds: DataStore = Depends(get_store)):
    """Danh sách khóa luận trong CSDL (kể cả đã đóng) kèm nhãn hiện hành và số thay đổi chưa dựng vào website."""
    return T.listing(ds, q, status, source, origin, sort, limit, offset)


@router.post("/thesis/add")
def thesis_add(body: ThesisNew, ds: DataStore = Depends(get_store)):
    return T.add(ds, title=body.title, year=body.year, source=body.source, report_url=body.report_url, source_code_url=body.source_code_url, advisors=body.advisors)


@router.post("/thesis/update")
def thesis_update(body: ThesisEdit, ds: DataStore = Depends(get_store)):
    return T.update(ds, body.thesis_id, {k: v for k, v in (body.model_dump if hasattr(body, "model_dump") else body.dict)(exclude={"thesis_id"}).items() if v is not None})


@router.post("/thesis/delete")
def thesis_delete(body: ThesisId, ds: DataStore = Depends(get_store)):
    return T.delete(ds, body.thesis_id)


@router.post("/thesis/restore")
def thesis_restore(body: ThesisId, ds: DataStore = Depends(get_store)):
    return T.restore(ds, body.thesis_id)


@router.post("/thesis/labels")
def thesis_labels(body: ThesisLabels, ds: DataStore = Depends(get_store)):
    return T.set_labels(ds, body.thesis_id, body.topics, body.domains, body.note)
