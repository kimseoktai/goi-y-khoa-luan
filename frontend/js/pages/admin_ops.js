import { h, clear } from "../dom.js";
import { loading, notice } from "../ui.js";

const NAMES = { crawl_jobs: "Crawl tin tuyển dụng", crawl_thesis: "Crawl khóa luận", build_thesis: "Gắn nhãn khóa luận", build_site: "Dựng dữ liệu", embeddings: "Dựng embedding", jobs_flow: "Chạy cả luồng", crawl_all: "Crawl tất cả" };
const mmss = (s) => Math.floor(s / 60) + " phút " + String(s % 60).padStart(2, "0") + " giây";

// Tab "Chạy lệnh & log": chạy crawl/dựng dữ liệu/embedding/test ở máy chủ, xem log trực tiếp và các log cũ.
export function mount(box, A) {
  const SLOW = { crawl_jobs: "Crawl 3 nguồn tuyển dụng mất khá lâu và gửi nhiều yêu cầu tới các trang tuyển dụng.", jobs_flow: "Chạy cả luồng gồm crawl 3 nguồn tuyển dụng, dựng dữ liệu và embedding, có thể mất hàng chục phút.", crawl_all: "Crawl cả 3 nguồn tuyển dụng và trang khóa luận NEU mất rất lâu và gửi nhiều yêu cầu tới các trang tuyển dụng.", embeddings: "Dựng embedding có thể mất vài phút và cần sentence-transformers." };
  let reloaded = false, timer = null, tasks = [], status = null, logs = [], viewing = null, viewText = "", confirming = null, flash = "";
  A.signal.addEventListener("abort", () => clearInterval(timer));

  const top = h("div", { style: "display:flex;flex-direction:column;gap:14px" });
  box.append(top);

  function load() {
    Promise.all([A.get("/tasks"), A.get("/logs")]).then(([t, l]) => { tasks = t.tasks; status = t.status; logs = l.items; paint(); poll(); }).catch((e) => A.fail(box, e, () => { clear(box).append(top); load(); }));
  }
  let step = 0;                                              // bước đang chạy của "Chạy cả luồng" (1..4), đọc từ logs/jobs_flow_step.log
  const readStep = () => A.get("/logs/jobs_flow_step.log?tail=3").then((r) => { const m = String(r.text || "").match(/^(lỗi )?(\d)\/4/m); step = m ? (m[1] ? -Number(m[2]) : Number(m[2])) : 0; }).catch(() => { step = 0; });
  function poll() {
    clearInterval(timer);
    if (!status || !status.running) return;
    const tick = () => A.get("/run/status?tail=300").then(async (s) => {
      const was = status.running; status = s;
      if (s.task === "jobs_flow") await readStep();
      if (was && !s.running) {
        clearInterval(timer);
        if (s.task === "jobs_flow" && s.code === 0) { reload(true); }                    // luồng xong thì tự nạp lại website
        A.get("/logs").then((l) => { logs = l.items; paint(); }).catch(() => paint());
      } else { paintStatus(); paintFlowState(); }
    }).catch((e) => { clearInterval(timer); A.fail(box, e, () => { clear(box).append(top); load(); }); });
    timer = setInterval(tick, 2000);
    if (status.task === "jobs_flow") readStep().then(paintFlowState);
  }
  function start(id) {
    confirming = null; reloaded = false; step = 0;
    A.post("/run", { task: id }).then((s) => { status = s; flash = ""; viewing = null; paint(); poll(); }).catch((e) => { flash = e.detail ? String(e.detail) : "Không chạy được lệnh."; paint(); });
  }
  function stop() { A.post("/run/stop").then((s) => { status = s; paint(); poll(); }).catch((e) => { flash = String(e.detail || "Không dừng được."); paint(); }); }
  function reload(auto) {
    flash = "Đang nạp lại dữ liệu…"; paint();
    A.post("/reload").then((r) => { reloaded = true; flash = `${auto ? "Xong cả luồng. " : ""}Đã nạp lại: ${r.jobs} tin (trước đó ${r.before}), nguồn ${r.jobs_source === "db" ? "CSDL" : "CSV"}.`; paint(); }).catch((e) => { flash = String(e.detail || "Không nạp lại được."); paint(); });
  }
  function view(name) {
    viewing = name; viewText = "Đang tải…"; paintLog();
    A.get("/logs/" + encodeURIComponent(name) + "?tail=500").then((r) => { if (viewing === name) { viewText = r.text; paintLog(); } }).catch((e) => { viewText = "Không đọc được log: " + String(e.detail || e.message); paintLog(); });
  }

  const statusBox = h("div"), logBox = h("pre", { class: "adm-log", tabindex: "0", "aria-label": "Nội dung log" }), histBox = h("div");
  function paintStatus() {
    clear(statusBox);
    if (!status || !status.task) { statusBox.append(h("div", { class: "muted" }, "Chưa chạy lệnh nào kể từ khi bật backend.")); return; }
    const s = status;
    const state = s.running ? h("span", { class: "chip chip-b" }, "Đang chạy · " + mmss(s.elapsed || 0)) : s.code === 0 ? h("span", { class: "chip", style: "background:var(--green-bg);color:var(--green)" }, "Xong, thành công")
      : h("span", { class: "chip", style: "background:var(--amber-bg);color:var(--amber)" }, "Kết thúc với mã " + s.code);
    statusBox.append(h("div", { class: "chips" }, h("strong", { title: s.label }, NAMES[s.task] || s.label), state, s.running ? h("button", { type: "button", class: "btn btn-sm", onclick: stop }, "Dừng") : null));
    if (!viewing || viewing === s.log) { logBox.textContent = s.tail || "(chưa có dòng log)"; logBox.scrollTop = logBox.scrollHeight; }
  }
  function paintLog() { logBox.textContent = viewText; logBox.scrollTop = logBox.scrollHeight; }
  function paintHist() {
    clear(histBox).append(logs.length ? h("table", { class: "adm-table" }, h("thead", null, h("tr", null, ["Log", "Cập nhật", "Kết quả", ""].map((x) => h("th", null, x)))),
      h("tbody", null, logs.map((l) => h("tr", null, h("td", null, l.name), h("td", null, l.modified), h("td", null, l.ok === true ? "Thành công" : l.ok === false ? "Có lỗi" : "–"),
        h("td", null, h("button", { type: "button", class: "btn btn-sm", onclick: () => view(l.name) }, "Xem")))))) : h("div", { class: "state" }, "Chưa có file log nào trong thư mục logs."));
  }
  const DESC = { crawl_jobs: "TopDev, ITviec, CareerViet", build_site: "Làm sạch, gán nhãn, dựng web", embeddings: "Mã hóa tin để so khớp", crawl_thesis: "Thêm mới, đóng cái đã gỡ", build_thesis: "Làm sạch, gán lĩnh vực" };
  // Trạng thái một nút: "run" | "ok" | "bad" | "" — từ lệnh đơn vừa chạy, hoặc từ bước hiện tại của "Chạy cả luồng"
  const FLOW_STEP = { crawl_jobs: 1, build_site: 2, embeddings: 3 };
  function stateOf(id) {
    const run = !!(status && status.running);
    if (status && status.task === "jobs_flow" && (FLOW_STEP[id] || id === "reload")) {
      const k = id === "reload" ? 4 : FLOW_STEP[id];
      if (run) return step === 0 ? (k === 1 ? "run" : "") : step < 0 ? (k < -step ? "ok" : k === -step ? "bad" : "") : k < step ? "ok" : k === step ? "run" : "";
      if (status.code === 0) return id === "reload" ? (reloaded ? "ok" : "") : "ok";
      return step < 0 ? (k < -step ? "ok" : k === -step ? "bad" : "") : "bad";
    }
    const cur = status && status.task === id;
    return cur && run ? "run" : cur && status.code === 0 ? "ok" : cur && status.code != null ? "bad" : "";
  }
  // Một nút trong sơ đồ: bấm để chạy một lệnh
  function node(id, n, extra) {
    const t = tasks.find((x) => x.id === id);
    if (!t) return null;
    const busy = !!(status && status.running), st = stateOf(id), ask = SLOW[id] && confirming === id;
    return h("button", { type: "button", "data-node": id, class: "pf-node" + (st ? " " + st : "") + (ask ? " ask" : "") + (extra ? " " + extra : ""), title: t.label, disabled: busy,
      onclick: () => { if (SLOW[id] && confirming !== id) { confirming = id; paint(); } else start(id); } },
      h("span", { class: "pf-n" }, st === "ok" ? "✓" : st === "bad" ? "!" : n ? String(n) : "▶"),
      h("span", { class: "pf-t" }, ask ? "Bấm lại để chạy" : NAMES[id] || t.label),
      h("span", { class: "pf-d" }, st === "run" ? "Đang chạy…" : DESC[id] || ""));
  }
  const arrow = () => h("span", { class: "pf-ar", "aria-hidden": "true" });
  function paintFlowState() { paintAll(); }
  function flow(busy) {
    const st4 = stateOf("reload");
    const full = tasks.find((x) => x.id === "jobs_flow");
    const fullAsk = confirming === "jobs_flow";
    const running = busy && status && status.task === "jobs_flow";
    return h("div", { class: "pf-flow" },
      h("div", { class: "pf-lane pf-job" }, h("div", { class: "pf-lt" }, "Tin tuyển dụng", h("span", { class: "pf-tag" }, "luồng chính · chạy hằng tuần"),
        full ? h("button", { type: "button", class: "pf-full" + (fullAsk ? " ask" : ""), disabled: busy, title: full.label, onclick: () => { if (!fullAsk) { confirming = "jobs_flow"; paint(); } else start("jobs_flow"); } },
          h("span", null, "▶"), running ? " Đang chạy…" : fullAsk ? " Bấm lại để chạy" : " Chạy cả luồng") : null),
        h("div", { class: "pf-row" }, node("crawl_jobs", 1, "big"), arrow(), node("build_site", 2), arrow(), node("embeddings", 3), arrow(),
          h("button", { type: "button", class: "pf-node pub" + (st4 ? " " + st4 : ""), disabled: busy, title: "Bấm sau khi dựng dữ liệu hoặc dựng embedding xong, để website dùng dữ liệu mới mà không cần khởi động lại backend.", onclick: () => reload(false) },
            h("span", { class: "pf-n" }, st4 === "ok" ? "✓" : "4"), h("span", { class: "pf-t" }, "Nạp lại website"), h("span", { class: "pf-d" }, "Web dùng dữ liệu mới")))),
      h("div", { class: "pf-lane pf-thesis" }, h("span", { class: "pf-up", title: "Khóa luận đã gắn nhãn đi vào bước Dựng dữ liệu" }),
        h("div", { class: "pf-lt" }, "Khóa luận NEU", h("span", { class: "pf-tag rare" }, "ít khi cần · chạy khi có khóa luận mới")),
        h("div", { class: "pf-row pf-ind" }, node("crawl_thesis", "A", "soft"), arrow(), node("build_thesis", "B", "soft"), h("span", { class: "pf-upl" }, "↑ đi vào bước 2 \u201cDựng dữ liệu\u201d"))));
  }
  const flowBox = h("div");
  function paintAll() { clear(flowBox).append(flow(!!(status && status.running))); }

  function paint() {
    const busy = !!(status && status.running);
    clear(top).append(
      h("section", { class: "card" }, h("h2", null, "Chạy lệnh"),
        h("div", { class: "muted" }, "Chạy ngay trên máy đang chạy backend, mỗi lúc một lệnh. Tránh chạy khi lịch hằng tuần (thứ Hai 02:00) đang crawl."),
        flash ? notice(flash) : null,
        flowBox,
        confirming ? notice(SLOW[confirming]) : null,
        statusBox, logBox),
      h("section", { class: "card" }, h("h2", null, "Log đã lưu"), h("div", { class: "muted" }, "Gồm log chạy từ trang này (admin_*) và log crawl hằng tuần (crawl_all_*)."), histBox));
    paintAll(); paintStatus(); paintHist();
  }
  top.append(loading());
  load();
}
