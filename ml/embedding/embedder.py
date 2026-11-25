"""Embedder: sinh vector cho văn bản, có cache theo văn bản chuẩn hóa.

backend:
  - "st"   : sentence-transformers (mô hình đa ngôn ngữ, cần cài thư viện + tải mô hình lần đầu)
  - "hash" : băm n-gram ký tự (CHỈ để kiểm thử luồng chạy, KHÔNG phải embedding ngữ nghĩa)
"""
import hashlib
import re
import unicodedata
from pathlib import Path
import numpy as np

from ml import config as C


def model_tag(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_name.lower()).strip("-")


def norm_key(text: str) -> str:
    t = unicodedata.normalize("NFC", str(text)).lower()
    return re.sub(r"\s+", " ", t).strip()


class Embedder:
    def __init__(self, model_name=C.DEFAULT_EMBED_MODEL, backend="st", prefix=None, dim=256):
        self.model_name, self.backend, self.dim = model_name, backend, dim
        # e5 yêu cầu tiền tố; dùng "query: " cho cả tác vụ phân loại/so khớp đối xứng
        self.prefix = prefix if prefix is not None else ("query: " if "e5" in model_name.lower() else "")
        self.cache = {}
        self._model = None

    @property
    def tag(self):
        return model_tag(self.model_name) if self.backend == "st" else f"hash{self.dim}"

    def __getstate__(self):                      # không pickle mô hình nặng, chỉ giữ cache
        d = self.__dict__.copy(); d["_model"] = None
        return d

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer   # import muộn
            C.EMBED_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(self.model_name, cache_folder=str(C.EMBED_MODEL_DIR))
        return self._model

    def _encode(self, texts):
        if self.backend == "hash":
            out = np.zeros((len(texts), self.dim), dtype=np.float32)
            for i, t in enumerate(texts):
                t = f" {t} "
                for n in (3, 4):
                    for j in range(len(t) - n + 1):
                        h = int(hashlib.md5(t[j:j + n].encode()).hexdigest()[:8], 16)
                        out[i, h % self.dim] += 1 if (h >> 3) & 1 else -1
            nrm = np.linalg.norm(out, axis=1, keepdims=True); nrm[nrm == 0] = 1
            return out / nrm
        m = self._load()
        v = m.encode([self.prefix + t for t in texts], batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)

    def encode(self, texts, allow_model=True):
        keys = [norm_key(t) for t in texts]
        miss = [k for k in dict.fromkeys(keys) if k not in self.cache]
        if miss:
            if not allow_model:
                raise KeyError(f"{len(miss)} văn bản chưa có embedding trong cache; chạy ml/embedding/build_embeddings.py trước")
            for k, v in zip(miss, self._encode(miss)):
                self.cache[k] = v
        return np.vstack([self.cache[k] for k in keys])

    # ---- lưu / nạp cache
    def cache_path(self):
        return C.EMBED_DIR / f"cache_{self.tag}.npz"

    def save_cache(self):
        C.EMBED_DIR.mkdir(parents=True, exist_ok=True)
        ks = list(self.cache)
        np.savez_compressed(self.cache_path(), keys=np.array(ks, dtype=object), vecs=np.vstack([self.cache[k] for k in ks]))

    def load_cache(self):
        p = self.cache_path()
        if p.exists():
            z = np.load(p, allow_pickle=True)
            self.cache.update({k: v for k, v in zip(z["keys"], z["vecs"])})
        return self
