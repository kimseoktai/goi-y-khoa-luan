"""Phase 1 - làm sạch Jobs: loại description rỗng/vô nghĩa, loại bản trùng, kiểm tra skills.

Không sửa file đầu vào. Mọi dòng bị loại được ghi vào file log kèm lý do.
"""
import argparse, json, logging, re, unicodedata
from pathlib import Path
import pandas as pd

log = logging.getLogger("clean_jobs")
MIN_DESC_CHARS = 50          # ngưỡng tối thiểu để description có nội dung (cấu hình được)


def norm_text(x) -> str:
    if pd.isna(x):
        return ""
    x = unicodedata.normalize("NFC", str(x))
    return re.sub(r"\s+", " ", x).strip()


def clean_jobs(df: pd.DataFrame, skills_repo: set, min_desc: int = MIN_DESC_CHARS):
    df = df.copy()
    for c in ["job_title", "description", "company", "url"]:
        df[c] = df[c].map(norm_text)
    removed = []

    # 1) description rỗng / vô nghĩa
    bad = df.description.str.len() < min_desc
    removed.append(df[bad].assign(reason=f"description < {min_desc} ký tự"))
    df = df[~bad]

    # 2) trùng url (sau khi bỏ query) -> giữ dòng đầu
    key = df.url.str.split("?").str[0]
    dup = key.duplicated(keep="first")
    removed.append(df[dup].assign(reason="trùng url"))
    df = df[~dup]

    # 3) trùng description (so sánh không phân biệt hoa/thường) -> giữ dòng đầu
    key = df.description.str.lower()
    dup = key.duplicated(keep="first")
    removed.append(df[dup].assign(reason="trùng description"))
    df = df[~dup]

    # 4) skills: parse JSON, kiểm tra thuộc repository
    def parse(v):
        try:
            return json.loads(v)
        except Exception:
            return None
    parsed = df.skills.map(parse)
    if parsed.isna().any():
        raise ValueError(f"{int(parsed.isna().sum())} dòng skills không phải JSON hợp lệ")
    unknown = {s for l in parsed for s in l} - skills_repo
    if unknown:
        raise ValueError(f"Skill chưa có trong repository: {sorted(unknown)}")
    df["skills"] = parsed.map(lambda l: json.dumps(list(dict.fromkeys(l)), ensure_ascii=False))

    # 5) company thiếu -> đánh dấu rõ ràng thay vì để NaN
    df["company"] = df.company.replace("", "Unknown")
    return df, pd.concat(removed, ignore_index=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--skills", required=True, help="skill_repository.csv (skill_raw)")
    p.add_argument("--output", default="data/processed/jobs/jobs_clean.csv")
    p.add_argument("--removed-log", default="logs/jobs_removed.csv")
    p.add_argument("--min-desc", type=int, default=MIN_DESC_CHARS)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    jobs = pd.read_csv(a.input, encoding="utf-8-sig")
    repo = set(pd.read_csv(a.skills, encoding="utf-8-sig").skill_raw)
    out, removed = clean_jobs(jobs, repo, a.min_desc)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.removed_log).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.output, index=False, encoding="utf-8-sig")
    removed.to_csv(a.removed_log, index=False, encoding="utf-8-sig")
    log.info("input=%d output=%d removed=%d", len(jobs), len(out), len(removed))


if __name__ == "__main__":
    main()
