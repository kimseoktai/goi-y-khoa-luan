import json
import pandas as pd
from ml.recommendation import market_demand as M

D = "data/processed/market/"
rd = lambda f: pd.read_csv(D + f, encoding="utf-8-sig")


def test_wilson_interval_contains_proportion():
    lo, hi = M.wilson(30, 100)
    assert 0 < lo < 0.3 < hi < 1 and M.wilson(0, 0) == (0.0, 0.0)


def test_small_support_is_not_called_reliable():
    df = M.demand_table([["a"], ["a"], ["b"]], ["x", "y", "z"])
    assert not df.support_ok.any()


def test_fractional_domain_weights_sum_to_labelled_jobs():
    df, n = M.fractional_domain_table([{"A": 1.0, "B": 1.0}, {"A": 0.5}, {}], ["c1", "c2", "c3"])
    assert n == 2 and abs(df.weighted_jobs.sum() - 2) < 1e-6


def test_output_tables_and_unmeasurable_topics():
    sv = rd("supply_vs_demand_topics.csv")
    assert {"gap_status", "measurable_in_jobs"} <= set(sv.columns)
    bad = sv[~sv.measurable_in_jobs]
    assert (bad.gap_status == "not_measurable_from_jobs").all() and (bad.job_count == 0).all()
    sk = rd("demand_skills.csv")
    assert (sk.job_count <= 520).all() and sk.share.between(0, 1).all()
    assert json.loads(open(D + "market_summary.json", encoding="utf-8").read())["n_jobs"] == 520
