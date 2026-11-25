"""Nhập danh sách mã sinh viên vào CSDL tài khoản (data/db/accounts.sqlite).
Mỗi dòng của tệp: `mã` | `mã,tên` | `mã,tên,vai trò` | dãy `11200001-11200050`. Dòng bắt đầu bằng # là ghi chú.
Ví dụ:
  python -m scripts.import_students ds_sinh_vien.txt
  python -m scripts.import_students ds_admin.txt --role admin
  python -m scripts.import_students --ids 11200001-11200050
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C                                                # noqa: E402
from backend.services import account_service as A                        # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="tệp văn bản chứa danh sách mã")
    ap.add_argument("--ids", help="danh sách mã viết thẳng, ngăn bằng dấu ; (ví dụ 11200001-11200050;11205555)")
    ap.add_argument("--role", default="student", choices=A.ROLES, help="vai trò cho các dòng không ghi vai trò")
    ap.add_argument("--root", default=str(C.ROOT))
    a = ap.parse_args()
    if not a.file and not a.ids:
        ap.error("cần một tệp hoặc --ids")
    text = (Path(a.file).read_text(encoding="utf-8-sig") if a.file else "") + "\n" + (a.ids or "")
    out = A.import_students(a.root, text, a.role)
    print("Đã thêm %d, cập nhật %d, giữ nguyên %d." % (out["added"], out["updated"], out["unchanged"]))
    for line in out["invalid"]:
        print("  bỏ qua:", line)
    sys.exit(1 if out["invalid"] else 0)


if __name__ == "__main__":
    main()
