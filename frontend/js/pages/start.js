// Trang bắt đầu: màn chào đầu tiên khi demo. Khách bấm "Bắt đầu"; quản trị viên dùng liên kết nhỏ ở cuối.
import { h, clear } from "../dom.js";
import { store } from "../store.js";
import { api } from "../api.js";
import { icon } from "../icons.js";
import { session } from "../session.js";

export const title = "NET";
const WORDS = ["dữ liệu", "kỹ năng của bạn", "xu hướng nghề nghiệp", "nhu cầu tuyển dụng"];
const FACES = ["AI", "Web", "Data", "IoT", "Cloud", "Sec"];
const cube = (size, cls, labels) => h("div", { class: "st-cube " + cls, style: "--s:" + size + "px" }, [1, 2, 3, 4, 5, 6].map((n, k) => h("i", { class: "f" + n }, labels ? labels[k] : "")));
// cảnh 3D thuần CSS: khối lập phương xoay, vòng quỹ đạo, tấm kính biểu đồ; nghiêng nhẹ theo con trỏ
function scene() {
  const bars = [38, 62, 46, 84, 58, 72];
  return h("div", { class: "st-3d", "aria-hidden": "true" }, h("div", { class: "st-sc" },
    h("div", { class: "st-obj o1" }, h("i", { class: "st-ring r1" }), h("i", { class: "st-ring r2" }), cube(170, "big", FACES)),
    h("div", { class: "st-obj o2" }, cube(64, "coral")),
    h("div", { class: "st-obj o3" }, cube(104, "soft")),
    h("div", { class: "st-obj o4" }, h("div", { class: "st-slab" }, h("span", null), h("div", null, bars.map((v, k) => h("b", { class: k === 3 ? "hot" : "", style: "height:" + v + "%" }))))),
    h("div", { class: "st-obj o5" }, cube(38, "soft")),
    ...[0, 1, 2, 3, 4, 5].map((k) => h("i", { class: "st-dot d" + k }))));
}


// "Bắt đầu": chưa đăng nhập thì sang đăng nhập bằng mã sinh viên; đã đăng nhập thì vào thẳng
const goStart = () => { window.location.hash = !session.get() ? "#/login" : session.isAdmin() || store.get().welcomed ? "#/" : "#/welcome"; };
const reduce = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const sec = (cls, ...kids) => h("section", { class: "sx " + cls }, h("div", { class: "sx-in" }, ...kids));
const head = (eyebrow, title, lead) => h("div", { class: "sx-head rv" }, h("span", { class: "sx-eb" }, eyebrow), h("h2", null, title), lead ? h("p", null, lead) : null);
const ic = (name) => h("span", { class: "sx-ic" }, icon(name, 22));

// phần giải thích ý tưởng, công dụng và giá trị, nằm dưới màn chào
function about(ctx, ov) {
  const stats = h("div", { class: "sx-stats rv", hidden: true });
  ov.then((d) => {
    if (!d) return;
    [[d.n_jobs, "tin tuyển dụng đã phân tích"], [d.n_thesis, "khóa luận trong kho"], [(d.hot_roles || []).length, "vị trí công việc"], [(d.top_skills || []).length, "kỹ năng được theo dõi"]].forEach(([n, l]) => {
      const b = h("b", { "data-n": String(n || 0) }, "0"); stats.append(h("div", null, b, h("span", null, l)));
    });
    stats.hidden = false;
  }).catch(() => { /* không có số liệu khi API chưa chạy: ẩn dải số */ });

  const pain = [["search", "Không biết mình hợp hướng nào", "Có quá nhiều chủ đề, nhưng chưa ai chỉ ra kỹ năng của bạn đang gần với hướng nào nhất."],
    ["generic", "Đề tài hay nhưng không ai cần", "Chọn theo cảm tính dễ ra đề tài khó xin việc, vì không khớp với thứ doanh nghiệp đang tuyển."],
    ["user", "Không biết nhờ ai hướng dẫn", "Mỗi giảng viên mạnh một mảng. Chọn sai người thì đề tài khó đi xa."]];
  const inputs = [["user", "Kỹ năng của bạn", "Bạn chọn những gì đã biết"], ["generic", "Tin tuyển dụng thật", "Thị trường đang cần gì"], ["book", "Khóa luận đã có", "Tránh trùng, học cách làm"]];
  const outputs = [["bulb", "Đề tài phù hợp", "Kèm điểm mạnh và điểm cần cân nhắc"], ["shield", "Giảng viên gợi ý", "Người hợp để nhờ hướng dẫn"]];
  const node = (side) => ([i, t, d]) => h("div", { class: "sx-node " + side }, ic(i), h("div", null, h("b", null, t), h("span", null, d)));

  const feats = [
    ["f1", "user", "Kỹ năng thành công việc phù hợp", "Chọn kỹ năng bạn đã dùng được, NET cho biết bạn đang hợp vị trí nào và còn thiếu gì.",
      h("div", { class: "sx-v1" }, ["Python", "SQL", "React"].map((t) => h("em", null, t)), h("div", null, h("i", { style: "--w:82%" }), h("small", null, "Backend Developer · hợp 82%")))],
    ["f2", "bulb", "Đề xuất có lý do rõ ràng", "Mỗi đề tài có điểm mạnh và điểm cần cân nhắc, để bạn quyết định có cơ sở.",
      h("div", { class: "sx-v2" }, h("p", { class: "ok" }, "Khớp kỹ năng bạn đã có"), h("p", { class: "warn" }, "Cần học thêm dữ liệu lớn"))],
    ["f3", "shield", "Giảng viên phù hợp với từng đề tài", "Mỗi ý tưởng đi kèm ba giảng viên gần với hướng đề tài nhất.",
      h("div", { class: "sx-v3" }, ["A", "B", "C"].map((t) => h("b", null, t)), h("span", null, "3 gợi ý"))],
    ["f4", "file", "Kho khóa luận, mở thẳng báo cáo", "Lọc theo chủ đề, trường, năm và xem PDF ngay để tham khảo.",
      h("div", { class: "sx-v4" }, h("span", null, icon("file", 26)), h("small", null, "Xem PDF"))],
    ["f5", "Data Analyst", "Xu hướng khóa luận", "Chủ đề nào đang tăng, chủ đề nào đã bão hòa, theo từng năm.",
      h("div", { class: "sx-v5" }, [30, 44, 40, 62, 78].map((v, k) => h("i", { style: "height:" + v + "%", class: k === 4 ? "hot" : "" })))],
    ["f6", "heart", "Lưu lại, so sánh, quyết định", "Giữ các đề tài bạn thích, đối chiếu với khóa luận có sẵn rồi chốt.",
      h("div", { class: "sx-v6" }, h("span", null, icon("heart", 22)), h("small", null, "Đã lưu 3"))]];

  const values = [["1", "Tiết kiệm thời gian", "Thay vì lướt từng nơi, bạn thấy ngay hướng hợp mình trong vài phút."], ["2", "Quyết định bằng dữ liệu", "Đề tài bám theo nhu cầu tuyển dụng thật, không chỉ cảm tính."], ["3", "Tránh trùng lặp", "Đối chiếu với kho khóa luận trước khi chốt."]];

  const wrap = h("div", { class: "st-light", id: "st-about" },
    sec("sx-s0", stats),
    sec("sx-s1", head("Vấn đề", "Chọn đề tài, ai cũng từng mắc kẹt", "Ba nỗi khó mà gần như sinh viên nào cũng gặp."),
      h("div", { class: "sx-pain" }, pain.map(([i, t, d], k) => h("div", { class: "sx-card rv", style: "--d:" + k * 90 + "ms" }, ic(i), h("h3", null, t), h("p", null, d))))),
    sec("sx-s2", head("Ý tưởng", "NET nối ba thứ vào một câu trả lời", "Kỹ năng của bạn, nhu cầu thị trường và các khóa luận đã có được đặt cạnh nhau, để chỉ ra điểm giao hợp nhất."),
      h("div", { class: "sx-flow rv" }, h("div", { class: "sx-col" }, inputs.map(node("in"))),
        h("div", { class: "sx-hub" }, h("i", { class: "p1" }), h("i", { class: "p2" }), h("img", { src: "logo.svg", alt: "NET", width: 84, height: 84 })),
        h("div", { class: "sx-col" }, outputs.map(node("out")))),
      h("p", { class: "sx-flow-note rv" }, "Điểm giao giữa ba nguồn dữ liệu là đề tài dành cho bạn.")),
    sec("sx-s3", head("Công dụng", "Bạn nhận được gì khi dùng NET"),
      h("div", { class: "sx-bento" }, feats.map(([c, i, t, d, v], k) => h("div", { class: "sx-feat " + c + " rv", style: "--d:" + k * 70 + "ms" }, h("div", { class: "txt" }, ic(i), h("h3", null, t), h("p", null, d)), v)))),
    sec("sx-s4", head("Giá trị", "Vì sao đáng để thử"),
      h("div", { class: "sx-val" }, values.map(([n, t, d], k) => h("div", { class: "rv", style: "--d:" + k * 90 + "ms" }, h("b", null, n), h("h3", null, t), h("p", null, d))))),
    h("section", { class: "sx-cta" }, h("div", { class: "sx-cta-in rv" }, h("h2", null, "Sẵn sàng tìm đề tài của bạn?"), h("p", null, "Mất chưa tới một phút để chọn kỹ năng. Hồ sơ lưu theo mã sinh viên của bạn."),
      h("button", { type: "button", class: "st-go", onclick: goStart }, "Bắt đầu ngay", h("span", { "aria-hidden": "true" }, "→")))));

  // hiện dần khi cuộn tới; số đếm lên khi lộ ra
  const count = (b) => { const n = +b.dataset.n || 0; if (reduce()) { b.textContent = n.toLocaleString("vi-VN"); return; } const t0 = performance.now(); (function f(t) { const p = Math.min(1, (t - t0) / 1200); b.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))).toLocaleString("vi-VN"); if (p < 1 && b.isConnected) requestAnimationFrame(f); })(t0); };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (!e.isIntersecting) return; e.target.classList.add("in"); e.target.querySelectorAll("b[data-n]").forEach(count); io.unobserve(e.target); }), { threshold: 0.15 });
    window.setTimeout(() => wrap.querySelectorAll(".rv").forEach((el) => io.observe(el)), 0);
    ctx.signal.addEventListener("abort", () => io.disconnect());
  } else { wrap.querySelectorAll(".rv").forEach((el) => el.classList.add("in")); }
  return wrap;
}

const BUBBLES = [["Làm web hay AI nhỉ?", 4, 24, -4], ["Nghe nói ngành này hot…", 50, 20, 3], ["Thầy nào dễ duyệt?", 8, 52, 2], ["Đề này có ai làm chưa?", 56, 46, -3],
  ["Deadline sắp tới rồi!", 30, 70, 4], ["Thôi, chọn đại…", 64, 70, -2], ["Bạn A bảo làm blockchain", 28, 38, -2]];

// "cảm tính" (rối, mệt) chuyển thành "dữ liệu" (rõ ràng, số liệu thật từ backend)
function flip(ctx, ov) {
  const stage = h("div", { class: "fl-stage" });
  const sec = h("section", { class: "fl" }, h("i", { class: "st-glow g2" }), h("div", { class: "fl-in" }));
  const tabC = h("button", { type: "button", class: "fl-tab on", onclick: () => user("chaos") }, "Cảm tính");
  const tabD = h("button", { type: "button", class: "fl-tab", onclick: () => user("data") }, "Dữ liệu");
  const meterV = h("b", null, "12%"), tabsV = h("b", null, "0");
  const fill = h("i");
  const chaos = h("div", { class: "fl-chaos" },
    h("div", { class: "fl-meter" }, h("div", null, h("span", null, "Độ phân vân"), meterV), h("div", { class: "fl-bar" }, fill), h("div", { class: "fl-tabs-open" }, h("span", null, "Tab đang mở"), tabsV)),
    ...BUBBLES.map(([t, x, y, r], k) => h("span", { class: "fl-bub", style: `--x:${x}%;--y:${y}%;--r:${r}deg;--d:${-k * 0.7}s` }, t)),
    ...[["?", 80, 10, 90], ["?", 14, 74, 60], ["?", 88, 58, 120]].map(([q, x, y, z]) => h("span", { class: "fl-q", style: `--x:${x}%;--y:${y}%;--z:${z}px` }, q)),
    h("p", { class: "fl-cap" }, "Đoán, hỏi bạn bè, mở hết tab này tới tab khác… rồi vẫn chưa biết chọn gì."));
  const dataBox = h("div", { class: "fl-data" }, h("p", { class: "fl-cap" }, "Đang tải số liệu…"));
  const scan = h("i", { class: "fl-scan" });
  stage.append(chaos, dataBox, scan);

  const bars = [];
  ov.then((d) => {
    if (!d) { clear(dataBox).append(h("p", { class: "fl-cap" }, "Chưa kết nối được máy chủ, chưa có số liệu để hiển thị.")); return; }
    const roles = (d.hot_roles || []).slice(0, 4), maxJ = Math.max(1, ...roles.map((r) => r.job_count));
    const pairs = (d.skill_pairs || []).slice(0, 3), maxP = Math.max(1, ...pairs.map((q) => q.count));
    const cnts = [];
    const num = (n, l) => { const b = h("b", { "data-n": String(n || 0) }, "0"); cnts.push(b); return h("div", null, b, h("span", null, l)); };
    const row = (label, v, max, cls) => { const f = h("i", { class: cls || "" }); bars.push([f, (v / max * 100).toFixed(0) + "%"]); return h("div", { class: "fl-row" }, h("span", null, label), h("div", { class: "fl-track" }, f), h("em", null, String(v))); };
    clear(dataBox).append(
      h("div", { class: "fl-grid" },
        h("div", { class: "fl-panel" }, h("h3", null, "Vị trí đang cần nhiều nhất"), ...roles.map((r, k) => row(r.label, r.job_count, maxJ, k === 0 ? "hot" : ""))),
        h("div", { class: "fl-panel" }, h("h3", null, "Kỹ năng hay đi cùng nhau"), ...pairs.map((q) => row(q.a + " + " + q.b, q.count, maxP))),
        h("div", { class: "fl-panel big" }, num(d.n_jobs, "tin tuyển dụng đã phân tích"), num(d.n_thesis, "khóa luận để đối chiếu"), h("p", { class: "fl-pick" }, icon("check", 20), "Kết quả: một đề tài rõ ràng cho bạn"))),
      h("p", { class: "fl-cap" }, "Mọi con số lấy từ dữ liệu thật của NET, không phải cảm tính."));
    dataBox._cnts = cnts;
  }).catch(() => { clear(dataBox).append(h("p", { class: "fl-cap" }, "Chưa kết nối được máy chủ, chưa có số liệu để hiển thị.")); });

  const countTo = (b, n) => { if (reduce()) { b.textContent = n.toLocaleString("vi-VN"); return; } const t0 = performance.now(); (function f(t) { const p = Math.min(1, (t - t0) / 1300); b.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))).toLocaleString("vi-VN"); if (p < 1 && b.isConnected) requestAnimationFrame(f); })(t0); };
  let timers = [], mode = "";
  const clearT = () => { timers.forEach(clearTimeout); timers = []; };
  const tick = (el, to, ms, fmt) => { const t0 = performance.now(); (function f(t) { const p = Math.min(1, (t - t0) / ms); el.textContent = fmt(Math.round(to * p)); if (p < 1 && el.isConnected && mode === "chaos") requestAnimationFrame(f); })(t0); };
  function show(m) {
    clearT(); mode = m;
    const isData = m === "data";
    stage.classList.toggle("is-data", isData); sec.classList.toggle("is-data", isData);
    tabC.classList.toggle("on", !isData); tabD.classList.toggle("on", isData);
    stage.classList.add("glitch"); timers.push(setTimeout(() => stage.classList.remove("glitch"), 600));
    if (isData) {
      bars.forEach(([f, w], k) => { f.style.width = "0"; timers.push(setTimeout(() => { f.style.width = w; }, 350 + k * 90)); });
      timers.push(setTimeout(() => (dataBox._cnts || []).forEach((b) => countTo(b, +b.dataset.n || 0)), 450));
    } else {
      fill.classList.remove("go"); void fill.offsetWidth; fill.classList.add("go");
      tick(meterV, 97, 4200, (v) => Math.max(12, v) + "%"); tick(tabsV, 47, 4200, (v) => String(v));
    }
  }
  const user = (m) => { auto = false; show(m); };
  let auto = true, started = false;
  const begin = () => { if (started) return; started = true; if (reduce()) { show("data"); return; } show("chaos"); timers.push(setTimeout(() => { if (auto) show("data"); }, 5200)); };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { begin(); io.disconnect(); } }), { threshold: 0.4 });
    window.setTimeout(() => io.observe(sec), 0); ctx.signal.addEventListener("abort", () => { io.disconnect(); clearT(); });
  } else begin();

  sec.querySelector(".fl-in").append(
    h("div", { class: "fl-head" }, h("span", { class: "sx-eb dk" }, "Thông điệp của NET"),
      h("h2", null, h("span", { class: "ta" }, "Mệt vì phải chọn?"), h("span", { class: "tb" }, "Để dữ liệu chọn cùng bạn.")),
      h("div", { class: "fl-tabsw", role: "group", "aria-label": "So sánh cách chọn" }, tabC, tabD)),
    stage);
  return sec;
}

export function render(root, params, ctx) {
  const word = h("span", { class: "st-word" }, WORDS[0]);
  let i = 0;
  const timer = window.setInterval(() => {
    if (!word.isConnected) { window.clearInterval(timer); return; }
    word.classList.add("out");
    window.setTimeout(() => { i = (i + 1) % WORDS.length; word.textContent = WORDS[i]; word.classList.remove("out"); }, 280);
  }, 2600);
  const go = goStart;

  const page = h("div", { class: "st-root" },
    h("i", { class: "st-glow g1" }), h("i", { class: "st-glow g2" }),
    scene(),
    h("header", { class: "st-top" },
      h("span", { class: "st-brand" }, h("img", { src: "logo.svg", alt: "", width: 44, height: 44 }), h("b", null, "NE", h("em", null, "T")), h("small", null, "National Economics Thesis"))),
    h("section", { class: "st-hero" },
      h("span", { class: "st-eyebrow" }, h("i"), "Dành cho sinh viên CNTT sắp làm khóa luận"),
      h("h1", null, "Đừng chọn đề tài", h("br"), "bằng cảm tính.", h("br"), h("span", { class: "st-grad" }, "Hãy chọn bằng"), h("br"), word, "."),
      h("p", { class: "st-lead" }, "Từ hàng nghìn khóa luận và tin tuyển dụng có thật, NET chỉ ra đề tài hợp với kỹ năng của bạn, thị trường đang cần và có giảng viên phù hợp để hướng dẫn."),
      h("div", { class: "st-cta" },
        h("button", { type: "button", class: "st-go", onclick: go }, "Bắt đầu ngay", h("span", { "aria-hidden": "true" }, "→")),
        session.get() ? h("a", { class: "st-ghost", href: "#/library" }, "Xem kho khóa luận") : h("a", { class: "st-ghost", href: "#/login" }, "Đăng nhập bằng mã sinh viên"),
        h("button", { type: "button", class: "st-down", onclick: () => { const el = document.getElementById("st-about"); if (el) el.scrollIntoView({ behavior: reduce() ? "auto" : "smooth" }); } }, "Tìm hiểu thêm", h("span", { "aria-hidden": "true" }, "↓"))),
      h("p", { class: "st-note" }, session.get() ? "Hồ sơ của bạn được lưu theo mã sinh viên." : "Dùng mã sinh viên để đăng nhập. Kỹ năng và đề tài bạn lưu sẽ gắn với mã này.")),
    h("section", { class: "st-steps", "aria-label": "Cách hoạt động" },
      [["1", "Chọn kỹ năng", "Bấm vào những gì bạn đã biết, mất chưa tới một phút."],
       ["2", "Nhận đề xuất", "Đề tài kèm điểm mạnh, điểm cần cân nhắc và giảng viên phù hợp."],
       ["3", "Chốt đề tài", "Lưu lại, so sánh và mở thẳng báo cáo mẫu để tham khảo."]].map(([n, t, d]) =>
        h("div", { class: "st-step" }, h("b", null, n), h("div", null, h("strong", null, t), h("span", null, d))))),
    h("footer", { class: "st-foot" }, h("span", null, "Đồ án sinh viên · Khoa Công nghệ thông tin"), h("a", { href: "#/login" }, "Quản trị viên")));
  const sc = () => page.querySelector(".st-sc");
  page.addEventListener("pointermove", (e) => {
    const el = sc(); if (!el) return;
    const x = e.clientX / window.innerWidth - 0.5, y = e.clientY / window.innerHeight - 0.5;
    el.style.setProperty("--rx", (x * 16).toFixed(2) + "deg");
    el.style.setProperty("--ry", (-y * 12).toFixed(2) + "deg");
  });
  const ov = api.overview({ signal: ctx.signal }).catch(() => null);
  root.append(h("div", { class: "st-wrap" }, page, flip(ctx, ov), about(ctx, ov)));
}
