"""Kiểm thử tài khoản theo mã sinh viên: nhập dãy mã, đăng nhập (sinh viên, admin), hồ sơ theo mã, xóa."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from fastapi.testclient import TestClient                    # noqa: E402
    from backend.main import create_app                          # noqa: E402
except ImportError:                                              # chưa cài fastapi: chỉ chạy các test tầng service
    TestClient = create_app = None
from backend.errors import BadRequest, NotFound, Unauthorized    # noqa: E402
from backend.services import account_service as A               # noqa: E402


def root():
    return tempfile.mkdtemp()


def raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    return False


def test_parse_ids():
    rows, bad = A.parse_ids("11200001-11200003\n11205555, Nguyễn An\n11205555\nadmin01,Quản trị,admin\n# ghi chú\nab\n5-3\n")
    ids = [r[0] for r in rows]
    assert ids == ["11200001", "11200002", "11200003", "11205555", "ADMIN01"]          # trùng bị bỏ, dãy được bung
    assert dict((r[0], r[2]) for r in rows)["ADMIN01"] == "admin" and dict((r[0], r[1]) for r in rows)["11205555"] == "Nguyễn An"
    assert len(bad) == 2                                                               # 'ab' quá ngắn, '5-3' dãy ngược
    assert raises(BadRequest, A.parse_ids, "123456", "root")
    rows, bad = A.parse_ids("1-" + "9" * 1)                                            # 1-9 khác độ dài? cùng độ dài 1, hợp lệ nhưng mã ngắn
    assert rows == [] and bad


def test_import_and_list():
    r = root()
    out = A.import_students(r, "11200001-11200010\n99999999,Cô Lan,admin")
    assert out == {"added": 11, "updated": 0, "unchanged": 0, "invalid": []}
    out = A.import_students(r, "11200001,Tên mới\n11200002")                            # nhập lại: chỉ đổi cái khác
    assert out["added"] == 0 and out["updated"] == 1 and out["unchanged"] == 1
    lst = A.list_students(r, "", "", 5, 0)
    assert lst["total"] == 11 and lst["by_role"] == {"admin": 1, "student": 10} and len(lst["items"]) == 5
    assert A.list_students(r, "lan", "", 50, 0)["total"] == 1 and A.list_students(r, "", "admin", 50, 0)["items"][0]["student_id"] == "99999999"
    assert raises(BadRequest, A.import_students, r, "   ")


def test_login_and_state():
    r = root()
    A.import_students(r, "11200001,An\n99999999,Cô Lan,admin")
    assert raises(Unauthorized, A.login, r, "tok", "22209999")                          # sai định dạng (không bắt đầu bằng 11) và không có sẵn
    assert raises(Unauthorized, A.login, r, "tok", "1123619")                           # thiếu số
    assert raises(BadRequest, A.login, r, "tok", "!!")
    new = A.login(r, "tok", "11236197")                                                  # đúng định dạng: tự tạo ở lần đầu
    assert new["status"] == "ok" and new["student"]["role"] == "student" and A.list_students(r, "11236197", "", 5, 0)["total"] == 1
    assert A.login(r, "tok", " 11236197 ")["status"] == "ok" and A.list_students(r, "", "", 50, 0)["total"] == 3
    a = A.login(r, "tok", "11200001")
    assert a["status"] == "ok" and a["student"]["role"] == "student" and a["token"]
    assert A.session(r, a["token"])["student_id"] == "11200001"
    assert A.get_state(r, "11200001")["state"] is None
    A.save_state(r, "11200001", {"skills": ["Python"], "saved": [{"id": "x", "title": "t"}], "welcomed": True, "lạ": 1})
    st = A.get_state(r, "11200001")["state"]
    assert st["skills"] == ["Python"] and "lạ" not in st                                # trường lạ bị bỏ
    assert A.get_state(r, "99999999")["state"] is None                                  # hồ sơ tách riêng từng mã
    assert raises(BadRequest, A.save_state, r, "11200001", {"saved": ["x" * 300000]})
    assert raises(BadRequest, A.save_state, r, "11200001", [1])
    lst = A.list_students(r, "11200001", "", 5, 0)["items"][0]
    assert lst["saved"] == 1 and lst["skills"] == 1 and lst["last_login"]
    A.logout(r, a["token"])
    assert raises(Unauthorized, A.session, r, a["token"]) and raises(Unauthorized, A.session, r, "")


def test_admin_login_same_screen():
    r = root()
    A.import_students(r, "99999999,Cô Lan,admin")
    ok = A.login(r, "", "99999999")                                                     # mã admin có sẵn trong CSDL: vào bằng chính mã đó, không cần mã quản trị
    assert ok["status"] == "ok" and ok["student"]["role"] == "admin" and A.session(r, ok["token"])["role"] == "admin"
    assert raises(Unauthorized, A.login, r, "", "99999998")                             # mã admin không có sẵn thì không tự tạo được
    assert A.login(r, "", "11236197")["student"]["role"] == "student"                   # mã đúng định dạng 11xxxxxx tự tạo là sinh viên


def test_save_student():
    r = root()
    out = A.save_student(r, "11200001", "  Nguyễn   An ", "student", True)
    assert out["name"] == "Nguyễn An" and out["created"]
    assert raises(BadRequest, A.save_student, r, "11200001", "", "student", True)               # thêm trùng mã
    assert raises(NotFound, A.save_student, r, "11299999", "", "student", False)                 # sửa mã không có
    assert raises(BadRequest, A.save_student, r, "11200001", "", "boss", False)                  # quyền lạ
    A.save_student(r, "11200001", "", "student", False)                                          # sửa có thể xóa tên
    assert A.list_students(r, "11200001", "", 5, 0)["items"][0]["name"] == ""
    tk = A.login(r, "", "11200001")["token"]
    A.save_student(r, "11200001", "An", "admin", False)                                          # nâng quyền: phiên cũ bị thu hồi
    assert raises(Unauthorized, A.session, r, tk) and A.login(r, "", "11200001")["student"]["role"] == "admin"
    assert raises(BadRequest, A.save_student, r, "11200001", "An", "student", False)             # admin cuối cùng không hạ quyền được
    assert raises(BadRequest, A.delete_student, r, "11200001")                                   # cũng không xóa được
    A.save_student(r, "11200002", "Bình", "admin", True)
    A.save_student(r, "11200001", "An", "student", False)                                        # có admin khác thì hạ quyền được


def test_delete_cascades():
    r = root()
    A.import_students(r, "11200001")
    tk = A.login(r, "", "11200001")["token"]
    A.save_state(r, "11200001", {"skills": ["SQL"]})
    assert A.delete_student(r, "11200001") == {"deleted": "11200001"}
    assert raises(Unauthorized, A.session, r, tk) and raises(NotFound, A.delete_student, r, "11200001")
    assert A.get_state(r, "11200001")["state"] is None


def test_routes():
    if TestClient is None:
        return
    from backend.settings import Settings
    from tests.test_phase12 import store
    ds = store(False)
    c = TestClient(create_app(ds, Settings(root=str(ds.root), admin_token="tok")))
    H = {"X-Admin-Token": "tok"}
    assert c.get("/admin/students").status_code == 401
    assert c.post("/admin/students/import", json={"text": "11200001-11200003"}, headers=H).json()["added"] == 3
    assert c.post("/auth/login", json={"student_id": "22209999"}).status_code == 401
    assert c.post("/auth/login", json={"student_id": "11236197"}).status_code == 200
    t = c.post("/auth/login", json={"student_id": "11200002"}).json()["token"]
    assert c.get("/me").status_code == 401 and c.get("/me", headers={"X-Student-Token": t}).json()["student_id"] == "11200002"
    c.post("/me/state", json={"state": {"skills": ["Python"]}}, headers={"X-Student-Token": t})
    assert c.get("/me/state", headers={"X-Student-Token": t}).json()["state"]["skills"] == ["Python"]
    assert c.get("/admin/students?q=1120000", headers=H).json()["total"] == 3 and c.get("/admin/students", headers=H).json()["total"] == 4
    # quản trị bằng phiên của mã admin (không cần X-Admin-Token); sinh viên thường bị từ chối
    c.post("/admin/students/import", json={"text": "99999999,Cô Lan,admin"}, headers=H)
    ta = c.post("/auth/login", json={"student_id": "99999999"}).json()["token"]
    assert c.get("/admin/students", headers={"X-Student-Token": ta}).status_code == 200
    assert c.get("/admin/students", headers={"X-Student-Token": t}).status_code == 401
