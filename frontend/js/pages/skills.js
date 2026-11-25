// Kỹ năng của tôi: hồ sơ lưu trên trình duyệt, mức hợp với từng công việc, nên học gì tiếp.
import { h, clear } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { errorBox, foot, loading, notice, pctText } from "../ui.js";

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const a = h("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function render(root, params, ctx) {
  const known = store.get().skills;
  if (!known.length) {
    root.append(h("section", { class: "card empty" }, h("h1", null, "Kỹ năng của tôi"), h("p", { class: "lead" }, "Bạn chưa chọn kỹ năng nào. Chọn những kỹ năng bạn đã biết để xem mình hợp với công việc nào và nên học gì tiếp."),
      h("a", { class: "btn btn-primary btn-lg", href: "#/welcome" }, "Chọn kỹ năng của tôi")));
    return;
  }
  const msg = h("div", { class: "stack-s" });
  const fileIn = h("input", { type: "file", accept: "application/json,.json", hidden: true, onchange: () => {
    const f = fileIn.files && fileIn.files[0];
    if (!f) return;
    if (f.size > 500000) { clear(msg).append(notice("Tệp quá lớn để là hồ sơ.")); return; }
    f.text().then((t) => { try { store.importJson(t); clear(root); render(root, params, ctx); } catch (e) { clear(msg).append(notice(e.message)); } });
  } });
  const stat = (v, l) => h("div", null, h("b", null, v), h("span", null, l));
  const stats = h("div", { class: "sk-stats" }, stat(String(known.length), "kỹ năng đã chọn"), stat("…", "hợp nhất với công việc"), stat("…", "kỹ năng nên học tiếp"));
  const skillsBox = h("div", { class: "sk-groups" }, h("div", { class: "sk-chips" }, known.map((k) => h("span", null, k))));
  const body = h("div", { class: "sk-body" });
  root.append(h("div", { class: "sk" },
    h("section", { class: "sk-hero" },
      h("div", { class: "sk-top" }, h("div", null, h("h1", null, "Kỹ năng của tôi"),
        h("p", null, "Bạn đã chọn " + known.length + " kỹ năng. Hệ thống đối chiếu với các tin tuyển dụng để xem bạn hợp với việc nào.")),
        h("div", { class: "sk-act" }, h("a", { class: "sk-b w", href: "#/welcome" }, "Sửa kỹ năng"),
          h("button", { type: "button", class: "sk-b", onclick: () => download("ho-so-ky-nang.json", store.exportJson()) }, "Tải hồ sơ về"),
          h("button", { type: "button", class: "sk-b", onclick: () => fileIn.click() }, "Nhập hồ sơ"), fileIn)),
      stats, h("p", { class: "sk-lab" }, "Kỹ năng của bạn"), skillsBox,
      h("p", { class: "sk-note" }, "Hồ sơ được lưu theo mã sinh viên của bạn, đăng nhập ở máy khác vẫn thấy. Bạn cũng có thể bấm \"Tải hồ sơ về\" để giữ một bản riêng."), msg),
    body));

  body.append(h("div", { class: "sk-card" }, h("h2", null, "Bạn hợp với công việc nào?"), h("p", { class: "sk-sub" }, "Đang đối chiếu với các tin tuyển dụng…"),
    h("div", { class: "sk-roles" }, [0, 1, 2, 3].map(() => h("div", { class: "sk-role hold" }, h("span", { class: "skel" }), h("span", { class: "skel skel-s" }))))));
  api.profile(known, { signal: ctx.signal }).then((d) => {
    if (ctx.signal.aborted) return;
    const best = d.roles[0];
    clear(stats).append(stat(String(known.length), "kỹ năng đã chọn"), stat(best ? pctText(best.match) : "—", best ? "hợp nhất: " + best.label : "hợp nhất với công việc"), stat(String(d.path.length), "kỹ năng nên học tiếp"));
    if (d.groups && d.groups.length) clear(skillsBox).append(...d.groups.map((g) => h("div", { class: "sk-g" }, h("small", null, g.label), h("div", { class: "sk-chips" }, g.skills.map((k) => h("span", null, k))))));
    clear(body);
    if (d.ignored.length) body.append(notice("Có kỹ năng không còn trong danh mục nên chưa tính: " + d.ignored.join(", ") + "."));
    const MAXR = 3, picked = new Set(store.get().roles.filter((x) => d.roles.some((r) => r.role === x)).slice(0, MAXR));
    const rows = new Map(), goBtn = h("button", { type: "button", class: "sk-b w", onclick: go }, "Xem đề tài gợi ý"), pickTxt = h("div", { class: "pt" });
    const pickBar = h("div", { class: "sk-pick" }, pickTxt, goBtn);
    function go() { if (!picked.size) return; store.setRoles([...picked]); window.location.hash = "#/ideas"; }
    function paintPick() {
      for (const [role, el] of rows) {
        const on = picked.has(role), full = picked.size >= MAXR && !on;
        el.classList.toggle("on", on); el.classList.toggle("off", full); el.setAttribute("aria-checked", on ? "true" : "false"); el.setAttribute("aria-disabled", full ? "true" : "false");
      }
      const names = d.roles.filter((r) => picked.has(r.role)).map((r) => r.label);
      clear(pickTxt).append(h("b", null, picked.size ? "Đã chọn " + picked.size + "/" + MAXR + " công việc" : "Chọn tối đa " + MAXR + " công việc để xem đề tài"),
        h("span", null, picked.size ? names.join(" · ") : "Bấm vào công việc bạn quan tâm trong danh sách."));
      goBtn.disabled = !picked.size; pickBar.classList.toggle("ready", picked.size > 0);
    }
    function toggle(role) { if (picked.has(role)) picked.delete(role); else if (picked.size < MAXR) picked.add(role); paintPick(); }
    const roleCard = (r, i) => { const el = h("div", { class: "sk-role" + (i === 0 ? " best" : ""), role: "checkbox", tabindex: "0", onclick: () => toggle(r.role),
        onkeydown: (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle(r.role); } } },
      h("span", { class: "no" }, String(i + 1)),
      h("div", { class: "mid" }, h("div", { class: "nm" }, h("b", null, r.label), i === 0 ? h("em", { class: "bst" }, "Hợp nhất") : null),
        r.missing.length ? h("div", { class: "chs" }, h("small", null, "Còn thiếu"), r.missing.map((m) => h("span", null, m.name))) : h("div", { class: "chs" }, h("small", { class: "ok" }, "Đã đủ kỹ năng cốt lõi"))),
      h("div", { class: "pc" }, h("b", null, pctText(r.match)), h("div", { class: "tr" }, h("i", { style: `width:${(r.match * 100).toFixed(0)}%` }))),
      h("span", { class: "cb", "aria-hidden": "true" }, "✓"));
      rows.set(r.role, el); return el; };
    body.append(
      h("section", { class: "sk-card" }, h("h2", null, "Bạn hợp với công việc nào?"),
        h("p", { class: "sk-sub" }, "Tỷ lệ kỹ năng thường gặp của công việc mà bạn đã có. Chọn tối đa 3 công việc bạn quan tâm rồi bấm \"Xem đề tài gợi ý\". ", h("a", { href: "#/jobs?role=" + encodeURIComponent((d.roles[0] || {}).role || "") }, "Xem tin tuyển dụng thật ›")),
        h("div", { class: "sk-roles" }, d.roles.map(roleCard)), pickBar),
      h("section", { class: "sk-card" }, h("h2", null, "Nên học gì tiếp theo?"),
        h("p", { class: "sk-sub" }, "Xếp theo mức được nhắc đến trong tin của " + d.path_roles.join(", ") + " (các công việc bạn đang hợp nhất), kèm kỹ năng bạn đã có mà nó hay đi cùng."),
        d.path.length ? h("div", { class: "sk-path" }, d.path.map((p, i) => h("div", { class: "st" }, h("span", { class: "n" }, String(i + 1)),
          h("div", { class: "sb" }, h("div", { class: "sh" }, h("b", null, p.name), h("em", null, pctText(p.share) + " tin nhắc đến")),
            h("div", { class: "tr" }, h("i", { style: `width:${Math.min(100, p.share * 100).toFixed(0)}%` })),
            h("p", null, p.near ? "Hay đi cùng " : "Kỹ năng này nhiều tin nhắc đến.", p.near ? h("u", null, p.near) : null, p.near ? " mà bạn đã biết." : null))))) : h("p", { class: "sk-sub" }, "Chưa có gợi ý thêm: bạn đã có các kỹ năng được nhắc nhiều nhất.")),
      foot(d.note + " Hệ thống đối chiếu với " + d.n_jobs + " tin tuyển dụng đã thu thập."));
    paintPick();
  }).catch((e) => { if (e && e.name !== "AbortError") clear(body).append(errorBox(e, () => { clear(root); render(root, params, ctx); })); });
}
