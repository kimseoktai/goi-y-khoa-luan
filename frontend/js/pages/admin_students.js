import { h, clear } from "../dom.js";
import { loading, notice } from "../ui.js";
import { session } from "../session.js";

const PAGE = 25;
const when = (t) => (t ? new Date(t * 1000).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "chưa đăng nhập");

// Tab "Sinh viên": nhập hàng loạt mã sinh viên (và mã admin) vào CSDL, xem danh sách, xóa. Mỗi mã có hồ sơ riêng (kỹ năng, đề tài đã lưu).
export function mount(box, A) {
  let q = "", role = "", offset = 0, flash = null;
  const importBox = h("div", { id: "st-bulk" }), listBox = h("div", { style: "display:flex;flex-direction:column;gap:14px" });
  box.append(importBox, listBox);

  function importForm() {
    const ta = h("textarea", { class: "input adm-ta", id: "st-ta", rows: "4", spellcheck: "false", placeholder: "11200001-11200050\n11205555, Nguyễn Văn An\n99999999, Cô Lan, admin" });
    const roleSel = h("select", { class: "select", "aria-label": "Vai trò mặc định" }, h("option", { value: "student" }, "Sinh viên"), h("option", { value: "admin" }, "Quản trị viên (admin)"));
    const file = h("input", { type: "file", accept: ".txt,.csv,text/plain,text/csv", hidden: true, onchange: (ev) => { const f = ev.target.files[0]; if (f) f.text().then((t) => { ta.value = t; }); ev.target.value = ""; } });
    const go = h("button", { type: "submit", class: "btn btn-primary" }, "Nhập vào CSDL");
    clear(importBox).append(h("details", { class: "ad-fold", open: !!flash && !flash.single },
      h("summary", null, h("span", null, "Nhập hàng loạt"), h("small", null, "dán danh sách, nhập cả dãy mã hoặc chọn tệp")),
      h("form", { class: "ad-import", onsubmit: (ev) => {
        ev.preventDefault();
        if (!ta.value.trim()) { flash = { err: "Hãy nhập ít nhất một mã." }; return paintFlash(); }
        go.disabled = true;
        A.post("/students/import", { text: ta.value, role: roleSel.value }).then((r) => { flash = { ok: r }; ta.value = ""; offset = 0; load(); })
          .catch((e) => { go.disabled = false; flash = { err: String(e.detail || "Không nhập được.") }; paintFlash(); });
      } },
        h("p", { class: "ad-hint" }, "Mỗi dòng một mã: ", h("code", null, "mã"), " · ", h("code", null, "mã, tên"), " · ", h("code", null, "mã, tên, admin"), " · hoặc dãy ", h("code", null, "11200001-11200050"), " (tối đa 5000 mã). Mã 8 số bắt đầu bằng 11 tự vào được ở lần đăng nhập đầu; mục này dùng để gán sẵn tên hoặc tạo admin. Nhập lại mã đã có chỉ cập nhật tên và vai trò, không mất hồ sơ."),
        ta,
        h("div", { class: "ad-row" }, roleSel, go, h("button", { type: "button", class: "btn", onclick: () => file.click() }, "Chọn tệp .txt / .csv"), file),
        h("div", { id: "st-flash" }))));
  }

  // Hộp thoại thêm / sửa một sinh viên (mã, tên, quyền)
  function editor(row) {
    const edit = !!row;
    const idIn = h("input", { class: "input", id: "se-id", value: edit ? row.student_id : "", disabled: edit, maxlength: "24", autocomplete: "off", spellcheck: "false", placeholder: "Ví dụ: 11236197" });
    const nameIn = h("input", { class: "input", id: "se-name", value: edit ? row.name || "" : "", maxlength: "80", autocomplete: "off", placeholder: "Không bắt buộc" });
    const roleSel = h("select", { class: "select", id: "se-role" }, h("option", { value: "student", selected: !edit || row.role !== "admin" }, "Sinh viên"), h("option", { value: "admin", selected: edit && row.role === "admin" }, "Quản trị viên (admin)"));
    const err = h("p", { class: "lg-msg", role: "alert" });
    const save = h("button", { type: "submit", class: "btn btn-primary" }, edit ? "Lưu thay đổi" : "Thêm sinh viên");
    const dlg = h("dialog", { class: "ad-dlg" }, h("form", { method: "dialog", onsubmit: (ev) => {
      ev.preventDefault();
      if (!idIn.value.trim()) { err.textContent = "Hãy nhập mã sinh viên."; err.classList.add("on"); idIn.focus(); return; }
      save.disabled = true; err.classList.remove("on");
      A.post("/students/save", { student_id: idIn.value.trim(), name: nameIn.value.trim(), role: roleSel.value, create: !edit })
        .then((r) => { dlg.close(); const me = session.student(); flash = { single: edit ? "Đã lưu thay đổi cho " + r.student_id + "." : "Đã thêm sinh viên " + r.student_id + "." };
          if (edit && me && me.student_id === r.student_id && r.role !== me.role) { window.alert("Bạn vừa đổi quyền của chính mình, hãy đăng nhập lại."); session.clear(); window.location.hash = "#/login"; return; }
          load(); })
        .catch((e) => { save.disabled = false; err.textContent = String(e.detail || "Không lưu được."); err.classList.add("on"); });
    } },
      h("h3", null, edit ? "Sửa sinh viên" : "Thêm sinh viên"),
      h("label", { class: "lg-lab", for: "se-id" }, "Mã sinh viên"), idIn,
      h("label", { class: "lg-lab", for: "se-name" }, "Họ tên"), nameIn,
      h("label", { class: "lg-lab", for: "se-role" }, "Quyền"), roleSel,
      h("p", { class: "ad-hint" }, "Quản trị viên vào được trang Quản trị và đăng nhập bằng chính mã của mình. Đổi quyền thì người đó phải đăng nhập lại."),
      err,
      h("div", { class: "ad-row", style: "justify-content:flex-end" }, h("button", { type: "button", class: "btn", onclick: () => dlg.close() }, "Hủy"), save)));
    dlg.addEventListener("close", () => dlg.remove());
    document.body.append(dlg);
    dlg.showModal();
    (edit ? nameIn : idIn).focus();
  }

  function paintFlash() {
    const el = document.getElementById("st-flash");
    if (!el || !flash || flash.single) return;
    clear(el);
    if (flash.err) el.append(h("div", { class: "state state-error", role: "alert" }, flash.err));
    else {
      const r = flash.ok;
      el.append(notice(`Đã thêm ${r.added} mã, cập nhật ${r.updated}, giữ nguyên ${r.unchanged}.` + (r.invalid.length ? ` Bỏ qua ${r.invalid.length} dòng lỗi.` : "")));
      if (r.invalid.length) el.append(h("ul", { class: "small", style: "color:#b4402a;margin:8px 0 0 18px" }, r.invalid.map((x) => h("li", null, x))));
    }
  }

  function load() {
    clear(listBox).append(loading());
    const p = new URLSearchParams({ q, role, limit: PAGE, offset });
    A.get("/students?" + p).then(paint).catch((e) => A.fail(listBox, e, load));
    importForm(); paintFlash();
  }

  function paint(d) {
    const qi = h("input", { class: "input", type: "search", placeholder: "Tìm theo mã hoặc tên", value: q, "aria-label": "Tìm sinh viên", onkeydown: (ev) => { if (ev.key === "Enter") { q = ev.target.value.trim(); offset = 0; load(); } } });
    const rs = h("select", { class: "select", "aria-label": "Lọc theo vai trò", onchange: (ev) => { role = ev.target.value; offset = 0; load(); } },
      [["", "Tất cả vai trò"], ["student", "Sinh viên"], ["admin", "Quản trị viên"]].map(([v, l]) => h("option", { value: v, selected: v === role }, l)));
    const by = d.by_role || {};
    const stat = (l, v) => h("div", { class: "ad-stat" }, h("b", null, String(v)), h("span", null, l));
    clear(listBox).append(flash && flash.single ? notice(flash.single) : null, h("section", { class: "card ad-card" },
      h("div", { class: "ad-stats" }, stat("Tổng số mã", (by.student || 0) + (by.admin || 0)), stat("Sinh viên", by.student || 0), stat("Quản trị viên", by.admin || 0)),
      h("div", { class: "ad-tool" }, qi, rs, h("span", { class: "muted small" }, `${d.total} mã khớp`),
        h("button", { type: "button", class: "btn btn-primary", onclick: () => editor(null) }, "＋ Thêm sinh viên"),
        h("button", { type: "button", class: "btn", onclick: () => { const dt = importBox.querySelector("details"); if (dt) { dt.open = true; dt.scrollIntoView({ behavior: "smooth", block: "center" }); } } }, "Nhập hàng loạt")),
      d.items.length ? h("div", { class: "ad-tw" }, h("table", { class: "adm-table" }, h("thead", null, h("tr", null, ["Mã", "Tên", "Vai trò", "Đăng nhập gần nhất", "Kỹ năng", "Đã lưu", ""].map((x) => h("th", null, x)))),
        h("tbody", null, d.items.map((r) => h("tr", null, h("td", null, h("b", null, r.student_id)), h("td", null, r.name || "—"),
          h("td", null, r.role === "admin" ? h("span", { class: "chip ad-admin" }, "admin") : h("span", { class: "ad-st" }, "sinh viên")), h("td", { class: "small muted" }, when(r.last_login)), h("td", null, String(r.skills)), h("td", null, String(r.saved)),
          h("td", { class: "ad-act" }, h("button", { type: "button", class: "btn btn-sm", onclick: () => editor(r) }, "Sửa"), h("button", { type: "button", class: "btn btn-sm", onclick: () => {
            if (!window.confirm("Xóa mã " + r.student_id + "? Hồ sơ đã lưu của mã này cũng bị xóa.")) return;
            A.post("/students/delete", { student_id: r.student_id }).then(() => { flash = null; load(); }).catch((e) => A.fail(listBox, e, load));
          } }, "Xóa"))))))) : h("div", { class: "state" }, d.total === 0 && !q && !role ? "Chưa có mã nào. Sinh viên sẽ tự xuất hiện khi đăng nhập lần đầu." : "Không có mã nào khớp."),
      d.total > PAGE ? h("div", { style: "display:flex;gap:10px;align-items:center" },
        h("button", { type: "button", class: "btn btn-sm", disabled: offset === 0, onclick: () => { offset = Math.max(0, offset - PAGE); load(); } }, "Trước"),
        h("span", { class: "muted small" }, `${offset + 1}–${Math.min(offset + PAGE, d.total)} / ${d.total}`),
        h("button", { type: "button", class: "btn btn-sm", disabled: offset + PAGE >= d.total, onclick: () => { offset += PAGE; load(); } }, "Sau")) : null));
  }
  load();
}
