// Phiên đăng nhập bằng mã sinh viên. Lưu ở localStorage để mở lại trang vẫn còn đăng nhập (máy chủ cho phiên sống 30 ngày).
const KEY = "rec_session_v1";
let cur;

function read() {
  if (cur !== undefined) return cur;
  try { cur = JSON.parse(window.localStorage.getItem(KEY) || "null"); } catch (e) { cur = null; }
  if (!cur || typeof cur !== "object" || !cur.student || typeof cur.student.student_id !== "string" || !cur.token) cur = null;
  return cur;
}

export const session = {
  get: read,
  token: () => (read() && read().token) || "",
  student: () => (read() && read().student) || null,
  isAdmin: () => !!(read() && read().student.role === "admin"),
  set(v) { cur = v; try { window.localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* vẫn đăng nhập được trong lúc trang đang mở */ } },
  clear() {
    cur = null;
    try { window.localStorage.removeItem(KEY); window.sessionStorage.removeItem("rec_admin_token"); } catch (e) { /* bỏ qua */ }
  },
};
