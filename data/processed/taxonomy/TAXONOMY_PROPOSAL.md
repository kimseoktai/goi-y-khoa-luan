# Đề xuất Taxonomy v1.0 (DRAFT, chờ Admin duyệt)

Phiên bản: `taxonomy_v1.0-draft` | Ngày: 2026-10-05
File chính thức (draft): `data/repository/technical_topics.csv` (22 topic), `data/repository/domains.csv` (17 domain)
Bằng chứng: `data/processed/taxonomy/taxonomy_evidence.csv` | Ánh xạ nhãn cũ: `old_to_new_label_map.csv`

## 1. Vấn đề của 20 nhãn cũ
- 6 nhãn thực chất là **Domain**: Finance, Healthcare, Education / E-learning, E-commerce, Tourism, News / Content.
- 14 nhãn còn lại là Technical Topic. Riêng **Information Management** mơ hồ (vừa là loại hệ thống, vừa là nghiệp vụ) nên cần xét từng bản ghi.
- Jobs cần nhiều chủ đề mà Gold chưa có nhãn nào: Cloud & DevOps, Database, Data Engineering, Software Architecture, GenAI/LLM, UI/UX.

## 2. Thay đổi so với taxonomy cũ
| Hành động | Nội dung |
|---|---|
| Giữ nguyên (11) | AI/ML, NLP, Computer Vision, Web, Mobile, Cybersecurity, IoT / Embedded, Software Testing, Game Development, Optimization / OR, Recommendation System |
| Đổi tên (2) | Computer Networks → Computer Networks & Infrastructure; Data Science / Analytics → Data Science & Analytics |
| Tách (1) | Information Management → Information & Enterprise Systems (T17) + Domain theo từng bản ghi |
| Chuyển sang Domain (6) | Finance, Healthcare, Education, E-commerce, Tourism (→ Tourism & Hospitality), News / Content (→ News & Media) |
| Tạo mới, status `draft` (5) | Generative AI & LLM, Data Engineering, Cloud & DevOps, Database, Software Architecture & Engineering |
| Tạo mới, status `candidate` (3) | UI/UX Design, Blockchain, AR/VR & Spatial Computing |
| Domain mới (11) | Draft (8): Transportation & Logistics, Agriculture, Entertainment & Gaming, Real Estate & Construction, Government & Public Sector, Manufacturing & Industry, Environment & Energy, HR & Recruitment. Candidate (3): Social & Community, Telecommunications, Sports & Fitness |

## 3. Bằng chứng chính (xem taxonomy_evidence.csv)
- **Lệch cung–cầu rất rõ:** Cloud & DevOps chiếm ~56% Jobs nhưng chỉ ~1.6% title Thesis; Database ~47% vs ~1.7%; Data Engineering ~22% vs ~1.0%; Web ~45% vs ~20%. Đây là khoảng trống mà Recommendation có thể khai thác, nhưng cần xác nhận lại bằng classifier thay vì keyword.
- **Thesis nghiêng về Web (20%), Information & Enterprise Systems (16%), AI/ML (12%).**
- **Độ phủ:** với bộ keywords hiện tại, 26% title Thesis không khớp topic nào và 55% không khớp domain nào. Domain phải cho phép **rỗng**, đừng ép mỗi Thesis một Domain.
- **Độ tin cậy của keywords** (so với nhãn Gold hiện có): precision cao ở hầu hết topic (0.9+ với AI/ML, Web, Mobile, Testing, Recommendation), thấp hơn ở T17 (0.66) và T19 (0.68) do từ khóa quá chung ("quản lý", "thuật toán"). Recall thấp ở NLP (0.15) và Data Science (0.21) vì Gold gắn nhãn theo ngữ nghĩa chứ không theo từ khóa. Vì vậy keywords chỉ để hỗ trợ re-label, **không thay thế classifier**.

## 4. Hạn chế cần biết
- Số đếm chỉ là khớp từ khóa trên title Thesis và trên Jobs; chưa phải nhãn thật.
- Số đếm Jobs theo description bị nhiễu (ví dụ Transportation 24% do từ "delivery" trong "Delivery Manager", Environment 16% do từ "environment"). Dùng cột `job_pct_title_skills` cho Technical Topic; Domain của Jobs cần classifier ở Phase 7.
- Domain gần như không thể suy ra từ skills; Banking chiếm nhiều Jobs vì nhiều tin của ngân hàng, đó là đặc điểm của nguồn dữ liệu chứ chưa chắc là xu hướng thị trường.
- Topic `candidate` có ít bằng chứng (≤2% ở cả hai phía) nên không nên dùng để train cho đến khi có thêm dữ liệu.
- Business Analysis, Project Management, IT Governance/Audit xuất hiện nhiều trong Jobs nhưng là vai trò chứ không phải chủ đề kỹ thuật, nên chưa đưa vào taxonomy. Cần Admin quyết định.

## 5. Điểm cần Admin quyết định
1. Tách riêng **Generative AI & LLM** khỏi AI/ML hay gộp lại?
2. Gộp **Database** và **Data Engineering**, hay giữ riêng?
3. Giữ **Computer Networks & Infrastructure** gộp mạng + quản trị hệ thống, hay tách?
4. Giữ hay bỏ 3 topic và 3 domain `candidate`?
5. Có đưa nhóm "IT Governance / Risk / Audit" vào taxonomy không?

## 6. Hệ quả cho Phase 3 (Gold)
- Topic mới chưa có Gold nào: T04, T07, T08, T15, T16, T20, T21, T22. Domain mới chưa có Gold: D06 đến D17. Cần bổ sung và re-label thêm mẫu cho các nhóm này.
- Chuyển 6 nhãn domain cũ sang cột `domains` bằng `old_to_new_label_map.csv`, nhưng **chưa áp dụng** cho đến khi bạn duyệt.
