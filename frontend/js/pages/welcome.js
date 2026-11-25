// Màn lần đầu vào web: chọn kỹ năng đã biết. Có nút "Để sau"; dữ liệu chỉ lưu trên trình duyệt.
import { h, clear } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { session } from "../session.js";
import { icon } from "../icons.js";
import { errorBox, loading } from "../ui.js";

const MONO = { "JavaScript": "JS", "TypeScript": "TS", "Kubernetes": "K8", "PostgreSQL": "PG", "MongoDB": "Mg", "MySQL": "My", "SQL Server": "SS", "Oracle Database": "Or", "NoSQL": "NS", "SQL": "SQ", "CI/CD": "CI", "AWS": "AW", "GCP": "GC", "Azure": "Az", "HTML/CSS": "H5", ".NET": ".N", "C#": "C#", "C++": "C+", "REST API": "API", "gRPC": "gR", "Node.js": "Nd", "Power BI": "BI", "AI": "AI", "LLM": "LM", "RAG": "RG", "NLP": "NL" };
export function monogram(name) {
  if (MONO[name]) return MONO[name];
  const w = String(name).split(/[\s/&-]+/).filter(Boolean);
  return (w.length > 1 ? w[0][0] + w[1][0].toUpperCase() : String(name).slice(0, 2)).replace(/^./, (c) => c.toUpperCase());
}

export function render(root, params, ctx) {
  let picked = store.get().skills.slice(), max = 80;
  const box = h("div", { class: "wl-groups" }, loading());
  const count = h("span", { class: "pk-count" });
  const ok = h("button", { type: "button", class: "btn btn-primary btn-lg", onclick: () => { store.setSkills(picked); window.location.hash = "#/skills"; } }, "Xem kết quả của mình");
  const later = h("button", { type: "button", class: "btn btn-lg", onclick: () => { store.setWelcomed(); window.location.hash = "#/"; } }, "Để sau");
  root.append(h("div", { class: "wl" }, h("div", { class: "wl-card" },
    h("div", { class: "pk-head" }, h("div", null, h("span", { class: "pill" }, "Chào bạn, lần đầu ghé thăm"), h("h1", null, "Bạn đã biết những gì rồi?"),
      h("p", { class: "lead" }, "Bấm chọn những kỹ năng bạn đã dùng được. Mình sẽ cho bạn thấy bạn đang hợp với công việc nào và nên học gì tiếp theo.")), h("span", { class: "pk-step" }, "Chỉ mất 1 phút")),
    box,
    h("p", { class: "note" }, "Thông tin này được lưu theo mã sinh viên của bạn, đăng nhập ở máy nào cũng thấy. Bạn có thể sửa hoặc tải về bất cứ lúc nào ở mục \"Kỹ năng của tôi\".", h("button", { type: "button", class: "wl-out", onclick: () => { const tk = session.token(); if (tk) api.logout(tk).catch(() => {}); session.clear(); store.detach(); window.location.hash = "#/start"; } }, "Không phải bạn? Đăng xuất")),
    h("div", { class: "pk-foot" }, count, h("div", { class: "row" }, later, ok)))));

  function paintCount() {
    count.textContent = "";
    count.append("Đã chọn ", h("strong", null, String(picked.length)), " kỹ năng");
    ok.disabled = picked.length === 0;
  }

  function paint(groups) {
    clear(box).append(...groups.map((g) => h("div", { class: "wl-group" }, h("span", { class: "wl-gname" }, g.label),
      h("div", { class: "tiles" }, g.skills.map((s) => {
        const on = picked.includes(s.name);
        return h("button", { type: "button", class: "tile" + (on ? " tile-on" : ""), "aria-pressed": on ? "true" : "false", onclick: (ev) => {
          picked = picked.includes(s.name) ? picked.filter((x) => x !== s.name) : picked.length < max ? [...picked, s.name] : picked;
          const b = ev.currentTarget, nowOn = picked.includes(s.name);
          b.classList.toggle("tile-on", nowOn); b.setAttribute("aria-pressed", nowOn ? "true" : "false");
          paintCount();
        } }, (String(s.name).length > 3 && monogram(s.name).toLowerCase() !== String(s.name).toLowerCase() ? h("span", { class: "tile-mono" }, monogram(s.name)) : null), h("span", { class: "tile-name" }, s.name), h("span", { class: "tile-tick" }, icon("check", 12)));
      })))));
    paintCount();
  }

  function fetchSkills() {
    clear(box).append(loading());
    api.skills({ signal: ctx.signal }).then((d) => { if (ctx.signal.aborted) return; max = d.max_skills || 80; paint(d.groups); })
      .catch((e) => { if (e && e.name === "AbortError") return; clear(box).append(errorBox(e, fetchSkills)); });
  }
  fetchSkills();
  paintCount();
}
