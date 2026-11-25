import { API_BASE } from "./config.js";

export class ApiError extends Error {
  constructor(status, detail) { super(typeof detail === "string" ? detail : JSON.stringify(detail)); this.status = status; this.detail = detail; }
}

async function req(path, { method = "GET", body, signal, headers } = {}) {
  let res;
  try {
    res = await fetch(API_BASE + path, { method, signal, headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(headers || {}) }, body: body ? JSON.stringify(body) : undefined });
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
    throw new ApiError(0, "network");
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* phản hồi không phải JSON */ }
  if (!res.ok) throw new ApiError(res.status, data && data.detail != null ? data.detail : res.statusText);
  return data;
}

const qs = (o) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o || {})) if (v !== undefined && v !== null && v !== "") p.set(k, v);
  const s = p.toString();
  return s ? "?" + s : "";
};

import { session } from "./session.js";
const adminH = () => ({ "X-Student-Token": session.token() });   // quản trị viên: dùng phiên đăng nhập của mã admin

export const api = {
  health: (o) => req("/health", o),
  // giao diện sinh viên
  overview: (o) => req("/student/overview", o),
  studentRoles: (o) => req("/student/roles", o),
  skills: (o) => req("/student/skills", o),
  labels: (o) => req("/student/labels", o),
  profile: (skills, o) => req("/student/profile", { ...o, method: "POST", body: { skills } }),
  ideas: (body, o) => req("/student/ideas", { ...o, method: "POST", body }),
  ideaTitle: (body, o) => req("/student/ideas/title", { ...o, method: "POST", body }),
  noveltyCheck: (body, o) => req("/novelty/check", { ...o, method: "POST", body }),
  jobsOfRole: (params, o) => req("/student/jobs" + qs(params), o),
  thesisList: (params, o) => req("/thesis" + qs(params), o),
  advisorsFor: (body, o) => req("/student/advisors", { ...o, method: "POST", body }),
  advisorList: (params, o) => req("/advisors" + qs(params), o),
  dashboardThesis: (params, o) => req("/dashboard/thesis" + qs(params), o),
  thesisTrends: (params, o) => req("/trends/thesis" + qs(params), o),
  thesisOne: (id, o) => req("/thesis/" + encodeURIComponent(id), o),
  // tài khoản theo mã sinh viên
  login: (student_id, secret, o) => req("/auth/login", { ...o, method: "POST", body: { student_id, secret: secret || null } }),
  logout: (token, o) => req("/auth/logout", { ...o, method: "POST", body: {}, headers: { "X-Student-Token": token } }),
  me: (token, o) => req("/me", { ...o, headers: { "X-Student-Token": token } }),
  meState: (token, o) => req("/me/state", { ...o, headers: { "X-Student-Token": token } }),
  meSave: (token, state, o) => req("/me/state", { ...o, method: "POST", body: { state }, headers: { "X-Student-Token": token } }),
  // quản trị nhóm công việc
  roles: (o) => req("/roles", o),
  adminRoles: (token, o) => req("/admin/roles", { ...o, headers: adminH() }),
  adminGet: (token, path, o) => req("/admin" + path, { ...o, headers: adminH() }),
  adminPost: (token, path, body, o) => req("/admin" + path, { ...o, method: "POST", body: body || {}, headers: adminH() }),
  adminDecide: (token, body, o) => req("/admin/roles/decision", { ...o, method: "POST", body, headers: adminH() }),
};

// Thông báo lỗi bằng tiếng Việt, nói rõ cách xử lý.
export function describeError(e) {
  if (!(e instanceof ApiError)) return { title: "Có lỗi xảy ra", text: String((e && e.message) || e), hint: "" };
  if (e.status === 0) return { title: "Không kết nối được máy chủ API", text: "Địa chỉ đang dùng: " + API_BASE,
    hint: "Hãy chạy backend (uvicorn backend.main:create_app --factory --reload). Nếu API ở địa chỉ khác, mở trang với ?api=http://địa-chỉ:cổng" };
  if (e.status === 401) return { title: "Phiên quản trị đã hết hạn", text: String(e.detail), hint: "Đăng nhập lại bằng mã quản trị viên." };
  if (e.status === 403) return { title: "Chỉ dành cho quản trị viên", text: String(e.detail), hint: "Đăng nhập bằng mã có vai trò admin." };
  if (e.status === 404) return { title: "Không tìm thấy", text: String(e.detail), hint: "" };
  if (e.status === 503) return { title: "Chưa dùng được chức năng này", text: String(e.detail),
    hint: /gemini|mô hình/i.test(String(e.detail)) ? "Kiểm tra khóa Gemini (GEMINI_API_KEY) và kết nối mạng, rồi thử lại." : "Thường là chưa tạo embedding. Chạy scripts/build_embeddings.py trên máy của bạn rồi khởi động lại backend." };
  if (e.status === 400 || e.status === 422) return { title: "Dữ liệu gửi lên chưa hợp lệ", text: Array.isArray(e.detail) ? e.detail.map((d) => d.msg).join("; ") : String(e.detail), hint: "" };
  return { title: "Lỗi máy chủ", text: "Máy chủ gặp lỗi nội bộ.", hint: "Xem log của backend để biết chi tiết." };
}
