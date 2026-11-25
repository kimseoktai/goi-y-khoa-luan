import numpy as np
from ml.novelty import novelty as N


def _unit(v):
    v = np.asarray(v, dtype=np.float32); return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_self_neighbors_exclude_self_by_index_even_with_duplicates():
    E = _unit([[1, 0], [1, 0], [0, 1]])            # hai Thesis trùng hệt nhau
    idx, sims = N.self_neighbors(E, k=1)
    assert idx[0, 0] == 1 and idx[1, 0] == 0 and np.isclose(sims[0, 0], 1)
    assert idx[2, 0] in (0, 1) and np.isclose(sims[2, 0], 0)


def test_novelty_score_is_empirical_and_monotone():
    ref = np.linspace(0.7, 0.95, 100)
    assert N.novelty_score(0.6, ref) == 1.0 and N.novelty_score(0.99, ref) == 0.0
    assert N.novelty_score(0.75, ref) > N.novelty_score(0.9, ref)


def test_status_and_provisional_thresholds_ordered():
    ref = np.random.default_rng(0).uniform(0.7, 0.95, 500)
    th = N.provisional_thresholds(ref)
    assert th["similar"] < th["duplicate"] and th["source"] == "provisional_quantiles"
    s = N.status([0.5, th["similar"] + 1e-6, th["duplicate"] + 1e-6], th)
    assert s.tolist() == ["Novel", "Similar", "Duplicate"]


def test_combo_support_counts_subsets():
    L = [({"AI/ML", "NLP"}, {"Education"}), ({"AI/ML"}, set()), ({"Web"}, {"Education"})]
    assert N.combo_support(L, ["AI/ML"]) == 2
    assert N.combo_support(L, ["AI/ML"], ["Education"]) == 1
    assert N.combo_support(L, ["Cloud"], []) == 0


def test_fit_thresholds_recovers_separable_labels():
    sims = [0.60, 0.65, 0.70, 0.82, 0.85, 0.88, 0.97, 0.98, 0.99]
    labs = ["Different"] * 3 + ["Similar"] * 3 + ["Duplicate"] * 3
    th = N.fit_thresholds(sims, labs, min_duplicate=3)
    assert 0.70 < th["similar"] <= 0.82 and 0.88 < th["duplicate"] <= 0.97 and th["balanced_accuracy"] == 1.0


def test_fit_thresholds_needs_two_classes():
    try:
        N.fit_thresholds([0.1, 0.2], ["Similar", "Similar"]); assert False
    except ValueError:
        pass
