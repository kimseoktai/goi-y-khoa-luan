"""Trích phần tóm tắt (Tóm tắt / Abstract) từ vài trang đầu của một báo cáo khóa luận (PDF đã tải về máy).
Chỉ đọc file cục bộ; không tải gì từ mạng. Kết quả chỉ là đoạn chữ tóm tắt, không lưu lại file PDF."""
import re
import unicodedata

HEAD = re.compile(r"^\s*(?:(?:\d+|[IVX]+)[.)]?\s+)?(tóm\s*tắt(?:\s+(?:khóa\s*luận|đồ\s*án|đề\s*tài|luận\s*văn|nội\s*dung))?|abstract|summary)\s*[:.]?\s*(.*)$", re.I)
STOP = re.compile(r"^\s*(từ\s*khóa|keywords?|key\s*words|mục\s*lục|table\s*of\s*contents|lời\s*(cảm\s*ơn|cam\s*đoan|nói\s*đầu|mở\s*đầu)|danh\s*mục|mở\s*đầu|chương\s*\d|chapter\s*\d|abstract\s*$|tóm\s*tắt\s*$|(?:\d+|[IVX]+)[.)]?\s+(?:giới\s*thiệu|mở\s*đầu|introduction))", re.I)
DOTS = re.compile(r"\.{4,}|\s\d{1,3}\s*$")          # dòng của mục lục: chấm dẫn hoặc số trang ở cuối
MAX_CHARS = 3000
MIN_CHARS = 150


def _nfc(s):
    return unicodedata.normalize("NFC", s or "")


def extract_abstract(text):
    """Trả về (đoạn tóm tắt hoặc None, 'tiếng Việt'/'English'/None). Chọn đoạn dài nhất tìm được (bỏ mục lục)."""
    lines = [_nfc(l).rstrip() for l in (text or "").splitlines()]
    best, lang = None, None
    for i, l in enumerate(lines):
        m = HEAD.match(l)
        if not m or DOTS.search(l):
            continue
        kind, rest = m.group(1).lower(), m.group(2).strip()
        if len(l) > 120:                                    # câu văn thường, không phải tiêu đề
            continue
        parts = [rest] if rest else []
        for nxt in lines[i + 1:]:
            if STOP.match(nxt) and parts:
                break
            if STOP.match(nxt) and not parts and not HEAD.match(nxt):
                break
            parts.append(nxt.strip())
            if sum(map(len, parts)) > MAX_CHARS:
                break
        txt = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if len(txt) >= MIN_CHARS and (best is None or len(txt) > len(best)):
            best, lang = txt[:MAX_CHARS], "English" if kind in ("abstract", "summary") else "tiếng Việt"
    return best, lang


INTRO = re.compile(r"(?:LỜI\s+)?MỞ\s+ĐẦU|(?:Lời\s+)?Mở\s+đầu\s", 0)
INTRO_END = re.compile(r"CHƯƠNG\s*(?:1|I)\b|Chương\s*(?:1|I)\b|CHAPTER\s*1|DANH\s+MỤC|TÀI\s+LIỆU\s+THAM")
INTRO_MAX = 6000      # đoạn thô tối đa để chọn câu
OUT_MAX = 1300        # độ dài văn bản đầu ra (vừa cửa sổ ~512 token của mô hình embedding)
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ỹ“\"(])")
FOCUS = re.compile(r"đề\s*tài|mục\s*tiêu|mục\s*đích|nghiên\s*cứu\s+và\s+phát|xây\s*dựng|phát\s*triển\s+(?:một|hệ)|hệ\s*thống\s+(?:có|cho|nhằm)", re.I)


def focus_text(seg, limit=OUT_MAX):
    """Đưa các câu nói về chính đề tài (đề tài, mục tiêu, xây dựng...) lên đầu, rồi đến bối cảnh; chỉ lấy câu nguyên vẹn."""
    sents = [x.strip() for x in SENT.split(seg) if len(x.strip()) >= 25]      # bỏ mảnh vụn như "1." của danh sách đánh số
    if sents and not re.search(r"[.!?]$", sents[-1]):
        sents = sents[:-1]                                   # câu cuối bị cắt dở
    key = [x for x in sents if FOCUS.search(x)][:3]
    rest = [x for x in sents if x not in key]
    out, n = [], 0
    for x in key + rest:
        if n + len(x) > limit and out:
            break
        out.append(x); n += len(x) + 1
    return " ".join(out)


def extract_intro(text):
    """Báo cáo không có mục Tóm tắt thì dùng đoạn đầu của phần 'Mở đầu' (bối cảnh, mục tiêu) làm văn bản mô tả.
    Làm việc trên chữ đã gộp khoảng trắng nên chịu được PDF trích ra từng từ một dòng. Bỏ qua mục lục (chấm dẫn)."""
    flat = re.sub(r"\s+", " ", _nfc(text or ""))
    best = None
    for m in INTRO.finditer(flat):
        seg = flat[m.end():]
        e = INTRO_END.search(seg)
        seg = seg[: e.start()] if e else seg[:INTRO_MAX]
        seg = re.sub(r"^[\s\d.:–-]+", "", seg)
        if "....." in seg[:60] or len(seg) < MIN_CHARS:
            continue
        if best is None or len(seg) > len(best):
            best = seg
    return focus_text(best[:INTRO_MAX]) or None if best else None


def extract_text(text):
    """Trả về (văn bản, loại, ngôn ngữ): ưu tiên Tóm tắt/Abstract, không có thì Mở đầu."""
    ab, lang = extract_abstract(text)
    if ab:
        return ab, "abstract", lang
    it = extract_intro(text)
    return (it, "intro", "tiếng Việt") if it else (None, None, None)


def read_pages(path, max_pages=14):
    """Lấy chữ của max_pages trang đầu. Thứ tự thử: PyMuPDF (pip install pymupdf, sạch nhất), pdftotext (poppler), pypdf.
    Trả về (chữ, số trang tổng)."""
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        d = fitz.open(path)
        return "\n".join(d[i].get_text() for i in range(min(max_pages, len(d)))), len(d)
    except ImportError:
        pass
    import shutil, subprocess
    from pypdf import PdfReader
    n = len(PdfReader(str(path)).pages)
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-f", "1", "-l", str(max_pages), "-layout", str(path), "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout, n
    rd = PdfReader(str(path))
    return "\n".join((rd.pages[i].extract_text() or "") for i in range(min(max_pages, n))), n
