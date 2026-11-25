"""Phase 1 - tạo data/repository/skills.csv từ skill_repository.csv + skill_curation.csv.

skill_curation.csv là dữ liệu curated (aliases, category) chờ Admin duyệt,
nên mọi skill được tạo với status = draft.
"""
import argparse, logging
from datetime import date
from pathlib import Path
import pandas as pd

log = logging.getLogger("build_skills")


def build(repo: pd.DataFrame, cur: pd.DataFrame, version: str, today: str) -> pd.DataFrame:
    if repo.skill_raw.duplicated().any() or repo.skill_normalized.duplicated().any():
        raise ValueError("skill trùng trong repository")
    m = repo.merge(cur, on="skill_raw", how="left", validate="one_to_one")
    if m.category.isna().any():
        raise ValueError(f"Thiếu category: {m[m.category.isna()].skill_raw.tolist()}")
    # alias không được trùng với skill_name hay alias của skill khác
    seen = {n.lower(): n for n in m.skill_raw}
    for _, r in m.iterrows():
        for al in filter(None, str(r.aliases if pd.notna(r.aliases) else "").split("|")):
            if al.lower() in seen and seen[al.lower()] != r.skill_raw:
                raise ValueError(f"Alias '{al}' xung đột với '{seen[al.lower()]}'")
            seen[al.lower()] = r.skill_raw
    out = pd.DataFrame({
        "skill_id": range(1, len(m) + 1),
        "skill_name": m.skill_raw,
        "aliases": m.aliases.fillna(""),
        "category": m.category,
        "description": "",
        "status": "draft",
        "created_at": today,
        "version": version,
    })
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--curation", required=True)
    p.add_argument("--output", default="data/repository/skills.csv")
    p.add_argument("--version", default="v1.0")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = build(pd.read_csv(a.repo, encoding="utf-8-sig"),
                pd.read_csv(a.curation, encoding="utf-8-sig"),
                a.version, date.today().isoformat())
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.output, index=False, encoding="utf-8-sig")
    log.info("skills=%d version=%s", len(out), a.version)


if __name__ == "__main__":
    main()
