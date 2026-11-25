// Một màn hình đăng nhập chung: sinh viên và quản trị viên đều nhập mã trong CSDL. Mã có vai trò admin tự vào trang quản trị.
import { h } from "../dom.js";
import { api } from "../api.js";
import { session } from "../session.js";
import { store } from "../store.js";

export const title = "Đăng nhập";

export function render(root, params, ctx) {
  const idIn = h("input", { class: "lg-input", id: "lg-id", type: "text", inputmode: "text", autocomplete: "username", autocapitalize: "characters", spellcheck: "false", placeholder: "Ví dụ: 11236197", maxlength: "24" });
  const msg = h("p", { class: "lg-msg", id: "lg-msg", role: "alert" });
  const btn = h("button", { type: "submit", class: "lg-btn" }, "Đăng nhập");
  const fail = (t) => { msg.textContent = t; msg.classList.add("on"); btn.disabled = false; btn.textContent = "Đăng nhập"; };
  const busy = () => { btn.disabled = true; btn.textContent = "Đang kiểm tra…"; msg.classList.remove("on"); };

  function go(admin) {
    let next = "";
    try { next = window.sessionStorage.getItem("rec_next") || ""; window.sessionStorage.removeItem("rec_next"); } catch (e) { /* bỏ qua */ }
    window.location.hash = admin ? "#/admin" : next.startsWith("#/") && !next.startsWith("#/login") ? next : "#/";
  }

  async function submit(ev) {
    ev.preventDefault();
    const id = idIn.value.trim();
    if (!id) { fail("Hãy nhập mã sinh viên."); idIn.focus(); return; }
    busy();
    try {
      const r = await api.login(id, "", { signal: ctx.signal });
      session.set({ token: r.token, student: r.student });
      await store.attach();
      go(r.student.role === "admin");
    } catch (e) {
      if (e && e.name === "AbortError") return;
      if (e && e.status === 401) { session.clear(); return fail(String(e.detail || "Mã chưa đúng.")); }
      if (e && e.status === 400) return fail(String(e.detail || "Mã sinh viên không hợp lệ."));
      if (e && e.status === 0) return fail("Chưa kết nối được máy chủ. Hãy kiểm tra backend đã chạy chưa.");
      if (e && e.status === 404) return fail("Máy chủ chưa được cập nhật. Hãy khởi động lại backend rồi nhấn Ctrl+F5.");
      fail("Có lỗi xảy ra, hãy thử lại.");
    }
  }

  root.append(h("div", { class: "lg" }, h("i", { class: "st-glow g1" }), h("i", { class: "st-glow g2" }),
    h("div", { class: "lg-card" },
      h("img", { class: "lg-logo", src: "logo.svg", alt: "NET", width: 64, height: 64 }),
      h("h1", null, "Đăng nhập"),
      h("p", { class: "lg-sub" }, "Nhập mã sinh viên (8 chữ số, bắt đầu bằng 11) để vào NET. Kỹ năng và đề tài bạn lưu sẽ gắn với mã này, đăng nhập ở máy nào cũng thấy."),
      h("form", { onsubmit: submit, novalidate: true },
        h("label", { class: "lg-lab", for: "lg-id" }, "Mã sinh viên"), h("div", { class: "lg-field" }, idIn), msg, btn),
      h("a", { class: "lg-back", href: "#/start" }, "← Về trang giới thiệu"))));
  window.setTimeout(() => idIn.focus(), 50);
}
