"""Đăng nhập bằng mã sinh viên, hồ sơ theo mã, và quản lý danh sách mã (quản trị)."""
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field

from backend.routes.deps import get_store, require_admin
from backend.services import account_service as A

router = APIRouter(tags=["account"])
admin_router = APIRouter(prefix="/admin/students", tags=["admin"], dependencies=[Depends(require_admin)])


def _root(request: Request):
    return request.app.state.store.root


def current(request: Request, x_student_token: str = Header(default="")):
    return A.session(_root(request), x_student_token)


class LoginBody(BaseModel):
    student_id: str = Field(..., max_length=40)
    secret: Optional[str] = Field(None, max_length=200, description="mã quản trị, chỉ cần với mã có vai trò admin")


class StateBody(BaseModel):
    state: dict


class ImportBody(BaseModel):
    text: str = Field(..., max_length=500_000, description="mỗi dòng: mã | mã,tên | mã,tên,vai trò | dãy a-b")
    role: str = Field("student", description="vai trò mặc định cho các dòng không ghi vai trò")


class SaveBody(BaseModel):
    student_id: str = Field(..., max_length=40)
    name: str = Field("", max_length=120)
    role: str = Field("student", description="student hoặc admin")
    create: bool = Field(False, description="true = thêm mới (báo lỗi nếu mã đã có); false = sửa mã đã có")


class DeleteBody(BaseModel):
    student_id: str


@router.post("/auth/login")
def login(body: LoginBody, request: Request):
    st = request.app.state.settings
    return A.login(_root(request), st.admin_token, body.student_id, body.secret or "", st.student_id_pattern)


@router.post("/auth/logout")
def logout(request: Request, x_student_token: str = Header(default="")):
    return A.logout(_root(request), x_student_token)


@router.get("/me")
def me(who=Depends(current)):
    return who


@router.get("/me/state")
def get_state(request: Request, who=Depends(current)):
    return A.get_state(_root(request), who["student_id"])


@router.post("/me/state")
def save_state(body: StateBody, request: Request, who=Depends(current)):
    return A.save_state(_root(request), who["student_id"], body.state)


@admin_router.get("")
def students(request: Request, q: str = "", role: str = "", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return A.list_students(_root(request), q, role, limit, offset)


@admin_router.post("/import")
def import_students(body: ImportBody, request: Request):
    return A.import_students(_root(request), body.text, body.role)


@admin_router.post("/save")
def save_student(body: SaveBody, request: Request):
    return A.save_student(_root(request), body.student_id, body.name, body.role, body.create)


@admin_router.post("/delete")
def delete_student(body: DeleteBody, request: Request):
    return A.delete_student(_root(request), body.student_id)
