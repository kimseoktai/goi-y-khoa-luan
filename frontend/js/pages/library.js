// Kho khóa luận: khám phá theo lĩnh vực, tìm theo từ khóa, lọc theo năm; lưu đề tài để so sánh.
import { h, clear, debounce } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { icon } from "../icons.js";
import { errorBox, foot, loading, schoolName, SCHOOLS, yearSchool } from "../ui.js";

const PAGE = 18;
const HEADLINES = [   // [đầu câu, phần nhấn màu, cuối câu]
  ["Chưa biết làm gì? ", "Xem các anh chị đã làm", " gì trước đã"],
  ["Đừng nghĩ một mình, ", "lướt xem hơn 1.400 khóa luận", " trước đã"],
  ["Lướt kho khóa luận, ", "biết đâu chốt luôn", " ý tưởng ưng ý"],
  ["Chưa biết bắt đầu từ đâu? ", "Mình xem thử", " cùng nhau nha"],
  ["Nghĩ đề tài một mình dễ rụng tóc, ", "lướt thử kho này", " đi"],
  ["Có người đi trước rồi, ", "bạn chỉ cần lướt", " và chọn thôi"],
  ["Chọn đề tài như chọn món: ", "xem thực đơn trước", " rồi hãy gọi"],
  ["Hôm nay chưa cần chốt, ", "chỉ cần xem thử", " thôi"],
];
const HINTS = ["chatbot", "dự báo", "an toàn thông tin", "thương mại điện tử", "nhận diện hình ảnh"];
const hueOf = (n) => { let x = 0; for (const c of String(n || "")) x = (x * 31 + c.charCodeAt(0)) % 360; return x; };

export function render(root, params, ctx) {
  let q = params.q || "", topic = params.topic || "", year = params.year || "", domain = params.domain || "", source = params.source || "", sort = "new", view = "grid", offset = 0, labels = { topics: {}, library: { topics: [], years: [], total: 0 } };
  const headline = h("h1", { class: "lb-title", "aria-live": "off" });
  const setHeadline = (i) => { const [a, b, c] = HEADLINES[i]; clear(headline).append(a, h("em", null, b), c); };
  setHeadline(0);
  const pill = h("span", { class: "lb-eyebrow" }, h("i"), h("span", null, "Kho khóa luận"));
  const input = h("input", { type: "search", placeholder: "Gõ từ khóa: chatbot, dự báo, an toàn thông tin…", "aria-label": "Tìm khóa luận", value: q, autocomplete: "off" });
  const hints = h("div", { class: "lb-try" }, h("span", null, "Thử gõ:"));
  const stats = h("div", { class: "lb-stats" });
  const rail = h("div", { class: "lb-rail", role: "group", "aria-label": "Chủ đề" });
  const schoolSel = h("select", { "aria-label": "Lọc theo trường" }, h("option", { value: "" }, "Trường: Tất cả"), ...Object.keys(SCHOOLS).map((k) => h("option", { value: k, selected: k === source }, schoolName(k))));
  const domainSel = h("select", { "aria-label": "Lọc theo lĩnh vực" }, h("option", { value: "" }, "Lĩnh vực: Tất cả"));
  const yearSel = h("select", { "aria-label": "Lọc theo năm" });
  const sortSel = h("select", { "aria-label": "Sắp xếp" }, h("option", { value: "new" }, "Mới nhất"), h("option", { value: "old" }, "Cũ nhất"), h("option", { value: "az" }, "A → Z"));
  const vg = h("button", { type: "button", class: "on", "aria-pressed": "true", onclick: () => setView("grid") }, "▦ Lưới");
  const vl = h("button", { type: "button", "aria-pressed": "false", onclick: () => setView("list") }, "☰ Danh sách");
  const arrow = (dir) => h("button", { type: "button", class: "lb-arr " + (dir < 0 ? "l" : "r"), "aria-label": dir < 0 ? "Cuộn sang trái" : "Cuộn sang phải", onclick: () => rail.scrollBy({ left: dir * (rail.firstElementChild ? rail.firstElementChild.offsetWidth + 12 : 208), behavior: "smooth" }) }, icon(dir < 0 ? "chevL" : "chevR", 20));
  const arrL = arrow(-1), arrR = arrow(1);
  const railWrap = h("div", { class: "lb-railwrap" }, arrL, rail, arrR);
  const syncArr = () => { const m = rail.scrollWidth - rail.clientWidth - 2; railWrap.classList.toggle("at-start", rail.scrollLeft < 2); railWrap.classList.toggle("at-end", rail.scrollLeft >= m); };
  rail.addEventListener("scroll", syncArr, { passive: true });
  setTimeout(syncArr, 400);
  let drag = null, moved = false;
  rail.addEventListener("pointerdown", (e) => { if (e.pointerType !== "mouse") return; drag = { x: e.clientX, l: rail.scrollLeft }; moved = false; });
  window.addEventListener("pointermove", (e) => { if (!drag) return; const dx = e.clientX - drag.x; if (Math.abs(dx) > 5) { moved = true; rail.classList.add("drag"); } if (moved) rail.scrollLeft = drag.l - dx; });
  window.addEventListener("pointerup", () => { drag = null; setTimeout(() => rail.classList.remove("drag"), 0); });
  rail.addEventListener("click", (e) => { if (moved) { e.stopPropagation(); e.preventDefault(); moved = false; } }, true);
  const chipsBox = h("div", { class: "lb-chips" });
  const resTitle = h("h2", null, "Vừa lên sóng");
  const resSub = h("span", { class: "muted" });
  const clearBtn = h("button", { type: "button", class: "btn btn-sm", onclick: () => { q = ""; topic = ""; year = ""; domain = ""; source = ""; input.value = ""; reload(); } }, "Bỏ bộ lọc");
  const grid = h("div", { class: "lb-grid" });
  const pick = h("section", { class: "stack-s", hidden: true });
  const more = h("div", { class: "row center" });

  root.append(
    h("div", { class: "lb" }, pick,
      h("section", { class: "lb-hero" }, h("i", { class: "lb-blob b1" }), h("i", { class: "lb-blob b2" }), h("i", { class: "lb-blob b3" }),
        pill,
        headline,
        h("p", { class: "lb-sub" }, "Lướt qua hàng nghìn khóa luận, lọc theo chủ đề bạn thích và mở thẳng báo cáo để tham khảo."),
        h("form", { class: "lb-search", role: "search", onsubmit: (ev) => { ev.preventDefault(); q = input.value.trim(); reload(); } }, icon("search", 22), input, h("kbd", null, "/"), h("button", { type: "submit" }, "Tìm")),
        hints, stats),
      h("section", null, h("div", { class: "lb-sec" }, h("h2", null, "Bạn mê chủ đề nào?"), h("span", null, "Kéo hoặc bấm mũi tên để xem thêm")), railWrap),
      h("section", { class: "lb-main" },
        h("div", { class: "lb-bar" }, schoolSel, domainSel, yearSel, h("span", { class: "sp" }), sortSel, h("div", { class: "lb-seg", role: "group", "aria-label": "Kiểu hiển thị" }, vg, vl)),
        chipsBox,
        h("div", { class: "lb-res" }, resTitle, resSub),
        grid, more,
        foot("Dữ liệu là các khóa luận đã thu thập, không phải toàn bộ khóa luận của mọi trường."))));

  if (!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {   // câu đầu trang đổi chữ nhẹ nhàng
    let i = 0;
    const timer = window.setInterval(() => {
      headline.classList.add("out");
      window.setTimeout(() => { i = (i + 1) % HEADLINES.length; setHeadline(i); headline.classList.remove("out"); }, 350);
    }, 5000);
    ctx.signal.addEventListener("abort", () => window.clearInterval(timer));
  }
  HINTS.forEach((k) => hints.append(h("button", { type: "button", onclick: () => { input.value = k; q = k; reload(); } }, k)));
  const onKey = (ev) => { if (ev.key === "/" && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { ev.preventDefault(); input.focus(); } };
  document.addEventListener("keydown", onKey); ctx.signal.addEventListener("abort", () => document.removeEventListener("keydown", onKey));

  function setView(v) { view = v; grid.classList.toggle("list", v === "list"); vg.classList.toggle("on", v === "grid"); vl.classList.toggle("on", v === "list"); vg.setAttribute("aria-pressed", String(v === "grid")); vl.setAttribute("aria-pressed", String(v === "list")); }

  function paintStats() {
    clear(stats);
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    [[labels.library.total, "khóa luận"], [Object.keys(SCHOOLS).length, "trường"], [labels.library.topics.length, "chủ đề kỹ thuật"], [labels.library.years.length, "năm dữ liệu"]].forEach(([n, l]) => {
      const b = h("b", null, reduce ? n.toLocaleString("vi-VN") : "0"); stats.append(h("div", null, b, h("span", null, l)));
      if (reduce) return;
      const t0 = performance.now(); (function f(t) { const p = Math.min(1, (t - t0) / 1100), e = 1 - Math.pow(1 - p, 3); b.textContent = Math.round(n * e).toLocaleString("vi-VN"); if (p < 1 && !ctx.signal.aborted) requestAnimationFrame(f); })(t0);
    });
  }

  function paintRail() {
    clear(rail);
    const list = labels.library.topics.slice();
    if (topic && !list.some((t) => t.name === topic)) list.push({ name: topic, label: labels.topics[topic] || topic, count: 0 });
    list.forEach((t) => {
      const on = topic === t.name;
      rail.append(h("button", { type: "button", class: "lb-tc" + (on ? " on" : ""), style: "--h:" + hueOf(t.name), "aria-pressed": on ? "true" : "false", onclick: () => { topic = on ? "" : t.name; reload(); } },
        h("span", { class: "lb-dot" }, (t.label || t.name)[0]), h("span", null, h("b", null, t.label || t.name), h("small", null, (t.count ? t.count + " " : "") + "khóa luận"))));
    });
  }

  async function showPicked() {
    if (!params.id) return;
    try {
      const t = await api.thesisOne(params.id, { signal: ctx.signal });
      if (ctx.signal.aborted) return;
      const c = card(t);
      c.classList.add("kh-picked");
      c.id = "picked-thesis";
      clear(pick).append(h("div", { class: "head-row" }, h("h2", null, "Khóa luận bạn vừa chọn"), h("a", { class: "btn btn-sm", href: "#/library" }, "Xem cả kho")), c);
      pick.hidden = false;
      c.scrollIntoView({ block: "center" });
    } catch (e) {
      if (e && e.name === "AbortError") return;
      clear(pick).append(h("div", { class: "state" }, e && e.status === 404 ? "Không tìm thấy khóa luận này trong kho." : errorBox(e, showPicked)));
      pick.hidden = false;
    }
  }

  function card(t, i) {
    const id = "thesis:" + t.thesis_id;
    const heart = h("button", { type: "button", class: "lb-heart", "aria-label": "Lưu khóa luận", onclick: () => { store.toggleSaved({ id, kind: "thesis", title: t.title, report_url: t.report_url || "", topics: t.technical_topics.map((x) => labels.topics[x] || x), year: t.year, source: t.source }); paint(); } }, icon("heart", 18));
    function paint() { const on = store.isSaved(id); heart.classList.toggle("on", on); heart.setAttribute("aria-pressed", on ? "true" : "false"); heart.title = on ? "Đã lưu" : "Lưu"; heart.querySelector("svg").setAttribute("fill", on ? "currentColor" : "none"); }
    paint();
    const hh = hueOf(t.technical_topics[0] || (t.domains || [])[0] || ""), dm = (t.domains || [])[0];
    return h("article", { class: "lb-card", style: `--h:${hh};--i:${Math.min(i, 12)}` },
      h("div", { class: "lb-body" }, h("div", { class: "lb-tags" }, ...t.technical_topics.slice(0, 2).map((x, k) => h("span", { class: "lb-tag" + (k ? " t2" : "") }, labels.topics[x] || x)), dm ? h("span", { class: "lb-tag g" }, (labels.domains || {})[dm] || dm) : null), h("h3", null, niceTitle(t.title))),
      h("div", { class: "lb-top" }, heart),
      h("div", { class: "lb-foot" }, h("div", { class: "lb-meta" }, h("b", null, t.year || "—"), schoolName(t.source)),
        t.report_url ? h("a", { class: "lb-pdf", href: t.report_url, target: "_blank", rel: "noopener noreferrer", "aria-label": "Xem PDF: " + t.title }, icon("file", 16), "Xem PDF") : h("span", { class: "lb-nopdf" }, "Chưa có PDF")));
  }

  // tiêu đề viết hoa toàn bộ → chữ thường đầu câu cho dễ đọc (giữ nguyên các từ viết tắt ngắn như AI, IoT)
  function niceTitle(s) {
    const t = String(s || "").trim(), letters = t.replace(/[^A-ZÀ-Ỹa-zà-ỹ]/g, "");
    if (letters.length < 12 || letters !== letters.toUpperCase()) return t;
    return t.toLowerCase().replace(/(^|[.:\-–]\s*)(\p{L})/gu, (m, a, c) => a + c.toUpperCase()).replace(/\b(ai|iot|api|ui|ux|sql|nlp|cnn|lstm|gpt|llm|rag|erp|crm|cms|pdf|qr|vnpay|momo)\b/gi, (w) => w.toUpperCase());
  }

  function paintChips() {
    clear(chipsBox);
    const mk = (text, on) => chipsBox.append(h("button", { type: "button", class: "lb-chip", "aria-label": "Bỏ lọc: " + text, onclick: on }, text, h("span", { "aria-hidden": "true" }, "✕")));
    if (q) mk("“" + q + "”", () => { q = ""; input.value = ""; reload(); });
    if (topic) mk(labels.topics[topic] || topic, () => { topic = ""; reload(); });
    if (domain) mk((labels.domains || {})[domain] || domain, () => { domain = ""; reload(); });
    if (source) mk(schoolName(source), () => { source = ""; reload(); });
    if (year) mk("Năm " + year, () => { year = ""; reload(); });
    if (chipsBox.childElementCount > 1) chipsBox.append(clearBtn);
    chipsBox.hidden = !chipsBox.childElementCount;
  }

  function paintHead(total) {
    const filtered = !!(q || topic || year || domain || source);
    resTitle.textContent = filtered ? "Kết quả" : "Vừa lên sóng";
    resSub.textContent = total != null ? total.toLocaleString("vi-VN") + " khóa luận" : "";
    pill.querySelector("span").textContent = labels.library.total ? labels.library.total.toLocaleString("vi-VN") + " khóa luận" + (labels.library.years.length ? " · " + Math.min(...labels.library.years) + " đến " + Math.max(...labels.library.years) : "") : "Kho khóa luận";
  }

  async function fetchPage() {
    more.replaceChildren(loading("Đang tải…"));
    if (offset === 0) grid.replaceChildren(...Array.from({ length: 6 }, () => h("div", { class: "lb-sk" })));
    try {
      const d = await api.thesisList({ q: q || undefined, topic: topic || undefined, domain: domain || undefined, source: source || undefined, year: year || undefined, sort: sort === "new" ? undefined : sort, limit: PAGE, offset }, { signal: ctx.signal });
      if (ctx.signal.aborted) return;
      if (offset === 0) { clear(grid); paintHead(d.total); }
      if (offset === 0 && !d.items.length) grid.append(h("div", { class: "lb-empty" }, h("b", null, "Chưa thấy khóa luận nào khớp"), h("p", null, "Thử bỏ bớt bộ lọc hoặc đổi từ khóa nhé.")));
      d.items.forEach((t, i) => grid.append(card(t, i)));
      offset += PAGE;
      clear(more);
      if (offset < d.total) more.append(h("button", { type: "button", class: "lb-more", onclick: fetchPage }, "Xem thêm khóa luận"), h("span", { class: "muted" }, "Đang hiện " + Math.min(offset, d.total) + "/" + d.total));
    } catch (e) {
      if (e && e.name === "AbortError") return;
      clear(more).append(errorBox(e, fetchPage));
    }
  }
  function reload() { offset = 0; yearSel.value = year; schoolSel.value = source; domainSel.value = domain; paintRail(); paintChips(); fetchPage(); }

  input.addEventListener("input", debounce(() => { q = input.value.trim(); reload(); }, 300));
  yearSel.addEventListener("change", () => { year = yearSel.value; reload(); });
  schoolSel.addEventListener("change", () => { source = schoolSel.value; reload(); });
  domainSel.addEventListener("change", () => { domain = domainSel.value; reload(); });
  sortSel.addEventListener("change", () => { sort = sortSel.value; reload(); });

  api.labels({ signal: ctx.signal }).then((d) => {
    if (ctx.signal.aborted) return;
    labels = d;
    showPicked();
    domainSel.append(...Object.entries(d.domains || {}).sort((a, b) => a[1].localeCompare(b[1], "vi")).map(([k, v]) => h("option", { value: k, selected: k === domain }, v)));
    yearSel.append(h("option", { value: "" }, "Năm: Tất cả"), ...d.library.years.slice().sort((a, b) => b - a).map((y) => h("option", { value: String(y), selected: String(y) === year }, "Năm " + y)));
    paintStats();
    reload();
  }).catch((e) => { if (e && e.name !== "AbortError") clear(grid).append(errorBox(e, () => { clear(root); render(root, params, ctx); })); });
}
