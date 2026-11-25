import { h, clear } from "../dom.js";
import { loading, notice, chip } from "../ui.js";

const PAGE = 20;
const ORIGIN = { legacy: "dữ liệu có sẵn", crawl: "crawl từ trang", manual: "thêm tay" };
const SORTS = [["newest", "Mới thêm trước"], ["year", "Năm mới trước"], ["title", "Tiêu đề A-Z"], ["oldest", "Cũ trước"]];

// Tab "Khóa luận": xem, thêm, sửa, xóa (đóng) và khôi phục đề tài; chỉnh nhãn tay. Thay đổi ghi vào CSDL ngay, website đổi sau khi bấm "Dựng lại và nạp".
export function mount(box, A) {
  let f = { q: "", status: "", source: "", origin: "", sort: "newest" }, offset = 0, flash = "", editor = null, meta = { topics: [], domains: [], sources: [] }, building = false;
  const bar = h("div", { class: "card" }), pend = h("div"), edit = h("div"), list = h("div");
  box.append(bar, pend, edit, list);

  const say = (m) => { flash = m; };
  const fail = (e) => String((e && (e.detail || e.message)) || "Không thực hiện được.");

  function load() {
    clear(list).append(loading());
    const p = new URLSearchParams({ ...f, limit: PAGE, offset });
    A.get("/thesis?" + p).then((d) => { meta = d; paintBar(); paintPending(d.pending); paintList(d); }).catch((e) => A.fail(list, e, load));
  }

  function paintBar() {
    const sel = (key, opts, label) => h("select", { class: "select", "aria-label": label, onchange: (ev) => { f[key] = ev.target.value; offset = 0; load(); } },
      opts.map(([v, l]) => h("option", { value: v, selected: v === f[key] }, l)));
    const qi = h("input", { class: "input", type: "search", placeholder: "Tìm theo tiêu đề", value: f.q, "aria-label": "Tìm khóa luận", onkeydown: (ev) => { if (ev.key === "Enter") { f.q = ev.target.value.trim(); offset = 0; load(); } } });
    clear(bar).append(h("h2", null, "Quản lý khóa luận"),
      h("div", { class: "muted" }, "Thêm, sửa, xóa đề tài và chỉnh nhãn bằng tay. Xóa chỉ là đóng (không mất dữ liệu, bấm Khôi phục để mở lại). Đề tài bạn sửa hoặc thêm sẽ không bị lần crawl sau ghi đè hay đóng."),
      h("div", { style: "display:flex;gap:10px;flex-wrap:wrap" }, qi,
        sel("status", [["", "Mọi trạng thái"], ["active", "Đang hiệu lực"], ["closed", "Đã đóng"]], "Lọc trạng thái"),
        sel("source", [["", "Mọi nguồn"], ...meta.sources.map((s) => [s, s])], "Lọc nguồn"),
        sel("origin", [["", "Mọi xuất xứ"], ...Object.entries(ORIGIN)], "Lọc xuất xứ"),
        sel("sort", SORTS, "Sắp xếp"),
        h("button", { type: "button", class: "btn btn-primary", onclick: () => open({}) }, "Thêm đề tài")));
  }

  // ---- dựng lại dữ liệu website
  function paintPending(n) {
    clear(pend);
    if (flash) { pend.append(notice(flash)); flash = ""; }
    if (building) return;
    if (n > 0) pend.append(h("div", { class: "card", style: "display:flex;gap:12px;align-items:center;flex-wrap:wrap" },
      h("div", null, h("strong", null, n + " thay đổi chưa vào website. "), "Bấm để gắn nhãn lại và nạp dữ liệu mới (khoảng vài chục giây)."),
      h("button", { type: "button", class: "btn btn-primary", onclick: build }, "Dựng lại và nạp")));
  }
  async function build() {
    building = true;
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const status = h("div", { class: "card", role: "status" }, "Đang dựng dữ liệu khóa luận…");
    clear(pend).append(status);
    try {
      await A.post("/run", { task: "build_thesis" });
      for (;;) {
        await wait(2500);
        if (A.signal && A.signal.aborted) return;
        const s = await A.get("/run/status?tail=5");
        if (!s.running) {
          if (s.code !== 0) { say("Dựng dữ liệu lỗi (mã " + s.code + "). Xem tab \"Chạy lệnh & log\"."); break; }
          const r = await A.post("/reload", {});
          say("Đã dựng và nạp xong, website đang dùng dữ liệu mới (" + (r.jobs != null ? r.jobs + " tin tuyển dụng, " : "") + "khóa luận đã cập nhật).");
          break;
        }
      }
    } catch (e) {
      if (e && e.name === "AbortError") return;
      say(fail(e));
    }
    building = false;
    load();
  }

  // ---- thêm / sửa
  function open(row) { editor = row; paintEditor(); edit.scrollIntoView({ block: "nearest" }); }
  function paintEditor() {
    clear(edit);
    if (editor == null) return;
    const isNew = !editor.thesis_id;
    const inp = (id, label, val, ph, type = "text") => [h("label", { for: id }, label), h("input", { class: "input", style: "flex:none", id, type, value: val == null ? "" : val, placeholder: ph || "", autocomplete: "off" })];
    const [lt, title] = inp("th-title", "Tiêu đề khóa luận", editor.title, "Tên đề tài đầy đủ");
    const [ly, year] = inp("th-year", "Năm", editor.year, "Ví dụ 2025", "number");
    const [ls, src] = inp("th-src", "Nguồn (trường)", editor.source || "neu", "neu");
    const [lr, rep] = inp("th-rep", "Link báo cáo (PDF)", editor.report_url, "https://…");
    const [lc, code] = inp("th-code", "Link mã nguồn", editor.source_code_url, "https://…");
    const [la, adv] = inp("th-adv", "Giảng viên hướng dẫn (nhiều người cách nhau bằng dấu ;)", (editor.advisors || []).join("; "), "Ví dụ: Nguyễn Văn A; Trần Thị B");
    const err = h("div", { class: "notice", role: "alert", hidden: true });
    const save = h("button", { type: "submit", class: "btn btn-primary" }, isNew ? "Thêm" : "Lưu thông tin");
    const field = (a, b) => h("div", { class: "field" }, a, b);
    const form = h("form", { class: "card", onsubmit: (ev) => {
      ev.preventDefault(); err.hidden = true; save.disabled = true;
      const body = { title: title.value, year: isNew ? (year.value ? Number(year.value) : null) : year.value, source: src.value, report_url: rep.value, source_code_url: code.value, advisors: adv.value };
      const p = isNew ? A.post("/thesis/add", body) : A.post("/thesis/update", { thesis_id: editor.thesis_id, ...body });
      p.then((r) => { say(isNew ? "Đã thêm khóa luận (mã " + r.thesis_id + ")." : (r.changed ? "Đã lưu thay đổi." : "Không có gì thay đổi.")); editor = null; paintEditor(); load(); })
        .catch((e) => { err.hidden = false; err.textContent = fail(e); save.disabled = false; });
    } },
      h("h2", null, isNew ? "Thêm khóa luận" : "Sửa khóa luận " + editor.thesis_id),
      field(lt, title), h("div", { style: "display:flex;gap:12px;flex-wrap:wrap" }, field(ly, year), field(ls, src)), field(lr, rep), field(lc, code), field(la, adv), err,
      h("div", { style: "display:flex;gap:10px" }, save, h("button", { type: "button", class: "btn", onclick: () => { editor = null; paintEditor(); } }, "Đóng")),
      isNew ? h("div", { class: "muted small" }, "Sau khi thêm, hệ thống tự gắn nhãn ở lần \"Dựng lại và nạp\"; bạn có thể chỉnh nhãn tay ngay ở danh sách.") : null);
    edit.append(form);
    title.focus();
  }

  // ---- nhãn chỉnh tay
  function labelEditor(row) {
    const cur = row.labels || { topics: [], domains: [] };
    const checks = (name, opts, chosen) => h("div", { style: "display:flex;gap:6px 14px;flex-wrap:wrap" }, opts.map((o) =>
      h("label", { class: "small", style: "display:flex;gap:5px;align-items:center" }, h("input", { type: "checkbox", name, value: o, checked: chosen.includes(o) }), o)));
    const t = checks("lt", meta.topics, cur.topics), d = checks("ld", meta.domains, cur.domains);
    const note = h("input", { class: "input", style: "flex:none", placeholder: "Ghi chú (ví dụ: đã đọc mở đầu PDF)", "aria-label": "Ghi chú nhãn" });
    const err = h("div", { class: "notice", role: "alert", hidden: true });
    const pick = (root) => [...root.querySelectorAll("input:checked")].map((x) => x.value);
    const send = (topics, domains) => A.post("/thesis/labels", { thesis_id: row.thesis_id, topics, domains, note: note.value || null })
      .then(() => { say("Đã lưu nhãn cho khóa luận " + row.thesis_id + "."); editor = null; paintEditor(); load(); }).catch((e) => { err.hidden = false; err.textContent = fail(e); });
    clear(edit).append(h("section", { class: "card" }, h("h2", null, "Chỉnh nhãn: " + row.title),
      h("div", { class: "muted" }, "Nhãn bạn chọn thay nhãn do mô hình dự đoán và được dùng làm nhãn đã xác nhận khi huấn luyện lại. Tối đa 4 chủ đề kỹ thuật và 3 lĩnh vực."),
      h("h3", null, "Chủ đề kỹ thuật"), t, h("h3", null, "Lĩnh vực"), d, note, err,
      h("div", { style: "display:flex;gap:10px;flex-wrap:wrap" },
        h("button", { type: "button", class: "btn btn-primary", onclick: () => send(pick(t), pick(d)) }, "Lưu nhãn"),
        h("button", { type: "button", class: "btn", onclick: () => send([], []) }, "Bỏ nhãn tay (dùng nhãn mô hình)"),
        h("button", { type: "button", class: "btn", onclick: () => { clear(edit); } }, "Đóng"))));
    edit.scrollIntoView({ block: "nearest" });
  }

  function act(path, row, msg) {
    A.post(path, { thesis_id: row.thesis_id }).then(() => { say(msg); load(); }).catch((e) => { say(fail(e)); load(); });
  }

  function paintList(d) {
    clear(list);
    const rows = d.items;
    list.append(h("section", { class: "card" }, h("h2", null, d.total.toLocaleString("vi-VN") + " khóa luận"),
      rows.length ? h("table", { class: "adm-table" },
        h("thead", null, h("tr", null, ["Mã", "Tiêu đề", "Năm", "Nguồn", "Nhãn", "Trạng thái", ""].map((x) => h("th", null, x)))),
        h("tbody", null, rows.map((r) => {
          const lb = r.labels || { topics: [], domains: [] };
          const closed = r.status === "closed";
          return h("tr", { style: closed ? "opacity:.6" : null },
            h("td", null, String(r.thesis_id)),
            h("td", null, r.title, (r.advisors || []).length ? h("div", { class: "muted small" }, "GVHD: " + r.advisors.join("; ")) : null, r.report_url ? [" ", h("a", { class: "small", href: r.report_url, target: "_blank", rel: "noopener noreferrer" }, "PDF")] : null),
            h("td", null, r.year == null ? "–" : String(r.year)),
            h("td", { class: "small" }, r.source, h("div", { class: "muted" }, ORIGIN[r.origin] || r.origin)),
            h("td", { class: "small" }, lb.topics.length || lb.domains.length ? [...lb.topics.map((x) => chip(x)), ...lb.domains.map((x) => chip(x, "chip-soft"))] : h("span", { class: "muted" }, lb.built ? "chưa có nhãn" : "chờ dựng"),
              lb.label_source === "manual" ? h("div", { class: "muted" }, lb.built ? "nhãn tay" : "nhãn tay, chờ dựng") : (lb.built ? null : h("div", { class: "muted" }, "chưa gắn nhãn"))),
            h("td", { class: "small" }, closed ? "đã đóng" : "hiệu lực", r.locked ? h("div", { class: "muted" }, "đã khóa (không bị crawl ghi đè)") : null),
            h("td", { style: "white-space:nowrap" },
              h("button", { type: "button", class: "btn btn-sm", onclick: () => open(r) }, "Sửa"), " ",
              h("button", { type: "button", class: "btn btn-sm", onclick: () => labelEditor(r) }, "Nhãn"), " ",
              closed ? h("button", { type: "button", class: "btn btn-sm", onclick: () => act("/thesis/restore", r, "Đã khôi phục khóa luận " + r.thesis_id + ".") }, "Khôi phục")
                : h("button", { type: "button", class: "btn btn-sm", onclick: () => { if (window.confirm("Đóng khóa luận này? Dữ liệu không mất và có thể khôi phục.\n\n" + r.title)) act("/thesis/delete", r, "Đã đóng khóa luận " + r.thesis_id + "."); } }, "Xóa")));
        }))) : h("div", { class: "state" }, "Không có khóa luận nào khớp."),
      d.total > PAGE ? h("div", { style: "display:flex;gap:10px;align-items:center" },
        h("button", { type: "button", class: "btn btn-sm", disabled: offset === 0, onclick: () => { offset = Math.max(0, offset - PAGE); load(); } }, "Trước"),
        h("span", { class: "muted small" }, `${offset + 1}–${Math.min(offset + PAGE, d.total)} / ${d.total}`),
        h("button", { type: "button", class: "btn btn-sm", disabled: offset + PAGE >= d.total, onclick: () => { offset += PAGE; load(); } }, "Sau")) : null));
  }

  paintBar();
  load();
}
