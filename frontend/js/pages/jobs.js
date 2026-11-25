// Tin tuyển dụng thật của một công việc; kỹ năng bạn đã chọn được tô nổi, mức hợp hiện bằng vòng tròn.
import { h, clear, add } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { icon } from "../icons.js";
import { errorBox, foot, loading } from "../ui.js";

const PAGE = 10;
const HUES = [268, 292, 322, 222, 188, 24];
const hue = (t) => HUES[[...String(t || "?")].reduce((a, c) => a + c.charCodeAt(0), 0) % HUES.length];
const initial = (t) => (String(t || "?").replace(/^(ngân hàng|công ty|cty|tổng công ty|tập đoàn)\s+(tmcp\s+|cổ phần\s+|tnhh\s+)?/i, "").trim()[0] || "?").toUpperCase();

const SOURCES = { topdev: "TopDev", itviec: "ITviec", careerviet: "CareerViet" };
function when(j) {
  const p = [], m = /^(\d{4})-(\d{2})-(\d{2})/.exec(j.posted_at || "");
  if (m) p.push("Đăng " + m[3] + "/" + m[2] + "/" + m[1]);
  if (SOURCES[j.source]) p.push("Nguồn " + SOURCES[j.source]);
  return p.join(" · ");
}

export function render(root, params, ctx) {
  const mine = new Set(store.get().skills);
  let role = params.role || "", offset = 0, roles = [];
  const loaded = [];
  const chips = h("div", { class: "rolebar", role: "tablist", "aria-label": "Chọn công việc" });
  const list = h("div", { class: "stack-s" });
  const more = h("div", { class: "row center" });
  const title = h("h1", null, "Tin tuyển dụng");
  const stats = h("div", { class: "hstats" });
  const top = h("div", { class: "toprow" });
  const cta = h("a", { class: "btn btn-white btn-lg", href: "#/ideas" }, "Xem đề tài hợp với công việc này", icon("arrow", 18));
  root.append(
    h("section", { class: "jhero" },
      h("a", { class: "jback", href: "#/" }, "‹ Về trang chủ"),
      h("div", { class: "jhero-row" }, h("div", { class: "stack-s" }, h("span", { class: "jkicker" }, "Tin tuyển dụng thật"), title, stats), cta),
      top),
    h("section", { class: "card rolecard" }, h("span", { class: "lbl" }, "Chọn công việc khác"), chips),
    list, more, foot("Tin lấy từ dữ liệu đã thu thập, có thể đã hết hạn tuyển. Hãy mở tin gốc để xem thông tin mới nhất."));

  function stat(n, label) { return h("div", { class: "hstat" }, h("b", null, n), h("span", null, label)); }
  function paintHero(d) {
    title.textContent = d.role_label;
    cta.setAttribute("href", "#/ideas?role=" + encodeURIComponent(role));
    const companies = new Set(loaded.map((j) => j.company).filter(Boolean)).size;
    const avg = mine.size && loaded.length ? Math.round(100 * loaded.reduce((a, j) => a + (j.skills.length ? j.skills.filter((s) => mine.has(s)).length / j.skills.length : 0), 0) / loaded.length) : null;
    add(clear(stats), [stat(String(d.total), "tin tuyển"), companies ? stat(String(companies), "công ty (trong các tin đang xem)") : null,
      avg != null ? stat(avg + "%", "kỹ năng bạn đã có, trung bình") : h("a", { class: "hlink", href: "#/skills" }, "Chọn kỹ năng của bạn để xem mức hợp ›")]);
    const c = new Map(); loaded.forEach((j) => j.skills.forEach((s) => c.set(s, (c.get(s) || 0) + 1)));
    const best = [...c.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
    clear(top);
    if (best.length) add(top, [h("span", { class: "tlbl" }, "Hay gặp trong các tin"), best.map(([s]) => h("span", { class: "tchip" + (mine.has(s) ? " mine" : "") }, s))]);
  }

  function ring(pct) {
    return h("div", { class: "ring", style: "--v:" + pct, role: "img", "aria-label": "Bạn đã có " + pct + "% kỹ năng của tin này" }, h("span", null, pct + "%"));
  }

  function item(j) {
    const have = j.skills.filter((s) => mine.has(s)), miss = j.skills.filter((s) => !mine.has(s));
    const pct = j.skills.length ? Math.round(100 * have.length / j.skills.length) : 0;
    const showMatch = mine.size && j.skills.length;
    const link = j.url ? h("a", { class: "btn btn-soft btn-sm", href: j.url, target: "_blank", rel: "noopener noreferrer" }, "Xem tin gốc", icon("arrow", 16)) : h("span", { class: "muted small" }, "Không có đường dẫn tin gốc");
    return h("article", { class: "card jcard" + (showMatch && pct >= 50 ? " jcard-hot" : "") },
      h("div", { class: "jtop" },
        h("span", { class: "avatar", style: "--h:" + hue(j.company) }, initial(j.company)),
        h("div", { class: "jinfo" }, h("b", { class: "jt" }, j.title), h("span", { class: "muted" }, j.company || "Chưa rõ công ty"), when(j) ? h("span", { class: "muted small jwhen" }, when(j)) : null),
        showMatch ? h("div", { class: "jmatch" }, ring(pct), pct >= 50 ? h("span", { class: "tag tag-green" }, "Rất hợp") : null) : null),
      j.skills.length ? h("div", { class: "jskills" },
        have.length ? h("div", { class: "jgroup" }, h("span", { class: "jl jl-have" }, icon("check", 14), "Bạn đã có"), h("div", { class: "chips" }, have.map((s) => h("span", { class: "skill-tag mine" }, s)))) : null,
        miss.length ? h("div", { class: "jgroup" }, h("span", { class: "jl" }, mine.size ? "Còn thiếu" : "Kỹ năng yêu cầu"), h("div", { class: "chips" }, miss.map((s) => h("span", { class: "skill-tag" }, s)))) : null)
        : h("p", { class: "muted" }, "Tin này chưa có danh sách kỹ năng."),
      h("div", { class: "jfoot" }, link));
  }

  async function fetchPage() {
    more.replaceChildren(loading("Đang tải…"));
    try {
      const d = await api.jobsOfRole({ role, limit: PAGE, offset }, { signal: ctx.signal });
      if (ctx.signal.aborted) return;
      if (offset === 0) { clear(list); loaded.length = 0; }
      d.items.forEach((j) => { loaded.push(j); list.append(item(j)); });
      paintHero(d);
      offset += PAGE;
      clear(more);
      if (offset < d.total) more.append(h("button", { type: "button", class: "btn btn-primary btn-lg", onclick: fetchPage }, "Xem thêm tin"), h("span", { class: "muted" }, "Đang hiện " + Math.min(offset, d.total) + "/" + d.total + " tin"));
    } catch (e) {
      if (e && e.name === "AbortError") return;
      clear(more).append(errorBox(e, fetchPage));
    }
  }
  function pick(name) {
    role = name; window.history.replaceState(null, "", "#/jobs?role=" + encodeURIComponent(role));
    chips.querySelectorAll("button").forEach((b) => { const on = b.dataset.role === role; b.classList.toggle("on", on); b.setAttribute("aria-selected", on ? "true" : "false"); });
    offset = 0; clear(list); fetchPage();
  }

  api.studentRoles({ signal: ctx.signal }).then((d) => {
    if (ctx.signal.aborted) return;
    roles = d.items;
    if (!role || !roles.some((r) => r.name === role)) role = (roles[0] || {}).name || "";
    roles.forEach((r) => chips.append(h("button", { type: "button", role: "tab", class: "fchip" + (r.name === role ? " on" : ""), "data-role": r.name, "aria-selected": r.name === role ? "true" : "false", onclick: () => pick(r.name) }, r.label, h("small", null, " " + r.job_count))));
    if (role) pick(role);
  }).catch((e) => { if (e && e.name !== "AbortError") clear(list).append(errorBox(e, () => { clear(root); render(root, params, ctx); })); });
}
