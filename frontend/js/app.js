import { h, clear, add } from "./dom.js";
import { api } from "./api.js";
import { icon } from "./icons.js";
import { store } from "./store.js";
import { session } from "./session.js";
import "./tabs.js";
import * as home from "./pages/home.js";
import * as welcome from "./pages/welcome.js";
import * as ideas from "./pages/ideas.js";
import * as library from "./pages/library.js";
import * as trends from "./pages/trends.js";
import * as check from "./pages/check.js";
import * as skills from "./pages/skills.js";
import * as saved from "./pages/saved.js";
import * as jobs from "./pages/jobs.js";
import * as admin from "./pages/admin.js";
import * as start from "./pages/start.js";
import * as login from "./pages/login.js";

// nav: hiện trên thanh bên; parent: trang con sáng mục cha; bare: không có thanh bên
const cnt = (n) => (n > 9 ? "9+" : String(n));
const ROUTES = [
  { path: "/", label: "Trang chủ", icon: "home", page: home, nav: true },
  { path: "/skills", label: "Kỹ năng của tôi", icon: "user", page: skills, nav: true, group: "Chọn đề tài" },
  { path: "/ideas", label: "Đề xuất khóa luận", icon: "bulb", page: ideas, nav: true },
  { path: "/check", label: "Kiểm tra đề tài", icon: "scan", page: check, nav: true },
  { path: "/saved", label: "Đề tài đã lưu", icon: "heart", page: saved, nav: true, count: true },
  { path: "/library", label: "Kho khóa luận", icon: "book", page: library, nav: true, group: "Tham khảo" },
  { path: "/trends", label: "Xu hướng", icon: "generic", page: trends, nav: true },
  { path: "/dashboard", label: "Xu hướng khóa luận", page: trends, parent: "/trends" },     // đường dẫn cũ
  { path: "/jobs", label: "Tin tuyển dụng", page: jobs, parent: "/" },
  { path: "/start", label: "NET", page: start, bare: true, full: true },
  { path: "/login", label: "Đăng nhập quản trị", page: login, bare: true, full: true },
  { path: "/welcome", label: "Bạn đã biết những gì rồi", page: welcome, bare: true },
  { path: "/admin", label: "Quản trị", page: admin, parent: null },
];

function parseHash() {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, query] = raw.split("?");
  return { path: path || "/", params: Object.fromEntries(new URLSearchParams(query || "")) };
}

let current = null; // AbortController của trang đang hiển thị

const hasAdminToken = () => session.isAdmin();   // quản trị viên = mã có vai trò admin trong CSDL

function me() {
  const u = session.student();
  if (!u) return null;
  const nm = u.name || u.student_id;
  return h("div", { class: "me" }, h("span", { class: "av", "aria-hidden": "true" }, nm.trim()[0].toUpperCase()),
    h("div", { class: "who" }, h("b", null, nm), h("small", null, u.name ? u.student_id : u.role === "admin" ? "Quản trị viên" : "Sinh viên")),
    h("button", { type: "button", class: "out", title: "Đăng xuất", "aria-label": "Đăng xuất", onclick: logout }, icon("exit", 18)));
}

async function logout() {
  const tk = session.token();
  try { if (tk) await api.logout(tk); } catch (e) { /* hết hạn hoặc mất mạng: vẫn đăng xuất trên máy này */ }
  session.clear(); store.detach();
  if (window.location.hash === "#/start") route(); else window.location.hash = "#/start";
}

function paintNav(r) {
  const nav = document.getElementById("nav");
  const active = r.parent === undefined ? r.path : r.parent;
  const items = ROUTES.filter((x) => x.nav);
  const n = store.get().saved.length;
  add(clear(nav), [
    h("a", { class: "brand", href: "#/" }, h("span", { class: "logo" }, h("img", { src: "logo.svg", alt: "NET", width: 44, height: 44 })), h("span", { class: "brand-t" }, h("strong", null, "NE", h("em", null, "T")), h("small", null, "National Economics Thesis"))),
    h("ul", null, items.map((x) => h("li", x.group ? { class: "nav-grp", "data-grp": x.group } : null, h("a", { href: "#" + x.path, "aria-current": x.path === active ? "page" : null }, icon(x.icon), h("span", null, x.label),
      x.count && n > 0 ? h("span", { class: "count", id: "saved-count" }, cnt(n)) : null)))),
    session.isAdmin() && hasAdminToken() ? h("a", { class: "admin-link", href: "#/admin" }, "Quản trị") : null,
    me()]);
}

async function paintBadge() {
  if (!document.getElementById("pend-badge")) return;   // huy hiệu nhóm chờ duyệt đã bỏ cùng tab Nhóm công việc
  try {
    const d = await api.roles();
    const b = document.getElementById("pend-badge");
    if (b && d.pending_count > 0) { b.textContent = String(d.pending_count); b.hidden = false; b.title = d.pending_count + " nhóm công việc chờ duyệt"; }
  } catch (e) { /* không có huy hiệu khi API chưa chạy */ }
}

function route() {
  if (current) current.abort();
  current = new AbortController();
  const ctx = { signal: current.signal };
  const { path, params } = parseHash();
  const st = store.get();
  const sess = session.get();
  if (!sess && path !== "/start" && path !== "/login") {                    // chưa đăng nhập: về trang đăng nhập, xong quay lại đúng trang đang muốn vào
    try { window.sessionStorage.setItem("rec_next", window.location.hash); } catch (e) { /* bỏ qua */ }
    window.location.replace("#/login"); return;
  }
  if (sess && path === "/login") { window.location.replace(session.isAdmin() ? "#/admin" : "#/"); return; }
  if (path === "/admin" && !(session.isAdmin() && hasAdminToken())) {           // chỉ quản trị viên (mã có vai trò admin)
    if (sess && !session.isAdmin()) { window.location.replace("#/"); return; }
    session.clear(); store.detach(); window.location.replace("#/login"); return;
  }
  if (!st.welcomed && !session.isAdmin() && !["/start", "/welcome", "/login", "/admin"].includes(path)) { window.location.replace("#/welcome"); return; }   // lần đầu: hỏi kỹ năng (có nút Để sau)   // lần đầu vào: hỏi kỹ năng (có nút Để sau)
  const r = ROUTES.find((x) => x.path === path) || ROUTES[0];
  document.title = r.label + " · NET";
  document.getElementById("app").classList.toggle("bare", !!r.bare);
  document.getElementById("app").classList.toggle("full", !!r.full);
  paintNav(r);
  const main = document.getElementById("main");
  clear(main);
  r.page.render(main, params, ctx);
  paintBadge();
  window.scrollTo(0, 0);
}

// cập nhật số đề tài đã lưu trên thanh bên mà không dựng lại trang
window.addEventListener("rec:store", () => {
  const n = store.get().saved.length, li = [...document.querySelectorAll('#nav a[href="#/saved"]')][0];
  if (!li) return;
  let c = li.querySelector(".count");
  if (n > 0) { if (!c) { c = h("span", { class: "count" }); li.append(c); } c.textContent = cnt(n); c.title = n + " đề tài đã lưu"; }
  else if (c) c.remove();
});
window.addEventListener("hashchange", route);
window.addEventListener("rec:session-expired", () => { session.clear(); store.detach(); window.location.hash = "#/login"; });

// mở lại trang: nếu còn phiên thì kiểm tra với máy chủ và nạp hồ sơ của mã này trước khi vẽ trang
async function boot() {
  if (session.token()) {
    try { await api.me(session.token()); await store.attach(); }
    catch (e) { if (e && e.status === 401) { session.clear(); store.detach(); } /* lỗi khác (mất mạng): dùng bản lưu tạm trên máy */ }
  }
  route();
}
boot();
