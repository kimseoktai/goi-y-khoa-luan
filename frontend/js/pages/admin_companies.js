import { h, clear } from "../dom.js";
import { loading, notice } from "../ui.js";

const STATUS = { draft: "draft · nháp, đang dùng", approved: "approved · đã duyệt", review: "review · chờ duyệt, chưa dùng", rejected: "rejected · bỏ, chưa dùng" };
const PAGE = 25;

// Tab "Công ty → lĩnh vực": duyệt/sửa bảng company_domains.csv. Lĩnh vực của công ty được dùng thay cho từ khóa khi gán nhãn.
export function mount(box, A) {
  let status = "review", q = "", offset = 0, flash = "";
  const bar = h("div", { class: "card" });
  const list = h("div");
  box.append(bar, list);

  function load() {
    clear(list).append(loading());
    const p = new URLSearchParams({ status, q, limit: PAGE, offset });
    A.get("/companies?" + p).then(paint).catch((e) => A.fail(list, e, load));
  }
  function save(row, domainSel, statusSel) {
    const body = { company_key: row.company_key };
    if (domainSel.value !== (row.domain || "-")) body.domain = domainSel.value;
    if (statusSel.value !== row.status) body.status = statusSel.value;
    if (Object.keys(body).length === 1) { flash = "Không có gì thay đổi."; return load(); }
    A.post("/companies/decision", body).then(() => { flash = "Đã lưu \"" + row.company_example + "\". Dữ liệu website đổi sau khi dựng lại."; load(); }).catch((e) => { flash = String(e.detail || "Không lưu được."); load(); });
  }
  function paint(d) {
    clear(list);
    if (flash) { list.append(notice(flash)); flash = ""; }
    const opts = (cur) => ["-", ...d.domains, ...(cur && cur !== "-" && !d.domains.includes(cur) ? [cur] : [])];
    list.append(h("section", { class: "card" }, h("h2", null, `${d.total} công ty`),
      d.items.length ? h("table", { class: "adm-table" }, h("thead", null, h("tr", null, ["Công ty", "Tin", "Lĩnh vực", "Trạng thái", "Nguồn / ghi chú", ""].map((x) => h("th", null, x)))),
        h("tbody", null, d.items.map((r) => {
          const ds = h("select", { class: "select", "aria-label": "Lĩnh vực của " + r.company_example }, opts(r.domain).map((o) => h("option", { value: o, selected: o === (r.domain || "-") }, o === "-" ? "- (tùy vị trí)" : o)));
          const ss = h("select", { class: "select", "aria-label": "Trạng thái của " + r.company_example }, d.statuses.map((o) => h("option", { value: o, selected: o === r.status }, STATUS[o] || o)));
          return h("tr", null, h("td", null, r.company_example), h("td", null, String(r.n_jobs)), h("td", null, ds), h("td", null, ss),
            h("td", { class: "small muted" }, [r.source, r.note].filter(Boolean).join(" · ")), h("td", null, h("button", { type: "button", class: "btn btn-sm btn-primary", onclick: () => save(r, ds, ss) }, "Lưu")));
        }))) : h("div", { class: "state" }, "Không có công ty nào khớp."),
      d.total > PAGE ? h("div", { style: "display:flex;gap:10px;align-items:center" },
        h("button", { type: "button", class: "btn btn-sm", disabled: offset === 0, onclick: () => { offset = Math.max(0, offset - PAGE); load(); } }, "Trước"),
        h("span", { class: "muted small" }, `${offset + 1}–${Math.min(offset + PAGE, d.total)} / ${d.total}`),
        h("button", { type: "button", class: "btn btn-sm", disabled: offset + PAGE >= d.total, onclick: () => { offset += PAGE; load(); } }, "Sau")) : null),
      addForm(d));
  }
  function addForm(d) {
    const name = h("input", { class: "input", id: "nc-name", placeholder: "Tên công ty (như trên tin tuyển dụng)", autocomplete: "off" });
    const dom = h("select", { class: "select", id: "nc-dom", "aria-label": "Lĩnh vực" }, d.domains.map((o) => h("option", { value: o }, o)));
    return h("form", { class: "card", onsubmit: (ev) => { ev.preventDefault(); if (!name.value.trim()) return;
      A.post("/companies/add", { company: name.value.trim(), domain: dom.value }).then(() => { flash = "Đã thêm công ty."; status = ""; q = name.value.trim(); offset = 0; filters(); load(); }).catch((e) => { flash = String(e.detail || "Không thêm được."); load(); }); } },
      h("h2", null, "Thêm công ty"), h("div", { class: "muted" }, "Công ty thêm ở đây có trạng thái approved và có hiệu lực ngay ở lần dựng dữ liệu tiếp theo."),
      h("div", { style: "display:flex;gap:10px;flex-wrap:wrap" }, name, dom, h("button", { type: "submit", class: "btn btn-primary" }, "Thêm")));
  }
  function filters() {
    const ss = h("select", { class: "select", "aria-label": "Lọc theo trạng thái", onchange: (ev) => { status = ev.target.value; offset = 0; load(); } },
      [["", "Tất cả trạng thái"], ...Object.entries(STATUS)].map(([v, l]) => h("option", { value: v, selected: v === status }, l)));
    const qi = h("input", { class: "input", type: "search", placeholder: "Tìm theo tên công ty", value: q, "aria-label": "Tìm công ty", onkeydown: (ev) => { if (ev.key === "Enter") { q = ev.target.value.trim(); offset = 0; load(); } } });
    clear(bar).append(h("h2", null, "Duyệt bảng công ty → lĩnh vực"),
      h("div", { class: "muted" }, "Lĩnh vực của công ty được dùng thay cho từ khóa mô tả khi gán nhãn tin. Chỉ dòng draft và approved có hiệu lực; \"-\" nghĩa là không ép, vẫn dùng từ khóa."),
      h("div", { style: "display:flex;gap:10px;flex-wrap:wrap" }, ss, qi));
  }
  filters();
  load();
}
