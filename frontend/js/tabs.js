// Tab sinh động cho toàn app: một viên sáng trượt tới mục đang chọn (menu trái, thanh chuyển mục, nút Biểu đồ/Bảng, Lưới/Danh sách…).
// Không sửa từng trang: theo dõi DOM, thấy nhóm tab quen thuộc thì gắn viên trượt. Vị trí cũ được nhớ để viên trượt từ chỗ cũ sang chỗ mới
// ngay cả khi trang vẽ lại cả khối.
const GROUPS = [
  { sel: ".side ul", item: "a", style: "nav" },
  { sel: ".dash-tabs", item: "button", style: "solid" },
  { sel: ".dash-rail", item: "button", style: "solid" },
  { sel: ".rolebar", item: ".fchip", style: "solid" },
  { sel: ".dash-presets", item: "button", style: "solid" },
  { sel: ".dash-segs", item: "button", style: "white" },
  { sel: ".lb-seg", item: "button", style: "white" },
];
const ACTIVE = '.on, [aria-current="page"], [aria-selected="true"]';
const memory = new Map();          // khóa nhóm → vị trí viên trượt lần trước
let queued = false;

const reduce = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function box(el, host) { return { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight }; }
function put(thumb, b) { thumb.style.transform = `translate(${b.x}px,${b.y}px)`; thumb.style.width = b.w + "px"; thumb.style.height = b.h + "px"; }

function place(host, g, key, first) {
  const thumb = host.querySelector(":scope > .tb-thumb");
  const on = [...host.children].find((c) => c !== thumb && c.matches(g.item) && c.matches(ACTIVE)), target = on;
  if (!thumb) return;
  if (!target || !target.offsetWidth) { thumb.style.opacity = "0"; return; }
  const b = box(target, host);
  const old = memory.get(key);
  if (first && old && !reduce()) {            // vẽ lại cả khối: bắt đầu ở chỗ cũ rồi trượt sang chỗ mới
    thumb.style.transition = "none"; put(thumb, old); thumb.style.opacity = "1"; void thumb.offsetWidth; thumb.style.transition = "";
  } else if (first) { thumb.style.transition = "none"; put(thumb, b); thumb.style.opacity = "1"; void thumb.offsetWidth; thumb.style.transition = ""; }
  put(thumb, b); thumb.style.opacity = "1";
  memory.set(key, b);
}

function enhance() {
  queued = false;
  GROUPS.forEach((g) => {
    document.querySelectorAll(g.sel).forEach((host, idx) => {
      const key = g.sel + "#" + idx;
      let fresh = false;
      if (!host.classList.contains("tb")) {
        host.classList.add("tb", "tb-" + g.style);
        host.insertBefore(Object.assign(document.createElement("i"), { className: "tb-thumb", "aria-hidden": "true" }), host.firstChild);
        fresh = true;
      }
      if (host.tagName === "UL") {
        // thanh bên: mỗi mục nằm trong <li>; đặt viên trượt theo thẻ <a>, nên viên nằm trong <ul> và dùng toạ độ của <a> so với <ul>
        const thumb = host.querySelector(":scope > .tb-thumb"), a = host.querySelector('a[aria-current="page"]');
        if (!thumb) return;
        if (!a) { thumb.style.opacity = "0"; return; }
        const hr = host.getBoundingClientRect(), ar = a.getBoundingClientRect(), b = { x: ar.left - hr.left + host.scrollLeft, y: ar.top - hr.top + host.scrollTop, w: ar.width, h: ar.height };
        const old = memory.get(key);
        if (fresh) { thumb.style.transition = "none"; put(thumb, old && !reduce() ? old : b); thumb.style.opacity = "1"; void thumb.offsetWidth; thumb.style.transition = ""; }
        put(thumb, b); thumb.style.opacity = "1"; memory.set(key, b);
        return;
      }
      place(host, g, key, fresh);
    });
  });
}
const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(enhance); } };

new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "aria-current", "aria-selected", "hidden"] });
window.addEventListener("resize", schedule);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
schedule();

// gợn sóng nhẹ khi bấm các nút chọn
document.addEventListener("click", (ev) => {
  const b = ev.target.closest && ev.target.closest(".fchip, .dash-preset, .dash-seg, .dash-tab, .dash-rail-b, .kh-hint, .lb-tc, .lb-chip, .lb-try button");
  if (!b || reduce()) return;
  const r = b.getBoundingClientRect(), s = Math.max(r.width, r.height) * 1.2, d = document.createElement("span");
  d.className = "tb-rip"; d.style.cssText = `width:${s}px;height:${s}px;left:${ev.clientX - r.left - s / 2}px;top:${ev.clientY - r.top - s / 2}px`;
  const cs = getComputedStyle(b); if (cs.position === "static") b.style.position = "relative";
  b.style.overflow = "hidden"; b.append(d); setTimeout(() => d.remove(), 650);
});
