"""Tầng sạch (clean) cho CSDL tin tuyển dụng.

Đọc bảng raw (jobs, job_skills) và GHI SANG bảng riêng, không sửa raw:
  jobs_clean(job_id, title_norm, role, is_it, reason, n_skills, dup_of, flags, ...)
  job_skills_clean(job_id, skill, origin)      origin: listed (thẻ của trang) | extracted (tìm trong mô tả)
  skill_unmapped(raw, n_jobs)                  thẻ kỹ năng chưa có trong skills.csv, để xét có nên thêm vào repository không
Chạy lại bao nhiêu lần cũng được (xây lại toàn bộ từ raw + quy tắc). Quy tắc nằm trong data/repository:
  skills.csv (tên + alias), title_role_rules.csv (tiêu đề -> vai trò), skill_category_roles.csv + skill_role_overrides.csv.
"""
import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from ml import config as C

R = C.ROOT / "data/repository"
RULES_VERSION = "clean_v1.1"
MIN_LISTED = 3            # tin có ít hơn N kỹ năng khớp từ thẻ thì bổ sung bằng cách tìm trong mô tả
MIN_TECH_SKILLS = 3       # không rõ vai trò nhưng có >= N kỹ năng công nghệ thì vẫn coi là việc CNTT
NON_IT = "!non_it"
SKIP_TEXT_TERMS = {"go", "r", "c", "cv"}                     # quá dễ trùng từ thường khi tìm trong mô tả (vẫn nhận nếu là thẻ của trang)
SOURCE_PRIORITY = {"topdev": 0, "itviec": 1, "careerviet": 2}  # tin trùng giữa các nguồn: giữ bản của nguồn đứng trước

CLEAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs_clean (
  job_id INTEGER PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
  title_norm TEXT, role TEXT, description_core TEXT, is_it INTEGER NOT NULL, reason TEXT,
  n_skills INTEGER NOT NULL DEFAULT 0, dup_of INTEGER, flags TEXT,
  rules_version TEXT, cleaned_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_jc_role ON jobs_clean(role);
CREATE TABLE IF NOT EXISTS job_skills_clean (
  job_id INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
  skill TEXT NOT NULL, origin TEXT NOT NULL,
  PRIMARY KEY (job_id, skill)
);
CREATE INDEX IF NOT EXISTS ix_jsc_skill ON job_skills_clean(skill);
CREATE TABLE IF NOT EXISTS skill_unmapped (raw TEXT PRIMARY KEY, n_jobs INTEGER NOT NULL);
"""


def fold(text):
    """Chữ thường, bỏ dấu tiếng Việt: để một quy tắc khớp cả 'Kỹ sư hạ tầng' lẫn 'KY SU HA TANG'."""
    t = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(ch for ch in t if unicodedata.category(ch) != "Mn")).strip()


def norm_title(title):
    t = unicodedata.normalize("NFC", title or "")
    t = re.sub(r"^\s*\[[^\]]*\]\s*", "", t)                                   # [Hà Nội] ...
    t = re.sub(r"\(\s*[A-Za-z]*\d{3,}[A-Za-z0-9]*\s*\)", " ", t)             # (2026TD450181)
    t = re.sub(r"[-–—]\s*ID\s*\d+\s*$", " ", t, flags=re.I)                   # - ID12338
    t = re.sub(r"\b(with\s+)?joining\s+bonus\b|\burgent\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" -–—,")


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- nội dung công việc (bỏ phúc lợi, thông tin phụ)
_BENEFIT_HEADS = {"why you'll love working here", "why youll love working here", "top 3 reasons to join us", "quyen loi", "quyen loi duoc huong",
                  "phuc loi", "che do phuc loi", "benefits", "our benefits", "what we offer", "why join us", "what you will get", "ban se nhan duoc",
                  "moi truong lam viec", "tai sao ban nen gia nhap"}
_OTHER_HEADS = {"the job", "your skills and experience", "key responsibilities", "responsibilities", "requirements", "about the role", "nice to have",
                "preferred qualifications", "job description", "mo ta cong viec", "yeu cau cong viec", "yeu cau", "yeu cau ung vien", "thong tin khac",
                "about us", "gioi thieu cong ty", "qualifications", "what you will do", "ban se lam gi"}
_META_LINE = re.compile(r"^\s*(nganh nghe|kinh nghiem|cap bac|hinh thuc|dia diem|muc luong|han nop)\s*:", re.I)


def _head(line):
    return re.sub(r"[^a-z0-9' ]", " ", fold(line)).strip().rstrip(":").strip()


def core_text(description, benefits=""):
    """Phần mô tả công việc/yêu cầu, bỏ các mục phúc lợi và dòng thông tin phụ (Ngành nghề, Cấp bậc...). Dùng để gán lĩnh vực:
    nếu để cả phúc lợi thì 'bảo hiểm sức khỏe', 'môi trường làm việc', 'tiếng Anh' làm tin nào cũng bị gán Healthcare/Environment/Education."""
    ben_lines = {fold(x).strip(" -•*") for x in (benefits or "").split("\n") if len(x.strip()) > 8}
    out, skipping = [], False
    for line in (description or "").split("\n"):
        h = re.sub(r"\s+", " ", _head(line))
        if h in _BENEFIT_HEADS:
            skipping = True
            continue
        if h in _OTHER_HEADS:
            skipping = False
            continue
        if skipping or _META_LINE.match(fold(line)) or fold(line).strip(" -•*") in ben_lines:
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# ---------------------------------------------------------------- vai trò
def load_role_rules(path=None):
    rules = []
    for r in sorted(_read(path or R / "title_role_rules.csv"), key=lambda r: int(r["priority"])):
        rules.append((int(r["priority"]), r["role"], re.compile(r["pattern"])))
    return rules


def known_roles(path=None):
    """Mọi vai trò đã biết: bảng vai trò->topic và các vai trò (con/cha) trong role_groups.csv."""
    roles = {r["job_role"] for r in _read(path or R / "job_role_topic_map.csv")}
    if path is None and (R / "role_groups.csv").exists():
        for r in _read(R / "role_groups.csv"):
            roles |= {x for x in (r["role"], r["parent_role"]) if x}
    return roles


def assign_role(title_norm, rules, roles):
    """Trả về (role, lý do). role='!non_it' nếu rõ ràng không phải CNTT; '' nếu không xác định được."""
    f = fold(title_norm)
    first = [r for r in rules if r[0] <= 1]                       # quy tắc ưu tiên cao (Business Analyst, không phải CNTT) xét trước tên vai trò có sẵn
    for prio, role, rx in first:
        if rx.search(f):
            return role, f"rule{prio}"
    for role in roles:                                            # tiêu đề đã chính là tên vai trò (dữ liệu nhập từ CSV cũ)
        if f == fold(role):
            return role, "exact"
    for prio, role, rx in rules:
        if prio > 1 and rx.search(f):
            return role, f"rule{prio}"
    return "", "no_rule"


# ---------------------------------------------------------------- kỹ năng
class SkillDict:
    def __init__(self, skills_csv=None, cat_roles_csv=None, overrides_csv=None, generic_csv=None):
        rows = _read(skills_csv or R / "skills.csv")
        gp = generic_csv or (R / "skill_generic.csv" if skills_csv is None else None)
        self.generic = {r["skill_name"] for r in _read(gp)} if gp and Path(gp).exists() else set()   # khái niệm chung (AI, Database...): không ghi vào job_skills_clean, một nguồn cho phân tích và màn chọn của sinh viên
        self.names = [r["skill_name"] for r in rows]
        self.by_fold = {}                                         # tên/alias (đã fold) -> tên chuẩn
        tag_file = R / "skill_tag_aliases.csv"
        self.text_terms = []                                      # (tên chuẩn, regex) để tìm trong mô tả
        for r in rows:
            terms = [r["skill_name"]] + [a for a in (r.get("aliases") or "").split("|") if a.strip()]
            for t in terms:
                self.by_fold.setdefault(fold(t), r["skill_name"])
            pats = []
            for t in terms:
                if t.lower() in SKIP_TEXT_TERMS:
                    continue
                case_sens = len(t) <= 2 and t.replace(".", "").isalpha() and t.upper() == t or t.lower() in {"spring", "swift", "rust", "ruby", "flask", "express", "node", "unity"}
                pats.append((re.escape(t), case_sens, t))
            if pats:
                self.text_terms.append((r["skill_name"], pats))
        if skills_csv is None and tag_file.exists():              # thẻ của trang tuyển dụng đồng nghĩa với kỹ năng chuẩn (file riêng, không sửa skills.csv đã duyệt)
            for r in _read(tag_file):
                if r["skill_name"] in self.names:
                    self.by_fold.setdefault(fold(r["tag"]), r["skill_name"])
        cat_role = {r["category"]: r["role"] for r in _read(cat_roles_csv or R / "skill_category_roles.csv")}
        over = {r["skill_name"]: r["role"] for r in _read(overrides_csv or R / "skill_role_overrides.csv")}
        self.tech = {r["skill_name"] for r in rows if (over.get(r["skill_name"]) or cat_role.get(r["category"], "competency")) == "technology"}
        self._rx = {}

    def canonical(self, raw):
        return self.by_fold.get(fold(raw))

    def _compiled(self, name, pats):
        if name not in self._rx:
            ci = [p for p, cs, _ in pats if not cs]
            cs = [p for p, c, _ in pats if c]
            b, a = r"(?<![A-Za-z0-9+#])", r"(?![A-Za-z0-9+#]|\.[A-Za-z0-9])"
            self._rx[name] = (re.compile(b + "(?:" + "|".join(ci) + ")" + a, re.I) if ci else None,
                              re.compile(b + "(?:" + "|".join(cs) + ")" + a) if cs else None)
        return self._rx[name]

    def extract(self, text):
        found = []
        for name, pats in self.text_terms:
            ci, cs = self._compiled(name, pats)
            if (ci and ci.search(text)) or (cs and cs.search(text)):
                found.append(name)
        return found


# ---------------------------------------------------------------- trùng giữa các nguồn
_COMPANY_NOISE = re.compile(r"\b(cong ty|tap doan|co phan|tnhh|trach nhiem huu han|jsc|joint stock|company|co|ltd|limited|corp|corporation|inc|vietnam|viet nam|vn|chi nhanh)\b")


def dup_key(company, title_norm):
    c = _COMPANY_NOISE.sub(" ", re.sub(r"[^a-z0-9 ]", " ", fold(company)))
    t = re.sub(r"[^a-z0-9 ]", " ", fold(title_norm))
    c, t = re.sub(r"\s+", " ", c).strip(), re.sub(r"\s+", " ", t).strip()
    return (c, t) if c and t else None


# ---------------------------------------------------------------- chạy
def run(con, rules=None, roles=None, skill_dict=None, now=None):
    """Xây lại jobs_clean / job_skills_clean / skill_unmapped từ raw. Trả về dict thống kê."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(jobs_clean)")]
    if cols and "description_core" not in cols:                   # bảng sạch bản cũ: dữ liệu suy ra từ raw nên tạo lại được
        con.execute("DROP TABLE jobs_clean")
    con.executescript(CLEAN_SCHEMA)
    rules = rules or load_role_rules()
    roles = roles or known_roles()
    sd = skill_dict or SkillDict()
    now = now or datetime.now().isoformat(timespec="seconds")
    raw_skills = {}
    for r in con.execute("SELECT job_id, skill FROM job_skills"):
        raw_skills.setdefault(r["job_id"], []).append(r["skill"])
    rows, skill_rows, unmapped, keys = [], [], {}, {}
    for j in con.execute("SELECT job_id, source, title_raw, company, description, requirements, benefits, first_seen FROM jobs ORDER BY job_id"):
        jid = j["job_id"]
        title = norm_title(j["title_raw"])
        core = core_text(j["description"], j["benefits"])
        listed, seen_u = [], set()
        for s in raw_skills.get(jid, []):
            c = sd.canonical(s)
            if c:
                if c not in listed:
                    listed.append(c)
            elif fold(s) not in seen_u:
                seen_u.add(fold(s))
                unmapped[s.strip()] = unmapped.get(s.strip(), 0) + 1
        extracted = []
        if len(listed) < MIN_LISTED:
            text = " ".join(x for x in (j["title_raw"], core, j["requirements"]) if x)
            extracted = [s for s in sd.extract(text) if s not in listed]
        skills_all = [(s, "listed") for s in listed] + [(s, "extracted") for s in extracted]
        skills = [x for x in skills_all if x[0] not in sd.generic]
        role, why = assign_role(title, rules, roles)
        flags = []
        n_tech = sum(1 for s, _ in skills_all if s in sd.tech)         # đếm trước khi bỏ khái niệm chung để không đổi kết quả lọc CNTT
        if role == NON_IT:
            is_it, role, reason = 0, "", "non_it_title"
        elif role:
            is_it, reason = 1, why
        elif n_tech >= MIN_TECH_SKILLS:
            is_it, reason = 1, "no_role_but_tech_skills"
            flags.append("no_role")
        else:
            is_it, reason = 0, "no_role_few_skills"
            flags.append("no_role")
        if is_it and not skills:
            flags.append("no_skills")
        if not (j["description"] or "").strip():
            flags.append("no_description")
        rows.append([jid, title, role, core, is_it, reason, len(skills), None, "|".join(flags), RULES_VERSION, now])
        skill_rows += [(jid, s, o) for s, o in skills]
        k = dup_key(j["company"], title)
        if k and is_it:
            keys.setdefault(k, []).append((SOURCE_PRIORITY.get(j["source"], 9), j["first_seen"] or "", jid))
    dup_of = {}
    for members in keys.values():
        if len(members) > 1:
            keep = sorted(members)[0][2]
            for _, _, jid in members:
                if jid != keep:
                    dup_of[jid] = keep
    for r in rows:
        r[7] = dup_of.get(r[0])
    with con:                                                    # một giao dịch: đọc không bao giờ thấy trạng thái nửa vời
        con.execute("DELETE FROM job_skills_clean")
        con.execute("DELETE FROM jobs_clean")
        con.execute("DELETE FROM skill_unmapped")
        con.executemany("INSERT INTO jobs_clean (job_id,title_norm,role,description_core,is_it,reason,n_skills,dup_of,flags,rules_version,cleaned_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO job_skills_clean (job_id,skill,origin) VALUES (?,?,?)", skill_rows)
        con.executemany("INSERT INTO skill_unmapped (raw,n_jobs) VALUES (?,?)", list(unmapped.items()))
    return dict(jobs=len(rows), it=sum(r[4] for r in rows), non_it=sum(1 for r in rows if not r[4]), dup=len(dup_of),
                no_role=sum(1 for r in rows if "no_role" in r[8]), unmapped=len(unmapped))


def export_csv(con, out, only_active=True):
    """Xuất đúng dạng đầu vào của Phase 7 (job_id, job_title=vai trò, description, skills JSON, company, url) kèm vài cột phụ.
    Chỉ lấy tin CNTT, không phải bản trùng. Cột description là phần nội dung công việc (đã bỏ phúc lợi)."""
    where = "c.is_it=1 AND c.dup_of IS NULL" + (" AND j.status='active'" if only_active else "")
    q = f"""SELECT j.job_id, c.role AS job_title, c.description_core AS description, j.company, j.url, j.source, j.status, j.posted_at, j.deadline, j.location, j.first_seen, c.title_norm
            FROM jobs j JOIN jobs_clean c USING(job_id) WHERE {where} AND c.role<>'' ORDER BY j.job_id"""
    sk = {}
    for r in con.execute("SELECT job_id, skill FROM job_skills_clean ORDER BY skill"):
        sk.setdefault(r["job_id"], []).append(r["skill"])
    n = 0
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["job_id", "job_title", "description", "skills", "company", "url", "source", "status", "posted_at", "deadline", "location", "first_seen", "title_norm"])
        for r in con.execute(q):
            if not sk.get(r["job_id"]):
                continue
            w.writerow([r["job_id"], r["job_title"], r["description"] or "", json.dumps(sk[r["job_id"]], ensure_ascii=False),
                        r["company"] or "Unknown", r["url"], r["source"], r["status"], r["posted_at"], r["deadline"], r["location"], r["first_seen"], r["title_norm"]])
            n += 1
    return n
