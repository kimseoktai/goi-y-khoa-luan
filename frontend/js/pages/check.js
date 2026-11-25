// Kiểm tra đề tài: nhập tên đề tài dự kiến, so với kho khóa luận, cho biết Mới / Khá giống / Trùng và các khóa luận gần nhất.
import { h, clear } from "../dom.js";
import { api } from "../api.js";
import { icon } from "../icons.js";
import { NOVELTY, yearSchool } from "../labels.js";
import { errorBox, foot, loading, notice, pctText } from "../ui.js";

const MAX = 300;
const EXAMPLES = ["Xây dựng chatbot hỗ trợ tư vấn tuyển sinh bằng RAG", "Dự báo giá cổ phiếu bằng mô hình LSTM", "Hệ thống phát hiện gian lận giao dịch ngân hàng"];

export function render(root, params, ctx) {
  const box = h("textarea", { rows: 3, maxlength: MAX, placeholder: "Gõ tên đề tài bạn đang nghĩ tới, ví dụ: Xây dựng chatbot hỗ trợ tư vấn tuyển sinh bằng RAG", "aria-label": "Tên đề tài cần kiểm tra" });
  box.value = params.q || "";
  const count = h("span", { class: "ck-count" }, "0/" + MAX);
  const submit = h("button", { type: "submit", class: "ck-go" }, "Kiểm tra");
  const result = h("div", { class: "ck-result", "aria-live": "polite" });
  const sync = () => { count.textContent = box.value.length + "/" + MAX; submit.disabled = !box.value.trim(); };
  box.addEventListener("input", sync);

  async function run() {
    const title = box.value.trim();
    if (!title) return;
    submit.disabled = true;
    clear(result).append(loading("Đang so với kho khóa luận…"));
    try {
      const d = await api.noveltyCheck({ title, top_k: 5 }, { signal: ctx.signal });
      if (ctx.signal.aborted) return;
      clear(result).append(...view(title, d));
    } catch (e) {
      if (e && e.name === "AbortError") return;
      clear(result).append(errorBox(e, run));
    } finally { sync(); }
  }

  root.append(h("div", { class: "ck" },
    h("section", { class: "lb-hero ck-hero" }, h("i", { class: "lb-blob b1" }), h("i", { class: "lb-blob b2" }),
      h("span", { class: "lb-eyebrow" }, h("i"), h("span", null, "Kiểm tra đề tài")),
      h("h1", { class: "lb-title" }, "Đề tài của bạn ", h("em", null, "đã có ai làm"), " chưa?"),
      h("p", { class: "lb-sub" }, "Nhập tên đề tài dự kiến, hệ thống so với kho khóa luận và chỉ ra những khóa luận gần nhất để bạn tham khảo."),
      h("form", { class: "ck-form", onsubmit: (ev) => { ev.preventDefault(); run(); } },
        h("div", { class: "ck-in" }, icon("search", 22), box), h("div", { class: "ck-bar" }, count, submit)),
      h("div", { class: "lb-try" }, h("span", null, "Thử:"), EXAMPLES.map((t) => h("button", { type: "button", onclick: () => { box.value = t; sync(); run(); } }, t)))),
    result,
    foot("So sánh về nghĩa của tên đề tài với các khóa luận đã thu thập, không phải toàn bộ khóa luận của mọi trường. Kết quả chỉ để tham khảo.")));
  sync();
  if (box.value.trim()) run();
}

function view(title, d) {
  const st = NOVELTY[d.novelty_status] || NOVELTY.Novel;
  const th = d.thresholds || {};
  const tone = d.novelty_status === "Duplicate" ? "bad" : d.novelty_status === "Similar" ? "mid" : "good";
  const out = [h("section", { class: "sk-card ck-verdict " + tone },
    h("div", { class: "ck-vt" }, h("span", { class: "ck-badge", style: `background:${st.bg};color:${st.fg}` }, st.text), h("div", null, h("small", null, "Đề tài đang kiểm tra"), h("b", null, title))),
    h("p", { class: "ck-msg" }, st.msg),
    h("div", { class: "ck-meter" }, h("div", { class: "ck-ml" }, h("span", null, "Độ giống khóa luận gần nhất"), h("b", null, pctText(d.max_similarity))),
      h("div", { class: "tr" }, h("i", { style: `width:${Math.min(100, d.max_similarity * 100).toFixed(0)}%` }),
        th.similar != null ? h("u", { class: "mk", style: `left:${(th.similar * 100).toFixed(1)}%`, title: "Từ mốc này là Khá giống" }) : null,
        th.duplicate != null ? h("u", { class: "mk dup", style: `left:${(th.duplicate * 100).toFixed(1)}%`, title: "Từ mốc này là Trùng" }) : null),
      h("small", null, "Vạch ngắn: bắt đầu Khá giống" + (th.similar != null ? " (" + pctText(th.similar) + ")" : "") + (th.duplicate != null ? ". Vạch đậm: bắt đầu Trùng (" + pctText(th.duplicate) + ")." : ".")))),
    h("section", { class: "sk-card" }, h("h2", null, "Khóa luận gần nhất"),
      h("p", { class: "sk-sub" }, "Xếp theo độ giống về nghĩa với tên đề tài của bạn. Đọc để xem phần nào của bạn có thể khác biệt."),
      h("ol", { class: "ck-list" }, (d.top_neighbors || []).map((t, i) => h("li", null, h("span", { class: "no" }, String(i + 1)),
        h("div", { class: "mid" }, h("b", null, t.title), t.year || t.source ? h("small", null, yearSchool(t)) : null),
        h("div", { class: "pc" }, h("b", null, pctText(t.similarity)), h("div", { class: "tr" }, h("i", { style: `width:${Math.min(100, t.similarity * 100).toFixed(0)}%` })))))),
      h("div", { class: "row" }, h("a", { class: "btn btn-sm", href: "#/library?q=" + encodeURIComponent(title) }, "Tìm thêm trong Kho khóa luận ›")))];
  if (d.note) out.push(notice(d.note));
  return out;
}
