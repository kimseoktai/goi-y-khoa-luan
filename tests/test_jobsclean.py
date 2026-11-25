import json
import tempfile
from pathlib import Path

from ml.jobsdb import clean, db


def _con():
    return db.connect(":memory:")


def _add(c, sid, title, company="Acme", skills=(), desc="", source="itviec", **kw):
    jid, _ = db.upsert_job(c, f"https://{source}.com/x/{sid}", skills=skills, source=source, sid=str(sid), today="2026-10-18",
                           title_raw=title, company=company, description=desc, **kw)
    return jid


def test_norm_title():
    assert clean.norm_title("[Hà Nội] CV/CVC/CVCC Quản lý dự án") == "CV/CVC/CVCC Quản lý dự án"
    assert clean.norm_title("Business Analyst (Digital Investment) - Khối CNTT (2026TD450181)") == "Business Analyst (Digital Investment) - Khối CNTT"
    assert clean.norm_title("Senior Database Administrator – ID12338") == "Senior Database Administrator"
    assert clean.norm_title("Urgent Middle/Senior AI Engineer") == "Middle/Senior AI Engineer"
    assert clean.norm_title("Lead AI Safety Security Engineer with Joining Bonus") == "Lead AI Safety Security Engineer"


def test_roles_from_real_titles():
    rules, roles = clean.load_role_rules(), clean.known_roles()
    want = {
        "Backend Developer": "Backend Developer",                       # tên vai trò có sẵn (CSV cũ)
        "Chuyên viên lập trình Back-end (Java)": "Backend Developer",
        "Middle UX Designer UI-UX, Android, iOS, Mobile Apps": "UI/UX Designer",
        "Junior/ Senior Full-stack Tester Auto  Manual": "QA/Tester",
        "QC Tester SQL, Jira, ERP, AI": "QA/Tester",
        "Software Development Manager JavaScript, SQL, AI": "Project/Delivery Manager",
        "CV CAO CẤP ỨNG DỤNG TRÍ TUỆ NHÂN TẠO - PHÒNG KIẾN TRÚC VÀ NGHIÊN CỨU GIẢI PHÁP": "AI/ML Engineer",
        "Chuyên viên Phân tích Nghiệp vụ (ERP / Accounting)": "Business Analyst",
        "Technical BA (Nhân viên phân tích nghiệp vụ)": "Business Analyst",
        "[HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA": "Database Administrator",
        "Chuyên viên Quản lý chất lượng dữ liệu - Data Quality Management Specialist": "Data Governance/Quality",
        "Chuyên viên Quản trị rủi ro công nghệ - Senior IT Risks Management Specialist": "IT Risk/Governance/Audit",
        "Kỹ sư dữ liệu (CVCC/Teamlead)": "Data Engineer",
        "CHUYÊN VIÊN PHÂN TÍCH DỮ LIỆU": "Data Analyst",
        "Senior Full Stack Developer .NET / React / Azure": "Fullstack Developer",
        "Front-End Developer PHP, Javascript, HTML, CSS": "Frontend Developer",
        "Unity Game Developer C#": "Game Developer",
        "Embedded Software Engineer – QNX / Automotive": "Embedded Engineer",
        "NetSuite ERP Administrator": "ERP/IT Consultant",
        "Senior Solution Architect - Engineering Golang/ Java": "Solution/System Architect",
        "Infrastructure Engineer Cloud  KY SU HA TANG": "System/Network Engineer",
        "Senior DevOps Engineer": "DevOps/Cloud Engineer",
        "Senior Security Engineer": "Security Engineer",
        "Kỹ sư DevOps": "DevOps/Cloud Engineer",
        "Product Owner - Khối Ngân hàng Số": "Product Owner/Manager",
        "Chuyên viên Công nghệ thông tin (IT Project)": "Project/Delivery Manager",
        "IT Staff": "IT Support/Operations",
        "Senior Software Engineer Remote, Backend/FullStack": "Fullstack Developer"   # Fullstack gồm cả frontend và backend,
    }
    bad = {}
    for t, exp in want.items():
        got, _ = clean.assign_role(clean.norm_title(t), rules, roles)
        if got != exp:
            bad[t] = got
    assert not bad, bad


def test_non_it_titles():
    rules, roles = clean.load_role_rules(), clean.known_roles()
    for t in ["Nhân Viên Kinh Doanh", "Chuyên Viên Kinh Doanh Phần Mềm", "Business Development (Blockchain/Web3)",
              "Chuyên viên Huấn luyện & Đào tạo bên ngoài", "Nhân Viên Media", "Kế toán tổng hợp"]:
        assert clean.assign_role(t, rules, roles)[0] == clean.NON_IT, t
    assert clean.assign_role("Salesforce Developer", rules, roles)[0] != clean.NON_IT


def test_rule_roles_exist():
    roles = clean.known_roles()
    for _, role, _ in clean.load_role_rules():
        assert role == clean.NON_IT or role in roles, role


def test_skill_mapping_and_extraction():
    sd = clean.SkillDict()
    assert sd.canonical("k8s") == "Kubernetes" and sd.canonical("Amazon Web Services") == "AWS"
    assert sd.canonical("Tiếng Anh") is None
    text = "Yêu cầu: Java, Spring Boot, C++ và C#. Biết ReactJS, k8s, Go to market, gửi CV về HR. Kinh nghiệm .NET Core, AWS."
    found = set(sd.extract(text))
    assert {"Kubernetes", "AWS", "C#", ".NET"} <= found, found
    assert "Go" not in found and "Computer Vision" not in found     # 'Go to market', 'CV' không phải kỹ năng
    assert "Java" in found and "JavaScript" not in found           # Java không kéo theo JavaScript


def test_run_cleans_without_touching_raw():
    c = _con()
    a = _add(c, "a", "Backend Developer", skills=["Python", "Django", "SQL", "tiếng anh"], desc="x")
    b = _add(c, "b", "Chuyên viên IT", source="careerviet", desc="Cần biết Python, SQL, Docker, Git và k8s.")
    k = _add(c, "c", "Nhân viên kinh doanh", desc="bán hàng")
    before = [tuple(r) for r in c.execute("SELECT * FROM jobs ORDER BY job_id")], [tuple(r) for r in c.execute("SELECT * FROM job_skills ORDER BY 1,2")]
    st = clean.run(c, now="2026-10-18T00:00:00")
    after = [tuple(r) for r in c.execute("SELECT * FROM jobs ORDER BY job_id")], [tuple(r) for r in c.execute("SELECT * FROM job_skills ORDER BY 1,2")]
    assert before == after                                          # raw nguyên vẹn
    jc = {r["job_id"]: r for r in c.execute("SELECT * FROM jobs_clean")}
    assert jc[a]["is_it"] == 1 and jc[a]["role"] == "Backend Developer"
    assert jc[k]["is_it"] == 0 and jc[k]["reason"] == "non_it_title"
    sk = {(r["job_id"], r["skill"]): r["origin"] for r in c.execute("SELECT * FROM job_skills_clean")}
    assert sk[(a, "Python")] == "listed" and (a, "tiếng anh") not in sk
    assert sk[(b, "Docker")] == "extracted" and sk[(b, "Kubernetes")] == "extracted"
    assert c.execute("SELECT n_jobs FROM skill_unmapped WHERE raw='tiếng anh'").fetchone()[0] == 1
    assert st["jobs"] == 3 and st["non_it"] == 1
    clean.run(c)                                                    # chạy lại không nhân đôi
    assert c.execute("SELECT COUNT(*) FROM jobs_clean").fetchone()[0] == 3
    assert c.execute("SELECT COUNT(*) FROM job_skills_clean").fetchone()[0] == len(sk)


def test_skills_extracted_only_when_few_listed():
    c = _con()
    a = _add(c, "a", "Backend Developer", skills=["Python", "Django", "SQL"], desc="Cũng dùng Docker và Kubernetes")
    clean.run(c)
    got = {r["skill"] for r in c.execute("SELECT skill FROM job_skills_clean WHERE job_id=?", (a,))}
    assert got == {"Python", "Django", "SQL"}                       # đủ 3 thẻ -> không lấy thêm từ mô tả


def test_duplicates_across_sources():
    c = _con()
    t = _add(c, "1", "Backend Developer", company="Công ty TNHH FPT Software", source="topdev")
    i = _add(c, "2", "Backend Developer", company="FPT Software Co., Ltd", source="itviec")
    o = _add(c, "3", "Backend Developer", company="Zalo")
    st = clean.run(c)
    d = {r["job_id"]: r["dup_of"] for r in c.execute("SELECT job_id, dup_of FROM jobs_clean")}
    assert d[t] is None and d[i] == t and d[o] is None and st["dup"] == 1


def test_no_role_needs_tech_skills():
    c = _con()
    a = _add(c, "a", "Chuyên viên tổng hợp", skills=["Python", "Docker", "Git"])
    b = _add(c, "b", "Chuyên viên tổng hợp", company="Other", skills=[])
    clean.run(c)
    r = {x["job_id"]: x for x in c.execute("SELECT * FROM jobs_clean")}
    assert r[a]["is_it"] == 1 and r[a]["role"] == "" and "no_role" in r[a]["flags"]
    assert r[b]["is_it"] == 0


def test_export_csv():
    c = _con()
    a = _add(c, "a", "Backend Developer", skills=["Python", "SQL", "Git"], desc="d" * 60, url_dummy=None) if False else _add(c, "a", "Backend Developer", skills=["Python", "SQL", "Git"], desc="d" * 60)
    _add(c, "k", "Nhân viên kinh doanh", skills=["Python"])
    clean.run(c)
    out = Path(tempfile.mkdtemp()) / "o.csv"
    assert clean.export_csv(c, out) == 1
    import csv
    rows = list(csv.DictReader(open(out, encoding="utf-8-sig")))
    assert rows[0]["job_title"] == "Backend Developer" and json.loads(rows[0]["skills"]) == ["Git", "Python", "SQL"]


def test_core_text_drops_benefits_and_meta():
    d = ("Top 3 Reasons To Join Us\nThe Job\n- Xây dựng API\nYour Skills and Experience\n- Biết Python\nWhy You'll Love Working Here\n"
         "- Bảo hiểm sức khỏe cao cấp\n- Môi trường làm việc trẻ\n")
    core = clean.core_text(d)
    assert "Xây dựng API" in core and "Biết Python" in core and "sức khỏe" not in core and "Môi trường" not in core
    cv = "- Plan audits\nQuyền lợi:\n- Khám sức khỏe định kì\nYêu cầu:\n- Hiểu ngân hàng\n Ngành nghề: CNTT - Phần mềm, Tài chính\n Kinh nghiệm: 3 Năm"
    core = clean.core_text(cv)
    assert "Plan audits" in core and "Hiểu ngân hàng" in core and "Khám sức khỏe" not in core and "Ngành nghề" not in core and "Kinh nghiệm" not in core
    assert "Chăm sóc" not in clean.core_text("Việc A\nChăm sóc sức khỏe toàn diện cho nhân viên", "Chăm sóc sức khỏe toàn diện cho nhân viên")


def test_export_uses_core_text():
    c = _con()
    _add(c, "a", "Backend Developer", skills=["Python", "SQL", "Git"], desc="Việc chính\nWhy You'll Love Working Here\n- Bảo hiểm sức khỏe")
    clean.run(c)
    out = Path(tempfile.mkdtemp()) / "o.csv"
    clean.export_csv(c, out)
    import csv
    r = list(csv.DictReader(open(out, encoding="utf-8-sig")))[0]
    assert "Việc chính" in r["description"] and "sức khỏe" not in r["description"]


def test_generic_skills_not_written():
    c = _con()
    jid = _add(c, 1, "Backend Developer", skills=["Python", "AI", "Database"])
    clean.run(c)
    got = {r[0] for r in c.execute("SELECT skill FROM job_skills_clean WHERE job_id=?", (jid,))}
    assert "Python" in got and not ({"AI", "Database"} & got)
    assert "AI" not in {r[0] for r in c.execute("SELECT raw FROM skill_unmapped")}
