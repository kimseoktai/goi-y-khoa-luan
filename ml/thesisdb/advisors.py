"""Tên giảng viên hướng dẫn (GVHD): tách nhiều người, bỏ học hàm/học vị, tạo khóa so khớp không phân biệt dấu và hoa thường.
Chỉ lưu tên GVHD (thông tin công khai của khoa). Tên và mã sinh viên không được đọc hay lưu."""
import re
import unicodedata

SEP = re.compile(r"\s*(?:[;,/&\n]|\s+và\s+|\s+and\s+)\s*", re.I)
# học hàm, học vị ở đầu tên: PGS.TS., TS., ThS., Th.S, GS, Dr., Prof., GVC, NCS, TS.BS ...
TITLE = re.compile(r"^\s*(?:(?:pgs|gs|ts|ths|th\.s|nghiên cứu sinh|ncs|gvc|gv|dr|prof|mr|ms|mrs|thầy|cô|ths\.|ts\.)\b[\s.\-:]*)+", re.I)
MAX_NAME = 80


def _nfc(s):
    return unicodedata.normalize("NFC", str(s or ""))


def clean_name(raw):
    """'TS. Nguyễn  Văn A' -> 'Nguyễn Văn A'. Chuỗi rỗng nếu không còn gì dùng được."""
    s = _nfc(raw).replace(" ", " ")
    s = TITLE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" .,-;:()[]")
    if not s or len(s) > MAX_NAME or any(ch.isdigit() for ch in s) or len(s.split()) < 2:
        return ""
    return s


def key(name):
    """Khóa so khớp: bỏ dấu tiếng Việt, đ->d, chữ thường, một khoảng trắng."""
    s = _nfc(name).lower().replace("đ", "d")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", s)).strip()


def split_names(value):
    """Chuỗi hoặc danh sách -> danh sách tên đã làm sạch, không trùng (giữ thứ tự)."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    out, seen = [], set()
    for it in items:
        if isinstance(it, dict):                       # kiểu thuộc tính Notion: {"name": ...} hoặc {"plain_text": ...}
            it = it.get("name") or it.get("plain_text") or it.get("title") or ""
        for part in SEP.split(_nfc(it)):
            n = clean_name(part)
            k = key(n)
            if n and k not in seen:
                seen.add(k); out.append(n)
    return out
