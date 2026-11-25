// Cửa sổ "Đề tài đã có": danh sách khóa luận cùng hướng với một gợi ý. Bấm một khóa luận sẽ đi tới đúng khóa luận đó trong Kho khóa luận.
import { h, clear } from "./dom.js";
import { api } from "./api.js";
import { errorBox, loading, yearSchool } from "./ui.js";

const PAGE = 20;
let open = null;                 // chỉ mở một cửa sổ một lúc

// opts: { topic, topicLabel, domain, domainLabel }  (domain có thể trống)
export function openRefs(opts) {
  if (open) return;
  const back = document.activeElement;
  let scope = opts.domain ? "both" : "topic", offset = 0, seq = 0;
  const ctrl = new AbortController();

  const chips = h("div", { class: "rf-chips" });
  const list = h("div", { class: "rf-list" });
  const more = h("div", { class: "row center" });
  const count = h("span", { class: "pk-count" });
  const title = h("h2", { id: "rf-title" }, opts.title || "Đề tài đã có trong kho");
  const dlg = h("div", { class: "pk rf", role: "dialog", "aria-modal": "true", "aria-labelledby": "rf-title" },
    h("div", { class: "pk-head" },
      h("div", null, title, h("p", { class: "lead" }, opts.lead || ("Các khóa luận cùng hướng \"" + opts.topicLabel + "\". Bấm vào một khóa luận để xem nó trong Kho khóa luận."))),
      h("button", { type: "button", class: "btn", onclick: close, "aria-label": "Đóng" }, "Đóng")),
    chips,
    h("div", { class: "pk-body" }, list, more),
    h("div", { class: "pk-foot" }, count, h("button", { type: "button", class: "btn btn-lg", onclick: close }, "Đóng")));
  const overlay = h("div", { class: "overlay", onmousedown: (ev) => { if (ev.target === overlay) close(); } }, dlg);
  overlay.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") { ev.preventDefault(); close(); return; }
    if (ev.key !== "Tab") return;                                       // giữ tiêu điểm bàn phím trong cửa sổ
    const f = [...dlg.querySelectorAll("button:not([disabled]), a[href]")];
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
  });
  document.body.append(overlay);
  document.body.classList.add("modal-open");
  open = { overlay };
  paintChips();
  fetchPage();
  dlg.querySelector("button").focus();

  function close() {
    if (!open) return;
    ctrl.abort();
    overlay.remove(); open = null;
    document.body.classList.remove("modal-open");
    if (back && back.focus) back.focus();
  }

  function paintChips() {
    clear(chips);
    if (!opts.domain || opts.topics || opts.fixed) return;
    [["both", "Cùng chủ đề và lĩnh vực " + opts.domainLabel], ["topic", "Mọi khóa luận cùng chủ đề"]].forEach(([k, text]) =>
      chips.append(h("button", { type: "button", class: "kh-hint" + (scope === k ? " on" : ""), "aria-pressed": scope === k ? "true" : "false", onclick: () => { if (scope === k) return; scope = k; paintChips(); reload(); } }, text)));
  }

  function row(t) {
    if (opts.fixed) return h("div", { class: "rf-item rf-pdf" },
      h("div", null, h("span", { class: "rf-t" }, t.title), h("small", null, yearSchool(t))),
      t.report_url ? h("a", { class: "btn btn-sm", href: t.report_url, target: "_blank", rel: "noopener noreferrer", "aria-label": "Xem PDF: " + t.title }, "Xem PDF ›") : h("small", null, "Chưa có PDF"));
    return h("a", { class: "rf-item", href: "#/library?id=" + encodeURIComponent(t.thesis_id), onclick: close },
      h("span", { class: "rf-t" }, t.title), h("small", null, yearSchool(t)));
  }

  function reload() { offset = 0; clear(list); fetchPage(); }

  async function fetchPage() {
    const mine = ++seq;
    more.replaceChildren(loading("Đang tải…"));
    try {
      let d;
      if (opts.topics) {                                                  // nhóm "Khác": gộp nhiều chủ đề nhỏ của một lĩnh vực, lọc phía trình duyệt
        const all = await api.thesisList({ domain: opts.domain, source: opts.source || undefined, limit: 200 }, { signal: ctrl.signal });
        const want = new Set(opts.topics.filter(Boolean));
        const items = all.items.filter((t) => (t.technical_topics || []).some((x) => want.has(x)) || (opts.noTopic && !(t.technical_topics || []).length));
        d = { items: items.slice(offset, offset + PAGE), total: items.length };
      } else d = await api.thesisList({ topic: opts.topic, domain: scope === "both" ? opts.domain : undefined, source: opts.source || undefined, limit: PAGE, offset }, { signal: ctrl.signal });
      if (mine !== seq || ctrl.signal.aborted) return;
      d.items.forEach((t) => list.append(row(t)));
      offset += PAGE;
      clear(more);
      if (!d.total) list.append(h("div", { class: "state" }, "Chưa có khóa luận nào khớp."));
      if (offset < d.total) more.append(h("button", { type: "button", class: "btn btn-primary", onclick: fetchPage }, "Xem thêm"));
      count.textContent = "Đang hiện " + Math.min(offset, d.total) + "/" + d.total + " khóa luận" + (d.total ? ", năm mới nhất trước" : "");
    } catch (e) {
      if (e && e.name === "AbortError") return;
      if (mine === seq) clear(more).append(errorBox(e, fetchPage));
    }
  }
}
