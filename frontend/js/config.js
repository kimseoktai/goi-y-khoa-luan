// Địa chỉ API. Thứ tự ưu tiên: ?api=http://... trên URL  >  localStorage("rec_api")  >  mặc định.
function pick() {
  try {
    const q = new URLSearchParams(window.location.search).get("api");
    if (q) { try { window.localStorage.setItem("rec_api", q); } catch (e) { /* bỏ qua */ } return q; }
    return window.localStorage.getItem("rec_api") || "";
  } catch (e) { return ""; }
}
export const API_BASE = (pick() || "http://localhost:8000").replace(/\/+$/, "");
export const TOP_K = 5;            // số hướng đề tài mỗi lần
export const MMR_ON = 0.5;         // giá trị mmr khi bật "Tránh gợi ý trùng nhau" (tính năng thử nghiệm, chưa đánh giá)
