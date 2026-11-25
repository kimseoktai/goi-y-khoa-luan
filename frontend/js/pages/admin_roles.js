import { h, clear } from "../dom.js";
import { notice, loading } from "../ui.js";

// Tab "Nhóm công việc": duyệt nhóm công việc nhỏ đã gộp (logic cũ của trang quản trị).
export function mount(box, A) {
  let flash = "";
  function refresh() {
    clear(box).append(loading());
    A.get("/roles").then((d) => paint(d)).catch((e) => A.fail(box, e, refresh));
  }
  function decide(role, action, parent) {
    A.post("/roles/decision", { role, action, parent }).then(() => { flash = "Đã lưu quyết định cho \"" + role + "\"."; refresh(); }).catch((e) => A.fail(box, e, refresh));
  }
  function parentSelect(d, role, cur) {
    const sel = h("select", { class: "select", "aria-label": "Nhóm cha của " + role });
    [...d.parent_choices.filter((p) => p !== role), "Nhóm khác"].forEach((p) => sel.append(h("option", { value: p, selected: p === cur }, p)));
    return sel;
  }
  const cnt = (r) => r.job_count + " tin · " + r.n_companies + " công ty";
  function paint(d) {
    const th = d.thresholds;
    clear(box);
    if (flash) { box.append(notice(flash)); flash = ""; }
    box.append(h("section", { class: "card" }, h("h2", null, `Chờ duyệt (${d.pending.length})`),
      h("div", { class: "muted" }, `Nhóm công việc có ít tin được gộp vào nhóm khác. Ngưỡng tách riêng: từ ${th.min_support} tin và ${th.min_companies} công ty.`),
      d.pending.length ? h("table", { class: "adm-table" }, h("thead", null, h("tr", null, ["Nhóm", "Số tin", "Đang gộp vào", "Quyết định"].map((x) => h("th", null, x)))),
        h("tbody", null, d.pending.map((r) => h("tr", null, h("td", null, r.role), h("td", null, cnt(r)), h("td", null, r.parent_role),
          h("td", { style: "display:flex;gap:8px;flex-wrap:wrap" },
            h("button", { type: "button", class: "btn btn-primary btn-sm", onclick: () => decide(r.role, "approve_split") }, "Duyệt, tách riêng"),
            h("button", { type: "button", class: "btn btn-sm", title: "Giữ gộp; hỏi lại khi số tin tăng thêm 50%", onclick: () => decide(r.role, "keep_merged") }, "Từ chối, giữ gộp")))))) : h("div", { class: "state" }, "Chưa có nhóm nào đủ ngưỡng.")));
    if (d.unassigned.length) box.append(h("section", { class: "card" }, h("h2", null, `Chưa có nhóm cha (${d.unassigned.length})`), h("div", { class: "muted" }, "Đang nằm trong \"Nhóm khác\". Chọn nhóm cha cho từng nhóm."),
      h("table", { class: "adm-table" }, h("tbody", null, d.unassigned.map((r) => { const sel = parentSelect(d, r.role, "Nhóm khác"); return h("tr", null, h("td", null, r.role), h("td", null, r.job_count + " tin"), h("td", null, sel), h("td", null, h("button", { type: "button", class: "btn btn-sm", onclick: () => decide(r.role, "merge", sel.value) }, "Gộp"))); })))));
    box.append(h("section", { class: "card" }, h("h2", null, `Đang gộp (${d.merged.length})`),
      d.merged.length ? h("table", { class: "adm-table" }, h("thead", null, h("tr", null, ["Nhóm", "Số tin", "Nhóm cha", "Lý do", ""].map((x) => h("th", null, x)))),
        h("tbody", null, d.merged.map((r) => { const sel = parentSelect(d, r.role, r.parent_role); return h("tr", null, h("td", null, r.role), h("td", null, cnt(r)), h("td", null, sel), h("td", null, r.reason),
          h("td", null, h("button", { type: "button", class: "btn btn-sm", onclick: () => decide(r.role, "merge", sel.value) }, "Lưu nhóm cha"))); }))) : h("div", { class: "state" }, "Không có nhóm nào đang gộp.")));
  }
  refresh();
}
