"""Khởi động API:  uvicorn backend.main:create_app --factory --reload   (docs tự động ở /docs)"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database.store import DataStore
from backend.errors import BadRequest, Forbidden, NotFound, Unauthorized, Unavailable
from backend.routes import account, admin, analysis, catalog, roles, student, system
from backend.settings import Settings

log = logging.getLogger("backend")


def create_app(store=None, settings=None):
    settings = settings or Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(title="Thesis Recommendation API", version="0.1.0",
                  description="Phân tích nhu cầu việc làm IT, ghép Job-Thesis, kiểm tra novelty và đề xuất hướng đề tài khóa luận (chưa dùng LLM).")
    app.state.settings = settings
    app.state.store = store or DataStore(settings.root, settings.embedding_model, settings.embedding_backend, settings.jobs_source)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

    def err(status, exc):
        return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": str(exc)})

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound):
        return err(404, exc)

    @app.exception_handler(BadRequest)
    async def _br(_: Request, exc: BadRequest):
        return err(400, exc)

    @app.exception_handler(Unavailable)
    async def _un(_: Request, exc: Unavailable):
        return err(503, exc)

    @app.exception_handler(Unauthorized)
    async def _ua(_: Request, exc: Unauthorized):
        return err(401, exc)

    @app.exception_handler(Forbidden)
    async def _fb(_: Request, exc: Forbidden):
        return err(403, exc)

    @app.exception_handler(Exception)
    async def _ex(request: Request, exc: Exception):
        log.exception("lỗi không xử lý được tại %s", request.url.path)       # chi tiết chỉ ghi log, không trả cho client
        return JSONResponse(status_code=500, content={"error": "InternalError", "detail": "lỗi nội bộ, xem log của máy chủ"})

    for r in (system.router, catalog.router, analysis.router, roles.router, student.router, account.router, account.admin_router, admin.router):
        app.include_router(r)
    return app
