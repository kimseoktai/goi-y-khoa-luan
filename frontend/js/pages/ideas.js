// Đề xuất khóa luận: hướng đề tài theo các công việc đã chọn. Hướng/công nghệ/đề tài đã có đến ngay từ dữ liệu;
// tên đề tài và tóm tắt do mô hình ngôn ngữ viết sau, từng thẻ một, nên thẻ hiện trước và phần chữ điền dần.
import { h, clear } from "../dom.js";
import { api } from "../api.js";
import { store, titleCache } from "../store.js";
import { icon } from "../icons.js";
import { openPicker } from "../picker.js";
import { openRefs } from "../refs.js";
import { errorBox, foot, loading, notice, pctText, yearSchool } from "../ui.js";
import { describeError } from "../api.js";

const PAGE = 3;
const firstPage = new Map();                         // lần sau vào lại thì hiện ngay trang đầu, không chờ máy chủ

const placeholder = (i) => h("article", { class: "id-card hold", "aria-hidden": "true" }, h("div", { class: "id-top" }, h("span", { class: "id-no" }, String(i + 1)), h("span", { class: "skel pill" }), h("span", { class: "skel pill" })),
  h("div", { class: "id-title" }, h("span", { class: "skel" }), h("span", { class: "skel skel-s" })), h("div", { class: "id-sumbox" }, h("span", { class: "skel" }), h("span", { class: "skel" }), h("span", { class: "skel skel-s" })));
const sideHolder = () => [h("h2", null, "Kỹ năng bạn nên có"), h("p", { class: "id-sub" }, "Đang tính từ các tin tuyển dụng…"), ...[0, 1, 2, 3, 4, 5].map(() => h("div", { class: "id-sk hold" }, h("span", { class: "st" }), h("span", { class: "skel" }), h("b", null), h("div", { class: "t" })))];

function fitText(it) {
  if (it.fit === 0) return "Ít gặp trong các việc bạn chọn";
  if (it.fit === it.fit_total) return it.fit_total === 1 ? "Hợp với việc bạn chọn" : "Hợp với cả " + it.fit_total + " việc bạn chọn";
  return "Hợp " + it.fit + "/" + it.fit_total + " việc bạn chọn";
}

function statusTag(nov, checked) {
  if (!checked || !nov) return h("span", { class: "id-tag wait" }, "Chưa kiểm tra trùng");
  if ((typeof nov === "string" ? nov : nov.status) === "Novel") return h("span", { class: "id-tag ok" }, "Chưa ai làm");
  return h("span", { class: "id-tag warn" }, "Có bạn làm hướng gần giống");
}

export function render(root, params, ctx) {
  const ctl = new AbortController();
  ctx.signal.addEventListener("abort", () => ctl.abort());
  const signal = ctl.signal;
  const single = params.role || "";
  const roles = single ? [single] : store.get().roles.slice();
  const rerender = () => { ctl.abort(); clear(root); render(root, params, ctx); };

  if (!roles.length) {
    root.append(h("section", { class: "card empty" }, h("h1", null, "Đề tài gợi ý cho bạn"), h("p", { class: "lead" }, "Bạn chưa chọn công việc nào. Chọn 1 đến 3 công việc bạn mê để nhận gợi ý."),
      h("button", { type: "button", class: "btn btn-primary btn-lg", onclick: () => openPicker({ onDone: rerender }) }, "Chọn công việc bạn mê")));
    openPicker({ onDone: rerender });
    return;
  }

  const head = h("section", { class: "id-hero" });
  const paintHeadHolder = () => head.replaceChildren(h("div", null, h("h1", null, "Đề tài gợi ý cho bạn"), h("p", null, "Đang tìm hướng đề tài hợp với lựa chọn của bạn…"), h("div", { class: "id-lab" }, "Bạn đã chọn"),
    h("div", { class: "id-rc" }, roles.map(() => h("span", { class: "skel" })))),
    h("button", { type: "button", class: "id-ghost", onclick: () => openPicker({ onDone: () => { if (single) window.location.hash = "#/ideas"; else rerender(); } }) }, "Đổi công việc"));
  paintHeadHolder();
  const aside = h("aside", { class: "id-side" }, ...sideHolder());
  const list = h("div", { class: "id-list" }, ...[0, 1, 2].map(placeholder));
  const more = h("div", { class: "id-more" });
  root.append(h("div", { class: "id" }, head, h("div", { class: "id-grid" }, aside, h("div", { class: "id-col" }, list, more)),
    foot("Tên đề tài và phần tóm tắt do trí tuệ nhân tạo viết, bạn nên chỉnh lại cho hợp với mình và trao đổi với giảng viên hướng dẫn.")));

  let offset = 0, total = 0, n = 0, queue = Promise.resolve();
  const shown = [];                                   // tên đã hiện, để mô hình viết tên khác

  function paintHead(d) {
    clear(head).append(h("div", null,
      h("h1", null, "Đề tài gợi ý cho bạn"),
      h("p", null, single ? "Đang xem riêng cho công việc này. " : "Dựa trên " + d.n_jobs + " tin tuyển dụng của " + (d.roles.length === 1 ? "công việc" : d.roles.length + " công việc") + " bạn chọn. Mình nhớ lựa chọn của bạn trên trình duyệt này.",
        single ? h("a", { href: "#/ideas" }, "Quay lại lựa chọn của tôi") : null),
      h("div", { class: "id-lab" }, "Bạn đã chọn"),
      h("div", { class: "id-rc" }, d.roles.map((r) => h("span", null, r.label)))),
      h("button", { type: "button", class: "id-ghost", onclick: () => openPicker({ onDone: () => { if (single) window.location.hash = "#/ideas"; else rerender(); } }) }, "Đổi công việc"));
  }

  const TIERS = [["t1", 3, "Cốt lõi", "gần như tin nào cũng cần", 2], ["t2", 2, "Quan trọng", "nhiều tin nhắc đến", 3], ["t3", 1, "Nên biết", "cộng điểm khi xin việc", 99]];
  function paintAside(d) {
    const mine = new Set(store.get().skills), sk = d.top_skills, max = Math.max(0.0001, ...sk.map((s) => s.share));
    const have = sk.filter((s) => mine.has(s.name)).length, miss = sk.filter((s) => !mine.has(s.name)).map((s) => s.name);
    const rowOf = (s) => { const ok = mine.has(s.name); return h("div", { class: "id-sk " + (ok ? "have" : "miss") }, h("span", { class: "st" }, ok ? "✓" : ""), h("span", { class: "nm" }, s.name), h("b", null, pctText(s.share)),
      h("div", { class: "t" }, h("i", { style: `width:${(s.share / max * 100).toFixed(0)}%` }))); };
    const groups = []; let at = 0;
    for (const [cls, lv, name, hint, n] of TIERS) { const part = sk.slice(at, at + n); at += n; if (!part.length) continue;
      groups.push(h("div", { class: "id-tier " + cls }, h("span", { class: "lv" }, [0, 1, 2].map((i) => h("i", { class: i < lv ? "" : "off" }))), name, h("em", null, hint)), ...part.map(rowOf)); }
    clear(aside).append(h("h2", null, "Kỹ năng bạn nên có"),
      h("p", { class: "id-sub" }, "Tỷ lệ tin tuyển dụng nhắc đến kỹ năng đó trong " + (d.roles.length === 1 ? "công việc" : d.roles.length + " công việc") + " bạn chọn (" + d.n_jobs + " tin)."),
      h("div", { class: "id-score" }, h("div", { class: "ring", style: `--p:${sk.length ? Math.round(have / sk.length * 100) : 0}` }, h("b", null, String(have), h("small", null, "/" + sk.length))),
        h("div", null, h("strong", null, "Bạn đã có " + have + "/" + sk.length + " kỹ năng"), h("span", null, miss.length ? "Còn thiếu: " : "Bạn đã có đủ kỹ năng hàng đầu.", ...miss.slice(0, 3).flatMap((m, i) => [i ? ", " : "", h("u", null, m)])))),
      ...groups,
      h("div", { class: "id-legend" }, h("span", null, h("span", { class: "st on" }, "✓"), "Bạn đã có"), h("span", null, h("span", { class: "st" }), "Chưa có, nên học")));
  }

  function card(it, idx) {
    const t = { title: null, summary: "", novelty: null, checked: true };
    const titleEl = h("h3", { class: "id-title" }, h("span", { class: "skel" }), h("span", { class: "skel skel-s" }));
    const sumEl = h("p", { class: "id-sum" }, h("span", { class: "skel" }), h("span", { class: "skel" }), h("span", { class: "skel skel-s" }));
    const stat = h("span", { class: "id-tag wait" }, "Đang viết tên đề tài…");
    const msg = h("div", { class: "id-msg", hidden: true });
    const save = h("button", { type: "button", class: "id-save", disabled: true, onclick: onSave }, icon("heart", 16), h("span", null, "Lưu đề tài"));
    const id = () => "idea:" + it.topic + ":" + t.title.toLowerCase().slice(0, 90);
    function paintSave() {
      const on = t.title && store.isSaved(id());
      save.classList.toggle("on", !!on); save.setAttribute("aria-pressed", on ? "true" : "false");
      save.querySelector("svg").setAttribute("fill", on ? "currentColor" : "none");
      save.querySelector("span").textContent = on ? "Đã lưu" : "Lưu đề tài";
    }
    function onSave() {
      if (!t.title) return;
      store.toggleSaved({ id: id(), kind: "idea", title: t.title, summary: t.summary, tech: t.tech || it.technologies, skills: it.skills, topics: [it.topic_label], topic: it.topic, domains: it.domains.slice(0, 1),
        fit: it.fit, fit_total: it.fit_total, status: t.novelty ? (t.novelty.status || t.novelty) : null });
      paintSave();                                   // chỉ đổi nút tại chỗ, không chuyển trang
    }
    const showRefs = () => openRefs({ topic: it.topic, topicLabel: it.topic_label, domain: it.domains[0] || "", domainLabel: it.domain_labels[0] || "" });
    const techBox = h("div", { class: "id-chips tech" }, it.technologies.map((x) => h("span", null, x)));
    const domExtra = h("span", { hidden: true });                                    // lĩnh vực do tên đề tài gợi ý, khi hướng này chưa có lĩnh vực
    const refs = it.related_theses.length
      ? h("div", { class: "id-refs" }, it.related_theses.map((r) => h("button", { type: "button", class: "id-ref", onclick: showRefs }, h("span", null, r.title), h("small", null, yearSchool(r)))))
      : h("p", { class: "id-sub" }, "Chưa có luận văn nào tương tự trong kho hiện có.");
    const advBox = h("div", { class: "id-adv" });
    const advBtn = h("button", { type: "button", class: "id-btn dark", disabled: true, onclick: showAdvisors }, "Gợi ý giảng viên hướng dẫn (NEU)");
    async function showAdvisors() {
      advBtn.disabled = true;
      clear(advBox).append(h("p", { class: "muted small" }, "Đang tìm giảng viên phù hợp…"));
      try {
        const r = await api.advisorsFor({ topic: it.topic, domains: it.domains.slice(0, 1), text: (t.title || "") + ". " + (t.summary || ""), top_k: 5 }, { signal });
        const LV = { strong: ["Hợp nhất", "ok"], ok: ["Hợp", "fit"], weak: ["Có thể", "wait"] };
        const rows = r.items.map((a) => { const lv = LV[a.level]; return h("li", null,
          h("div", { class: "id-ad-h" }, h("b", null, a.advisor), lv ? h("span", { class: "id-tag " + lv[1] }, lv[0]) : null),
          h("div", { class: "id-ad-s" }, a.n_related ? a.n_related + " khóa luận cùng hướng" + (a.latest_related_year ? ", gần nhất " + a.latest_related_year : "") + " · tổng " + a.n_theses + " khóa luận" : "Tổng " + a.n_theses + " khóa luận" + (a.latest_year ? ", gần nhất " + a.latest_year : "")),
          h("div", { class: "muted small" }, "Đã hướng dẫn: " + a.nearest.map((x) => x.title).join(" · "))); });
        clear(advBox).append(h("b", null, "Giảng viên có thể phù hợp"),
          rows.length ? h("ol", { class: "id-adlist" }, rows) : h("p", { class: "muted small" }, "Chưa tìm thấy giảng viên nào có khóa luận gần đề tài này."),
          ...(r.low_data ? [h("p", { class: "id-ad-warn" }, "Hướng này có rất ít khóa luận trong dữ liệu nên kết quả chỉ mang tính tham khảo.")] : []),
          h("p", { class: "muted small" }, "Xếp theo số khóa luận cùng hướng đã hướng dẫn, rồi độ chuyên sâu, mức gần đây và độ gần nội dung đề tài. " + "Không phải phân công, và không cho biết thầy/cô còn nhận hướng dẫn hay không. Hãy liên hệ khoa để xác nhận." + (r.note ? " (" + r.note + ".)" : "")));
      } catch (e) {
        if (signal.aborted) return;
        clear(advBox).append(h("p", { class: "muted small" }, describeError(e).text));
      }
      advBtn.disabled = false;
    }
    const nRef = it.same_topic_theses || it.related_theses.length;
    const el = h("article", { class: "id-card" },
      h("div", { class: "id-top" }, h("span", { class: "id-no" }, String(idx + 1)), h("span", { class: "id-tag fit" }, fitText(it)), stat, save),
      titleEl,
      h("div", { class: "id-meta" }, h("span", null, "Hướng ", h("b", null, it.topic_label)), it.domain_labels.length ? h("span", null, "Lĩnh vực ", h("b", null, it.domain_labels.join(", "))) : null, domExtra, h("span", null, h("b", null, String(it.n_jobs)), " tin tuyển dụng")),
      h("div", { class: "id-sumbox" }, h("small", null, "Tóm tắt"), sumEl), msg,
      h("div", { class: "id-two" },
        h("div", null, h("small", null, "Công nghệ nên dùng"), techBox),
        h("div", null, h("small", null, "Kỹ năng bạn rèn được"), h("div", { class: "id-chips" }, it.skills.map((x) => h("span", null, x))))),
      h("details", { class: "id-det" }, h("summary", null, "Đề tài đã có để tham khảo" + (nRef ? " (" + nRef + ")" : "")), refs,
        it.same_topic_theses ? h("button", { type: "button", class: "id-btn", onclick: showRefs }, "Xem cả " + it.same_topic_theses + " khóa luận cùng chủ đề này") : null),
      h("div", { class: "id-act" }, advBtn), advBox);

    function applyTitle(x, checked) {
      t.title = x.title; t.summary = x.summary || x.why || ""; t.novelty = x.novelty; t.checked = checked;
      shown.push(x.title);
      clear(titleEl).append(x.title);
      clear(sumEl).append(t.summary || "Chưa có tóm tắt cho đề tài này.");
      t.tech = x.tech && x.tech.length ? x.tech : it.technologies;
      if (x.tech && x.tech.length) techBox.replaceChildren(...x.tech.map((c) => h("span", null, c)));      // chỉ hiện công nghệ tên đề tài thật sự dùng
      if (!it.domain_labels.length && x.domain_labels && x.domain_labels.length) { domExtra.textContent = "Lĩnh vực gợi ý " + x.domain_labels.join(", "); domExtra.hidden = false; }
      stat.replaceWith(Object.assign(statusTag(x.novelty, checked), {}));
      save.disabled = false; paintSave(); advBtn.disabled = false; clear(advBox);
    }
    async function fetchTitle() {
      if (signal.aborted) return;
      msg.hidden = true;
      const hit = titleCache.get(roles, it.topic);
      if (hit) { applyTitle(hit, hit.checked); return; }          // đã viết trước đó: dùng lại, không gọi mô hình
      try {
        const r = await api.ideaTitle({ roles, topic: it.topic, avoid: shown.slice(-6), n: 1 }, { signal });
        if (signal.aborted) return;
        const x = r.titles[0];
        if (!x) return fail("Mô hình chỉ viết được tên trùng với đề tài đã có. Bạn thử lại để nhận tên khác.");
        titleCache.set(roles, it.topic, { title: x.title, summary: x.summary || x.why, novelty: x.novelty ? x.novelty.status : null, checked: r.novelty_checked, tech: x.tech, domain_labels: x.domain_labels });
        applyTitle(x, r.novelty_checked);
      } catch (e) {
        if (e && e.name === "AbortError") return;
        fail(describeError(e).text);
      }
    }
    function fail(text) {
      clear(titleEl).append(it.topic_label);
      clear(sumEl).append("Chưa viết được tóm tắt.");
      stat.textContent = "Chưa có tên đề tài"; stat.className = "id-tag wait";
      clear(msg).append(h("span", null, text), " ", h("button", { type: "button", class: "btn btn-sm", onclick: retry }, "Thử lại"));
      msg.hidden = false;
    }
    function retry() {
      clear(titleEl).append(h("span", { class: "skel" }), h("span", { class: "skel skel-s" }));
      clear(sumEl).append(h("span", { class: "skel" }), h("span", { class: "skel skel-s" }));
      stat.textContent = "Đang viết tên đề tài…";
      queue = queue.then(fetchTitle);
    }
    queue = queue.then(fetchTitle);                 // viết lần lượt từng thẻ để máy chạy mô hình cục bộ không bị nghẽn
    return el;
  }

  async function fetchIdeas() {
    const key = roles.join("|"), cached = offset === 0 ? firstPage.get(key) : null;
    if (offset > 0) more.replaceChildren(loading("Đang tìm hướng đề tài…"));
    try {
      const d = cached || await api.ideas({ roles, offset, n: PAGE }, { signal });
      if (signal.aborted) return;
      if (offset === 0) { firstPage.set(key, d); paintHead(d); paintAside(d); clear(list); }
      total = d.total_directions;
      if (d.message) { list.append(notice(d.message)); }
      d.items.forEach((it) => list.append(card(it, n++)));
      offset += PAGE;
      clear(more);
      if (offset < total) more.append(h("button", { type: "button", class: "id-btn dark big", onclick: fetchIdeas }, "Gợi ý thêm đề tài khác"), h("button", { type: "button", class: "id-btn big", onclick: () => openPicker({ onDone: () => { if (single) window.location.hash = "#/ideas"; else rerender(); } }) }, "Chọn lại công việc"));
      else if (n > 0) more.append(h("p", { class: "muted" }, "Đã hết hướng gợi ý cho các công việc này. Thử đổi hoặc chọn thêm công việc để xem hướng khác."), h("button", { type: "button", class: "btn", onclick: () => openPicker({ onDone: rerender }) }, "Đổi công việc"));
    } catch (e) {
      if (e && e.name === "AbortError") return;
      clear(more);
      if (offset === 0) { clear(list); clear(head).append(errorBox(e, rerender)); } else more.append(errorBox(e, fetchIdeas));
    }
  }
  fetchIdeas();
}
