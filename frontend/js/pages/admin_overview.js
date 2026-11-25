import { h, clear } from "../dom.js";
import { loading } from "../ui.js";

const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("vi-VN"));
const share = (a, b) => (b ? Math.round((100 * a) / b) + "%" : "–");
const pctN = (a, b) => (b ? Math.round((100 * a) / b) : 0);
// Ô chỉ số: nhãn nhỏ, số lớn, thanh tiến độ (nếu có tỉ lệ) và dòng phụ.
const tile = (label, value, sub, ratio, tone) => h("div", { class: "adm-tile" + (tone ? " tone-" + tone : "") },
  h("div", { class: "adm-tile-l" }, label), h("div", { class: "adm-tile-v" }, value),
  ratio == null ? null : h("div", { class: "adm-meter", role: "progressbar", "aria-valuenow": String(ratio), "aria-valuemin": "0", "aria-valuemax": "100", "aria-label": label }, h("div", { class: "adm-meter-f", style: "width:" + ratio + "%" })),
  sub ? h("div", { class: "adm-tile-s" }, sub) : null);
const table = (head, rows) => h("table", { class: "adm-table" }, h("thead", null, h("tr", null, head.map((x) => h("th", null, x)))), h("tbody", null, rows.map((r) => h("tr", null, r.map((c) => h("td", null, c))))));

// Tab "Tổng quan": chỉ số dữ liệu, các lần crawl gần nhất, trạng thái lịch tuần.
export function mount(box, A) {
  function refresh() {
    clear(box).append(loading());
    A.get("/overview").then(paint).catch((e) => A.fail(box, e, refresh));
  }
  function paint(d) {
    const c = d.coverage, db = d.db, sc = d.schedule, ct = d.company_table;
    clear(box).append(
      h("section", { class: "card" }, h("h2", null, "Dữ liệu website đang dùng"),
        h("div", { class: "adm-tiles" },
          tile("Tin tuyển dụng", fmt(c.jobs), "nguồn: " + (c.source === "db" ? "CSDL" : "CSV cũ"), null, "dark"),
          tile("Technical Topic", share(c.with_topic, c.jobs), fmt(c.with_topic) + " / " + fmt(c.jobs) + " tin", pctN(c.with_topic, c.jobs), "p"),
          tile("Domain", share(c.with_domain, c.jobs), fmt(c.with_domain) + " / " + fmt(c.jobs) + " tin", pctN(c.with_domain, c.jobs), "b"),
          tile("Skill", share(c.with_skill, c.jobs), fmt(c.with_skill) + " / " + fmt(c.jobs) + " tin", pctN(c.with_skill, c.jobs), "g")),
        h("div", { class: "adm-tiles adm-tiles-2" },
          tile("Domain từ bảng công ty", fmt(c.domain_from_company_table), "trên " + fmt(c.with_domain) + " tin có Domain", pctN(c.domain_from_company_table, c.with_domain)),
          tile("Embedding", c.embeddings ? "Có" : "Chưa có", c.embeddings_filled ? "mã hóa bù " + c.embeddings_filled + " tin khi chạy" : "đủ cho mọi tin")),
        h("div", { class: "muted small" }, "Số này tính trên dữ liệu website đã nạp. Sau khi dựng lại dữ liệu, vào tab \"Chạy lệnh\" và bấm \"Nạp lại dữ liệu\" để thấy số mới.")),
      db ? h("section", { class: "card" }, h("h2", null, "Tin trong CSDL theo nguồn"),
        db.by_source.length ? table(["Nguồn", "Tổng", "Đang tuyển", "Mới 7 ngày", "Thấy lần cuối"], db.by_source.map((r) => [r.source, fmt(r.total), fmt(r.active), fmt(r.new_7d), r.last_seen || "–"])) : h("div", { class: "state" }, "CSDL chưa có tin nào."),
        bars(db.daily_new)) : h("section", { class: "card" }, h("h2", null, "Tin trong CSDL"), h("div", { class: "state" }, "Chưa thấy data/db/jobs.sqlite nên chưa có số liệu theo nguồn.")),
      db && db.recent_batches.length ? h("section", { class: "card" }, h("h2", null, "Các lần chạy crawl gần nhất"), h("div", { class: "muted small" }, "Mỗi lần chạy gồm các nguồn crawl liên tiếp (TopDev, ITviec, CareerViet). Bấm một lần chạy để xem từng nguồn."),
        db.recent_batches.map((b, i) => batch(b, i === 0))) : null,
      h("section", { class: "card" }, h("h2", null, "Lịch crawl hằng tuần"),
        sc.available ? table(["Trạng thái", "Lần chạy kế tiếp", "Lần chạy cuối", "Kết quả lần cuối"], [[sc.status, sc.next_run, sc.last_run, sc.last_result === "0" ? "Thành công (0)" : sc.last_result]])
          : h("div", { class: "state" }, sc.note || "Không đọc được lịch.")));
  }
  refresh();
}

const when = (t) => { const m = String(t || "").match(/(\d{4})-(\d\d)-(\d\d)[T ](\d\d:\d\d)/); return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}` : String(t || "–"); };
function batch(b, open) {
  const bad = b.runs.filter((r) => !r.ok).length;
  const state = h("span", { class: "chip " + (bad ? "adm-bad" : "adm-good") }, bad ? bad + " nguồn lỗi" : "Thành công");
  return h("details", { class: "adm-batch", open }, h("summary", null,
    h("span", { class: "adm-batch-t" }, when(b.started_at)), state,
    h("span", { class: "muted small" }, `${b.runs.length} nguồn · thấy ${fmt(b.n_seen)} · mới ${fmt(b.n_new)} · đóng ${fmt(b.n_closed)}`)),
    table(["Nguồn", "Bắt đầu", "Thấy", "Mới", "Đóng", "Kết quả"], b.runs.map((r) => [r.source, when(r.started_at), fmt(r.n_seen), fmt(r.n_new), fmt(r.n_closed), r.ok ? "Thành công" + (r.note ? " · " + r.note : "") : "Lỗi" + (r.note ? ": " + r.note : "")])));
}

function bars(daily) {
  if (!daily || !daily.length) return null;
  const by = Object.fromEntries(daily.map((x) => [x.day, x.n]));
  const days = [];                                           // đủ 14 ngày liên tục, ngày không có tin hiển thị 0
  for (let i = 13; i >= 0; i--) { const d = new Date(Date.now() - i * 864e5), k = d.toISOString().slice(0, 10); days.push({ day: k, n: by[k] || 0 }); }
  const max = Math.max(...days.map((x) => x.n), 1);
  return h("div", { class: "adm-chart" }, h("div", { class: "adm-chart-t" }, "Tin mới mỗi ngày · 14 ngày gần nhất"),
    h("div", { class: "adm-bars", role: "img", "aria-label": "Số tin mới mỗi ngày" }, days.map((x) => h("div", { class: "adm-bar" + (x.n ? "" : " zero"), title: x.day + ": " + x.n + " tin" },
      h("div", { class: "adm-bar-n" }, x.n ? String(x.n) : ""), h("div", { class: "adm-bar-f", style: "height:" + (x.n ? Math.max(6, Math.round((100 * x.n) / max)) : 3) + "%" }), h("div", { class: "adm-bar-d" }, x.day.slice(8) + "/" + x.day.slice(5, 7))))));
}
