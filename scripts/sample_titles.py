"""Sinh một mẫu tên đề tài bằng Gemini để người dùng chấm tay (tốt / chung chung / sai) rồi chỉnh prompt.
Cần GEMINI_API_KEY (và REC_GEMINI_MODEL nếu đổi mô hình). Mỗi lần chạy gọi Gemini khoảng --roles x --per-role lần.

  python scripts\\sample_titles.py --roles 5 --per-role 2
Kết quả: data/evaluation/title_sample.csv (điền cột danh_gia: tot / chung_chung / sai, và ghi_chu)."""
import argparse
import csv
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.store import DataStore
from backend.settings import Settings
from backend.services import student_service as S
from ml.generation import llm_client as LC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", type=int, default=5, help="số nhóm công việc lấy mẫu (theo số tin nhiều nhất)")
    ap.add_argument("--per-role", type=int, default=2, help="số hướng đề tài mỗi nhóm công việc")
    ap.add_argument("--out", default="data/evaluation/title_sample.csv")
    a = ap.parse_args()
    cfg = Settings()
    if not cfg.gemini_api_key:
        sys.exit("Chưa đặt GEMINI_API_KEY. Trong PowerShell: $env:GEMINI_API_KEY=\"khóa\"")
    ds = DataStore(cfg.root, cfg.embedding_model, cfg.embedding_backend, cfg.jobs_source)
    llm = partial(LC.gemini_json, model=cfg.gemini_model, api_key=cfg.gemini_api_key, timeout=min(cfg.llm_timeout, 90))
    print(f"Nguồn Jobs: {ds.jobs_source} | mô hình: {cfg.gemini_model} | embedding: {ds.has_embeddings()}")
    rows = []
    for role in [r["name"] for r in S.overview(ds)["hot_roles"][:a.roles]]:
        ideas = S.ideas(ds, [role], offset=0, n=a.per_role)["items"]
        for it in ideas:
            try:
                t = S.idea_title(ds, llm, [role], it["topic"], n=1)["titles"]
            except Exception as e:                                           # một hướng lỗi không làm hỏng cả mẫu
                print(f"  bỏ qua {role} / {it['topic']}: {e}")
                continue
            if not t:
                continue
            x = t[0]
            rows.append(dict(vi_tri=role, chu_de=it["topic_label"], linh_vuc=", ".join(it["domain_labels"]), cong_nghe=", ".join(it["technologies"][:6]),
                             ten_de_tai=x["title"], tom_tat=x.get("summary", ""), trung=(x.get("novelty") or {}).get("status", ""), danh_gia="", ghi_chu=""))
            print(f"\n[{role} | {it['topic_label']}]\n  {x['title']}\n  {x.get('summary', '')}")
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["vi_tri", "chu_de", "linh_vuc", "cong_nghe", "ten_de_tai", "tom_tat", "trung", "danh_gia", "ghi_chu"])
        w.writeheader(); w.writerows(rows)
    print(f"\nĐã ghi {len(rows)} tên vào {out}. Điền cột danh_gia (tot / chung_chung / sai) và ghi_chu rồi gửi lại file.")


if __name__ == "__main__":
    main()
