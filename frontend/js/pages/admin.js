import { h, clear } from "../dom.js";
import { api } from "../api.js";
import { session } from "../session.js";
import { pageHead, errorBox, notice, limits } from "../ui.js";
import * as overview from "./admin_overview.js";
import * as ops from "./admin_ops.js";
import * as thesis from "./admin_thesis.js";
import * as students from "./admin_students.js";

export const title = "Quản trị";
const KEY = "rec_admin_token";
const getTok = () => (session.isAdmin() ? "session" : "");
const setTok = () => {};

const TABS = [
  { id: "overview", label: "Tổng quan", mod: overview },
  { id: "ops", label: "Chạy lệnh", mod: ops },
  { id: "thesis", label: "Khóa luận", mod: thesis },
  { id: "students", label: "Sinh viên", mod: students },
];

export function render(root, params, ctx) {
  const body = h("div", { class: "adm ad-wrap" });
  const me = session.student();
  root.append(body);
  let token = getTok();

  function login(msg) {
    window.location.replace("#/login" + (msg ? "?e=1" : ""));
    return;
    const input = h("input", { class: "input", id: "tk", type: "password", autocomplete: "off" });
    clear(body).append(h("form", { class: "card", onsubmit: (ev) => { ev.preventDefault(); token = input.value.trim(); if (!token) return; setTok(token); start(); } },
      h("div", { class: "field" }, h("label", { for: "tk" }, "Mã quản trị"), input), msg ? notice(msg) : null, h("button", { type: "submit", class: "btn btn-primary" }, "Vào")));
  }
  const A = {
    signal: ctx.signal,
    get: (p) => api.adminGet(token, p, { signal: ctx.signal }),
    post: (p, b) => api.adminPost(token, p, b, { signal: ctx.signal }),
    fail(box, e, retry) {
      if (e && e.name === "AbortError") return;
      if (e && e.status === 401) { session.clear(); window.location.hash = "#/login"; return; }
      clear(box).append(errorBox(e, retry));
    },
  };
  function start() {
    if (!token) return login();
    const tab = TABS.find((t) => t.id === params.tab) || TABS[0];
    const content = h("div", { class: "ad-body" });
    clear(body).append(
      h("header", { class: "ad-head" },
        h("div", null, h("h1", null, "Quản trị"), h("p", null, "Dữ liệu, crawl, nhãn và tài khoản của NET")),
        h("span", { class: "ad-who" }, h("i", null), (me && me.student_id) || "admin")),
      h("nav", { class: "ad-tabs", "aria-label": "Mục quản trị" }, TABS.map((t) => h("a", { href: "#/admin?tab=" + t.id, class: "ad-tab", "aria-current": t.id === tab.id ? "page" : null }, t.label))),
      content,
      h("details", { class: "ad-notes" }, h("summary", null, "Lưu ý khi quản trị"),
        h("ul", null, h("li", null, "Quyền quản trị lấy từ mã quản trị viên đã đăng nhập (vai trò admin trong cơ sở dữ liệu)."), h("li", null, "Lệnh chạy ngay trên máy đang chạy backend."))));
    tab.mod.mount(content, A);
  }
  start();
}
