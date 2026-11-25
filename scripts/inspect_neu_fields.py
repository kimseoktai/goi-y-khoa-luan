"""Xem tên các trường trong dữ liệu khóa luận của trang NEU để biết trường nào chứa giảng viên hướng dẫn (GVHD).

Chỉ in TÊN trường, kiểu dữ liệu và số bản ghi có giá trị; với trường nghi là GVHD in tối đa 3 giá trị mẫu.
Không in họ tên hay mã sinh viên: trường nghi là sinh viên bị loại khỏi phần mẫu.
Dùng: python scripts/inspect_neu_fields.py [--html file.html]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.thesisdb import advisors, neu   # noqa: E402

STUDENT = re.compile(r"sinh.?vi[eê]n|student|mssv|ma.?sv|hoTen|h[oọ].?t[eê]n|fullname|email|phone|sdt", re.I)


def records(html):
    """Bản ghi thô (trước khi bỏ trường nào), đọc cùng đường với neu.parse."""
    chunks = neu.PUSH_RE.findall(html)
    txt = "".join(json.loads('"' + c + '"') for c in chunks)
    i = txt.find('{"object":"list"')
    if i < 0:
        return []
    obj, _ = json.JSONDecoder().raw_decode(txt[i:])
    return [r for r in obj.get("results", []) if isinstance(r, dict)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="đọc từ file HTML đã lưu thay vì tải trang")
    a = ap.parse_args()
    html = Path(a.html).read_text(encoding="utf8") if a.html else neu.fetch()
    recs = records(html)
    if not recs:
        print("Không đọc được bản ghi nào (trang đổi cấu trúc?). Thử lưu trang bằng trình duyệt rồi dùng --html.")
        return 1
    print(f"Đọc được {len(recs)} bản ghi. Các trường:")
    filled, kinds = Counter(), {}
    for r in recs:
        for k, v in r.items():
            kinds.setdefault(k, type(v).__name__)
            if v not in (None, "", [], {}):
                filled[k] += 1
    for k in kinds:
        print(f"  {k:28s} {kinds[k]:8s} có giá trị ở {filled[k]}/{len(recs)}")
    cand = [k for k in kinds if neu.ADVISOR_RE.search(k) and not STUDENT.search(k)]
    print("\nTrường nghi là GVHD:", cand or "không có (có thể GVHD không nằm trong dữ liệu trang này)")
    for k in cand:
        names = []
        for r in recs:
            names += advisors.split_names(r.get(k))
        c = Counter(names)
        print(f"  {k}: {len(c)} giảng viên khác nhau, ví dụ: {', '.join(list(c)[:3])}")
    if cand:
        print(f"\nNếu đúng, đặt ADVISOR_KEY = \"{cand[0]}\" trong ml/thesisdb/neu.py (hoặc để None để tự dò), rồi chạy lại scripts/crawl_neu_thesis.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
