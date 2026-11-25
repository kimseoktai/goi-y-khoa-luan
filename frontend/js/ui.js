import { h, clear } from "./dom.js";
import { describeError } from "./api.js";

export const chip = (text, cls) => h("span", { class: "chip" + (cls ? " " + cls : "") }, text);

export function pageHead(title, lead) {
  return h("header", { class: "page-head" }, h("h1", null, title), lead ? h("p", { class: "lead" }, lead) : null);
}

export function loading(text = "Đang tải…") {
  return h("div", { class: "state", role: "status" }, text);
}

export function errorBox(e, retry) {
  const d = describeError(e);
  return h("div", { class: "state state-error", role: "alert" },
    h("strong", null, d.title), h("p", null, d.text), d.hint ? h("p", { class: "muted" }, d.hint) : null,
    retry ? h("button", { class: "btn", type: "button", onclick: retry }, "Thử lại") : null);
}

export function notice(text) { return h("div", { class: "notice", role: "note" }, text); }

// Ghi chú nhỏ cuối trang: nói rõ số liệu lấy từ đâu và giới hạn.
export function foot(text) { return h("p", { class: "foot" }, text); }

// Chạy loader rồi dựng nội dung vào `box`; có nút thử lại; bỏ qua kết quả của lần chạy đã bị huỷ.
export async function load(box, ctx, loader, build) {
  clear(box).append(loading());
  try {
    const data = await loader();
    if (ctx.signal.aborted) return;
    clear(box);
    build(data);
  } catch (e) {
    if (e && e.name === "AbortError") return;
    if (ctx.signal.aborted) return;
    clear(box).append(errorBox(e, () => load(box, ctx, loader, build)));
  }
}

// Mở link ngoài an toàn: chỉ http(s), mở tab mới, không lộ trang gốc.
export function extLink(url, text, cls) {
  if (!/^https?:\/\//i.test(String(url || ""))) return null;
  return h("a", { class: cls || "btn", href: url, target: "_blank", rel: "noopener noreferrer" }, text);
}

export const pctText = (x) => Math.round((x || 0) * 100) + "%";

// Tên trường từ mã nguồn trong dữ liệu luận văn.
export const SCHOOLS = {
  uit: "ĐH Công nghệ Thông tin (UIT)", neu: "ĐH Kinh tế Quốc dân (NEU)", ptit: "Học viện Công nghệ Bưu chính Viễn thông (PTIT)", duytan: "ĐH Duy Tân",
  uet_chuan: "ĐH Công nghệ - ĐHQGHN (UET), chương trình chuẩn", uet_clc: "ĐH Công nghệ - ĐHQGHN (UET), chất lượng cao",
};
export const schoolName = (code) => (code ? SCHOOLS[String(code).toLowerCase()] || String(code).toUpperCase() : "");
export const yearSchool = (t) => [t.year, schoolName(t.source)].filter(Boolean).join(" · ");

export function limits(items) {
  return h("section", { class: "limits", "aria-label": "Cần lưu ý" }, h("h2", null, "Cần lưu ý"), h("ul", null, items.map((t) => h("li", null, t))));
}
