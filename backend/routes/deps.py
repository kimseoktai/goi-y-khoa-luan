import hmac
from functools import partial

from fastapi import Header, Request

from backend.errors import Forbidden, Unauthorized

from backend.database.store import DataStore
from backend.services import account_service as A


def get_store(request: Request) -> DataStore:
    return request.app.state.store


def weights_from(prefix_names, values):
    """Gộp các tham số w_* (None = không gửi) thành dict trọng số."""
    return {n: v for n, v in zip(prefix_names, values) if v is not None} or None


def require_admin(request: Request, x_admin_token: str = Header(default=""), x_student_token: str = Header(default="")):
    """Route quản trị: cho qua nếu phiên đăng nhập (X-Student-Token) thuộc mã có vai trò admin trong CSDL.
    Ngoài ra vẫn nhận X-Admin-Token khớp REC_ADMIN_TOKEN (dùng cho script/kiểm thử); không có cả hai thì từ chối."""
    if x_student_token:
        try:
            if A.session(request.app.state.store.root, x_student_token)["role"] == "admin":
                return
        except Unauthorized:
            pass
    tok = request.app.state.settings.admin_token
    if not tok:
        raise Forbidden("chỉ quản trị viên mới dùng được; hãy đăng nhập bằng mã có vai trò admin (hoặc đặt REC_ADMIN_TOKEN cho script)")
    if not hmac.compare_digest(x_admin_token.encode("utf-8"), tok.encode("utf-8")):
        raise Unauthorized("mã quản trị không đúng")


def llm_from(request: Request):
    """Hàm gọi LLM (Gemini): llm(messages) -> dict JSON."""
    from ml.generation import llm_client as LC
    s = request.app.state.settings
    return partial(LC.gemini_json, model=s.gemini_model, api_key=s.gemini_api_key, timeout=min(s.llm_timeout, 90))
