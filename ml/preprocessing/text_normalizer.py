"""Chuẩn hóa văn bản title (viết tắt, biến thể chính tả/dấu thanh) theo bảng data/processed/text_normalization.csv.
Dùng chung cho train và predict để hai bên nhất quán."""
import re
from functools import lru_cache
import pandas as pd

from ml import config as C


@lru_cache(maxsize=1)
def _rules():
    df = pd.read_csv(C.ROOT / "data/processed/text_normalization.csv", encoding="utf-8-sig")
    rules = []
    for r in df.itertuples():
        if r.type == "word":
            rules.append((re.compile(r"(?<![^\W\d_])" + re.escape(r.pattern) + r"(?![^\W\d_])"), r.replacement))
        else:
            rules.append((re.compile(re.escape(r.pattern)), r.replacement))
    return rules


def normalize(text: str) -> str:
    for rx, rep in _rules():
        text = rx.sub(rep, text)
    return text
