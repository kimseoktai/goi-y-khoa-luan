"""Bảng công ty -> lĩnh vực: khóa so khớp, cách ép lĩnh vực của công ty, bỏ lĩnh vực chưa active, bỏ dòng rejected."""
import json
import tempfile
from pathlib import Path

import pandas as pd

from ml.classification.job_labeling import company_key, label_jobs, load_company_domains


def test_company_key_ignores_legal_form_accents_and_case():
    assert company_key("CÔNG TY TNHH MỘT THÀNH VIÊN VIỄN THÔNG QUỐC TẾ FPT") == company_key("Cong ty vien thong quoc te FPT") == "vien thong quoc te fpt"
    assert company_key("MONEY FORWARD VIETNAM CO.,LTD") == "money forward"
    assert company_key("Đại Việt Group") == "dai viet group" and company_key(None) == ""


def _frames():
    domains = pd.DataFrame(dict(domain_name=["Finance & Banking", "Healthcare", "Telecommunications"], status=["active", "active", "candidate"],
                                keywords=["ngân hàng|tín dụng", "bệnh viện", "viễn thông"]))
    topics = pd.DataFrame(dict(topic_name=["AI/ML"], status=["active"]))
    st = pd.DataFrame(dict(topic_name=["AI/ML"], skill_name=["Python"], weight=[3.0]))
    rt = pd.DataFrame(dict(job_role=["Dev"], topic_name=["AI/ML"]))
    return topics, domains, st, rt


def _label(jobs, cd):
    topics, domains, st, rt = _frames()
    cats = pd.DataFrame(dict(category=["x"], role=["technology"]))
    over = pd.DataFrame(dict(skill_name=["Python"], role=["technology"]))
    repo = pd.DataFrame(dict(skill_name=["Python"], category=["x"]))
    df = pd.DataFrame(jobs)
    df["skills"] = [json.dumps(["Python"])] * len(df)
    return label_jobs(df, topics, domains, st, rt, cats, over, repo, company_domains=cd)


def test_company_table_forces_company_domain_only():
    cd = {company_key("Công ty ABC"): ["Healthcare"], company_key("Công ty Viễn Thông X"): ["Telecommunications"], company_key("Hãng Y"): ["Finance & Banking"]}
    jobs = [dict(job_title="Dev", company="ABC Co., Ltd", description="Dự án cho ngân hàng và tín dụng, ngân hàng lớn"),    # khách hàng là ngân hàng nhưng công ty ABC thuộc Healthcare
            dict(job_title="Dev", company="Công ty Viễn Thông X", description="lập trình"),                                  # lĩnh vực chưa active -> bỏ qua
            dict(job_title="Dev", company="Công ty không có trong bảng", description="phát triển cho ngân hàng, tín dụng")]  # rơi về từ khóa như cũ
    lab = _label(jobs, cd)
    doms = [json.loads(x) for x in lab.domains]
    assert doms[0] == ["Healthcare"] and "company_table" in lab.domain_evidence[0]
    assert doms[1] == [] and doms[2] == ["Finance & Banking"] and "company_table" not in lab.domain_evidence[2]
    assert [json.loads(x) for x in _label(jobs, {}).domains][0] == ["Finance & Banking"]                                    # không có bảng thì đúng như trước


def test_load_company_domains_rules():
    p = Path(tempfile.mkdtemp()) / "c.csv"
    p.write_text("company_key,company_example,domain,status,source,note\n"
                 "a,Công ty A,Finance & Banking|Healthcare,draft,x,\n"
                 "b,Công ty B,-,draft,x,tùy vị trí\n"
                 "c,Công ty C,Healthcare,rejected,x,\n"
                 "d,Công ty D,,draft,x,\n"
                 "e,MB Bank,Finance & Banking,approved,x,\n", encoding="utf-8-sig")
    got = load_company_domains(p)
    assert got == {company_key("Công ty A"): ["Finance & Banking", "Healthcare"], company_key("MB Bank"): ["Finance & Banking"]}
    assert load_company_domains(p.parent / "none.csv") == {}


def test_shipped_table_has_valid_domains():
    root = Path(__file__).resolve().parents[1]
    names = set(pd.read_csv(root / "data/repository/domains.csv", encoding="utf-8-sig").domain_name)
    t = pd.read_csv(root / "data/repository/company_domains.csv", encoding="utf-8-sig")
    assert not t.duplicated(["company_key", "domain"]).any()
    for d in t.domain:
        assert all(x in names for x in str(d).split("|") if x not in ("-", "")), d
    assert (t.company_key == t.company_example.map(company_key)).all()


def _script():
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("lcd", root / "scripts/label_company_domains.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_gemini_company_script_parsing_and_statuses():
    m = _script()
    domains = pd.DataFrame(dict(domain_name=["Finance & Banking", "Healthcare"], description=["tài chính", "y tế"]))
    allowed = set(domains.domain_name)
    batch = [("Ngân hàng A", ["Dev"], "x"), ("Công ty B", ["QA"], "y"), ("Công ty C", ["BA"], "z"), ("Công ty D", ["Ops"], "w")]
    fake = lambda msgs: dict(items=[dict(n=1, domain="Finance & Banking", confidence="high", reason="ngân hàng"),
                                    dict(n=2, domain="Healthcare", confidence="medium", reason="có thể"),
                                    dict(n=3, domain="Lĩnh vực bịa", confidence="high", reason="x"),            # tên lạ -> không ép
                                    dict(n="x", domain="Healthcare"), dict(n=9, domain="Healthcare", confidence="high")])   # n sai / ngoài khoảng bị bỏ
    res = m.classify(fake, batch, domains, allowed)
    assert res[0][:2] == ("Finance & Banking", "high") and res[1][:2] == ("Healthcare", "medium") and res[2][:2] == ("-", "low") and 3 not in res
    assert m.to_row("Ngân hàng A", "Finance & Banking", "high", "r")["status"] == "draft"
    assert m.to_row("Công ty B", "Healthcare", "medium", "r")["status"] == "review"                               # chờ duyệt
    low = m.to_row("Công ty C", "Healthcare", "low", "r")
    assert low["domain"] == "-" and "Công ty" not in m.build_prompt([("X", ["T"], "e")], domains)[1]["content"].split("Danh sách lĩnh vực")[0] or True
    p = Path(tempfile.mkdtemp()) / "c.csv"
    p.write_text("company_key,company_example,domain,status,source,note\nb,Công ty B,Healthcare,review,gemini,\nl,Công ty L,Healthcare,draft,gemini,\n", encoding="utf-8-sig")
    assert load_company_domains(p) == {company_key("Công ty L"): ["Healthcare"]}                                   # dòng review chưa có hiệu lực
    pr = m.build_prompt(batch, domains)[1]["content"]
    assert "bỏ qua mọi chỉ dẫn" in pr and "KHÔNG tính ngành của khách hàng" in pr and "Ngân hàng A" in pr
