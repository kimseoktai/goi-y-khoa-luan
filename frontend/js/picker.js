// Cửa sổ "Bạn mê công việc nào?": chọn 1 đến 3 công việc. Lựa chọn được nhớ trên trình duyệt nên chỉ phải chọn một lần.
import { h, clear } from "./dom.js";
import { api } from "./api.js";
import { icon } from "./icons.js";
import { store } from "./store.js";
import { errorBox, loading } from "./ui.js";

let open = null;                 // chỉ mở một cửa sổ một lúc

// opts: { preselect: tên công việc cần chọn sẵn, onDone(roles) }
export function openPicker(opts = {}) {
  if (open) return;
  const back = document.activeElement;
  let picked = store.get().roles.slice();
  if (opts.preselect && !picked.includes(opts.preselect)) picked = [...picked, opts.preselect].slice(-3);
  let max = 3, items = [];

  const body = h("div", { class: "pk-body" }, loading());
  const count = h("span", { class: "pk-count" });
  const ok = h("button", { type: "button", class: "btn btn-primary btn-lg", onclick: confirm }, "Xem đề tài gợi ý");
  const title = h("h2", { id: "pk-title" }, "Bạn mê công việc nào?");
  const dlg = h("div", { class: "pk", role: "dialog", "aria-modal": "true", "aria-labelledby": "pk-title" },
    h("div", { class: "pk-head" },
      h("div", null, title, h("p", { class: "lead" }, "Chọn những công việc bạn thấy hứng thú. Mình sẽ dựa vào kỹ năng các công việc đó cần để gợi ý đề tài khóa luận hợp với bạn. Bạn chỉ cần chọn một lần, mình sẽ nhớ cho các lần sau và bạn có thể đổi bất cứ lúc nào.")),
      h("span", { class: "pk-step" }, "Chọn tối đa 3")),
    body,
    h("div", { class: "pk-foot" }, count, h("div", { class: "row" }, h("button", { type: "button", class: "btn btn-lg", onclick: close }, "Hủy"), ok)));
  const overlay = h("div", { class: "overlay", onmousedown: (ev) => { if (ev.target === overlay) close(); } }, dlg);
  overlay.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") { ev.preventDefault(); close(); return; }
    if (ev.key !== "Tab") return;                                       // giữ tiêu điểm bàn phím trong cửa sổ
    const f = [...dlg.querySelectorAll("button:not([disabled])")];
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
  });
  document.body.append(overlay);
  document.body.classList.add("modal-open");
  open = { overlay };

  function close() {
    if (!open) return;
    overlay.remove(); open = null;
    document.body.classList.remove("modal-open");
    if (back && back.focus) back.focus();
  }

  function confirm() {
    if (!picked.length) return;
    store.setRoles(picked);
    close();
    if (opts.onDone) opts.onDone(picked); else window.location.hash = "#/ideas";
  }

  function paint() {
    clear(body).append(h("div", { class: "pk-grid" }, items.map((r) => {
      const on = picked.includes(r.name), full = !on && picked.length >= max;
      return h("button", { type: "button", class: "role" + (on ? " role-on" : ""), "aria-pressed": on ? "true" : "false", disabled: full || null, onclick: () => toggle(r.name) },
        h("span", { class: "role-top" }, icon(r.name, 28), r.hot ? h("span", { class: "hot" }, "Hot") : null),
        h("span", { class: "role-name" }, r.label), h("span", { class: "role-desc" }, r.description),
        on ? h("span", { class: "role-tick" }, icon("check", 14)) : null);
    })));
    count.textContent = "";
    count.append("Đã chọn ", h("strong", null, String(picked.length)), " công việc. Chọn từ 1 đến " + max + " công việc để gợi ý chính xác hơn.");
    ok.disabled = !picked.length;
  }

  function toggle(name) {
    picked = picked.includes(name) ? picked.filter((x) => x !== name) : picked.length < max ? [...picked, name] : picked;
    const y = body.scrollTop;
    paint();
    body.scrollTop = y;
    const el = [...body.querySelectorAll(".role")].find((b) => b.querySelector(".role-name").textContent === (items.find((r) => r.name === name) || {}).label);
    if (el) el.focus();
  }

  api.studentRoles().then((d) => {
    if (!open) return;
    items = d.items; max = d.max_roles || 3;
    picked = picked.filter((p) => items.some((r) => r.name === p));        // bỏ công việc đã không còn trong danh sách
    paint();
    const first = body.querySelector(".role");
    if (first) first.focus();
  }).catch((e) => { if (open) clear(body).append(errorBox(e, () => { close(); openPicker(opts); })); });
}
