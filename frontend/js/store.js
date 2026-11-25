// Hồ sơ của sinh viên lưu ngay trên trình duyệt (không cần tài khoản): kỹ năng đã chọn, công việc đã chọn, đề tài đã lưu.
// localStorage có thể bị chặn hoặc bị xóa (cửa sổ riêng tư, xóa dữ liệu trình duyệt): khi đó dùng bộ nhớ tạm của trang và không báo lỗi.
import { api } from "./api.js";
import { session } from "./session.js";
const BASE = "rec_student_v1";
const key = () => { const u = session.student(); return u ? BASE + ":" + u.student_id : BASE; };   // mỗi mã sinh viên một bản lưu tạm trên máy
const EMPTY = () => ({ welcomed: false, skills: [], roles: [], saved: [] });
let mem = null;

function read() {
  if (mem) return mem;
  let data = null;
  try { data = JSON.parse(window.localStorage.getItem(key()) || "null"); } catch (e) { data = null; }
  mem = clean(data);
  return mem;
}

function clean(d) {
  const o = EMPTY();
  if (!d || typeof d !== "object") return o;
  o.welcomed = d.welcomed === true;
  const strs = (a, max) => (Array.isArray(a) ? a.filter((x) => typeof x === "string" && x.length < 120).slice(0, max) : []);
  o.skills = strs(d.skills, 80);
  o.roles = strs(d.roles, 3);
  o.saved = Array.isArray(d.saved) ? d.saved.filter((x) => x && typeof x.id === "string" && typeof x.title === "string").slice(0, 100).map(cleanItem) : [];
  return o;
}

function cleanItem(x) {
  const arr = (a) => (Array.isArray(a) ? a.filter((s) => typeof s === "string").slice(0, 12) : []);
  return { id: x.id, kind: x.kind === "thesis" ? "thesis" : "idea", title: x.title.slice(0, 300), summary: typeof x.summary === "string" ? x.summary.slice(0, 700) : "",
    tech: arr(x.tech), skills: arr(x.skills), topics: arr(x.topics), report_url: typeof x.report_url === "string" && /^https?:\/\//i.test(x.report_url) ? x.report_url.slice(0, 500) : "", topic: typeof x.topic === "string" ? x.topic.slice(0, 120) : "", domains: arr(x.domains).slice(0, 3), fit: Number.isFinite(x.fit) ? x.fit : null, fit_total: Number.isFinite(x.fit_total) ? x.fit_total : null,
    status: x.status === "Novel" || x.status === "Similar" ? x.status : null, year: Number.isFinite(x.year) ? x.year : null, source: typeof x.source === "string" ? x.source : "", saved_at: typeof x.saved_at === "string" ? x.saved_at : "" };
}

function persist() { try { window.localStorage.setItem(key(), JSON.stringify(mem)); } catch (e) { /* vẫn dùng được trong lúc trang đang mở */ } }

// Đồng bộ lên máy chủ theo mã sinh viên (gộp các thay đổi liên tiếp trong 0,6 giây). Mất mạng thì vẫn còn bản lưu tạm trên máy.
let pushTimer = null;
async function push() {
  const tk = session.token();
  if (!tk || !mem) return;
  try { await api.meSave(tk, mem); } catch (e) { if (e && e.status === 401) window.dispatchEvent(new CustomEvent("rec:session-expired")); }
}

function write() {
  persist();
  window.dispatchEvent(new CustomEvent("rec:store"));
  if (session.token()) { clearTimeout(pushTimer); pushTimer = setTimeout(push, 600); }
}

// Bộ nhớ tên đề tài đã viết (tách khỏi hồ sơ): mở lại trang hay quay lại không phải gọi lại mô hình, đỡ tốn lượt gọi Gemini.
const TKEY = "rec_titles_v1", TMAX = 60;
const strList = (a) => (Array.isArray(a) ? a.filter((s) => typeof s === "string").slice(0, 12).map((s) => s.slice(0, 80)) : []);
const tkey = (roles, topic) => roles.slice().sort().join("|") + "::" + topic;
function tread() { try { const o = JSON.parse(window.localStorage.getItem(TKEY) || "{}"); return o && typeof o === "object" ? o : {}; } catch (e) { return {}; } }
export const titleCache = {
  get(roles, topic) {
    const x = tread()[tkey(roles, topic)];
    return x && typeof x.title === "string" ? x : null;
  },
  set(roles, topic, v) {
    const o = tread();
    o[tkey(roles, topic)] = { title: String(v.title).slice(0, 300), summary: String(v.summary || "").slice(0, 700), novelty: v.novelty === "Novel" || v.novelty === "Similar" ? v.novelty : null, checked: !!v.checked, tech: strList(v.tech), domain_labels: strList(v.domain_labels), at: Date.now() };
    const keys = Object.keys(o).sort((a, b) => (o[b].at || 0) - (o[a].at || 0));
    keys.slice(TMAX).forEach((k) => delete o[k]);
    try { window.localStorage.setItem(TKEY, JSON.stringify(o)); } catch (e) { /* không lưu được thì thôi */ }
  },
};

export const store = {
  get: () => read(),
  // gọi sau khi đăng nhập hoặc mở lại trang: lấy hồ sơ của mã này từ máy chủ (hồ sơ trên máy chủ được ưu tiên)
  async attach() {
    mem = null;
    const tk = session.token();
    if (!tk) { window.dispatchEvent(new CustomEvent("rec:store")); return; }
    const local = read();
    try {
      const r = await api.meState(tk);
      if (r && r.state) { mem = clean(r.state); persist(); }
      else if (local.welcomed || local.skills.length || local.roles.length || local.saved.length) await push();     // mã mới nhưng máy đã có bản lưu tạm
    } catch (e) { if (e && e.status === 401) throw e; /* không gọi được máy chủ: dùng bản lưu tạm */ }
    window.dispatchEvent(new CustomEvent("rec:store"));
  },
  detach() { clearTimeout(pushTimer); mem = null; },
  setWelcomed() { read().welcomed = true; write(); },
  setSkills(skills) { read().skills = clean({ skills }).skills; read().welcomed = true; write(); },
  setRoles(roles) { read().roles = clean({ roles }).roles; write(); },
  isSaved: (id) => read().saved.some((s) => s.id === id),
  toggleSaved(item) {
    const d = read(), i = d.saved.findIndex((s) => s.id === item.id);
    if (i >= 0) d.saved.splice(i, 1);
    else d.saved.unshift(cleanItem({ ...item, saved_at: new Date().toISOString() }));
    write();
    return i < 0;
  },
  removeSaved(id) { const d = read(); d.saved = d.saved.filter((s) => s.id !== id); write(); },
  // xuất/nhập hồ sơ để mang sang máy khác
  exportJson() { const d = read(); return JSON.stringify({ app: "rec_student", version: 1, skills: d.skills, roles: d.roles, saved: d.saved }, null, 2); },
  importJson(text) {
    let d;
    try { d = JSON.parse(text); } catch (e) { throw new Error("Tệp không phải hồ sơ hợp lệ."); }
    if (!d || d.app !== "rec_student") throw new Error("Tệp này không phải hồ sơ tải từ trang này.");
    const c = clean(d);
    mem = { ...c, welcomed: true };
    write();
    return mem;
  },
};
