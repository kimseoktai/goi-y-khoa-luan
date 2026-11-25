"""Chức năng quản trị: chạy lệnh nền (crawl, dựng dữ liệu, embedding, test), đọc log, chỉ số dữ liệu, duyệt bảng công ty -> lĩnh vực.

An toàn: chỉ chạy các lệnh trong TASKS (không nhận tham số từ người dùng), mỗi lúc chỉ một lệnh, log chỉ đọc trong thư mục logs/.
"""
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from backend.errors import BadRequest, NotFound
from ml.classification.job_labeling import company_key

TASKS = {
    "crawl_all": ("Crawl 3 nguồn tuyển dụng + khóa luận NEU, dựng dữ liệu website", ["scripts/crawl_all.py"]),
    "crawl_jobs": ("Crawl tin tuyển dụng (3 nguồn, không gồm khóa luận)", ["scripts/crawl_all.py", "--skip", "neu_thesis", "--skip", "thesis", "--skip", "site"]),
    "jobs_flow": ("Chạy cả luồng tin tuyển dụng (crawl, dựng dữ liệu, embedding)", ["scripts/run_jobs_flow.py"]),
    "crawl_thesis": ("Crawl khóa luận NEU (thêm mới, đóng cái đã gỡ)", ["scripts/crawl_neu_thesis.py"]),
    "build_thesis": ("Làm sạch + gắn nhãn khóa luận (bỏ qua nếu không đổi)", ["scripts/build_thesis_data.py"]),
    "build_site": ("Xử lý + dựng dữ liệu website (không crawl)", ["scripts/build_site_data.py"]),
    "embeddings": ("Dựng embedding cho tin tuyển dụng", ["scripts/build_site_data.py", "--embeddings"]),
    "tests": ("Chạy kiểm thử (pytest)", ["-m", "pytest", "-q"]),
}
LOG_RE = re.compile(r"^[\w.\-]+\.log$")
COMPANY_FILE = "data/repository/company_domains.csv"
COMPANY_COLS = ["company_key", "company_example", "domain", "status", "source", "note"]
COMPANY_STATUSES = ("draft", "review", "approved", "rejected")
SCHEDULE_TASK = "RecCrawlWeekly"


# ---------------------------------------------------------------- chạy lệnh nền
class Runner:
    """Chạy một lệnh nền tại một thời điểm; log ghi vào logs/admin_<lệnh>_<thời gian>.log, dòng cuối '[exit <mã>]'."""

    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.Lock()
        self.proc = None
        self.task = None
        self.log_name = None
        self.started = None
        self.code = None
        self.stopped = False

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, task):
        if task not in TASKS:
            raise BadRequest("lệnh không có trong danh sách: " + str(task))
        with self.lock:
            if self.running():
                raise BadRequest(f"đang chạy '{TASKS[self.task][0]}'; đợi xong hoặc bấm Dừng")
            logs = self.root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            self.task, self.code, self.stopped = task, None, False
            self.started = time.time()
            self.log_name = f"admin_{task}_{datetime.now():%Y%m%d_%H%M%S}.log"
            argv = TASKS[task][1]
            argv = [sys.executable] + ([str(self.root / argv[0])] + argv[1:] if not argv[0].startswith("-") else argv)
            log = open(logs / self.log_name, "w", encoding="utf-8", errors="replace")
            log.write(f"[{datetime.now():%H:%M:%S}] {TASKS[task][0]}\n"); log.flush()
            self.proc = subprocess.Popen(argv, cwd=self.root, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            threading.Thread(target=self._wait, args=(self.proc, log), daemon=True).start()
        return self.status()

    def _wait(self, proc, log):
        code = proc.wait()
        self.code = code
        log.write(f"\n[{datetime.now():%H:%M:%S}] [exit {code}]{' (đã dừng)' if self.stopped else ''}\n")
        log.close()

    def stop(self):
        if not self.running():
            raise BadRequest("không có lệnh nào đang chạy")
        self.stopped = True
        if os.name == "nt":                                   # kết thúc cả cây tiến trình (crawl_all sinh ra các crawler con)
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
        else:
            self.proc.terminate()
        return self.status()

    def status(self, tail=200):
        if self.task is None:
            return {"running": False, "task": None, "label": None, "log": None, "code": None, "elapsed": None, "tail": ""}
        run = self.running()
        return {"running": run, "task": self.task, "label": TASKS[self.task][0], "log": self.log_name, "code": None if run else self.code,
                "elapsed": int(time.time() - self.started) if run else None, "tail": read_log(self.root, self.log_name, tail)}


# ---------------------------------------------------------------- log
def list_logs(root, limit=40):
    d = Path(root) / "logs"
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        t = _tail_text(p, 2000)
        m = re.findall(r"\[exit (-?\d+)\]", t)
        ok = None
        if m:
            ok = m[-1] == "0"
        elif "=== Kết thúc: tất cả thành công" in t:
            ok = True
        elif "=== Kết thúc: có lỗi" in t:
            ok = False
        out.append({"name": p.name, "size": p.stat().st_size, "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"), "ok": ok})
    return out


def _tail_text(p, n_chars):
    with open(p, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - n_chars))
        return f.read().decode("utf-8", errors="replace")


def read_log(root, name, tail=300):
    if not name or not LOG_RE.match(name):
        raise BadRequest("tên log không hợp lệ")
    p = Path(root) / "logs" / name
    if not p.is_file():
        raise NotFound("không có log " + name)
    lines = _tail_text(p, 200_000).splitlines()
    return "\n".join(lines[-max(1, min(int(tail), 2000)):])


# ---------------------------------------------------------------- chỉ số
BATCH_GAP_MIN = 20          # hai lần crawl của các nguồn cách nhau dưới này phút thì thuộc cùng một lần chạy lệnh (crawl_all chạy lần lượt 3 nguồn)


def group_runs(runs, max_batches=8, gap_min=BATCH_GAP_MIN):
    """Gom các dòng crawl_runs (mới nhất trước) thành từng lần chạy lệnh; trả về tối đa max_batches lần, mới nhất trước."""
    def t(r):
        try:
            return datetime.fromisoformat(str(r["started_at"]).replace(" ", "T"))
        except ValueError:
            return datetime.min
    batches, cur, last = [], [], None
    for r in sorted(runs, key=t):                           # cũ -> mới, cắt khi khoảng cách giữa hai lần lớn hơn ngưỡng
        if cur and (t(r) - last).total_seconds() > gap_min * 60:
            batches.append(cur); cur = []
        cur.append(r); last = t(r)
    if cur:
        batches.append(cur)
    out = []
    for b in reversed(batches[-max_batches:]):
        out.append({"started_at": b[0]["started_at"], "finished_at": max((x["finished_at"] or x["started_at"]) for x in b), "ok": all(x["ok"] for x in b),
                    "n_seen": sum(x["n_seen"] or 0 for x in b), "n_new": sum(x["n_new"] or 0 for x in b), "n_closed": sum(x["n_closed"] or 0 for x in b), "runs": b})
    return out


def _db_metrics(root):
    p = Path(root) / "data/db/jobs.sqlite"
    if not p.exists():
        return None
    con = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        q = lambda sql: [dict(r) for r in con.execute(sql).fetchall()]
        by_source = q("SELECT source, COUNT(*) AS total, SUM(status='active') AS active, SUM(first_seen >= date('now','-7 day')) AS new_7d, MAX(last_seen) AS last_seen "
                      "FROM jobs WHERE is_it=1 GROUP BY source ORDER BY total DESC")
        daily = q("SELECT substr(first_seen,1,10) AS day, COUNT(*) AS n FROM jobs WHERE is_it=1 AND first_seen >= date('now','-14 day') GROUP BY day ORDER BY day")
        runs = q("SELECT source, started_at, finished_at, n_seen, n_new, n_closed, ok, note FROM crawl_runs ORDER BY run_id DESC LIMIT 90")
        return {"by_source": by_source, "daily_new": daily, "recent_batches": group_runs(runs)}
    finally:
        con.close()


def _coverage(ds):
    j = ds.jobs
    n = len(j)
    has = lambda col: int(j[col].map(lambda v: bool(v)).sum()) if col in j else 0
    forced = int(j["_domain_evidence"].map(lambda e: any(isinstance(v, dict) and v.get("company_table") for v in e.values()) if isinstance(e, dict) else False).sum()) if "_domain_evidence" in j else 0
    return {"jobs": n, "with_domain": has("_domains"), "with_topic": has("_technical_topics"), "with_skill": has("_skills"), "domain_from_company_table": forced,
            "source": ds.jobs_source, "embeddings": ds.has_embeddings(), "embeddings_filled": sum(ds.filled.values()) if ds.filled else 0}


def _schedule():
    """Trạng thái lịch RecCrawlWeekly của Windows Task Scheduler (chỉ có trên Windows)."""
    if os.name != "nt":
        return {"available": False, "note": "chỉ đọc được lịch trên Windows"}
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", SCHEDULE_TASK, "/fo", "LIST", "/v"], capture_output=True, text=True, timeout=10, errors="replace")
    except Exception as e:
        return {"available": False, "note": str(e)}
    if r.returncode != 0:
        return {"available": False, "note": "chưa có lịch " + SCHEDULE_TASK}
    d = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip().lower()] = v.strip()
    pick = lambda *ks: next((d[k] for k in ks if k in d), "")
    if not pick("status", "trạng thái"):                    # Windows ngôn ngữ khác: không nhận ra tên cột, trả vài dòng gốc để người dùng đọc
        return {"available": False, "note": "Có lịch " + SCHEDULE_TASK + " nhưng không đọc được chi tiết: " + " | ".join(r.stdout.split("\n")[:6])[:300]}
    return {"available": True, "status": pick("status", "trạng thái"), "next_run": pick("next run time", "thời gian chạy kế tiếp"),
            "last_run": pick("last run time", "thời gian chạy lần cuối"), "last_result": pick("last result", "kết quả lần chạy cuối")}


def overview(ds):
    comp = _read_companies(ds.root)
    counts = comp["status"].value_counts().to_dict() if len(comp) else {}
    return {"coverage": _coverage(ds), "db": _db_metrics(ds.root), "schedule": _schedule(),
            "company_table": {"total": int(len(comp)), "by_status": {k: int(v) for k, v in counts.items()}}}


# ---------------------------------------------------------------- bảng công ty -> lĩnh vực
def _read_companies(root):
    p = Path(root) / COMPANY_FILE
    if not p.exists():
        return pd.DataFrame(columns=COMPANY_COLS)
    df = pd.read_csv(p, encoding="utf-8-sig", dtype=str).fillna("")
    for c in COMPANY_COLS:
        if c not in df:
            df[c] = ""
    return df[COMPANY_COLS]


def _write_companies(root, df):
    p = Path(root) / COMPANY_FILE
    tmp = p.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(p)


def _domain_names(ds, active_only=True):
    d = ds.domains
    if active_only and "status" in d:
        d = d[d.status == "active"]
    return d.domain_name.tolist()


def _check_domain(ds, domain):
    domain = (domain or "").strip()
    if domain in ("", "-"):
        return "-"
    parts = [x.strip() for x in domain.split("|") if x.strip()]
    ok = set(_domain_names(ds, False))
    bad = [x for x in parts if x not in ok]
    if bad:
        raise BadRequest("lĩnh vực không có trong danh sách: " + ", ".join(bad))
    return "|".join(parts)


def list_companies(ds, status="", q="", limit=50, offset=0):
    df = _read_companies(ds.root)
    n_jobs = ds.jobs["company"].fillna("").map(company_key).value_counts().to_dict() if "company" in ds.jobs else {}
    df["n_jobs"] = df.company_example.map(lambda x: int(n_jobs.get(company_key(x), 0)))
    if status:
        df = df[df.status == status]
    if q:
        df = df[df.company_example.str.contains(q, case=False, regex=False) | df.company_key.str.contains(q.lower(), regex=False)]
    total = len(df)
    df = df.sort_values(["n_jobs", "company_example"], ascending=[False, True]).iloc[offset:offset + limit]
    return {"total": total, "items": df.to_dict("records"), "domains": _domain_names(ds), "statuses": list(COMPANY_STATUSES)}


def decide_company(ds, key, status=None, domain=None):
    df = _read_companies(ds.root)
    i = df.index[df.company_key == key]
    if len(i) == 0:
        raise NotFound("không có công ty " + str(key))
    if status is not None:
        if status not in COMPANY_STATUSES:
            raise BadRequest("trạng thái phải là một trong: " + ", ".join(COMPANY_STATUSES))
        df.loc[i, "status"] = status
    if domain is not None:
        df.loc[i, "domain"] = _check_domain(ds, domain)
        if status is None and df.loc[i[0], "status"] in ("draft", "review"):
            df.loc[i, "status"] = "approved"                   # người đã chọn lĩnh vực thì coi là đã duyệt
    df.loc[i, "source"] = df.loc[i, "source"].where(df.loc[i, "source"] != "", "admin")
    _write_companies(ds.root, df)
    return {"ok": True, "row": df.loc[i[0]].to_dict()}


def add_company(ds, name, domain, note=""):
    name = (name or "").strip()
    key = company_key(name)
    if not key:
        raise BadRequest("tên công ty trống")
    df = _read_companies(ds.root)
    if (df.company_key == key).any():
        raise BadRequest("công ty đã có trong bảng")
    row = dict(company_key=key, company_example=name, domain=_check_domain(ds, domain), status="approved", source="admin", note=note or "")
    _write_companies(ds.root, pd.concat([df, pd.DataFrame([row])], ignore_index=True))
    return {"ok": True, "row": row}


def reload_store(app):
    """Nạp lại dữ liệu website từ file mới dựng (không cần khởi động lại backend)."""
    from backend.database.store import DataStore
    s = app.state.settings
    old = app.state.store
    app.state.store = DataStore(s.root, s.embedding_model, s.embedding_backend, s.jobs_source)
    return {"ok": True, "jobs": len(app.state.store.jobs), "jobs_source": app.state.store.jobs_source, "before": len(old.jobs)}
