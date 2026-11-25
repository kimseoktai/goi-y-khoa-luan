// Nhãn tiếng Việt cho các giá trị kỹ thuật của API (không đổi tên trường trong API).
export const NOVELTY = {
  Novel: { text: "Mới", bg: "#BFE3C8", fg: "#0F3D1E", msg: "Chưa có luận văn nào trong kho giống đề tài này." },
  Similar: { text: "Khá giống", bg: "#F1D58B", fg: "#4A3000", msg: "Có luận văn khá gần. Hãy đọc để xem phần nào có thể khác biệt." },
  Duplicate: { text: "Trùng", bg: "#E9B1A7", fg: "#5A130A", msg: "Rất giống một luận văn đã có; nên chọn hướng khác hoặc làm rõ điểm mới." },
};
export const COMPONENTS = [
  ["job_relevance", "Hợp kỹ năng job"], ["topic", "Cùng chủ đề"], ["domain", "Cùng lĩnh vực"], ["semantic", "Giống nội dung job"], ["novelty", "Ít người làm"],
];
export const LEVEL = { same_labels: "Cùng chủ đề và lĩnh vực", partial_labels: "Chỉ cùng một phần chủ đề hoặc lĩnh vực" };
// Mức thiếu: "Thiếu" khi khoảng tin cậy 95% của tỷ lệ job nằm hoàn toàn trên của luận văn (gap_status của API);
// "Thiếu nhiều" khi thêm chênh lệch từ 20 điểm phần trăm trở lên (ngưỡng để đọc, không phải kết quả thống kê).
export const BIG_GAP = 0.20;
export function gapTag(r) {
  if (!r.support_ok) return { text: "Ít mẫu", bg: "#ECEAE3", fg: "#3E4643", kind: "low" };
  if (r.gap_status === "demand_exceeds_supply") return r.gap >= BIG_GAP ? { text: "Thiếu nhiều", bg: "#C2410C", fg: "#FFFFFF", kind: "big" } : { text: "Thiếu", bg: "#F6DFA8", fg: "#4A3000", kind: "short" };
  if (r.gap_status === "supply_exceeds_demand") return { text: "Dư", bg: "#DCEBEA", fg: "#074848", kind: "over" };
  if (r.gap_status === "not_measurable_from_jobs") return { text: "Chưa đo được", bg: "#ECEAE3", fg: "#3E4643", kind: "low" };
  return { text: "Chưa rõ chênh lệch", bg: "#ECEAE3", fg: "#3E4643", kind: "none" };
}
export function comboText(n) {
  if (n == null) return null;
  const word = n <= 1 ? "Ít luận văn cùng chủ đề" : n <= 3 ? "Vài luận văn cùng chủ đề" : "Nhiều luận văn cùng chủ đề";
  return { text: word + " (" + n + ")", bg: n <= 1 ? "#D8EEDD" : n <= 3 ? "#FBF3DF" : "#ECEAE3", fg: n <= 1 ? "#14532D" : n <= 3 ? "#5E3C00" : "#3E4643" };
}

// Mã nguồn trong dữ liệu luận văn -> tên trường hiển thị. Tên đầy đủ do người dùng xác nhận; mã lạ vẫn hiện nguyên mã (viết hoa).
export const SCHOOLS = {
  uit: "ĐH Công nghệ Thông tin (UIT)", neu: "ĐH Kinh tế Quốc dân (NEU)", ptit: "Học viện Công nghệ Bưu chính Viễn thông (PTIT)", duytan: "ĐH Duy Tân",
  uet_chuan: "ĐH Công nghệ - ĐHQGHN (UET), chương trình chuẩn", uet_clc: "ĐH Công nghệ - ĐHQGHN (UET), chất lượng cao",
};
export const schoolName = (code) => (code ? SCHOOLS[String(code).toLowerCase()] || String(code).toUpperCase() : "");
// "Năm · Trường"; thiếu phần nào thì bỏ phần đó.
export const yearSchool = (t) => [t.year, schoolName(t.source)].filter(Boolean).join(" · ");
