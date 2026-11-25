import pickle
import numpy as np
from ml.embedding.embedder import Embedder, norm_key


def test_cache_and_normalized_keys():
    e = Embedder("dummy", backend="hash", dim=64)
    a = e.encode(["Xây dựng  Website"]); b = e.encode(["xây dựng website"], allow_model=False)
    assert np.allclose(a, b) and norm_key("A  B") == "a b"


def test_missing_cache_raises_when_model_not_allowed():
    e = Embedder("dummy", backend="hash", dim=64)
    try:
        e.encode(["chưa có"], allow_model=False)
        assert False
    except KeyError:
        pass


def test_pickle_keeps_cache_drops_model():
    e = Embedder("dummy", backend="hash", dim=64); e.encode(["abc"])
    e._model = object()
    e2 = pickle.loads(pickle.dumps(e))
    assert e2._model is None and "abc" in e2.cache


def test_e5_prefix_default():
    assert Embedder("intfloat/multilingual-e5-base", backend="hash").prefix == "query: "
    assert Embedder("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", backend="hash").prefix == ""
