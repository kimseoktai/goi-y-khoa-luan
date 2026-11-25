import json
import pandas as pd

R = "data/repository/"
rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
jobs, topics, domains = rd("data/processed/jobs/jobs_processed.csv"), rd(R + "technical_topics.csv"), rd(R + "domains.csv")
skills = rd(R + "skills.csv")


def test_mapping_files_reference_repository_only():
    assert set(rd(R + "skill_topic_map.csv").skill_name) <= set(skills.skill_name)
    assert set(rd(R + "skill_topic_map.csv").topic_name) <= set(topics.topic_name)
    assert set(rd(R + "job_role_topic_map.csv").topic_name) <= set(topics.topic_name)
    assert set(rd(R + "domain_job_exclusions.csv").domain_name) <= set(domains.domain_name)


def test_processed_jobs_complete_and_labels_valid():
    assert len(jobs) == 520 and not jobs.job_id.duplicated().any()
    tn, dn = set(topics.topic_name), set(domains.domain_name)
    for v in jobs.technical_topics: assert set(json.loads(v)) <= tn
    for v in jobs.domains: assert set(json.loads(v)) <= dn
    assert not tn & dn


def test_technologies_and_competencies_partition_skills():
    for r in jobs.itertuples():
        assert sorted(json.loads(r.skills)) == sorted(json.loads(r.technologies) + json.loads(r.competencies))


def test_topics_have_evidence():
    for r in jobs.itertuples():
        t, ev = json.loads(r.technical_topics), json.loads(r.topic_evidence)
        assert set(t) == set(ev)
        assert all(e["role"] or e["skills"] for e in ev.values())


def test_no_topic_jobs_are_flagged_not_dropped():
    empty = jobs[jobs.technical_topics == "[]"]
    assert (empty.review_flag.fillna("").str.contains("no_technical_topic")).all()
