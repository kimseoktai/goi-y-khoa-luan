import { svg } from "./dom.js";

// Đường vẽ biểu tượng (nét đơn giản, viewBox 24x24).
export const PATHS = {
  logo: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
  home: "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  book: "M4 4h12a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4zM8 8h8M8 12h8",
  bulb: "M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  heart: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  check: "M5 12l5 5 9-10",
  scan: "M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2M8 12l3 3 5-6",
  file: "M6 3h8l4 4v14H6zM14 3v4h4M9 13h6M9 17h6",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  arrow: "M5 12h14M13 6l6 6-6 6",
  exit: "M9 4H5v16h4M16 8l4 4-4 4M20 12H9",
  chevL: "M15 5l-7 7 7 7",
  chevR: "M9 5l7 7-7 7",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z",
  // công việc
  "Backend Developer": "M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01",
  "AI/ML Engineer": "M12 3a4 4 0 0 0-4 4v1a3 3 0 0 0-2 5 3 3 0 0 0 3 4h6a3 3 0 0 0 3-4 3 3 0 0 0-2-5V7a4 4 0 0 0-4-4zM12 3v18",
  "Security Engineer": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z",
  "Business Analyst": "M3 8h18v12H3zM9 8V5h6v3M3 13h18",
  "Data Analyst": "M4 20V10M10 20V4M16 20v-8M22 20H2",
  "Fullstack Developer": "M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16",
  "DevOps/Cloud Engineer": "M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1 0 9H7z",
  "QA/Tester": "M9 9h6v8a3 3 0 0 1-6 0V9zM9 9a3 3 0 0 1 6 0M4 12h5M15 12h5M5 6l3 2M19 6l-3 2M5 19l3-2M19 19l-3-2",
  "Project/Delivery Manager": "M4 4h6v16H4zM14 4h6v9h-6z",
  "Data Engineer": "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  "Mobile Developer": "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM11 18h2",
  "System/Network Engineer": "M12 3v6M12 15v6M3 12h6M15 12h6M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  generic: "M4 5h16v14H4zM4 10h16",
};

export function icon(name, size = 22, extra) {
  return svg("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: extra && extra.fill ? "currentColor" : "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    svg("path", { d: PATHS[name] || PATHS.generic }));
}
