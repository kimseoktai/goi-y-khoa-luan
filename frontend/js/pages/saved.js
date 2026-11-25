// Đề tài đã lưu (lưu trên trình duyệt): xếp hạng theo mức hợp, có điểm mạnh/yếu từng đề tài và 3 giảng viên gợi ý.
import { h, clear } from "../dom.js";
import { store } from "../store.js";
import { api } from "../api.js";
import { icon } from "../icons.js";
import { foot, yearSchool } from "../ui.js";

const MAX = 3;
const shortTitle = (t) => (t.length > 60 ? t.slice(0, 57) + "…" : t);

function fitInfo(it) {
  if (it.kind === "thesis" || it.fit == null || !it.fit_total) return { text: "Không áp dụng (khóa luận đã làm)", frac: null };
  return { text: it.fit === it.fit_total ? (it.fit_total === 1 ? "Hợp với việc bạn chọn" : "Hợp cả " + it.fit_total + " việc bạn chọn") : it.fit === 0 ? "Ít gặp trong các việc bạn chọn" : "Hợp " + it.fit + " trong " + it.fit_total + " việc", frac: it.fit / it.fit_total };
}
function statusInfo(it) {
  if (it.kind === "thesis") return { text: "Đã có trong kho", cls: "warn", novel: false };
  if (it.status === "Novel") return { text: "Chưa ai làm", cls: "ok", novel: true };
  if (it.status === "Similar") return { text: "Có bạn làm hướng gần giống", cls: "warn", novel: false };
  return { text: "Chưa kiểm tra trùng", cls: "wait", novel: false };
}

const advCache = new Map();
const pdfCache = new Map();
function pdfBtn(s) {
  const mk = (url) => h("a", { class: "sf-pdf", href: url, target: "_blank", rel: "noopener noreferrer", "aria-label": "Xem PDF: " + s.title }, icon("file", 16), "Xem PDF");
  if (s.report_url) return mk(s.report_url);
  const none = () => h("span", { class: "sf-pdf off" }, "Chưa có PDF");
  const box = h("span", { class: "sf-pdfbox" }, h("span", { class: "sf-pdf off" }, "Đang kiểm tra PDF…"));
  const tid = String(s.id).replace(/^thesis:/, "");
  const known = pdfCache.get(tid);
  const put = (u) => { pdfCache.set(tid, u || ""); if (box.isConnected || true) clear(box).append(u ? mk(u) : none()); };
  if (known !== undefined) put(known);
  else api.thesisOne(tid).then((t) => put(t && t.report_url)).catch(() => put(""));
  return box;
}

function scoreOf(s) {
  const f = fitInfo(s).frac;
  return (f == null ? 0 : f * 10) + (statusInfo(s).novel ? 5 : 0) + (s.status === "Similar" ? -2 : 0);
}
function reasons(s, have) {
  const f = fitInfo(s), st = statusInfo(s), pro = [], con = [];
  if (f.frac != null && f.frac > 0) pro.push(f.text);
  if (st.novel) pro.push("Chưa ai làm, ít lo trùng");
  const sk = s.skills || [], mine = sk.filter((x) => have.has(x.toLowerCase())), miss = sk.filter((x) => !have.has(x.toLowerCase()));
  if (mine.length) pro.push("Dùng kỹ năng bạn đã có: " + mine.slice(0, 3).join(", "));
  if (f.frac === 0) con.push("Ít gặp trong các việc bạn chọn");
  else if (f.frac != null && f.frac < 1) con.push("Chỉ hợp " + s.fit + " trong " + s.fit_total + " việc bạn chọn");
  if (s.status === "Similar") con.push("Có bạn làm hướng gần giống");
  else if (!st.novel) con.push("Chưa kiểm tra trùng với khóa luận cũ");
  if (miss.length) con.push("Cần học thêm: " + miss.slice(0, 3).join(", "));
  if (!pro.length) pro.push("Có thể làm được nếu bạn quan tâm hướng này");
  if (!con.length) con.push("Chưa thấy điểm cần lưu ý");
  return { pro, con };
}

export function render(root, params, ctx) {
  const top = h("section", { class: "sv-hero" });
  const body = h("div", { class: "sf" });
    const tabs = h("div", { class: "sf-tabs", role: "tablist" });
  let tab = "idea";
  root.append(h("div", { class: "sv" }, top, tabs, body, foot("Danh sách này được lưu theo mã sinh viên của bạn. Thứ hạng và giảng viên chỉ là gợi ý để tham khảo, bạn nên trao đổi với giảng viên hướng dẫn và khoa.")));
  const signal = ctx && ctx.signal ? ctx.signal : undefined;

  function paint() {
    const saved = store.get().saved;
    const have = new Set((store.get().skills || []).map((x) => x.toLowerCase()));
    const ideas = saved.filter((s) => s.kind !== "thesis").sort((a, b) => scoreOf(b) - scoreOf(a));
    const theses = saved.filter((s) => s.kind === "thesis");
    clear(top).append(h("h1", null, "Đề tài đã lưu"),
      h("p", null, saved.length ? "Bạn đã lưu " + ideas.length + " đề tài được đề xuất và " + theses.length + " đề tài tham khảo." : "Bạn chưa lưu đề tài nào. Bấm \"Lưu đề tài\" ở trang gợi ý hoặc trong kho khóa luận để lưu lại đây."),
      ...(saved.length ? [] : [h("div", { class: "sv-empty" }, h("a", { class: "sk-b w", href: "#/ideas" }, "Xem đề tài gợi ý"), h("a", { class: "sk-b", href: "#/library" }, "Mở kho khóa luận"))]));
    const unsave = (s) => h("button", { type: "button", class: "x", "aria-label": "Bỏ lưu: " + s.title, onclick: () => { store.removeSaved(s.id); paint(); } }, "♥ Bỏ lưu");
    const sc = ideas.map(scoreOf), reco = ideas.length && (ideas.length === 1 || sc[0] > sc[1]);
    if (!ideas.length && theses.length) tab = "thesis";
    clear(tabs);
    if (saved.length) tabs.append(...[["idea", "Được đề xuất", "Đề tài bạn thích từ trang gợi ý", ideas.length, "bulb"], ["thesis", "Tham khảo", "Khóa luận có sẵn từ kho", theses.length, "book"]].map(([k, l, d, n, ic]) =>
      h("button", { type: "button", role: "tab", class: "sf-tab" + (tab === k ? " on" : ""), "aria-selected": tab === k ? "true" : "false", onclick: () => { tab = k; paint(); } },
        h("span", { class: "ic" }, icon(ic)), h("span", { class: "tx" }, h("b", null, l), h("small", null, d)), h("span", { class: "n" }, String(n)))));
    clear(body);
    if (tab === "thesis") {
      if (!theses.length) body.append(h("div", { class: "sf-none" }, "Bạn chưa lưu đề tài tham khảo nào. Mở ", h("a", { href: "#/library" }, "Kho khóa luận"), " và bấm lưu ở khóa luận bạn muốn tham khảo."));
      theses.forEach((s) => body.append(h("article", { class: "sf-card" },
        h("div", { class: "sf-h" }, h("b", null, s.title), h("span", { class: "id-tag wait" }, yearSchool(s) || "Khóa luận có sẵn")),
        s.summary ? h("p", { class: "sf-sum sf-flat" }, s.summary) : null,
        h("div", { class: "sf-f" }, h("div", { class: "sv-chips tech" }, (s.topics || []).slice(0, 4).map((x) => h("span", null, x))),
          h("div", { class: "sf-acts" }, pdfBtn(s), unsave(s))))));
      return;
    }
    if (!ideas.length) body.append(h("div", { class: "sf-none" }, "Bạn chưa lưu đề tài được đề xuất nào. Bấm \"Lưu đề tài\" ở trang ", h("a", { href: "#/ideas" }, "Đề xuất khóa luận"), "."));
    ideas.forEach((s, i) => {
      const f = fitInfo(s), st = statusInfo(s), r = reasons(s, have);
      const advBox = h("div", { class: "sf-ab" }, h("small", { class: "sf-hd adv" }, "Giảng viên có thể phù hợp"), h("p", { class: "muted small" }, "Đang tìm giảng viên phù hợp…"));
      setTimeout(() => loadAdv(s, advBox), i * 120);
      body.append(h("article", { class: "sf-card sf-j" + (reco && i === 0 ? " top" : "") },
        h("div", { class: "sf-l" },
          h("div", { class: "sf-h" }, h("span", { class: "no" }, String(i + 1)), h("b", null, s.title)),
          h("div", { class: "sf-tags" }, f.frac != null ? h("span", { class: "id-tag fit" }, f.text) : null, h("span", { class: "id-tag " + st.cls }, st.text)),
          s.summary ? h("div", { class: "sf-block abs" }, h("small", { class: "sf-hd abs" }, "Tóm tắt"), h("p", { class: "sf-sum" }, s.summary)) : null,
          ...(s.topics && s.topics[0] ? [h("div", { class: "sf-topicband" }, h("small", { class: "sf-hd topic" }, "Hướng đề tài"), h("b", { class: "sf-topic" }, s.topics[0]))] : []),
          h("div", { class: "sf-meta" },
            ...((s.tech || []).length ? [h("div", null, h("small", { class: "sf-hd tech" }, "Công nghệ nên dùng"), h("div", { class: "sv-chips tech" }, s.tech.slice(0, 6).map((x) => h("span", null, x))))] : []),
            ...((s.skills || []).length ? [h("div", null, h("small", { class: "sf-hd skill" }, "Kỹ năng rèn được"), h("div", { class: "sv-chips" }, s.skills.slice(0, 6).map((x) => h("span", null, x))))] : [])),
          h("div", { class: "sf-un" }, h("span", { class: "muted small" }, "Gợi ý chỉ để tham khảo, hãy trao đổi với khoa."), unsave(s))),
        h("aside", { class: "sf-r" },
          h("div", null, h("small", { class: "sf-hd pro" }, "Điểm mạnh"), h("ul", { class: "pro" }, r.pro.map((x) => h("li", null, x)))),
          h("div", null, h("small", { class: "sf-hd con" }, "Cần cân nhắc"), h("ul", { class: "con" }, r.con.map((x) => h("li", null, x)))),
          advBox)));
    });
  }

  async function loadAdv(it, box) {
    let r = advCache.get(it.id);
    if (r === undefined) {
      try { r = await api.advisorsFor({ topic: it.topic || null, domains: it.domains || [], text: (it.title + ". " + (it.summary || "")).slice(0, 1500), top_k: 3 }, { signal }); } catch (e) { r = null; }
      if (r) advCache.set(it.id, r);
    }
    if (!box.isConnected) return;
    const items = r ? (r.items || []).slice(0, 3) : null;
    clear(box).append(h("small", { class: "sf-hd adv" }, "Giảng viên có thể phù hợp"),
      items === null ? h("p", { class: "muted small" }, "Chưa tải được gợi ý giảng viên. Thử mở lại trang sau.")
        : !items.length ? h("p", { class: "muted small" }, "Chưa tìm thấy giảng viên nào có khóa luận gần đề tài này.")
        : h("ul", { class: "sf-bl" }, items.map((a) => h("li", null, h("b", null, a.advisor),
            h("span", { class: "id-ad-s" }, (a.n_related ? a.n_related + " khóa luận cùng hướng" + (a.latest_related_year ? ", gần nhất " + a.latest_related_year : "") + " · " : "") + "tổng " + a.n_theses + " khóa luận"),
            (a.nearest || []).length ? h("span", { class: "muted small sf-near" }, "Đã hướng dẫn: " + a.nearest[0].title) : null))),
      ...(r && r.low_data ? [h("p", { class: "id-ad-warn" }, "Hướng này có rất ít khóa luận trong dữ liệu nên chỉ mang tính tham khảo.")] : []));
  }
  paint();
}
