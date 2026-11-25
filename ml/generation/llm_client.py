"""Gọi mô hình ngôn ngữ (Gemini) qua REST, chỉ dùng thư viện chuẩn. Không cần cài thêm gói Python."""
import json
import re
import time
import urllib.error
import urllib.request


class LLMUnavailable(Exception):
    """Không gọi được Gemini (thiếu khóa, hết hạn mức, mất mạng...); thông báo nói rõ cách xử lý."""


class LLMBadOutput(Exception):
    """Mô hình trả về thứ không đọc được thành JSON."""


def _post(url, payload, timeout, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_json(text):
    """Đọc JSON từ câu trả lời của mô hình, chấp nhận khi bị bọc trong ```json ... ```."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    try:
        return json.loads(t)
    except ValueError:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                pass
    raise LLMBadOutput("mô hình trả về nội dung không phải JSON")


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


RETRY_CODES = (500, 502, 503, 504)        # lỗi tạm thời phía Google (thường là quá tải): thử lại vài lần trước khi báo lỗi
RETRY_WAIT = (2, 5)                        # giây chờ trước lần thử lại thứ nhất và thứ hai


def gemini_json(messages, model, api_key, timeout=60, temperature=0.7, post=_post, sleep=time.sleep):
    """Gọi Gemini qua REST (chỉ dùng thư viện chuẩn), trả về một đối tượng JSON. Khóa API đi trong header, không nằm trong URL hay thông báo lỗi.
    Lưu ý: nội dung prompt (tên vị trí tuyển dụng, kỹ năng, tiêu đề luận văn mẫu) được gửi tới Google."""
    if not api_key:
        raise LLMUnavailable("chưa đặt khóa Gemini; đặt biến môi trường GEMINI_API_KEY rồi khởi động lại backend")
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    payload = dict(contents=[dict(role="user" if m["role"] != "assistant" else "model", parts=[dict(text=m["content"])]) for m in messages if m["role"] != "system"],
                   generationConfig=dict(temperature=temperature, responseMimeType="application/json", maxOutputTokens=4096))
    if system:
        payload["systemInstruction"] = dict(parts=[dict(text=system)])
    try:
        for wait in (*RETRY_WAIT, None):
            try:
                res = post(GEMINI_URL.format(model=model), payload, timeout, {"x-goog-api-key": api_key})
                break
            except urllib.error.HTTPError as e:
                if e.code not in RETRY_CODES or wait is None:
                    raise
                sleep(wait)
    except urllib.error.HTTPError as e:
        hint = {400: "yêu cầu hoặc khóa API không hợp lệ", 401: "khóa API không đúng", 403: "khóa API không có quyền hoặc bị chặn", 404: f"không có mô hình '{model}'; kiểm tra REC_GEMINI_MODEL",
                429: "đã hết hạn mức gọi; đợi một lúc rồi thử lại", 503: "máy chủ Gemini đang quá tải (đã thử lại 3 lần); đợi một lúc rồi thử lại, hoặc đổi REC_GEMINI_MODEL sang mô hình khác"}.get(e.code, "lỗi từ máy chủ Gemini")
        raise LLMUnavailable(f"Gemini trả lỗi HTTP {e.code}: {hint}")
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise LLMUnavailable(f"không kết nối được Gemini ({getattr(e, 'reason', e)}); kiểm tra mạng")
    try:
        text = "".join(p.get("text", "") for p in res["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError):
        raise LLMBadOutput("Gemini không trả nội dung (có thể bị chặn bởi bộ lọc an toàn)")
    return parse_json(text)
