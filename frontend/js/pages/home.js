import { h, clear } from "../dom.js";
import { api } from "../api.js";
import { store } from "../store.js";
import { icon } from "../icons.js";
import { openPicker } from "../picker.js";
import { load, foot } from "../ui.js";

export const PHRASES = [
  "Có ý tưởng nào đang chờ bạn khám phá?",
  "Chưa biết bắt đầu từ đâu? Cùng tìm hướng đi nhé!",
  "Tương lai của bạn bắt đầu từ một ý tưởng.",
  "Khám phá điều bạn có thể làm với những kỹ năng mình có.",
  "Một ý tưởng hay có thể bắt đầu từ hôm nay.",
  "Cùng tìm ra hướng đi phù hợp với bạn nhé!",
];
const STEPS = [
  { t: "Chọn công việc bạn quan tâm", d: "Chọn 1 đến 3 vị trí, ví dụ Phân tích dữ liệu hay Lập trình viên Backend.", q: "Danh sách vị trí mục tiêu.", ill: () => h("div", { class: "hm-s1" }, ["Backend", "Dữ liệu", "AI / Học máy"].map((x) => h("span", null, x))) },
  { t: "Xem kỹ năng cần có", d: "Biết các công việc đó đòi hỏi kỹ năng gì và kỹ năng nào thường đi cùng nhau.", q: "Kỹ năng ưu tiên theo dữ liệu tuyển dụng.", ill: () => h("div", { class: "hm-s2" }, [["Python", 92], ["SQL", 74], ["Cloud", 58]].map(([n, w]) => h("div", null, h("em", null, n), h("i", { style: `--w:${w}%` })))) },
  { t: "Nhận gợi ý đề tài", d: "Hệ thống đề xuất một số đề tài khóa luận, kèm tóm tắt ngắn và công nghệ nên dùng.", q: "Các đề tài phù hợp, có tóm tắt.", ill: () => h("div", { class: "hm-s3" }, h("small", null, "ĐỀ TÀI GỢI Ý"), h("span", { class: "tx" }, "Chatbot tư vấn bằng AI"), h("b", { class: "sp" }, "✦"), h("b", { class: "sp" }, "✦"), h("b", { class: "sp" }, "✦")) },
  { t: "Đối chiếu và chọn", d: "Xem các khóa luận đã có để tránh trùng lặp, rồi chọn đề tài và trao đổi với giảng viên.", q: "Đề tài đã đối chiếu với kho khóa luận.", ill: () => h("div", { class: "hm-s4" }, h("div", null, "Website bán hàng…"), h("div", { class: "me" }, "Đề tài của bạn"), h("div", null, "Quản lý nhà hàng…"), h("i", { class: "lens" }), h("span", { class: "ok" }, "✓")) },
];
const hueOf = (n) => { let x = 0; for (const c of String(n || "")) x = (x * 31 + c.charCodeAt(0)) % 360; return x; };
const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function countUp(b, n, ctx) {
  if (reduceMotion()) { b.textContent = n.toLocaleString("vi-VN"); return; }
  const t0 = performance.now();
  (function f(t) { const p = Math.min(1, (t - t0) / 1100); b.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))).toLocaleString("vi-VN"); if (p < 1 && !ctx.signal.aborted) requestAnimationFrame(f); })(t0);
}
function typer(node, ctx) {                                              // câu gợi ý được gõ từng ký tự rồi xoá
  if (reduceMotion()) { node.textContent = PHRASES[0]; return; }
  let i = 0, c = 0, del = false, tm;
  ctx.signal.addEventListener("abort", () => clearTimeout(tm));
  (function tick() {
    if (ctx.signal.aborted) return;
    const s = PHRASES[i];
    if (!del) { c++; node.textContent = s.slice(0, c); if (c === s.length) { del = true; tm = setTimeout(tick, 2200); return; } tm = setTimeout(tick, 38); return; }
    c -= 2; node.textContent = s.slice(0, Math.max(c, 0));
    if (c <= 0) { del = false; i = (i + 1) % PHRASES.length; tm = setTimeout(tick, 350); return; }
    tm = setTimeout(tick, 18);
  })();
}

function start(preselect) {
  if (!preselect && store.get().roles.length) { window.location.hash = "#/ideas"; return; }      // đã chọn rồi thì vào thẳng kết quả
  openPicker({ preselect });
}

export function render(root, params, ctx) {
  const body = h("div", { class: "hm" });
  root.append(body);
  load(body, ctx, () => api.overview({ signal: ctx.signal }), (d) => {
    const maxJob = Math.max(1, ...d.hot_roles.map((r) => r.job_count)), maxSk = Math.max(0.0001, ...d.top_skills.map((s) => s.share));
    const first = d.hot_roles[0], hasRoles = store.get().roles.length > 0;
    const typed = h("p", { class: "hm-type", "aria-live": "off" });
    const stats = h("div", { class: "hm-stats" });
    [[d.n_jobs, "tin tuyển dụng"], [d.n_thesis, "khóa luận"], [d.hot_roles.length, "vị trí đang hot"], [d.top_skills.length, "kỹ năng phổ biến"]].forEach(([n, l]) => {
      const b = h("b", null, "0"); stats.append(h("div", null, b, h("span", null, l))); countUp(b, n || 0, ctx);
    });
    const POS = [["0%", "2%"], ["47%", "10%"], ["3%", "36%"], ["50%", "44%"], ["0%", "68%"], ["53%", "80%"]];
    const orbit = h("div", { class: "hm-orbit", "aria-hidden": "true" }, h("div", { class: "hm-core" }),
      ...d.hot_roles.slice(0, 6).map((r, i) => h("div", { class: "hm-bub", style: `--x:${POS[i][0]};--y:${POS[i][1]};--dl:${-i * 1.1}s;--h:${hueOf(r.name)}` }, h("span", { class: "ic" }, r.label[0]), h("span", null, r.label, h("small", null, r.job_count + " tin tuyển")))));

    // 4 bước: đường tiến trình, các thẻ có minh hoạ động, tự chuyển bước
    const stepEls = STEPS.map((s, i) => { const e = h("div", { class: "hm-step", tabindex: "0", role: "button", "aria-label": "Bước " + (i + 1) + ": " + s.t }, h("div", { class: "hm-stage" }, s.ill()), h("span", { class: "hm-k" }, "Bước " + (i + 1)), h("b", null, s.t), h("p", null, s.d), h("span", { class: "hm-q" }, s.q)); return e; });
    const prog = h("div", { class: "hm-prog" });
    const line = h("div", { class: "hm-line" }, prog);
    const nodes = STEPS.map((_, i) => { const n = h("i", { class: "hm-node", style: `left:${i / 3 * 100}%` }, String(i + 1)); line.append(n); return n; });
    let cur = -1, timer = null;
    const setStep = (i) => { cur = i; stepEls.forEach((s, k) => s.classList.toggle("on", k === i)); nodes.forEach((n, k) => { n.classList.toggle("on", k <= i); n.classList.toggle("cur", k === i); }); prog.style.width = (i / 3 * 100) + "%"; };
    const auto = () => { clearInterval(timer); if (!reduceMotion()) timer = setInterval(() => setStep((cur + 1) % 4), 5200); };
    ctx.signal.addEventListener("abort", () => clearInterval(timer));
    stepEls.forEach((s, i) => { const go = () => { setStep(i); auto(); }; s.addEventListener("click", go); s.addEventListener("mouseenter", go); s.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } }); });
    setStep(0); auto();

    const jobCards = d.hot_roles.map((r, i) => h("button", { type: "button", class: "hm-job hm-rv", style: `--h:${hueOf(r.name)};--d:${i}`, onclick: () => { window.location.hash = "#/jobs?role=" + encodeURIComponent(r.name); } },
      h("div", { class: "top" }, h("span", { class: "rank" }, String(i + 1)), h("span", { class: "tagp" }, r.job_count + " tin tuyển")),
      h("b", null, r.label), h("span", { class: "d" }, r.description), h("span", { class: "go" }, "Xem tin tuyển dụng thật ›"),
      h("div", { class: "hm-track" }, h("div", { class: "hm-fill", style: `--w:${(r.job_count / maxJob * 100).toFixed(0)}%` }))));
    const skillRows = d.top_skills.map((s) => { const v = h("span", { class: "v", "data-n": String(Math.round(s.share * 100)) }, "0%"); return h("div", { class: "hm-row" }, h("span", null, s.name), h("div", { class: "hm-track" }, h("div", { class: "hm-fill", style: `--w:${(s.share / maxSk * 100).toFixed(0)}%` })), v); });
    const maxP = Math.max(1, ...d.skill_pairs.map((p) => p.count));
    const pairs = d.skill_pairs.map((p) => h("div", { class: "hm-row pr" }, h("span", null, p.a, h("em", null, " + "), p.b), h("div", { class: "hm-track" }, h("div", { class: "hm-fill", style: `--w:${(p.count / maxP * 100).toFixed(0)}%` })), h("span", { class: "v" }, p.count + " tin")));

    body.append(
      h("section", { class: "hm-hero" }, h("i", { class: "hm-blob b1" }), h("i", { class: "hm-blob b2" }), h("i", { class: "hm-blob b3" }),
        h("div", null,
          h("span", { class: "hm-eyebrow" }, h("i"), h("span", null, "Dựa trên " + d.n_jobs + " tin tuyển dụng IT")),
          h("h1", null, "Bạn muốn làm khóa luận ", h("em", null, "về điều gì?")),
          typed,
          h("div", { class: "hm-cta" }, h("button", { type: "button", class: "hm-btn main", onclick: () => start() }, (hasRoles ? "Xem đề tài gợi ý của bạn" : "Bắt đầu chọn đề tài") + " →"), h("a", { class: "hm-btn ghost", href: "#/library" }, "Lướt kho khóa luận")),
          stats),
        orbit),
      h("section", { class: "hm-rv" }, h("h2", null, "4 bước để có tên đề tài"), h("p", { class: "lead" }, "Mất khoảng 2 phút, không cần đăng nhập. Chọn một bước để xem hệ thống làm gì ở bước đó."),
        h("div", { class: "hm-road" }, line, h("div", { class: "hm-steps" }, ...stepEls))),
      h("section", { class: "hm-rv" }, h("h2", null, "Công việc đang hot"), h("p", { class: "lead" }, "Những vị trí được các công ty tuyển nhiều nhất. ", first ? h("a", { href: "#/jobs?role=" + encodeURIComponent(first.name) }, "Xem tin tuyển dụng thật") : null),
        h("div", { class: "hm-jobs" }, ...jobCards)),
      h("section", { class: "hm-split" },
        h("div", { class: "hm-card hm-rv" }, h("h2", null, "Kỹ năng nên học"), h("p", { class: "lead" }, "Tỷ lệ tin tuyển dụng nhắc đến kỹ năng đó. Càng cao, học càng dễ có lợi khi đi xin việc."), h("div", { class: "hm-bars" }, ...skillRows)),
        h("div", { class: "hm-card hm-rv", style: "--d:1" }, h("h2", null, "Kỹ năng hay đi cùng nhau"), h("p", { class: "lead" }, "Những cặp kỹ năng thường xuất hiện chung trong một tin tuyển dụng. Học theo cặp sẽ hợp hơn học rời rạc."), h("div", { class: "hm-rows" }, ...pairs))),
      h("section", { class: "hm-band hm-rv" }, h("i", { class: "hm-blob b1" }), h("i", { class: "hm-blob b2" }),
        h("h2", null, "Sẵn sàng chọn đề tài chưa?"), h("p", null, "Chọn vài công việc bạn quan tâm, hệ thống gợi ý đề tài kèm tóm tắt và công nghệ nên dùng."),
        h("button", { type: "button", class: "hm-btn main", onclick: () => start() }, (hasRoles ? "Xem đề tài gợi ý của bạn" : "Bắt đầu ngay") + " →")),
      foot("Số liệu lấy từ " + d.n_jobs + " tin tuyển dụng ngành CNTT đã thu thập. Đây là bức ảnh tại một thời điểm, chưa phải xu hướng theo tháng."));

    typer(typed, ctx);
    // hiện dần khi cuộn tới; thanh và số chạy khi vào khung nhìn
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (!e.isIntersecting) return;
      const t = e.target; t.classList.add("in");
      t.querySelectorAll(".hm-fill").forEach((f) => { f.style.width = f.style.getPropertyValue("--w"); });
      t.querySelectorAll(".v[data-n]").forEach((v) => { const n = +v.dataset.n, t0 = performance.now(); (function f(tt) { const p = reduceMotion() ? 1 : Math.min(1, (tt - t0) / 1000); v.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))) + "%"; if (p < 1 && !ctx.signal.aborted) requestAnimationFrame(f); })(t0); });
      io.unobserve(t);
    }), { threshold: 0.15 });
    body.querySelectorAll(".hm-rv").forEach((n) => io.observe(n));
    ctx.signal.addEventListener("abort", () => io.disconnect());
  });
}
