"""Crawl danh sách khóa luận Khoa CNTT - NEU (https://fit.neu.edu.vn/theses).

Trang là Next.js: toàn bộ danh sách nằm sẵn trong HTML (dữ liệu nhúng self.__next_f), chia trang ở phía giao diện,
nên MỘT yêu cầu tới /theses là đủ. Theo robots.txt của trang: /theses được phép; /api/ bị cấm -> KHÔNG gọi /api/ và KHÔNG tải file PDF
(đường dẫn file báo cáo chỉ được LƯU lại để người dùng tự bấm mở).
Chỉ lấy tiêu đề, năm, đường dẫn file và TÊN giảng viên hướng dẫn; bỏ họ tên và mã sinh viên.
"""
import json
import re
import time
import urllib.error
import urllib.request

from ml.thesisdb import advisors, db

SOURCE = "neu"
RUN_SOURCE = "neu_thesis"
BASE = "https://fit.neu.edu.vn"
LIST_URL = BASE + "/theses"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"}
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)


ADVISOR_KEY = "GVHD"      # tên trường chứa GVHD trong dữ liệu nhúng; None = tự dò (chạy scripts/inspect_neu_fields.py để biết tên thật)
ADVISOR_RE = re.compile(r"gvhd|gi[aả]ng.?vi[eê]n|huong.?dan|hư[oớ]ng.?d[aẫ]n|advis|supervis|instruct|teacher|lecturer|mentor", re.I)


STUDENT_RE = re.compile(r"sinh.?vi[eê]n|student|mssv|ma.?sv|h[oọ].?t[eê]n|fullname|email|phone|sdt", re.I)   # không bao giờ lấy trường của sinh viên


def _advisor_value(r):
    k = ADVISOR_KEY or next((x for x in r if ADVISOR_RE.search(str(x)) and not STUDENT_RE.search(str(x))), None)
    return r.get(k) if k else None


class ParseError(ValueError):
    pass


def parse(html):
    """HTML -> (danh sách bản ghi đã bỏ dữ liệu cá nhân, has_more)."""
    chunks = PUSH_RE.findall(html)
    if not chunks:
        raise ParseError("không thấy dữ liệu nhúng (trang đổi cấu trúc?)")
    txt = "".join(json.loads('"' + c + '"') for c in chunks)
    i = txt.find('{"object":"list"')
    if i < 0:
        raise ParseError("không thấy danh sách khóa luận trong dữ liệu nhúng")
    obj, _ = json.JSONDecoder().raw_decode(txt[i:])
    out = []
    for r in obj.get("results", []):
        sid, title = r.get("id"), (r.get("tenChuyenDe") or "").strip()
        if not sid or not title:
            continue
        link = lambda p: (BASE + p) if p and str(p).startswith("/") else (p or None)
        out.append(dict(sid=sid, title=title, year=r.get("nam"), report_url=link(r.get("fileBaoCao")), source_code_url=link(r.get("sourceCode")),
                        advisors=advisors.split_names(_advisor_value(r))))
    if not out:
        raise ParseError("danh sách rỗng")
    return out, bool(obj.get("has_more"))


def fetch(url=LIST_URL, retries=3, timeout=60, opener=None):
    if not url.startswith(BASE + "/") or url.startswith(BASE + "/api"):
        raise ValueError("chỉ được tải trang danh sách, không tải /api/ (robots.txt)")
    last = None
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"không tải được {url}: {last}")


def crawl(con, html=None, today=None):
    """Một lần crawl. Trả về dict thống kê. html có thể truyền vào (kiểm thử hoặc file đã lưu)."""
    run = db_start(con)
    try:
        recs, has_more = parse(html if html is not None else fetch())
    except Exception as e:                      # lỗi tải/đọc: ghi lại, không đóng gì
        con.execute("UPDATE crawl_runs SET finished_at=datetime('now'), ok=0, note=? WHERE run_id=?", (f"lỗi: {e}", run))
        con.commit()
        raise
    ids, new, changed = [], 0, 0
    for r in recs:
        tid, is_new, ch = db.upsert_thesis(con, SOURCE, r["sid"], r["title"], year=r["year"], report_url=r["report_url"],
                                          source_code_url=r["source_code_url"], today=today, advisors=r.get("advisors"))
        ids.append(tid); new += is_new; changed += ch
    complete = not has_more
    note = None if complete else "danh sách chưa đủ (has_more), không đóng khóa luận nào"
    # ok=1 chỉ khi danh sách đủ; close_missing hạ về 0 nếu lần crawl bất thường để lần sau không lấy nó làm mốc so sánh
    con.execute("UPDATE crawl_runs SET finished_at=datetime('now'), n_seen=?, n_new=?, ok=?, note=? WHERE run_id=?",
                (len(ids), new, int(complete), note, run))
    closed = db.close_missing(con, run, RUN_SOURCE, SOURCE, ids) if complete else 0
    con.commit()
    return dict(seen=len(ids), new=new, title_changed=changed, closed=closed, complete=complete, note=note)


def db_start(con):
    from ml.jobsdb import db as jobsdb
    return jobsdb.start_run(con, RUN_SOURCE)
