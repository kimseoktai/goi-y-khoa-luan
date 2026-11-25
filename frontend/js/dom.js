// Dựng DOM an toàn: văn bản luôn đi qua textContent/createTextNode, không bao giờ innerHTML (dữ liệu crawl là đầu vào không tin cậy).
export function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "value") e.value = v;
    else if (v === true) e.setAttribute(k, "");
    else e.setAttribute(k, String(v));
  }
  add(e, kids);
  return e;
}
export function add(e, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k == null || k === false) continue;
    e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return e;
}
export function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); return e; }
export const pct = (x, d = 0) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
export const n2 = (x) => (x == null ? "–" : Number(x).toFixed(2));
export const n3 = (x) => (x == null ? "–" : Number(x).toFixed(3));
export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

// Phần tử SVG (cần đúng namespace). Văn bản vẫn đi qua textContent.
export function svg(tag, attrs, ...kids) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null && v !== false) e.setAttribute(k, String(v));
  add(e, kids);
  return e;
}
