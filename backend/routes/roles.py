from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.database.store import DataStore
from backend.routes.deps import get_store, require_admin
from backend.services import role_service

router = APIRouter(tags=["roles"])


class RoleDecision(BaseModel):
    role: str = Field(..., description="job_title của nhóm cần quyết định")
    action: str = Field(..., description="approve_split | keep_merged | merge")
    parent: Optional[str] = Field(None, description="nhóm cha khi action=merge; rỗng = Nhóm khác")


@router.get("/roles")
def roles(ds: DataStore = Depends(get_store)):
    """Nhóm công việc hiển thị cho sinh viên (nhóm nhỏ đã gộp), kèm số đề xuất đang chờ admin duyệt."""
    return role_service.roles(ds)


@router.get("/admin/roles", dependencies=[Depends(require_admin)])
def admin_roles(ds: DataStore = Depends(get_store)):
    """Cần header X-Admin-Token. Danh sách chờ duyệt, nhóm đang gộp, nhóm chưa có nhóm cha."""
    return role_service.admin_view(ds)


@router.post("/admin/roles/decision", dependencies=[Depends(require_admin)])
def admin_decide(body: RoleDecision, ds: DataStore = Depends(get_store)):
    """Cần header X-Admin-Token. approve_split: tách riêng; keep_merged: giữ gộp; merge: đặt nhóm cha."""
    return role_service.decide(ds, body.role, body.action, body.parent)
