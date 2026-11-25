# Taxonomy changelog

## taxonomy_v1.1 (2026-10-05)
- Blockchain: candidate -> active (Admin duyệt). Gold 147, 148, 149 được gắn nhãn Blockchain (manual_label_overrides.csv).
- UI/UX Design và Telecommunications: giữ `candidate`, không bổ sung thêm dữ liệu gán nhãn, chưa đưa vào training (ít nhu cầu và ít mẫu).
- Bản trước lưu ở data/repository/history/*_taxonomy_v1.0.csv.

## taxonomy_v1.0 (2026-10-05)
- Taxonomy đầu tiên từ 20 nhãn cũ: tách Domain khỏi Technical Topic (xem data/processed/taxonomy/TAXONOMY_PROPOSAL.md).

## gold_v2.1 (2026-10-05) - không đổi taxonomy
- Gộp 7 thesis vào Gold làm mẫu Data Engineering (gold_additions.csv): Data Engineering 10 -> 17 mẫu, đủ ngưỡng train (>=15).
- Các mẫu này do trợ lý chọn theo ủy quyền của người dùng, chờ người dùng xác nhận. 3 dòng recheck (thesis 786, 808, 1154) chưa quyết, giữ nguyên.

## model_v1.1 (2026-10-05) - không đổi taxonomy
- Thêm cờ từ khóa taxonomy (cột keywords) làm đặc trưng, blend với mô hình cơ sở. Giữ v1.0 để so sánh.
- Chuẩn hóa viết tắt (xd, ht...) đã thử nhưng không cải thiện nên KHÔNG dùng (bảng text_normalization.csv vẫn lưu để tham khảo).
- Lưu ý: nếu sửa cột keywords trong taxonomy thì phải train lại model.

## embedding (2026-10-05) - chưa có kết quả
- Thêm ml/embedding (embedder, build_embeddings) và thành phần `emb` trong train/tune. Chưa chạy được mô hình embedding thật trong môi trường không có mạng; chờ người dùng chạy local rồi so sánh bằng tune.py.

## tune embedding (2026-10-05) - kết quả người dùng chạy local, multilingual-e5-base
- Chọn cấu hình v1.2 = tfidf+kw + emb (kw+emb), tốt nhất ở Topic (macro 0.861) và Domain (macro 0.928) trong các cấu hình đã thử. train.py thêm --parts.

## model_v1.2 (2026-10-05) - người dùng train local, không đổi taxonomy/Gold
- Cấu hình tfidf+kw + emb (multilingual-e5-base). Topic micro-F1 0.860 / macro 0.857; Domain micro-F1 0.943 / macro 0.934 (5-fold CV, gold_v2.1). Ngưỡng: topic 0.45, domain 0.40.
- So với v1.1: Topic gần như không đổi ở macro-F1; Domain tăng (Finance +0.07, News & Media +0.07, Healthcare +0.06), không nhãn nào giảm.

## model_v1.2 - kiểm tra title không chứa từ khóa (2026-10-06)
- Ở cùng ngưỡng 0.40 và chỉ xét nhãn do người gán + mẫu đã kiểm chứng: Domain recall (positive không có từ khóa) v1.1 0.32 -> v1.2 0.45, macro-F1 0.832 -> 0.869, FP rate không đổi. Topic gần như không đổi (macro 0.839 -> 0.836 ở 0.40; 0.833 -> 0.846 ở ngưỡng đã chọn riêng 0.40 vs 0.45).
- Domain v1.2 nhạy ngưỡng: 0.40 cho macro 0.869 nhưng 0.45 chỉ còn 0.832.
- Điểm yếu còn lại của Topic: recall khoảng 0.5-0.6 với title không có từ khóa (IoT 0/9, Mobile 0/4, Optimization 0/4, Recommendation 0/4).

## Phase 6 - xử lý Thesis (2026-10-06)
- Thêm scripts/process_thesis.py (predict, không train), ml/classification/apply_models.py, ml/preprocessing/keyword_extractor.py.
- Thesis trong Gold dùng nhãn đã kiểm chứng (label_source = gold hoặc gold+model); Thesis ngoài Gold dùng dự đoán mô hình. Domain có thể rỗng.
- File *_PREVIEW_v1.1.csv chỉ để xem trước (mô hình v1.1); file chính thức tạo bằng v1.2 trên máy người dùng.

## Phase 6 chính thức (2026-10-06)
- thesis_processed.csv tạo bằng model v1.2 (taxonomy_v1.1, gold_v2.1). 1431 thesis: 310 gold, 275 gold+model, 846 model. 142 không có topic, 647 không có domain.
- Lưu ý: từ khóa "chatbot" trong Generative AI & LLM làm các thesis "website ... tích hợp chatbot" bị gán Generative AI, trong khi người dùng đã loại các chatbot không dùng LLM khi gán nhãn. Đề xuất bỏ khỏi keywords (đổi taxonomy cần Admin duyệt rồi train lại).

## Phase 7 - xử lý Jobs (2026-10-06) - rules_v1.0
- Thêm scripts/process_jobs.py, ml/classification/job_labeling.py. Quy tắc, không huấn luyện: Technical Topic = vai trò job_title (job_role_topic_map.csv) hoặc >= 2 trọng số skill (skill_topic_map.csv); Domain = từ khóa trong tên công ty hoặc >= 2 từ khác nhau trong mô tả, có loại trừ từ khóa chung (domain_job_exclusions.csv).
- Các ánh xạ và loại trừ do trợ lý đề xuất (status draft), chờ duyệt. Loại trừ được thêm sau khi xem kết quả lần chạy đầu (HR 44 -> 0, Government 8 -> 0, Transportation 12 -> 2) nên cần kiểm tra thủ công bằng jobs_validation_sample.csv.
- Topic candidate (UI/UX) vẫn được gán cho Jobs để thống kê nhu cầu (22 job).

## Phase 7 - rules_v1.1 sau vòng kiểm tra thủ công 1 (2026-10-06)
- Kết quả vòng 1 (50 job, người dùng chấm): Topic recall 0.94 (7 topic bị bỏ sót ở 5 job; precision không đo được vì người dùng không đánh dấu topic sai); Domain precision 0.95, recall 0.66 (10 domain bị bỏ sót, 5 là Finance & Banking).
- Sửa chung (không đổi taxonomy): từ khóa tiếng Anh nhận số nhiều; tên công ty nhận từ khóa dính liền (Techcombank); Domain đủ điều kiện khi 1 từ khóa lặp >= 3 lần; thêm job_domain_extra_keywords.csv (financial, sàn giao dịch, tài sản mã hóa, tutor...).
- Sau sửa: job không có domain 331 -> 288, Finance & Banking 165 -> 197. Các sửa được rút ra từ chính 50 job đã chấm nên cần mẫu độc lập (jobs_validation_sample_2.csv, 30 job).

- (2026-10-06) Sửa lỗi do rules_v1.1: từ khóa viết tắt ngắn (<4 ký tự) không còn nhận số nhiều, tránh 'HRS Group' bị gán Human Resources & Recruitment.

## Phase 7 - kết quả kiểm tra thủ công vòng 2 (30 job độc lập, rules_v1.1) (2026-10-06)
- So với bộ nhãn validated (coi hai tập rỗng là đúng; khác thứ tự vẫn đúng): Topic precision 0.77, recall 0.71, F1 0.74 (đúng hoàn toàn 10/30); Domain precision 0.94, recall 0.60, F1 0.73 (đúng hoàn toàn 20/30).
- Vai trò không có ánh xạ trực tiếp (BA, PO, Support, Audit, Data Governance, Software Engineer): Topic F1 0.52. Topic hay thiếu: Information & Enterprise Systems (6), Computer Networks & Infrastructure (4). Topic hay thừa: AI/ML (4), Database (3), Mobile (2).
- Domain bị thiếu chủ yếu do nhãn dựa vào hiểu biết về công ty (game, bán lẻ, sản xuất, y tế) không có trong văn bản tin.
- Mô phỏng trong mẫu (chưa áp dụng): thêm ánh xạ vai trò BA/Data Governance/IT Risk -> Information & Enterprise Systems và IT Support -> Computer Networks & Infrastructure đưa Topic F1 0.74 -> 0.81. Giảm trọng số skill 'AI' hoặc nâng ngưỡng skill làm giảm recall ở vòng 1, nên không áp dụng.

## Phase 7 rules_v1.2 + Phase 8 (2026-10-06)
- rules_v1.2: thêm ánh xạ vai trò (Business Analyst, Data Governance/Quality, IT Risk/Governance/Audit -> Information & Enterprise Systems; IT Support/Operations -> Computer Networks & Infrastructure); sửa lỗi topic chỉ có 1 skill (NLP, Computer Vision, Blockchain) không bao giờ đạt ngưỡng 2.0 (thêm 21, 23, 8 job). Job chưa có topic: 40 -> 19. Trong mẫu validated vòng 2: Topic P 0.79 / R 0.84 / F1 0.81 (trong mẫu, không độc lập).
- Phase 8: scripts/analyze_market.py + ml/recommendation/market_demand.py. Kết quả ở data/processed/market/. Domain tính phân đoạn (mỗi job tổng 1 điểm). Topic không có quy tắc cho Job (Recommendation System, Optimization / OR, AR/VR) được đánh dấu not_measurable_from_jobs. Không phân tích xu hướng thời gian vì dữ liệu không có ngày đăng.

## Phase 9 - Matching Job -> Thesis (2026-10-08) - matching_v0.1
- Thêm ml/matching (matcher, components, tune_weights), scripts/match_jobs_thesis.py, scripts/make_matching_eval_sample.py.
- Điểm = (w_topic*Topic + w_domain*Domain + w_semantic*Semantic) chuẩn hóa theo thành phần có dữ liệu; Job/Thesis không có Domain thì bỏ thành phần Domain (không phạt). Trọng số mặc định 0.4/0.2/0.4 chỉ là giá trị khởi đầu, chưa được đánh giá.
- Chưa chạy được semantic ở môi trường này (không có embedding thật). File *_PREVIEW_no_semantic.csv chỉ Topic+Domain, nhiều Thesis cùng điểm. Cần chạy local rồi đánh giá thủ công (matching_eval_sample.csv) để tinh chỉnh trọng số.

## Phase 7 trên dữ liệu từ CSDL (2026-10-19) - rules_v1.3
- Gán nhãn dựa trên mô tả đã bỏ phần phúc lợi (tầng sạch clean_v1.1) và thêm 6 từ loại trừ (domain_job_exclusions.csv).
- job_role_topic_map.csv: Project/Delivery Manager và Product Owner/Manager -> Information & Enterprise Systems (người dùng chấm vòng DB: 2 vai trò này trước đó không có topic).
- process_jobs: ngưỡng tổng trọng số skill hạ từ 2.0 xuống 1.5 (đo trên 30 job vòng DB: precision topic giữ 1.0, recall 0.72 -> 0.77; hạ xuống 1.0 làm precision tụt còn 0.64 nên không dùng).
- domain_min_hits.csv: Finance & Banking khi chỉ khớp qua mô tả cần >= 4 từ khóa khác nhau (đã gộp số nhiều); đo trên cùng 30 job: domain đúng hoàn toàn 25/30 -> 28/30. Cả hai chỉnh đều đo trên chính 30 job đã chấm nên cần kiểm tra lại bằng mẫu mới.
- Vòng chấm DB thứ 2 (30 job mới): thêm loại trừ hr (HR&Recruitment), video/media (News & Media), mua sắm (E-commerce) và từ khóa edutech, clinic/phòng khám. Domain đúng hoàn toàn: mẫu 1 28/30, mẫu 2 22/30 (trước khi thêm: 17/30). Quy tắc siết Finance & Banking >= 4 không chứng minh được trên mẫu 2 (hòa).
- Chính sách gán Domain cho Job (người dùng chốt 2026-10-19): lĩnh vực của CÔNG TY TUYỂN hoặc SẢN PHẨM CHÍNH của vị trí; KHÔNG tính khách hàng của dự án. Đã thử loại các đoạn nhắc "khách hàng/client" khỏi văn bản gán Domain: không cải thiện nên không áp dụng. Domain đúng hoàn toàn theo chính sách này: mẫu 1 28/30, mẫu 2 23/30; các lỗi còn lại cần biết công ty (VNPT-Net, Lộc Trời) hoặc ngữ cảnh, quy tắc từ khóa không bắt được.

## Bỏ Ollama, chỉ dùng Gemini cho tên đề tài (2026-10-19)
- ml/generation/ollama_client.py đổi thành llm_client.py, chỉ còn gemini_json + parse_json; bỏ REC_LLM_PROVIDER, REC_OLLAMA_URL, REC_OLLAMA_MODEL (REC_LLM_TIMEOUT mặc định 90 giây).
- Prompt sinh tên: thêm tin tuyển dụng tiêu biểu (làm dữ liệu), học phong cách luận văn trong kho, bắt buộc nêu bài toán/dữ liệu/phương pháp/bối cảnh, cấm khuôn mẫu chung chung, tách danh sách "tên đã hiện".

## Bảng công ty -> lĩnh vực và điền embedding (2026-10-20/21)
- data/repository/company_domains.csv: 46 công ty nháp (status draft, source claude_knowledge). Công ty có trong bảng thì lĩnh vực lấy từ bảng thay cho từ khóa mô tả; domain "-" = không ép; status review/rejected chưa có hiệu lực; tên khớp qua company_key (bỏ dấu, bỏ từ chỉ loại hình công ty).
- Đo trên 60 tin đã chấm (trước khi chốt chính sách lấy lĩnh vực của công ty): đúng hoàn toàn 47 -> 43, số tin có lĩnh vực 521 -> 614 (trong 1145). Các tin giảm là vị trí IT ở công ty có lĩnh vực rõ (GoTymeX, Betrimex, Money Forward, Shinhan DS, PTSC), người dùng đã chấm "không có lĩnh vực" trước khi chốt chính sách.
- scripts/label_company_domains.py: nhờ Gemini gán nháp cho công ty chưa có trong bảng (tên công ty và đoạn mô tả ngắn gửi tới Google). Chưa chạy được ở máy người dùng vì mạng hiện tại không nhận phản hồi từ Gemini; tạm bỏ.
- Backend điền embedding thiếu trong bộ nhớ khi chạy (tối đa 300 tin, /health hiện embeddings_filled).

## Trang quản trị (2026-10-21)
- Backend: /admin/overview, /admin/tasks, /admin/run (+ /run/stop, /run/status), /admin/logs, /admin/reload, /admin/companies (+ /decision, /add). Tất cả cần header X-Admin-Token (đặt REC_ADMIN_TOKEN trước khi chạy backend).
- Chạy lệnh chỉ nằm trong danh sách cố định (crawl_all, build_site_data, build_site_data --embeddings, pytest), mỗi lúc một lệnh, log ghi vào logs/admin_<lệnh>_<thời gian>.log. Log chỉ đọc trong thư mục logs/.
- Giao diện #/admin có 4 tab: Tổng quan (chỉ số, lần crawl, lịch tuần), Chạy lệnh & log, Công ty -> lĩnh vực (duyệt company_domains.csv), Nhóm công việc (như trước).
