"""Phần xử lý (không cần mạng) của crawler TopDev: chuyển một tin từ API danh sách thành bản ghi CSDL và ghi vào DB."""
import html
import json
import re
from datetime import datetime

from ml.jobsdb import db

SOURCE = "topdev"
API = "https://api.topdev.vn/td/v2/jobs"
IT_CATEGORIES = "2,3,4,5,6,7,8,9,10,11,12,13,67"   # 13 nhóm ngành IT trên trang tìm kiếm của TopDev; bỏ lọc thì lẫn nhiều việc bán hàng, kế toán, nhân sự...
FIELDS = ("id,title,content,responsibilities,requirements_arr,benefits_v2,company,skills_arr,addresses,salary,is_salary_visible,"
          "job_levels_str,job_types_str,contract_types_str,experiences_str,published,refreshed,expires,status_display,detail_url")


def text(h):
    """HTML mô tả -> văn bản thuần (giữ xuống dòng và gạch đầu dòng)."""
    if not h:
        return ""
    s = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", str(h))
    s = re.sub(r"(?i)<\s*(br|/p|/div|/ul|/ol|/h\d)[^>]*>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def iso_date(d):
    """'15-10-2026' -> '2026-10-15'; không đọc được thì trả None."""
    try:
        return datetime.strptime((d or {}).get("date", ""), "%d-%m-%Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


def salary_text(it):
    """Chỉ lấy lương khi trang cho hiển thị công khai (is_salary_visible)."""
    sal = it.get("salary") or {}
    if not it.get("is_salary_visible"):
        return ""
    if str(sal.get("is_negotiable")) == "1":
        return "Thỏa thuận"
    lo, hi = sal.get("min_filter"), sal.get("max_filter")
    return f"{lo:,} - {hi:,} {sal.get('currency', '')}".strip() if lo and hi else ""


def to_record(it):
    url = (it.get("detail_url") or "").split("?")[0]
    addr = [a for a in ((it.get("addresses") or {}).get("address_region_array") or []) if a]
    benefits = "\n".join(filter(None, (text(b.get("description")) for b in (it.get("benefits_v2") or []) if b)))
    desc = "\n\n".join(filter(None, (text(it.get("content")), text(it.get("responsibilities")))))
    return dict(
        sid=str(it["id"]), url=url, skills=[str(s).strip() for s in (it.get("skills_arr") or []) if str(s).strip()],
        fields=dict(title_raw=it.get("title") or "", company=(it.get("company") or {}).get("display_name") or "",
                    location=", ".join(dict.fromkeys(addr)), working_model=it.get("job_types_str") or "", salary_text=salary_text(it),
                    description=desc, requirements="\n".join(text(x) for x in (it.get("requirements_arr") or []) if x), benefits=benefits,
                    posted_at=iso_date(it.get("published")), deadline=iso_date(it.get("expires"))))


def ingest_items(con, items, today=None, errors=None):
    """Ghi một trang tin vào CSDL. Trả về (danh sách job_id đã thấy, số tin mới). Tin mới được lưu nguyên bản vào raw_pages.
    Tin nào lỗi thì bỏ qua và ghi vào danh sách errors (nếu có) thay vì làm hỏng cả lần chạy."""
    ids, new = [], 0
    for it in items:
        try:
            r = to_record(it)
        except Exception as e:                                       # noqa: BLE001
            if errors is None:
                raise
            errors.append(f"tin {it.get('id') if isinstance(it, dict) else '?'}: {type(e).__name__}: {e}")
            continue
        if not r["url"]:
            continue
        jid, is_new = db.upsert_job(con, r["url"], skills=r["skills"], today=today, source=SOURCE, origin="listed", sid=r["sid"], **r["fields"])
        if is_new:
            con.execute("INSERT OR REPLACE INTO raw_pages (source, source_job_id, fetched_at, payload) VALUES (?,?,?,?)",
                        (SOURCE, r["sid"], str(today or ""), json.dumps(it, ensure_ascii=False)))
        ids.append(jid)
        new += is_new
    con.commit()
    return ids, new
