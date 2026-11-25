# Embedding - hướng dẫn chạy trên máy của bạn

Mô hình mặc định: `intfloat/multilingual-e5-base` (đa ngôn ngữ, hợp title tiếng Việt + tiếng Anh, ~1.1 GB).
Mô hình khác: `--model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (nhỏ, nhanh) hoặc `--model BAAI/bge-m3` (mạnh, nặng).

Chạy từ `C:\Users\anhta\rec`:

    pip install -r requirements-embedding.txt
    python ml/embedding/build_embeddings.py
    python ml/classification/tune.py --kind topic  --embedding-model intfloat/multilingual-e5-base
    python ml/classification/tune.py --kind domain --embedding-model intfloat/multilingual-e5-base

Lần đầu sẽ tải mô hình vào `models/embeddings/`. Kết quả embedding nằm ở `data/processed/embeddings/`.
So sánh cấu hình trong `data/evaluation/tuning_*_<model>.csv`. Nếu `v1.1+emb` tốt hơn `v1.1 (tfidf+kw)`:

    python ml/classification/train.py --kind topic  --embedding-model intfloat/multilingual-e5-base --model-version v1.2
    python ml/classification/train.py --kind domain --embedding-model intfloat/multilingual-e5-base --model-version v1.2

Lưu ý: backend `hash` chỉ dùng để kiểm thử luồng chạy, không phải embedding ngữ nghĩa.
