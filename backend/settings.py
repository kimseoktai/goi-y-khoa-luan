"""Cấu hình backend, đọc từ biến môi trường (không hard-code). Đường dẫn dữ liệu lấy từ ml.config (REC_ROOT)."""
import os
from dataclasses import dataclass, field
from typing import List

from ml import config as C


def _csv(v):
    return [x.strip() for x in v.split(",") if x.strip()]


@dataclass
class Settings:
    root: str = str(C.ROOT)
    embedding_model: str = os.getenv("REC_EMBEDDING_MODEL", C.DEFAULT_EMBED_MODEL)
    embedding_backend: str = os.getenv("REC_EMBEDDING_BACKEND", "st")          # "st" hoặc "hash" (chỉ để thử luồng)
    cors_origins: List[str] = field(default_factory=lambda: _csv(os.getenv("REC_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")))
    jobs_source: str = os.getenv("REC_JOBS_SOURCE", "auto")                  # "auto" (CSDL nếu đã tạo, không thì CSV cũ), "db" hoặc "csv"
    max_page_size: int = int(os.getenv("REC_MAX_PAGE_SIZE", "200"))
    max_text_chars: int = int(os.getenv("REC_MAX_TEXT_CHARS", "500"))
    log_level: str = os.getenv("REC_LOG_LEVEL", "INFO")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("REC_GEMINI_MODEL", "gemini-3.8-flash")      # tên mô hình đổi theo thời gian; đổi bằng biến này nếu báo 404
    llm_timeout: int = int(os.getenv("REC_LLM_TIMEOUT", "90"))               # giây chờ Gemini trả lời
    admin_token: str = os.getenv("REC_ADMIN_TOKEN", "")     # rỗng = tắt các route quản trị (an toàn mặc định)
    student_id_pattern: str = os.getenv("REC_STUDENT_ID_PATTERN", r"^11\d{6}$")    # mã sinh viên được tự tạo khi đăng nhập lần đầu (8 chữ số, bắt đầu bằng 11)
