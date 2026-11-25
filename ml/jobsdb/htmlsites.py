"""Bộ đọc cho các trang tuyển dụng dạng HTML (ITviec, CareerViet) và bộ chạy crawl chung ghi vào CSDL.
Cả hai trang nhúng dữ liệu JobPosting (JSON-LD) trong trang chi tiết: có ngày đăng, hạn nộp, mô tả. Đọc từ đó ổn định hơn đọc giao diện."""
import json
import random
import re
import time
import urllib.error
import urllib.request

from ml.jobsdb import db
from ml.jobsdb.topdev import text

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"}
LD_RE = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S)


class NoJobPosting(ValueError):
    """Trang chi tiết không có khối JobPosting: thường là tin đã gỡ nhưng còn trong danh sách."""


UNREADABLE_MAX_RATIO = 0.02    # tối đa 2% tin đọc không được thì vẫn coi lần crawl là đủ (tránh vài trang hỏng chặn việc đóng tin mãi mãi)


def job_posting(html):
    """Tìm khối JobPosting trong các khối JSON-LD của trang; trả về dict hoặc None."""
    for m in LD_RE.finditer(html):
        try:
            j = json.loads(m.group(1).strip(), strict=False)
        except ValueError:
            continue
        for x in (j if isinstance(j, list) else [j]):
            if isinstance(x, dict) and x.get("@type") == "JobPosting":
                return x
    return None


def _date(v):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(v or ""))
    return m.group(1) if m else None


def _addresses(ld, key):
    loc = ld.get("jobLocation") or []
    out = []
    for p in (loc if isinstance(loc, list) else [loc]):
        v = ((p or {}).get("address") or {}).get(key)
        if v and v not in out:
            out.append(str(v))
    return ", ".join(out)


# ---------------- ITviec ----------------
class ITviec:
    NAME = "itviec"
    BASE = "https://itviec.com"
    GROUPS = ["ho-chi-minh-hcm", "ha-noi", "da-nang", "others"]       # giống cách chia địa điểm của script crawl cũ

    @staticmethod
    def list_url(group, page):
        return f"{ITviec.BASE}/it-jobs/{group}?page={page}"

    @staticmethod
    def parse_list(html):
        urls = []
        for h in re.findall(r'href="([^"]*lab_feature=preview_jd_page[^"]*)"', html):
            path = re.sub(r"^https://itviec\.com", "", h.split("?")[0])
            if re.fullmatch(r"/it-jobs/[a-z0-9-]+-\d{4}", path) and ITviec.BASE + path not in urls:
                urls.append(ITviec.BASE + path)
        return urls

    @staticmethod
    def total(html):
        return None

    @staticmethod
    def parse_detail(html, url):
        ld = job_posting(html)
        if not ld:
            raise NoJobPosting("không thấy khối JobPosting trong trang")
        skills = [s.strip() for s in str(ld.get("skills") or "").split(",") if s.strip()]    # kỹ năng của chính tin; thẻ phía dưới trang là của tin gợi ý
        return dict(skills=skills, raw=ld, fields=dict(
            title_raw=ld.get("title") or "", company=(ld.get("hiringOrganization") or {}).get("name") or "", location=_addresses(ld, "addressRegion"),
            description=text(ld.get("description")), benefits=text(ld.get("jobBenefits")), posted_at=_date(ld.get("datePosted")), deadline=_date(ld.get("validThrough"))))


# ---------------- CareerViet ----------------
class CareerViet:
    NAME = "careerviet"
    BASE = "https://careerviet.vn"
    GROUPS = ["all"]                                                  # toàn bộ ngành CNTT - Phần mềm trên cả nước

    @staticmethod
    def list_url(group, page):
        return f"{CareerViet.BASE}/viec-lam/cntt-phan-mem-c1-vi.html" if page == 1 else f"{CareerViet.BASE}/viec-lam/cntt-phan-mem-c1-trang-{page}-vi.html"

    @staticmethod
    def parse_list(html):
        urls = []
        for path in re.findall(r'href="((?:https://careerviet\.vn)?/vi/tim-viec-lam/[^"?#]*\.[0-9A-Fa-f]{8}\.html)', html):
            u = path if path.startswith("http") else CareerViet.BASE + path
            if u not in urls:
                urls.append(u)
        return urls

    @staticmethod
    def total(html):
        m = re.search(r"<title>\s*Tuyển dụng ([\d.,]+) việc làm", html)      # lấy từ thẻ title: các số khác trên trang (tổng toàn site) dễ nhầm
        return int(re.sub(r"\D", "", m.group(1))) if m else None

    @staticmethod
    def parse_detail(html, url):
        ld = job_posting(html)
        if not ld:
            raise NoJobPosting("không thấy khối JobPosting trong trang")
        sal = (((ld.get("baseSalary") or {}).get("value") or {}).get("value")) or ""
        # CareerViet không có mục kỹ năng riêng: kỹ năng sẽ được trích từ mô tả ở tầng làm sạch (trường 'skills' trong JSON-LD chỉ là từ khóa tên việc)
        return dict(skills=[], raw=ld, fields=dict(
            title_raw=ld.get("title") or "", company=(ld.get("hiringOrganization") or {}).get("name") or "", location=_addresses(ld, "addressLocality"),
            salary_text=str(sal), description=text(ld.get("description")), benefits=text(ld.get("jobBenefits")),
            posted_at=_date(ld.get("datePosted")), deadline=_date(ld.get("validThrough"))))


# ---------------- tải trang & chạy crawl ----------------
def fetch_html(url, tries=3, timeout=45):
    last = None
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(3 * attempt)
    raise RuntimeError(f"không tải được {url}: {last}")


def crawl(con, site, fetch=fetch_html, today=None, max_pages=60, max_details=None, sleep=(1.5, 3.0), log=print):
    """Duyệt danh sách của từng nhóm, rồi tải trang chi tiết cho tin MỚI hoặc tin còn thiếu ngày đăng; tin đã đủ thông tin chỉ cập nhật last_seen.
    Chỉ đóng tin vắng mặt khi duyệt đủ danh sách, không lỗi và không bỏ sót tin nào. Trả về dict thống kê."""
    run = db.start_run(con, site.NAME)
    errors, unreadable, listed, seen_urls, complete, note = [], [], [], set(), True, None
    for g in site.GROUPS:
        got, total = set(), None
        for p in range(1, max_pages + 1):
            try:
                html = fetch(site.list_url(g, p))
            except Exception as e:                                             # noqa: BLE001
                complete, note = False, f"lỗi tải danh sách {g} trang {p}: {e}"
                break
            if p == 1:
                total = site.total(html)
            new = [u for u in site.parse_list(html) if u not in got]
            if not new:
                break
            got.update(new)
            listed += [u for u in new if u not in seen_urls]
            seen_urls.update(new)
            log(f"[{g}] trang {p}: {len(new)} tin (nhóm đến nay {len(got)}{'/' + str(total) if total else ''})")
            if total and len(got) >= total:
                break
            time.sleep(random.uniform(*sleep) if sleep else 0)
        else:
            complete, note = False, f"nhóm {g} chạm giới hạn {max_pages} trang"
    ids, n_new, fetched, skipped = [], 0, 0, 0
    for u in listed:
        con.commit()                                                           # nhả khóa ghi trước khi chờ mạng, để crawler khác (nguồn khác) ghi được
        sid = db.source_job_id(u)
        row = con.execute("SELECT job_id, posted_at, description FROM jobs WHERE source=? AND source_job_id=?", (site.NAME, sid)).fetchone()
        need = row is None or not row["posted_at"] or not row["description"]
        if need and max_details is not None and fetched >= max_details:
            if row is None:
                skipped += 1
            else:
                ids.append(db.upsert_job(con, u, today=today, source=site.NAME)[0])
            continue
        if not need:
            ids.append(db.upsert_job(con, u, today=today, source=site.NAME)[0])
            continue
        try:
            time.sleep(random.uniform(*sleep) if sleep else 0)
            rec = site.parse_detail(fetch(u), u)
            fetched += 1
            jid, is_new = db.upsert_job(con, u, skills=rec["skills"], today=today, source=site.NAME, origin="listed", **rec["fields"])
            if is_new:
                con.execute("INSERT OR REPLACE INTO raw_pages (source, source_job_id, fetched_at, payload) VALUES (?,?,?,?)",
                            (site.NAME, sid, str(today or ""), json.dumps(rec["raw"], ensure_ascii=False)))
            ids.append(jid)
            n_new += is_new
            if fetched % 25 == 0:
                con.commit()
                log(f"  đã đọc chi tiết {fetched} tin...")
        except NoJobPosting as e:
            unreadable.append(sid)                                              # tin chưa từng có trong DB và trang không đọc được: bỏ qua, lần sau thử lại
            if row is not None:
                ids.append(db.upsert_job(con, u, today=today, source=site.NAME)[0])
        except Exception as e:                                                  # noqa: BLE001
            errors.append(f"{sid}: {type(e).__name__}: {e}")
            if row is not None:
                ids.append(db.upsert_job(con, u, today=today, source=site.NAME)[0])
    con.commit()
    if errors:
        complete = False
        note = note or f"{len(errors)} tin lỗi, ví dụ: {errors[0]}"
    if unreadable:
        msg = f"{len(unreadable)} trang không đọc được (không có JobPosting), ví dụ {unreadable[0]}"
        if len(unreadable) > UNREADABLE_MAX_RATIO * max(len(listed), 1):
            complete, note = False, note or msg
        else:
            note = note or msg + " - bỏ qua, vẫn tính là đủ"
    if skipped:
        complete = False
        note = note or f"bỏ qua {skipped} tin mới vì giới hạn --max-details"
    if not listed:
        complete, note = False, note or "không thấy tin nào trong danh sách (nghi bị chặn hoặc giao diện đổi)"
    closed = db.close_missing(con, run, site.NAME, ids, today=today) if complete else 0
    db.finish_run(con, run, n_seen=len(ids), n_new=n_new, ok=complete, note=note)
    return dict(listed=len(listed), seen=len(ids), new=n_new, fetched=fetched, closed=closed, errors=errors, complete=complete, note=note)
