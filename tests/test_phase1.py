import json
import pandas as pd

jobs = pd.read_csv("data/processed/jobs/jobs_clean.csv", encoding="utf-8-sig")
skills = pd.read_csv("data/repository/skills.csv", encoding="utf-8-sig")


def test_jobs_no_duplicates_or_empty():
    assert not jobs.job_id.duplicated().any()
    assert not jobs.url.duplicated().any()
    assert not jobs.description.str.lower().duplicated().any()
    assert (jobs.description.str.len() >= 50).all()
    assert not jobs.company.isna().any()


def test_job_skills_in_repository():
    repo = set(skills.skill_name)
    for v in jobs.skills:
        assert set(json.loads(v)) <= repo


def test_skills_repository_schema_and_uniqueness():
    cols = ["skill_id", "skill_name", "aliases", "category", "description", "status", "created_at", "version"]
    assert list(skills.columns) == cols
    assert not skills.skill_name.str.lower().duplicated().any()
    assert not skills.category.isna().any()
    al = [a.lower() for v in skills.aliases.fillna("") for a in v.split("|") if a]
    assert len(al) == len(set(al))
    assert not set(al) & set(skills.skill_name.str.lower())
