// Xu hướng khóa luận NEU trên MỘT trang: điểm nhanh bằng lời, bộ lọc, KPI, xu hướng theo năm, cơ cấu lĩnh vực và công nghệ, top 5, chủ đề mới nổi và bảng chi tiết theo năm.
// Mọi con số lấy từ một lát cắt do máy chủ tính (GET /dashboard/thesis), nên các khối luôn khớp nhau. Biểu đồ vẽ bằng SVG, chữ đi qua textContent.
import { h, clear, svg } from "../dom.js";
import { api } from "../api.js";
import { openRefs } from "../refs.js";
import { load, foot, pageHead } from "../ui.js";

const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];   // bảng màu danh mục đã kiểm tra (CVD, độ sáng)
const INK = "#1B1B1F", OTHER = "#8d8c97";
const TREND = { up: ["▲", "Đang tăng", "adm-good"], down: ["▼", "Đang giảm", "adm-bad"], flat: ["▬", "Ổn định", ""], insufficient: ["?", "Chưa đủ dữ liệu", ""] };
const fmtPct = (x, d = 0) => (x * 100).toFixed(d).replace(".", ",") + "%";
const signed = (x, d = 1) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d).replace(".", ",");

export function render(root, params, ctx) {
  const body = h("div", { class: "stack" });
  root.append(pageHead("Xu hướng khóa luận", "Khóa luận NEU đã làm về mảng nào, mảng nào đang lên."), body);
  const st = { from: "", to: "", domain: "", topic: "", view: "domain", chart: "chart", unit: "count", heat: "topics", quick: "scale", open: [] };
  let labels = { topics: {}, domains: {} }, last = null;
  const colors = new Map();                                               // màu theo thực thể, không theo thứ hạng: lọc lại không làm đổi màu mục còn lại
  const used = { topics: 0, domains: 0 };
  const colorOf = (kind, name) => { const k = kind + "|" + name; if (!colors.has(k)) colors.set(k, used[kind] < SERIES.length ? SERIES[used[kind]++] : OTHER); return colors.get(k); };
  const nm = (kind, n) => (labels[kind] && labels[kind][n]) || n;
  const frame = h("div", { class: "stack" });
  const tip = h("div", { class: "dash-tip", role: "status", hidden: true });

  api.labels({ signal: ctx.signal }).then((d) => { labels = d; }).catch(() => {}).finally(() => { if (!ctx.signal.aborted) fetchData(true); });

  function fetchData(first) {
    const q = { source: params.source || "neu", year_from: st.from, year_to: st.to, domain: st.domain, topic: st.topic, view: st.view };
    if (first) { load(body, ctx, () => api.dashboardThesis(q, { signal: ctx.signal }), (d) => { last = d; paint(d); }); return; }
    frame.style.opacity = ".5";                                           // giữ khung cũ khi tải lại, không nhảy bố cục
    api.dashboardThesis(q, { signal: ctx.signal }).then((d) => { if (ctx.signal.aborted) return; last = d; paint(d); })
      .catch((e) => { if (!ctx.signal.aborted && !(e && e.name === "AbortError")) { frame.style.opacity = ""; frame.prepend(h("div", { class: "notice", role: "alert" }, "Không tải lại được dữ liệu; đang hiện số liệu trước đó.")); } });
  }

  // ---------- thành phần dùng chung
  const note = (t) => h("details", { class: "dash-note" }, h("summary", null, "Cách đọc"), h("p", null, t));
  const tile = (label, value, sub) => h("div", { class: "adm-tile" }, h("div", { class: "adm-tile-l" }, label), h("div", { class: "adm-tile-v" }, value), sub ? h("div", { class: "adm-tile-s" }, sub) : null);
  const select = (id, label, opts, val, onchange) => h("div", { class: "dash-f" }, h("label", { for: id }, label),
    h("select", { id, class: "input", style: "flex:none", onchange: (e) => onchange(e.target.value) }, opts.map(([v, t]) => h("option", { value: v, selected: String(v) === String(val) ? "" : null }, t))));
  const badge = (tr) => h("span", { class: "chip " + TREND[tr][2] }, TREND[tr][0] + " " + TREND[tr][1]);
  const growth = (r) => {
    if (r.change_pp == null) return h("span", { class: "muted small" }, "–");
    const rel = r.change_rel == null ? "" : ` (${signed(r.change_rel * 100, 0)}%)`;
    return h("span", null, h("strong", null, signed(r.change_pp * 100) + " điểm %"), rel, h("div", { class: "muted small" }, `${fmtPct(r.share_prior)} → ${fmtPct(r.share_last)}`));
  };
  function showTip(host, x, y, title, rows) {
    clear(tip).append(h("div", { class: "dash-tip-t" }, title), ...rows.map(([c, v, l]) => h("div", { class: "dash-tip-r" }, h("i", { style: `background:${c}` }), h("b", null, v), h("span", null, l))));
    tip.hidden = false;
    const hr = host.getBoundingClientRect();
    tip.style.left = Math.min(Math.max(8, x - hr.left + 14), hr.width - 190) + "px"; tip.style.top = Math.max(0, y - hr.top - 12) + "px";
    host.append(tip);
  }
  const hideTip = () => { tip.hidden = true; };

  // ---------- biểu đồ đường
  function lineChart(d) {
    const years = d.years.map((y) => y.year);
    const share = st.unit === "share", nY = d.years.map((y) => y.n), val = (c, i) => (share ? (nY[i] ? (c / nY[i]) * 100 : 0) : c);
    const total = { key: "__total", name: "Tất cả", color: INK, data: share ? nY.map(() => 100) : nY, trend: null };
    const kind = d.series.view === "topic" ? "topics" : "domains";
    const series = [total, ...d.series.lines.map((r) => ({ key: r.name, name: nm(kind, r.name), color: colorOf(kind, r.name), data: r.by_year.map(val), trend: r.trend }))].filter((x) => !(share && x.key === "__total"));
    const W = 640, H = 260, m = { l: 40, r: 16, t: 14, b: 30 };
    const ymax = Math.max(1, ...series.flatMap((s) => s.data)), step = [1, 2, 5, 10, 20, 50, 100, 200].find((s) => ymax / s <= 5) || 500;
    const top = Math.ceil(ymax / step) * step;
    const X = (i) => (years.length === 1 ? (m.l + W - m.r) / 2 : m.l + (i * (W - m.l - m.r)) / (years.length - 1)), Y = (v) => m.t + (1 - v / top) * (H - m.t - m.b);
    const host = h("div", { class: "dash-chart" });
    const cross = svg("line", { y1: m.t, y2: H - m.b, stroke: "#c9c6d6", "stroke-width": 1, visibility: "hidden" });
    const g = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "dash-svg", role: "img", tabindex: 0, "aria-label": "Số khóa luận theo năm. Có bảng số liệu bên dưới nút Xem dạng bảng." });
    for (let v = 0; v <= top; v += step) g.append(svg("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: "#ECEAF2" }), svg("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end", class: "dash-ax" }, String(v) + (share ? "%" : "")));
    years.forEach((y, i) => g.append(svg("text", { x: X(i), y: H - 8, "text-anchor": "middle", class: "dash-ax" }, String(y))));
    g.append(cross);
    series.forEach((s) => {
      g.append(svg("polyline", { points: s.data.map((v, i) => `${X(i)},${Y(v)}`).join(" "), fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      s.data.forEach((v, i) => g.append(svg("circle", { cx: X(i), cy: Y(v), r: 4, fill: s.color, stroke: "#fff", "stroke-width": 2 })));
    });
    const at = (cx) => { const r = g.getBoundingClientRect(); const px = ((cx - r.left) / r.width) * W; return years.length === 1 ? 0 : Math.max(0, Math.min(years.length - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (years.length - 1)))); };
    const show = (i, ev) => {
      cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("visibility", "visible");
      const r = g.getBoundingClientRect();
      showTip(host, ev ? ev.clientX : r.left + (X(i) / W) * r.width, ev ? ev.clientY : r.top + 30, `Năm ${years[i]} · ${d.years[i].n} bài`, series.map((s) => [s.color, share ? s.data[i].toFixed(1).replace(".", ",") + "%" : String(s.data[i]), s.name]));
    };
    const off = () => { cross.setAttribute("visibility", "hidden"); hideTip(); };
    g.addEventListener("pointermove", (ev) => show(at(ev.clientX), ev)); g.addEventListener("pointerleave", off); g.addEventListener("blur", off);
    let cur = years.length - 1;
    g.addEventListener("keydown", (ev) => { if (ev.key === "ArrowLeft") cur = Math.max(0, cur - 1); else if (ev.key === "ArrowRight") cur = Math.min(years.length - 1, cur + 1); else return; ev.preventDefault(); show(cur, null); });
    host.append(g);
    const legend = h("ul", { class: "dash-legend" }, series.map((s) => h("li", { title: s.trend ? TREND[s.trend][1] : "" }, h("i", { class: "dash-key", style: `background:${s.color}` }), h("span", null, s.name),
      s.trend === "up" || s.trend === "down" ? h("em", { class: "dash-tr " + TREND[s.trend][2] }, TREND[s.trend][0]) : null)));
    const table = h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table" },
      h("thead", null, h("tr", null, [h("th", null, "Nhóm"), ...years.map((y) => h("th", { style: "text-align:right" }, String(y))), h("th", null, "Xu hướng")])),
      h("tbody", null, series.map((s) => h("tr", null, h("td", null, s.name), s.data.map((v) => h("td", { style: "text-align:right" }, share ? v.toFixed(1).replace(".", ",") + "%" : String(v))), h("td", null, s.trend ? badge(s.trend) : ""))))));
    return { host, legend, table };
  }

  function trendCard(d) {
    const c = lineChart(d), asTable = st.chart === "table";
    const small = d.years.filter((y) => y.small).map((y) => y.year);
    const seg = (k, l, cur, set) => h("button", { type: "button", class: "dash-seg" + (cur === k ? " on" : ""), "aria-pressed": cur === k ? "true" : "false", onclick: () => set(k) }, l);
    const grp = (label, ...btns) => h("div", { class: "dash-grp", role: "group", "aria-label": label }, h("span", null, label), h("div", { class: "dash-segs" }, btns));
    const ico = (paths) => svg("svg", { viewBox: "0 0 24 24", width: 22, height: 22, fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" }, ...paths.map((dd) => svg("path", { d: dd })));
    const rail = (k, l, paths) => h("button", { type: "button", role: "tab", "aria-selected": st.chart === k ? "true" : "false", class: "dash-rail-b" + (st.chart === k ? " on" : ""), onclick: () => { st.chart = k; paint(last); } }, ico(paths), h("span", null, l));
    return h("section", { class: "card" }, h("h2", null, "Theo năm"),
      h("div", { class: "dash-bar2" },                                                  // phía trên: lọc dữ liệu
        grp("Đơn vị", seg("count", "Số bài", st.unit, (k) => { st.unit = k; paint(last); }), seg("share", "Tỷ lệ %", st.unit, (k) => { st.unit = k; paint(last); })),
        grp("Nhóm theo", seg("domain", "Lĩnh vực", d.series.view, (k) => { st.view = k; fetchData(); }), seg("topic", "Chủ đề công nghệ", d.series.view, (k) => { st.view = k; fetchData(); }))),
      h("div", { class: "dash-split" },
        h("div", { class: "dash-main" }, d.years.length ? [asTable ? c.table : c.host, asTable ? null : c.legend] : h("p", { class: "muted" }, "Không có khóa luận khớp bộ lọc.")),
        h("div", { class: "dash-rail", role: "tablist", "aria-label": "Kiểu hiển thị" },                      // lề phải: kiểu hiển thị
          rail("chart", "Biểu đồ", ["M3 17l5-6 4 3 8-9", "M3 21h18"]), rail("table", "Bảng", ["M3 5h18v14H3z", "M3 10h18", "M9 5v14"]))),
      note(`${st.unit === "share" ? "Tỷ lệ = số bài của nhóm / tất cả bài khớp bộ lọc trong năm đó; một bài có thể thuộc nhiều nhóm. Các đường màu là 5 nhóm nhiều bài nhất." : "Đường đen là tổng số khóa luận khớp bộ lọc; các đường màu là 5 nhóm nhiều bài nhất. Chọn Tỷ lệ % để so các nhóm khi một năm có quá nhiều bài."} Nhãn "đang tăng/giảm" so tỷ lệ của năm ${d.latest_year ?? "cuối"} với các năm trước trong khoảng đã chọn, chỉ kết luận khi khoảng tin cậy 95% không chồng nhau và mỗi bên có ít nhất ${d.min_n} bài; còn lại là ổn định hoặc chưa đủ dữ liệu.` +
        (small.length ? ` Năm ${small.join(", ")} có dưới ${d.small_year} bài nên dao động nhiều.` : "")));
  }

  // ---------- treemap lĩnh vực > chủ đề (khối lớn = lĩnh vực, khối nhỏ = chủ đề công nghệ của lĩnh vực đó)
  function squarify(items, x, y, w, hh) {
    const out = [], total = items.reduce((t, i) => t + i.v, 0);
    if (!total || w <= 0 || hh <= 0) return out;
    const k = (w * hh) / total, rest = items.map((it) => ({ it, a: it.v * k }));
    const worst = (row, side) => { const sum = row.reduce((t, i) => t + i.a, 0), mx = Math.max(...row.map((i) => i.a)), mn = Math.min(...row.map((i) => i.a)); return Math.max((side * side * mx) / (sum * sum), (sum * sum) / (side * side * mn)); };
    const place = (row) => {
      const sum = row.reduce((t, i) => t + i.a, 0);
      if (w >= hh) { const cw = sum / hh; let yy = y; row.forEach((i) => { const ch = i.a / cw; out.push({ it: i.it, x, y: yy, w: cw, h: ch }); yy += ch; }); x += cw; w -= cw; }
      else { const rh = sum / w; let xx = x; row.forEach((i) => { const cw = i.a / rh; out.push({ it: i.it, x: xx, y, w: cw, h: rh }); xx += cw; }); y += rh; hh -= rh; }
    };
    let row = [];
    while (rest.length) {
      const side = Math.min(w, hh);
      if (!row.length || worst([...row, rest[0]], side) <= worst(row, side)) row.push(rest.shift()); else { place(row); row = []; }
    }
    if (row.length) place(row);
    return out;
  }
  const hexRgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  function cellStyle(color, alpha) {
    const [r, g, b] = hexRgb(color), mix = (v) => Math.round(alpha * v + (1 - alpha) * 255), lum = (0.299 * mix(r) + 0.587 * mix(g) + 0.114 * mix(b)) / 255;
    return `background:rgba(${r},${g},${b},${alpha});color:${lum < 0.6 ? "#fff" : "#1B1B1F"}`;
  }
  const libLink = (topic, domain, source) => "#/library?" + [topic && "topic=" + encodeURIComponent(topic), domain && "domain=" + encodeURIComponent(domain), source && "source=" + encodeURIComponent(source)].filter(Boolean).join("&");
  function treeView(d) {
    const W = 160, H = 90, host = h("div", { class: "dash-tree", style: `aspect-ratio:${W}/${H}` });
    if (!d.domain_topic) return h("p", { class: "muted" }, "Máy chủ chưa có dữ liệu lĩnh vực × chủ đề. Khởi động lại backend rồi tải lại trang.");
    const doms = d.domain_topic.filter((x) => x.count > 0).sort((a, b) => b.count - a.count);
    if (!doms.length) return h("p", { class: "muted" }, "Chưa có.");
    st.open = st.open.filter((n) => doms.some((x) => x.domain === n));
    const pc = (v, t) => (v / t) * 100 + "%", pos = (r) => `left:${pc(r.x, W)};top:${pc(r.y, H)};width:${pc(r.w, W)};height:${pc(r.h, H)}`;
    const wire = (el, title, rows, click) => {
      const on = (ev) => { const b = el.getBoundingClientRect(); showTip(host, ev ? ev.clientX : b.left + 20, ev ? ev.clientY : b.top, title, rows); };
      el.addEventListener("pointermove", on); el.addEventListener("focus", () => on(null)); el.addEventListener("pointerleave", hideTip); el.addEventListener("blur", hideTip);
      el.style.cursor = "pointer"; el.addEventListener("click", () => { hideTip(); click(); });
      el.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); hideTip(); click(); } });
    };
    const toggle = (name) => { st.open = st.open.includes(name) ? st.open.filter((n) => n !== name) : [...st.open, name]; paint(last); };
    squarify(doms.map((x) => ({ ...x, v: x.count })), 0, 0, W, H).forEach((r) => {
      const dm = r.it, color = colorOf("domains", dm.domain), label = nm("domains", dm.domain), real = dm.topics.filter((t) => t.name), open = st.open.includes(dm.domain);
      if (!open) {                                                           // chưa mở: một khối đặc, bấm để phân nhánh ngay tại chỗ
        const cell = h("div", { class: "dash-tree-d dash-tree-l1", tabindex: 0, role: "button", "aria-expanded": "false", style: pos(r) + ";" + cellStyle(color, 1), "aria-label": `${label}: ${dm.count} khóa luận. Bấm để mở các chủ đề` },
          h("span", { class: "dash-tree-name" }, label, h("b", null, dm.count + " bài"), real.length ? h("small", null, real.length + " chủ đề") : null));
        wire(cell, label, [[color, String(dm.count), "khóa luận · bấm để mở chủ đề"], ...real.slice(0, 3).map((t) => [color, String(t.count), nm("topics", t.name)])], () => toggle(dm.domain));
        host.append(cell); return;
      }
      const head = r.w > 15 && r.h > 13, hu = head ? 7 : 0, bh = Math.max(1, r.h - hu);          // đã mở: tên lĩnh vực ở trên, các chủ đề bên trong
      const body = h("div", { class: "dash-tree-b" });
      const cut = Math.max(2, dm.count * 0.07), small = dm.topics.filter((t) => t.count < cut), big = dm.topics.filter((t) => t.count >= cut);   // chủ đề ít gộp thành "Khác"
      const items = small.length >= 2 ? [...big, { name: null, other: true, count: small.reduce((a, t) => a + t.count, 0), list: small }] : dm.topics;
      squarify(items.map((t) => ({ ...t, v: t.count })).sort((a, b) => (a.other ? 1 : 0) - (b.other ? 1 : 0) || b.v - a.v), 0, 0, r.w, bh)   // "Khác" luôn xếp cuối → góc dưới bên phải
      .forEach((c, rank) => {
        const t = c.it, tl = t.other ? "Khác" : t.name ? nm("topics", t.name) : "Chưa có chủ đề";
        const names = t.other ? t.list.map((x) => (x.name ? nm("topics", x.name) : "Chưa có chủ đề") + " (" + x.count + ")") : [];
        const cell = h("div", { class: "dash-tree-c" + (t.other ? " is-other" : ""), role: "link", tabindex: 0, style: `left:${pc(c.x, r.w)};top:${pc(c.y, bh)};width:${pc(c.w, r.w)};height:${pc(c.h, bh)};` + (t.other ? "background:#8d8c97;color:#fff;" : cellStyle(color, Math.max(0.7, 0.98 - rank * 0.05))), "aria-label": `${label}, ${tl}: ${t.count} khóa luận. Bấm để xem khóa luận` },
          h("span", { class: "dash-tree-t" }, tl, h("b", null, String(t.count))));
        wire(cell, label, t.other ? [[color, String(t.count), "Khác · " + t.list.length + " chủ đề"], ...t.list.map((x) => ["#8d8c97", String(x.count), x.name ? nm("topics", x.name) : "Chưa có chủ đề"])] : [[color, String(t.count), tl + " · bấm để xem danh sách"]],
          () => {
          const dl = nm("domains", dm.domain);
          if (t.other) openRefs({ fixed: true, title: `${dl} - Khác`, topics: t.list.map((x) => x.name), noTopic: t.list.some((x) => !x.name), topic: "", topicLabel: "Khác", domain: dm.domain, domainLabel: dl, source: d.source, lead: `Các khóa luận thuộc lĩnh vực ${dl} và các chủ đề nhỏ gộp trong "Khác". Bấm "Xem PDF" để mở báo cáo.` });
          else if (!t.name) openRefs({ fixed: true, title: `${dl} - ${tl}`, topics: [], noTopic: true, topic: "", topicLabel: tl, domain: dm.domain, domainLabel: dl, source: d.source, lead: `Các khóa luận ${dl} chưa gán chủ đề kỹ thuật.` });
          else openRefs({ fixed: true, title: `${dl} - ${tl}`, topic: t.name, topicLabel: tl, domain: dm.domain, domainLabel: dl, source: d.source, lead: `Các khóa luận ${dl} · ${tl}. Bấm "Xem PDF" để mở báo cáo.` });
        });
        body.append(cell);
      });
      const hd = head ? h("div", { class: "dash-tree-h", tabindex: 0, role: "button", "aria-expanded": "true", title: "Bấm để thu gọn", style: cellStyle(color, 1) }, h("span", null, label), r.w > 26 ? h("b", null, dm.count + " bài ▾") : null) : null;
      if (hd) wire(hd, label, [[color, String(dm.count), "khóa luận · bấm để thu gọn"]], () => toggle(dm.domain));
      host.append(h("div", { class: "dash-tree-d", style: pos(r) }, h("div", { class: "dash-tree-in", style: `background:${color}` }, hd, body)));
    });
    const fit = () => {                                                        // ẩn chữ theo kích thước thật (px), tránh ô trống do tỉ lệ co giãn
      host.querySelectorAll(".dash-tree-c,.dash-tree-l1").forEach((el) => {
        const sp = el.firstElementChild; if (!sp) return;
        const w = el.clientWidth, hh = el.clientHeight, l1 = el.classList.contains("dash-tree-l1");
        sp.style.visibility = w >= 44 && hh >= 22 ? "" : "hidden";
        sp.querySelectorAll("b").forEach((b) => { b.style.display = hh >= (l1 ? 58 : 38) ? "" : "none"; });
        sp.querySelectorAll("small").forEach((b) => { b.style.display = hh >= 84 ? "" : "none"; });
      });
    };
    requestAnimationFrame(fit); if (window.ResizeObserver) new ResizeObserver(fit).observe(host);
    return host;
  }
  function mixCard(d) {
    const some = st.open.length > 0;
    return h("section", { class: "card", id: "sec-mix" }, h("div", { class: "head-row" }, h("h2", null, "Theo lĩnh vực"),
      h("div", { class: "row" }, h("span", { class: "muted small" }, "Bấm một lĩnh vực để mở chủ đề; bấm chủ đề để xem khóa luận"), some ? h("button", { type: "button", class: "btn btn-sm", onclick: () => { st.open = []; paint(last); } }, "Thu gọn tất cả") : null)),
      h("div", { class: "dash-chart", style: "margin-top:12px" }, treeView(d)),
      note(`Mỗi khối là một lĩnh vực, diện tích theo số khóa luận. Bấm vào khối để phân nhánh ra các chủ đề công nghệ bên trong (diện tích theo số bài có cả hai nhãn); bấm vào một chủ đề để mở kho khóa luận lọc sẵn theo đúng lĩnh vực và chủ đề đó. Một bài có nhiều nhãn thì được tính ở nhiều khối. ${d.no_domain} bài chưa có lĩnh vực không nằm trong biểu đồ này.`));
  }

  // ---------- biểu đồ thanh
  function barCard(d) {
    const max = Math.max(1, ...d.topic_bars.map((b) => b.count));
    const rows = d.topic_bars.map((b) => {
      const w = Math.max(0.5, (b.count / max) * 100), c = SERIES[0];            // một chuỗi duy nhất: một màu, tên đã nằm ở nhãn
      const bar = h("div", { class: "dash-bar", tabindex: 0, "aria-label": `${nm("topics", b.name)}: ${b.count} khóa luận` }, h("div", { class: "dash-bar-f", style: `width:${w}%;background:${c}` }));
      const on = (ev) => { const r = bar.getBoundingClientRect(); showTip(card, ev ? ev.clientX : r.left + 40, ev ? ev.clientY : r.top, nm("topics", b.name), [[c, String(b.count), `khóa luận (${fmtPct(b.share, 1)} số bài đang xem)`]]); };
      bar.addEventListener("pointermove", on); bar.addEventListener("focus", () => on(null)); bar.addEventListener("pointerleave", hideTip); bar.addEventListener("blur", hideTip);
      return h("div", { class: "dash-bar-row" }, h("span", { class: "dash-bar-l" }, nm("topics", b.name)), bar, h("b", { class: "dash-bar-v" }, String(b.count)));
    });
    const card = h("section", { class: "card dash-chart" }, h("h2", null, "Chủ đề phổ biến"), rows.length ? rows : h("p", { class: "muted" }, "Chưa có chủ đề nào trong lát cắt này."),
      note("Số khóa luận mang nhãn chủ đề đó; một bài có thể có nhiều chủ đề."));
    return card;
  }

  // ---------- top 5 và chủ đề mới nổi
  function top5Card(d) {
    return h("section", { class: "card" }, h("h2", null, "Top 5 chủ đề"),
      d.top5.length ? h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table dash-cards" },
        h("thead", null, h("tr", null, ["#", "Chủ đề", "Bài", "Tăng trưởng", "Lĩnh vực chính", ""].map((t) => h("th", null, t)))),
        h("tbody", null, d.top5.map((r, i) => h("tr", null, h("td", { "data-l": "Hạng" }, String(i + 1)), h("td", { "data-l": "Chủ đề" }, h("strong", null, nm("topics", r.name)), h("div", null, badge(r.trend))),
          h("td", { "data-l": "Bài" }, String(r.count)), h("td", { "data-l": "Tăng trưởng" }, growth(r)),
          h("td", { "data-l": "Lĩnh vực chính" }, h("div", null, r.common_domains.length ? r.common_domains.map((x) => h("div", null, nm("domains", x.name), h("span", { class: "muted small" }, " " + fmtPct(x.share)))) : h("span", { class: "muted" }, "Chưa có lĩnh vực"))),
          h("td", null, h("a", { class: "btn btn-sm", href: "#/library?topic=" + encodeURIComponent(r.name) }, "Xem khóa luận"))))))) :
        h("p", { class: "muted" }, "Chưa có chủ đề nào."),
      note("Xếp theo số khóa luận trong lát cắt đang xem. Tăng trưởng là thay đổi tỷ lệ của chủ đề trong năm cuối so với tỷ lệ gộp các năm trước đó trong khoảng (điểm phần trăm, kèm % tương đối)."));
  }

  function emergingCard(d) {
    const why = { new: "Mới", fast: "Tăng nhanh" };
    return h("section", { class: "card" }, h("h2", null, "Mới nổi"),
      d.emerging.length ? h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table dash-cards" },
        h("thead", null, h("tr", null, ["Chủ đề", "Từ năm", "Gần đây", "Xu hướng"].map((t) => h("th", null, t)))),
        h("tbody", null, d.emerging.map((r) => h("tr", null,
          h("td", { "data-l": "Chủ đề" }, h("strong", null, nm("topics", r.name)), r.status === "candidate" ? h("div", { class: "muted small" }, "chưa duyệt") : null),
          h("td", { "data-l": "Từ năm" }, String(r.first_year)), h("td", { "data-l": "Gần đây" }, `${r.recent_count} bài`),
          h("td", { "data-l": "Xu hướng" }, h("span", { class: "chip " + (r.reason === "new" ? "chip-b" : "adm-good") }, why[r.reason]), h("div", null, growth(r)))))))) :
        h("p", { class: "muted" }, "Chưa có."),
      note("“Bắt đầu xuất hiện” là năm đầu tiên chủ đề có từ 2 khóa luận trong toàn bộ dữ liệu của trường. Một chủ đề được liệt kê khi mới xuất hiện trong 2 năm gần nhất (và không có ngay từ năm đầu của dữ liệu), hoặc đang tăng rõ, hoặc tỷ lệ năm cuối gấp 1,5 lần giai đoạn trước với ít nhất 5 bài. Đây là mô tả dữ liệu, không phải dự báo."));
  }

  // ---------- điểm nhanh: mỗi tab một vài con số, không viết thành câu dài
  const QTABS = [["scale", "Quy mô"], ["topic", "Chủ đề"], ["domain", "Lĩnh vực"], ["up", "Đang lên"], ["new", "Mới xuất hiện"]];
  const stat = (v, l) => h("div", { class: "dash-stat" }, h("b", null, v), h("span", null, l));
  const empty = (t) => h("p", { class: "muted dash-empty" }, t);
  function rankRows(rows, kind, total) {
    const max = Math.max(1, ...rows.map((r) => r.total));
    return h("ol", { class: "dash-rank" }, rows.map((r) => h("li", null, h("span", { class: "dash-rank-n" }, nm(kind, r.name)),
      h("div", { class: "dash-rank-bar" }, h("i", { style: `width:${(r.total / max) * 100}%` })), h("b", null, r.total + " bài"), h("span", { class: "muted" }, fmtPct(r.total / total)))));
  }
  const pills = (items) => h("div", { class: "chips" }, items.map(([t, sub, cls]) => h("span", { class: "chip " + (cls || "") }, t, sub ? h("small", null, " " + sub) : null)));
  function quickPanel(d) {
    const k = d.kpi, yrs = d.years;
    if (!k.in_range) return empty("Không có khóa luận nào khớp bộ lọc.");
    const q = st.quick;
    if (q === "scale") {
      const peak = yrs.reduce((a, b) => (b.n > a.n ? b : a)), max = Math.max(...yrs.map((y) => y.n));
      return h("div", { class: "dash-scale" }, h("div", { class: "dash-stats" }, stat(String(k.in_range), "bài khóa luận"), stat(fmtPct(peak.n / k.in_range), "thuộc năm " + peak.year), stat(k.years_label, "khoảng năm")),
        h("div", { class: "dash-mini", "aria-hidden": "true" }, yrs.map((y) => h("div", { title: `${y.year}: ${y.n} bài` }, h("i", { style: `height:${Math.max(4, (y.n / max) * 100)}%` + (y.year === peak.year ? ";background:var(--p)" : "") }), h("small", null, String(y.year).slice(2))))));
    }
    if (q === "topic") return d.topics.length ? rankRows(d.topics.slice(0, 3), "topics", k.in_range) : empty("Chưa có");
    if (q === "domain") return d.domains.length ? rankRows(d.domains.slice(0, 3), "domains", k.in_range) : empty("Chưa có");
    if (q === "up") {
      const up = d.topics.filter((r) => r.trend === "up").sort((a, b) => b.change_pp - a.change_pp), down = d.topics.filter((r) => r.trend === "down").sort((a, b) => a.change_pp - b.change_pp);
      return h("div", { class: "dash-updown" }, up.length ? pills(up.slice(0, 4).map((r) => ["▲ " + nm("topics", r.name), signed(r.change_pp * 100) + " điểm", "adm-good"])) : empty("Chưa có chủ đề nào tăng đủ rõ"),
        down.length ? pills(down.slice(0, 4).map((r) => ["▼ " + nm("topics", r.name), signed(r.change_pp * 100) + " điểm", "adm-bad"])) : null);
    }
    const fresh = d.emerging.filter((r) => r.reason === "new");
    return fresh.length ? pills(fresh.slice(0, 5).map((r) => [nm("topics", r.name), "từ " + r.first_year, "chip-b"])) : empty("Chưa có");
  }
  function quickCard(d) {
    return h("section", { class: "card dash-quick" },
      h("div", { class: "dash-tabs", role: "tablist" }, QTABS.map(([k, l]) => h("button", { type: "button", role: "tab", "aria-selected": st.quick === k ? "true" : "false", class: "dash-tab" + (st.quick === k ? " on" : ""), onclick: () => { st.quick = k; paint(last); } }, l))),
      h("div", { class: "dash-panel", role: "tabpanel" }, quickPanel(d)));
  }

  // ---------- bảng chi tiết theo năm (tỷ lệ từng chủ đề hoặc lĩnh vực qua từng năm)
  function heatCard(d) {
    const kind = st.heat, rows = d[kind], yrs = d.years;
    if (!yrs.length) return null;
    const max = Math.max(0.01, ...rows.flatMap((r) => r.by_year.map((c, i) => (yrs[i].n ? c / yrs[i].n : 0))));
    const seg = (key, l) => h("button", { type: "button", class: "btn btn-sm" + (kind === key ? " btn-primary" : ""), "aria-pressed": kind === key ? "true" : "false", onclick: () => { st.heat = key; paint(last); } }, l);
    const cell = (c, i, r) => {
      const n = yrs[i].n, sh = n ? c / n : 0, a = c ? 0.1 + 0.8 * (sh / max) : 0, ci = r.ci[i];
      return h("td", { title: `${c} khóa luận (${fmtPct(sh, 1)}); khoảng dao động hợp lý ${fmtPct(ci[0])} đến ${fmtPct(ci[1])}`, style: `text-align:center;background:rgba(44,107,204,${a.toFixed(2)});color:${a > 0.5 ? "#fff" : "inherit"};${yrs[i].small ? "font-style:italic" : ""}` }, c ? fmtPct(sh) : "–");
    };
    return h("section", { class: "card", id: "sec-heat" },
      h("div", { class: "head-row" }, h("h2", null, "Chi tiết theo năm"), h("div", { class: "row" }, seg("topics", "Chủ đề công nghệ"), seg("domains", "Lĩnh vực"),
        h("button", { type: "button", class: "btn btn-sm", onclick: () => csv(d) }, "Tải CSV"))),
      h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table" },
        h("thead", null, h("tr", null, [h("th", null, kind === "topics" ? "Chủ đề" : "Lĩnh vực"), ...yrs.map((y) => h("th", { style: "text-align:center" }, String(y.year), h("div", { class: "muted small" }, "n=" + y.n))), h("th", null, "Xu hướng")])),
        h("tbody", null, rows.map((r) => h("tr", null,
          h("td", null, nm(kind, r.name), h("div", { class: "muted small" }, `${r.total} bài`)),
          ...r.by_year.map((c, i) => cell(c, i, r)),
          h("td", null, badge(r.trend), h("div", { class: "muted small" }, r.share_prior == null ? "" : `${fmtPct(r.share_prior)} → ${fmtPct(r.share_last)}`))))))),
      note("Mỗi ô là tỷ lệ khóa luận của năm đó có nhãn này (trên tất cả bài của năm). Ô càng đậm càng nhiều. Một bài có thể có nhiều nhãn nên cộng một cột có thể vượt 100%. Chữ nghiêng là năm có ít bài (n nhỏ), dễ dao động. Rê chuột vào ô để xem khoảng dao động hợp lý (độ tin cậy 95%)."));
  }
  function csv(d) {
    const q = (v) => '"' + String(v).replace(/"/g, '""') + '"';
    const lines = [["Loại", "Nhóm", ...d.years.map((y) => y.year), "Tổng"].map(q).join(",")];
    for (const [kind, rows] of [["Chủ đề", d.topics], ["Lĩnh vực", d.domains]]) for (const r of rows) lines.push([kind, nm(kind === "Chủ đề" ? "topics" : "domains", r.name), ...r.by_year, r.total].map(q).join(","));
    const a = h("a", { href: URL.createObjectURL(new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" })), download: "xu-huong-khoa-luan.csv" });
    document.body.append(a); a.click(); a.remove();
  }

  // ---------- bộ lọc, KPI, điều hướng trong trang
  const jump = (id) => document.getElementById(id) && document.getElementById(id).scrollIntoView({ behavior: "smooth", block: "start" });
  function filterBar(d) {
    const f = d.filters, yopts = f.years.map((y) => [y, String(y)]), ys = f.years, lastY = ys[ys.length - 1];
    const preset = (label, from, to) => h("button", { type: "button", class: "chip dash-preset" + (+f.year_from === from && +f.year_to === to ? " on" : ""), onclick: () => { st.from = String(from); st.to = String(to); fetchData(); } }, label);
    return h("div", { class: "dash-filters" },
      h("div", { class: "dash-presets", role: "group", "aria-label": "Chọn nhanh khoảng năm" },
        preset("Tất cả các năm", ys[0], lastY), ys.length > 3 ? preset("3 năm gần nhất", ys[ys.length - 3], lastY) : null, preset("Năm " + lastY, lastY, lastY)),
      h("div", { class: "dash-selects" },
        select("f-from", "Từ năm", yopts, f.year_from, (v) => { st.from = v; if (st.to && +st.to < +v) st.to = v; fetchData(); }),
        select("f-to", "Đến năm", yopts, f.year_to, (v) => { st.to = v; if (st.from && +st.from > +v) st.from = v; fetchData(); }),
        select("f-dom", "Lĩnh vực", [["", "Tất cả lĩnh vực"], ...f.domains.map((x) => [x, nm("domains", x)])], f.domain || "", (v) => { st.domain = v; fetchData(); }),
        select("f-top", "Chủ đề công nghệ", [["", "Tất cả chủ đề"], ...f.topics.map((x) => [x, nm("topics", x)])], f.topic || "", (v) => { st.topic = v; fetchData(); }),
        (st.from || st.to || st.domain || st.topic) ? h("button", { type: "button", class: "btn btn-sm", onclick: () => { Object.assign(st, { from: "", to: "", domain: "", topic: "" }); fetchData(); } }, "Xóa lọc") : null));
  }
  const jumpNav = () => h("nav", { class: "dash-jump", "aria-label": "Chuyển nhanh tới phần" }, [["sec-trend", "Xu hướng theo năm"], ["sec-mix", "Lĩnh vực & công nghệ"], ["sec-top", "Top 5 chủ đề"], ["sec-new", "Chủ đề mới nổi"], ["sec-heat", "Bảng chi tiết"]]
    .map(([id, t]) => h("button", { type: "button", class: "chip", onclick: () => jump(id) }, t)));

  function paint(d) {
    clear(body);
    if (!d || !d.filters) { body.append(h("div", { class: "state" }, (d && d.note) || "Chưa có dữ liệu theo năm.")); return; }
    const f = d.filters, k = d.kpi, filtered = f.domain || f.topic, lq = d.label_quality;
    clear(frame); frame.style.opacity = "";
    const wrap = (id, el) => { if (el) el.id = id; return el; };
    frame.append(
      quickCard(d),
      h("div", { class: "adm-tiles" },
        tile("Tổng số bài", String(k.total), `NEU, ${f.years[0]}–${f.years[f.years.length - 1]}`),
        tile("Đang xem", String(k.in_range), (k.single_year ? "năm " : "") + k.years_label + (filtered ? ", đã lọc" : "")),
        tile("Lĩnh vực", String(k.n_domains), `trên ${k.n_domains_all}`),
        tile("Chủ đề công nghệ", String(k.n_topics), `trên ${k.n_topics_all}`)),
      jumpNav(),
      wrap("sec-trend", trendCard(d)), mixCard(d), barCard(d), wrap("sec-top", top5Card(d)), wrap("sec-new", emergingCard(d)), heatCard(d),
      h("section", { class: "card dash-cta" }, h("div", null, h("h2", null, "Đã chọn được hướng?")),
        h("div", { class: "row" }, h("a", { class: "btn", href: "#/library" + (f.topic ? "?topic=" + encodeURIComponent(f.topic) : "") }, "Xem kho khóa luận"), h("a", { class: "btn btn-primary", href: "#/ideas" }, "Đề xuất khóa luận cho tôi"))),
      note(`Dữ liệu là các khóa luận NEU đã thu thập từ trang khoa, không phải mọi khóa luận của trường${d.years.length ? "; năm " + d.years.reduce((x, y) => (y.n > x.n ? y : x)).year + " chiếm nhiều bài nhất nên so sánh phụ thuộc nhiều vào năm này" : ""}. ` +
        `Nhãn đã được người xác nhận: ${fmtPct(lq.gold_share)} (${lq.gold} bài); còn lại do mô hình dự đoán nên có thể sai. ${d.no_topic} bài chưa có chủ đề, ${d.no_domain} bài chưa có lĩnh vực.`));
    body.append(filterBar(d), frame);
  }
}
