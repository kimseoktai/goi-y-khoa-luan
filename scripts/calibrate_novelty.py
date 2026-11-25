"""Hiệu chỉnh ngưỡng Duplicate/Similar từ mẫu đã chấm tay.
  python scripts\\calibrate_novelty.py --labeled data\\processed\\novelty\\novelty_calibration_sample.csv
Cột label nhận: Duplicate / Similar / Different (không phân biệt hoa thường; ô trống bị bỏ qua)."""
import argparse, json, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config as C            # noqa: E402
from ml.novelty import novelty as N   # noqa: E402

OUT = C.ROOT / "data/processed/novelty"


def read(p):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(p, encoding=enc)
        except UnicodeDecodeError:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeled", nargs="+", default=[str(OUT / "novelty_calibration_sample.csv"), str(OUT / "novelty_calibration_extra_sample.csv")])
    ap.add_argument("--key", nargs="+", default=[str(OUT / "novelty_calibration_key.csv"), str(OUT / "novelty_calibration_extra_key.csv")])
    ap.add_argument("--out", default=str(OUT / "thresholds.json"))
    a = ap.parse_args()
    lab = pd.concat([read(p) for p in a.labeled if Path(p).exists()], ignore_index=True)
    key = pd.concat([read(p) for p in a.key if Path(p).exists()], ignore_index=True)
    lab["label"] = lab.label.astype(str).str.strip().str.capitalize().replace({"Nan": "", "Khác": "Different", "Giống": "Similar", "Trùng": "Duplicate"})
    d = lab.merge(key, on="pair_id"); d = d[d.label.isin(["Duplicate", "Similar", "Different"])]
    print("số cặp đã chấm:", len(d), d.label.value_counts().to_dict())
    th = N.fit_thresholds(d.similarity, d.label)
    if th.get("warning"): print("CẢNH BÁO:", th["warning"])
    th["dataset_note"] = "ngưỡng khớp trên chính mẫu này (in-sample); mẫu nhỏ nên dùng như hướng dẫn, kiểm tra lại khi có thêm nhãn"
    json.dump(th, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(th, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
