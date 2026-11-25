"""Kiểm thử nhanh API đang chạy (dữ liệu THẬT). Chỉ dùng thư viện chuẩn.
  Cửa sổ 1:  uvicorn backend.main:create_app --factory
  Cửa sổ 2:  python scripts\\smoke_test_api.py            (hoặc --base http://127.0.0.1:8000)
In bảng PASS/FAIL cho từng kiểm tra; mã thoát 1 nếu có FAIL."""
import argparse, json, sys, urllib.error, urllib.request

ROWS = []


def call(base, method, path, body=None, headers=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else None), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, raw, dict(e.headers)


def check(name, ok, detail=""):
    ROWS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [{detail}]" if detail and not ok else ""))


def is_desc(items, key):
    v = [i[key] for i in items if i.get(key) is not None]
    return all(a >= b for a, b in zip(v, v[1:]))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default="http://127.0.0.1:8000")
    a = ap.parse_args(); B = a.base.rstrip("/")
    try:
        s, h, _ = call(B, "GET", "/health")
    except Exception as e:
        print(f"Không kết nối được {B}: {e}\nHãy chạy server trước: uvicorn backend.main:create_app --factory"); sys.exit(2)
    check("GET /health -> 200, status ok, có Job và Thesis", s == 200 and h["status"] == "ok" and h["jobs"] > 0 and h["thesis"] > 0, h)
    emb = bool(h.get("embeddings"))
    print(f"      embeddings={emb}, ngưỡng novelty={h.get('novelty_thresholds')}")
    s, v, _ = call(B, "GET", "/meta/versions"); check("GET /meta/versions có taxonomy_version và trọng số mặc định", s == 200 and v.get("taxonomy_version") and v.get("default_recommendation_weights"), v)
    s, t, _ = call(B, "GET", "/taxonomy/topics"); check("GET /taxonomy/topics trả danh sách Topic", s == 200 and len(t) >= 20 and "topic_name" in t[0], s)
    s, c, _ = call(B, "GET", "/taxonomy/topics?status=candidate"); check("lọc status=candidate là tập con", s == 200 and 0 < len(c) < len(t), s)
    s, d, _ = call(B, "GET", "/taxonomy/domains"); check("GET /taxonomy/domains", s == 200 and len(d) >= 10, s)

    s, jl, _ = call(B, "GET", "/jobs?limit=2"); check("GET /jobs?limit=2 -> tối đa 2 mục và có total", s == 200 and len(jl["items"]) <= 2 and jl["total"] >= 2, s)
    check("GET /jobs?limit=0 -> 422", call(B, "GET", "/jobs?limit=0")[0] == 422)
    check("GET /jobs?limit=500 -> 422", call(B, "GET", "/jobs?limit=500")[0] == 422)
    check("GET /jobs?offset=-1 -> 422", call(B, "GET", "/jobs?offset=-1")[0] == 422)
    s, jf, _ = call(B, "GET", "/jobs?topic=AI%2FML&limit=5"); check("lọc /jobs?topic=AI/ML chỉ trả Job có Topic đó", s == 200 and all("AI/ML" in i["technical_topics"] for i in jf["items"]), s)
    jid = jf["items"][0]["job_id"] if jf["items"] else jl["items"][0]["job_id"]
    s, j, _ = call(B, "GET", f"/jobs/{jid}"); check(f"GET /jobs/{jid} có Topic, bằng chứng, kỹ năng", s == 200 and "technical_topic_scores" in j and "topic_evidence" in j and isinstance(j["skills"], list), s)
    check("GET /jobs/khong-ton-tai -> 404", call(B, "GET", "/jobs/khong-ton-tai")[0] == 404)

    s, tl, _ = call(B, "GET", "/thesis?limit=2"); check("GET /thesis?limit=2", s == 200 and tl["total"] > 1000 and len(tl["items"]) <= 2, s)
    tid = tl["items"][0]["thesis_id"]
    s, tt, _ = call(B, "GET", f"/thesis/{tid}"); check(f"GET /thesis/{tid} có nhãn và phiên bản mô hình", s == 200 and "technical_topics" in tt and tt.get("topic_model_version"), s)
    check("GET /thesis/-5 -> 404", call(B, "GET", "/thesis/-5")[0] == 404)
    s, q, _ = call(B, "GET", "/thesis?q=chatbot&limit=3"); check("tìm /thesis?q=chatbot", s == 200 and all("chatbot" in i["title"].lower() for i in q["items"]), s)

    s, m, _ = call(B, "GET", "/market/summary"); check("GET /market/summary", s == 200 and m.get("n_jobs"), s)
    s, mt, _ = call(B, "GET", "/market/demand_topics?limit=5"); check("GET /market/demand_topics có CI và support_ok", s == 200 and mt["items"] and "ci_low" in mt["items"][0] and "support_ok" in mt["items"][0], s)
    check("GET /market/khong_co -> 400", call(B, "GET", "/market/khong_co")[0] == 400)

    s, mj, _ = call(B, "GET", f"/matching/jobs/{jid}?top_k=3")
    if emb:
        check("GET /matching/jobs/{id}?top_k=3 -> 3 mục, điểm giảm dần, có giải thích", s == 200 and len(mj["items"]) == 3 and is_desc(mj["items"], "score") and all(i["explanation"] for i in mj["items"]), s)
    else:
        check("matching khi chưa có embedding -> 503", s == 503, s)
    s, mn, _ = call(B, "GET", f"/matching/jobs/{jid}?top_k=3&use_semantic=false")
    check("matching use_semantic=false chạy được khi không có embedding", s == 200 and mn["semantic_used"] is False, s)
    check("matching w_topic=-1 -> 422", call(B, "GET", f"/matching/jobs/{jid}?w_topic=-1")[0] == 422)
    check("matching top_k=0 -> 422", call(B, "GET", f"/matching/jobs/{jid}?top_k=0")[0] == 422)
    check("matching job không tồn tại -> 404", call(B, "GET", "/matching/jobs/khong-ton-tai")[0] == 404)

    if emb:
        s, sm, _ = call(B, "GET", f"/thesis/{tid}/similar?top_k=3"); check("GET /thesis/{id}/similar không trả chính nó", s == 200 and len(sm["items"]) == 3 and all(str(i["thesis_id"]) != str(tid) for i in sm["items"]) and is_desc(sm["items"], "similarity"), s)
        s, tn, _ = call(B, "GET", f"/thesis/{tid}/novelty"); check("GET /thesis/{id}/novelty có status và ngưỡng", s == 200 and tn["novelty_status"] in ("Novel", "Similar", "Duplicate") and tn["thresholds"]["source"], s)
        body = {"title": "Hệ thống chatbot tư vấn tuyển sinh sử dụng mô hình ngôn ngữ lớn", "topics": ["Generative AI & LLM"], "domains": ["Education"], "top_k": 3}
        s, nv, _ = call(B, "POST", "/novelty/check", body)
        check("POST /novelty/check hợp lệ -> status, nearest, combo_support", s == 200 and nv["novelty_status"] in ("Novel", "Similar", "Duplicate") and nv["nearest_thesis"]["title"] and "combo_support" in nv and len(nv["top_neighbors"]) == 3 and 0 <= nv["novelty_score"] <= 1, s)
        s, same, _ = call(B, "POST", "/novelty/check", {"title": tt["title"], "top_k": 1})
        check("novelty/check với đúng tiêu đề Thesis đã có -> độ giống ~1 và nearest cùng tiêu đề", s == 200 and same["max_similarity"] > 0.99 and same["nearest_thesis"]["title"] == tt["title"], s)
        check("novelty/check title rỗng -> 400", call(B, "POST", "/novelty/check", {"title": "   "})[0] == 400)
        check("novelty/check Topic sai -> 400", call(B, "POST", "/novelty/check", {"title": "abc", "topics": ["Khong co"]})[0] == 400)
        check("novelty/check title > 500 ký tự -> 400", call(B, "POST", "/novelty/check", {"title": "x" * 600})[0] == 400)
        check("novelty/check thiếu title -> 422", call(B, "POST", "/novelty/check", {"topics": []})[0] == 422)
        check("novelty/check top_k=99 -> 422", call(B, "POST", "/novelty/check", {"title": "abc", "top_k": 99})[0] == 422)
    else:
        print("      (bỏ qua các kiểm tra cần embedding: similar, novelty)")

    s, r, _ = call(B, "GET", f"/recommendations/jobs/{jid}?top_k=3")
    ok = s == 200 and 0 < len(r["items"]) <= 3 and is_desc(r["items"], "recommendation_score") and all(i["explanation"] and i["components"] for i in r["items"])
    check(f"GET /recommendations/jobs/{jid} -> hướng sắp giảm dần, có giải thích", ok, s)
    if ok:
        jt = set(j["technical_topics"])
        check("mọi Topic của hướng nằm trong Topic của Job", all(set(i["direction_topics"]) <= jt for i in r["items"]))
        check("tổng trọng số response > 0 và có note cảnh báo", sum(r["weights"].values()) > 0 and "note" in r)
    s, r2, _ = call(B, "GET", f"/recommendations/jobs/{jid}?top_k=3&w_topic=1&w_job_relevance=0&w_domain=0&w_semantic=0&w_novelty=0")
    check("đổi trọng số qua query hoạt động (điểm = TopicMatch khi chỉ để w_topic)", s == 200 and all(abs(i["recommendation_score"] - i["components"]["topic"]) < 1e-3 for i in r2["items"]), s)
    check("recommendations w_topic=-1 -> 422", call(B, "GET", f"/recommendations/jobs/{jid}?w_topic=-1")[0] == 422)
    check("recommendations mmr=2 -> 422", call(B, "GET", f"/recommendations/jobs/{jid}?mmr=2")[0] == 422)
    check("recommendations novelty_mode=bogus -> 422", call(B, "GET", f"/recommendations/jobs/{jid}?novelty_mode=bogus")[0] == 422)
    check("recommendations top_k=0 -> 422", call(B, "GET", f"/recommendations/jobs/{jid}?top_k=0")[0] == 422)
    check("recommendations job không tồn tại -> 404", call(B, "GET", "/recommendations/jobs/khong-ton-tai")[0] == 404)
    # Job không có Topic: phải trả danh sách rỗng kèm thông báo, không lỗi
    no_topic = None
    for off in range(0, 600, 200):
        s, page, _ = call(B, "GET", f"/jobs?limit=200&offset={off}")
        if s != 200 or not page["items"]:
            break
        no_topic = next((i["job_id"] for i in page["items"] if not i["technical_topics"]), None)
        if no_topic:
            break
    if no_topic:
        s, e, _ = call(B, "GET", f"/recommendations/jobs/{no_topic}")
        check(f"Job không có Topic ({no_topic}) -> items rỗng + message, không lỗi", s == 200 and e["items"] == [] and e.get("message"), s)
    s, _, hd = call(B, "GET", "/health", headers={"Origin": "http://localhost:5173"})
    check("CORS cho http://localhost:5173 (frontend dev)", any(k.lower() == "access-control-allow-origin" for k in hd), list(hd))
    s, o, _ = call(B, "GET", "/openapi.json"); check("GET /openapi.json có đủ endpoint chính", s == 200 and all(p in o["paths"] for p in ["/jobs", "/recommendations/jobs/{job_id}", "/novelty/check", "/matching/jobs/{job_id}"]), s)

    bad = [n for n, ok, _ in ROWS if not ok]
    print(f"\n{len(ROWS) - len(bad)}/{len(ROWS)} đạt" + ("" if not bad else "; KHÔNG ĐẠT:\n  - " + "\n  - ".join(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
