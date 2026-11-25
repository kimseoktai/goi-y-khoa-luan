// Dashboard tổng quan xu hướng khóa luận NEU: bộ lọc, KPI, xu hướng theo năm, cơ cấu lĩnh vực và công nghệ, top 5 chủ đề, chủ đề mới nổi.
// Mọi con số lấy từ một lát cắt do máy chủ tính (GET /dashboard/thesis), nên các khối luôn khớp nhau. Biểu đồ vẽ bằng SVG, chữ đi qua textContent.
import { h, clear, svg } from "../dom.js";
import { api } from "../api.js";
import { load, foot, pageHead } from "../ui.js";

const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];   // bảng màu danh mục đã kiểm tra (CVD, độ sáng)
const INK = "#1B1B1F", OTHER = "#8d8c97";
const TREND = { up: ["▲", "Đang tăng", "adm-good"], down: ["▼", "Đang giảm", "adm-bad"], flat: ["▬", "Ổn định", ""], insufficient: ["?", "Chưa đủ dữ liệu", ""] };
const fmtPct = (x, d = 0) => (x * 100).toFixed(d).replace(".", ",") + "%";
const signed = (x, d = 1) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d).replace(".", ",");

export function render(root, params, ctx) {
  const body = h("div", { class: "stack" });
  root.append(pageHead("Tổng quan xu hướng khóa luận", "Khóa luận của Đại học Kinh tế Quốc dân qua từng năm: làm về mảng nào, mảng nào đang tăng, mảng nào mới xuất hiện. Đổi bộ lọc thì mọi con số bên dưới đổi theo."), body);
  const st = { from: "", to: "", domain: "", topic: "", view: "domain", chart: "chart", unit: "count" };
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
  const tile = (label, value, sub) => h("div", { class: "adm-tile" }, h("div", { class: "adm-tile-l" }, label), h("div", { class: "adm-tile-v" }, value), sub ? h("div", { class: "adm-tile-s" }, sub) : null);
  const select = (id, label, opts, val, onchange) => h("div", { class: "dash-f" }, h("label", { for: id }, label),
    h("select", { id, class: "input", style: "flex:none", onchange: (e) => onchange(e.target.value) }, opts.map(([v, t]) => h("option", { value: v, selected: String(v) === String(val) ? "" : null }, t))));
  const badge = (tr) => h("span", { class: "chip " + TREND[tr][2] }, TREND[tr][0] + " " + TREND[tr][1]);
  const growth = (r) => {
    if (r.change_pp == null) return h("span", { class: "muted small" }, "Chưa so được (chỉ có một năm)");
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
    const total = { key: "__total", name: "Tất cả khóa luận (đã lọc)", color: INK, data: share ? nY.map(() => 100) : nY, trend: null };
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
    const legend = h("ul", { class: "dash-legend" }, series.map((s) => h("li", null, h("i", { class: "dash-key", style: `background:${s.color}` }), h("span", null, s.name), s.trend ? badge(s.trend) : null)));
    const table = h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table" },
      h("thead", null, h("tr", null, [h("th", null, "Nhóm"), ...years.map((y) => h("th", { style: "text-align:right" }, String(y)))])),
      h("tbody", null, series.map((s) => h("tr", null, h("td", null, s.name), s.data.map((v) => h("td", { style: "text-align:right" }, share ? v.toFixed(1).replace(".", ",") + "%" : String(v))))))));
    return { host, legend, table };
  }

  function trendCard(d) {
    const c = lineChart(d), asTable = st.chart === "table";
    const seg = (k, l, cur, set) => h("button", { type: "button", class: "btn btn-sm" + (cur === k ? " btn-primary" : ""), "aria-pressed": cur === k ? "true" : "false", onclick: () => set(k) }, l);
    const small = d.years.filter((y) => y.small).map((y) => y.year);
    return h("section", { class: "card" },
      h("div", { class: "head-row" }, h("h2", null, "Xu hướng khóa luận theo năm"),
        h("div", { class: "row" }, seg("count", "Số bài", st.unit, (k) => { st.unit = k; paint(last); }), seg("share", "Tỷ lệ %", st.unit, (k) => { st.unit = k; paint(last); }), seg("domain", "Theo lĩnh vực", d.series.view, (k) => { st.view = k; fetchData(); }), seg("topic", "Theo chủ đề công nghệ", d.series.view, (k) => { st.view = k; fetchData(); }),
          seg("table", "Xem dạng bảng", st.chart, (k) => { st.chart = st.chart === "table" ? "chart" : k; paint(last); }))),
      d.years.length ? [asTable ? c.table : c.host, c.legend] : h("p", { class: "muted" }, "Không có khóa luận nào khớp bộ lọc."),
      h("p", { class: "muted small" }, `${st.unit === "share" ? "Tỷ lệ = số bài của nhóm / tất cả bài khớp bộ lọc trong năm đó; một bài có thể thuộc nhiều nhóm. Các đường màu là 5 nhóm nhiều bài nhất." : "Đường đen là tổng số khóa luận khớp bộ lọc; các đường màu là 5 nhóm nhiều bài nhất. Chọn Tỷ lệ % để so các nhóm khi một năm có quá nhiều bài."} Nhãn "đang tăng/giảm" so tỷ lệ của năm ${d.latest_year ?? "cuối"} với các năm trước trong khoảng đã chọn, chỉ kết luận khi khoảng tin cậy 95% không chồng nhau và mỗi bên có ít nhất ${d.min_n} bài; còn lại là ổn định hoặc chưa đủ dữ liệu.` +
        (small.length ? ` Năm ${small.join(", ")} có dưới ${d.small_year} bài nên dao động nhiều.` : "")));
  }

  // ---------- biểu đồ tròn (donut)
  function pieCard(d) {
    const R = 86, r = 54, cx = 100, cy = 100, tot = d.domain_mix.reduce((s, x) => s + x.count, 0);
    const host = h("div", { class: "dash-chart dash-pie" });
    const g = svg("svg", { viewBox: "0 0 200 200", class: "dash-svg", role: "img", "aria-label": "Tỷ trọng khóa luận theo lĩnh vực" });
    let a0 = -Math.PI / 2;
    const items = d.domain_mix.map((x) => ({ ...x, color: x.other ? OTHER : colorOf("domains", x.name), label: x.other ? `Khác (${x.n_labels} lĩnh vực)` : nm("domains", x.name) }));
    items.forEach((x) => {
      const a1 = a0 + (x.count / tot) * Math.PI * 2, big = a1 - a0 > Math.PI ? 1 : 0, p = (a, rad) => `${(cx + rad * Math.cos(a)).toFixed(2)},${(cy + rad * Math.sin(a)).toFixed(2)}`;
      const full = items.length === 1;
      const path = svg(full ? "circle" : "path", full ? { cx, cy, r: (R + r) / 2, fill: "none", stroke: x.color, "stroke-width": R - r } :
        { d: `M${p(a0, R)} A${R},${R} 0 ${big} 1 ${p(a1, R)} L${p(a1, r)} A${r},${r} 0 ${big} 0 ${p(a0, r)} Z`, fill: x.color, stroke: "#fff", "stroke-width": 2 });
      path.addEventListener("pointermove", (ev) => showTip(host, ev.clientX, ev.clientY, x.label, [[x.color, fmtPct(x.share, 1), `${x.count} lượt gắn nhãn`]]));
      path.addEventListener("pointerleave", hideTip);
      g.append(path); a0 = a1;
    });
    g.append(svg("text", { x: cx, y: cy - 2, "text-anchor": "middle", class: "dash-big" }, String(d.kpi.in_range)), svg("text", { x: cx, y: cy + 16, "text-anchor": "middle", class: "dash-ax" }, "khóa luận"));
    host.append(g);
    const legend = h("ul", { class: "dash-legend dash-legend-col" }, items.map((x) => h("li", null, h("i", { class: "dash-key", style: `background:${x.color}` }), h("span", null, x.label), h("b", null, fmtPct(x.share, 1)), h("span", { class: "muted small" }, x.count))));
    return h("section", { class: "card" }, h("h2", null, "Tỷ trọng theo lĩnh vực"),
      items.length ? h("div", { class: "dash-pie-row" }, host, legend) : h("p", { class: "muted" }, "Chưa có lĩnh vực nào trong lát cắt này."),
      h("p", { class: "muted small" }, `Tính theo số lần gắn nhãn lĩnh vực (một bài có thể thuộc nhiều lĩnh vực) nên cộng lại đúng 100%. ${d.no_domain} bài chưa có lĩnh vực không nằm trong biểu đồ này.`));
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
    const card = h("section", { class: "card dash-chart" }, h("h2", null, "Chủ đề công nghệ phổ biến"), rows.length ? rows : h("p", { class: "muted" }, "Chưa có chủ đề nào trong lát cắt này."),
      h("p", { class: "muted small" }, "Số khóa luận mang nhãn chủ đề đó; một bài có thể có nhiều chủ đề."));
    return card;
  }

  // ---------- top 5 và chủ đề mới nổi
  function top5Card(d) {
    return h("section", { class: "card" }, h("h2", null, "Top 5 chủ đề nổi bật"),
      d.top5.length ? h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table" },
        h("thead", null, h("tr", null, ["#", "Chủ đề", "Số khóa luận", `Tăng trưởng (năm ${d.latest_year} so với trước)`, "Lĩnh vực hay gặp"].map((t) => h("th", null, t)))),
        h("tbody", null, d.top5.map((r, i) => h("tr", null, h("td", null, String(i + 1)), h("td", null, h("strong", null, nm("topics", r.name)), h("div", null, badge(r.trend))),
          h("td", null, String(r.count)), h("td", null, growth(r)),
          h("td", null, r.common_domains.length ? r.common_domains.map((x) => h("div", null, nm("domains", x.name), h("span", { class: "muted small" }, ` ${fmtPct(x.share)} số bài của chủ đề`))) : h("span", { class: "muted" }, "Chưa có lĩnh vực"))))))) :
        h("p", { class: "muted" }, "Chưa có chủ đề nào."),
      h("p", { class: "muted small" }, "Xếp theo số khóa luận trong lát cắt đang xem. Tăng trưởng là thay đổi tỷ lệ của chủ đề trong năm cuối so với tỷ lệ gộp các năm trước đó trong khoảng (điểm phần trăm, kèm % tương đối)."));
  }

  function emergingCard(d) {
    const why = { new: "Mới xuất hiện", fast: "Tăng nhanh" };
    return h("section", { class: "card" }, h("h2", null, "Chủ đề mới nổi"),
      d.emerging.length ? h("div", { style: "overflow-x:auto" }, h("table", { class: "adm-table" },
        h("thead", null, h("tr", null, ["Chủ đề", "Bắt đầu xuất hiện", "Khóa luận gần đây", "Xu hướng"].map((t) => h("th", null, t)))),
        h("tbody", null, d.emerging.map((r) => h("tr", null,
          h("td", null, h("strong", null, nm("topics", r.name)), r.status === "candidate" ? h("div", { class: "muted small" }, "chủ đề đề xuất, chưa duyệt") : null),
          h("td", null, String(r.first_year)), h("td", null, `${r.recent_count} bài (2 năm cuối của khoảng)`),
          h("td", null, h("span", { class: "chip " + (r.reason === "new" ? "chip-b" : "adm-good") }, why[r.reason]), h("div", null, growth(r)))))))) :
        h("p", { class: "muted" }, "Chưa có chủ đề nào đủ dấu hiệu mới nổi trong lát cắt này."),
      h("p", { class: "muted small" }, "“Bắt đầu xuất hiện” là năm đầu tiên chủ đề có từ 2 khóa luận trong toàn bộ dữ liệu của trường. Một chủ đề được liệt kê khi mới xuất hiện trong 2 năm gần nhất (và không có ngay từ năm đầu của dữ liệu), hoặc đang tăng rõ, hoặc tỷ lệ năm cuối gấp 1,5 lần giai đoạn trước với ít nhất 5 bài. Đây là mô tả dữ liệu, không phải dự báo."));
  }

  function paint(d) {
    clear(body);
    if (!d || !d.filters) { body.append(h("div", { class: "state" }, (d && d.note) || "Chưa có dữ liệu theo năm.")); return; }
    const f = d.filters, k = d.kpi, yopts = f.years.map((y) => [y, String(y)]);
    const bar = h("div", { class: "dash-filters" },
      select("f-from", "Từ năm", yopts, f.year_from, (v) => { st.from = v; if (st.to && +st.to < +v) st.to = v; fetchData(); }),
      select("f-to", "Đến năm", yopts, f.year_to, (v) => { st.to = v; if (st.from && +st.from > +v) st.from = v; fetchData(); }),
      select("f-dom", "Lĩnh vực", [["", "Tất cả lĩnh vực"], ...f.domains.map((x) => [x, nm("domains", x)])], f.domain || "", (v) => { st.domain = v; fetchData(); }),
      select("f-top", "Chủ đề công nghệ", [["", "Tất cả chủ đề"], ...f.topics.map((x) => [x, nm("topics", x)])], f.topic || "", (v) => { st.topic = v; fetchData(); }),
      (st.from || st.to || st.domain || st.topic) ? h("button", { type: "button", class: "btn btn-sm", onclick: () => { Object.assign(st, { from: "", to: "", domain: "", topic: "" }); fetchData(); } }, "Xóa bộ lọc") : null);
    const filtered = f.domain || f.topic;
    clear(frame); frame.style.opacity = "";
    frame.append(
      h("div", { class: "adm-tiles" },
        tile("Tổng số khóa luận", String(k.total), `trong dữ liệu NEU, ${f.years[0]}–${f.years[f.years.length - 1]}`),
        tile(k.single_year ? "Khóa luận năm " + k.years_label : "Khóa luận " + k.years_label, String(k.in_range), filtered ? "khớp cả bộ lọc lĩnh vực/chủ đề" : "trong khoảng đã chọn"),
        tile("Lĩnh vực được thống kê", String(k.n_domains), `trên ${k.n_domains_all} lĩnh vực trong danh mục`),
        tile("Chủ đề công nghệ phát hiện", String(k.n_topics), `trên ${k.n_topics_all} chủ đề trong danh mục`)),
      trendCard(d), h("div", { class: "dash-two" }, pieCard(d), barCard(d)), top5Card(d), emergingCard(d),
      foot(`Dữ liệu là các khóa luận NEU đã thu thập được từ trang khoa, không phải mọi khóa luận của trường${d.years.length ? "; năm " + d.years.reduce((a, b) => (b.n > a.n ? b : a)).year + " chiếm nhiều bài nhất nên các so sánh phụ thuộc nhiều vào năm này" : ""}. Nhãn chủ đề và lĩnh vực của các bài chưa được người xác nhận do mô hình phân loại dự đoán nên có thể sai ở một số bài.`));
    body.append(bar, frame);
  }
}
