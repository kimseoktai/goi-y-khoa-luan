"""Lỗi nghiệp vụ của backend; main.py ánh xạ sang mã HTTP."""


class NotFound(Exception):
    """Không có bản ghi yêu cầu (404)."""


class BadRequest(Exception):
    """Tham số không hợp lệ (400)."""


class Unavailable(Exception):
    """Tính năng cần dữ liệu/embedding chưa có (503); thông báo nói rõ cách khắc phục."""


class Unauthorized(Exception):
    """Thiếu hoặc sai mã quản trị (401)."""


class Forbidden(Exception):
    """Chức năng quản trị chưa được bật trên máy chủ (403)."""
