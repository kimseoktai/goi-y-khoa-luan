"""Cấu hình đường dẫn tập trung (không hard-code path trong module ML)."""
import os
from pathlib import Path

ROOT = Path(os.getenv("REC_ROOT", Path(__file__).resolve().parents[1]))
GOLD = ROOT / "data/processed/gold/gold_dataset_clean.csv"
GOLD_NEGATIVES = ROOT / "data/processed/gold/gold_verified_negatives.csv"
GOLD_REPORT = ROOT / "data/processed/gold/gold_label_report.csv"
TOPICS = ROOT / "data/repository/technical_topics.csv"
DOMAINS = ROOT / "data/repository/domains.csv"
LABEL_MAP = ROOT / "data/processed/taxonomy/old_to_new_label_map.csv"
EVAL_DIR = ROOT / "data/evaluation"
MODEL_DIRS = {"topic": ROOT / "models/thesis_classifier", "domain": ROOT / "models/domain_classifier"}
SEED = 42

EMBED_DIR = ROOT / "data/processed/embeddings"
EMBED_MODEL_DIR = ROOT / "models/embeddings"      # chỉ chứa artifact mô hình, không chứa code
DEFAULT_EMBED_MODEL = "intfloat/multilingual-e5-base"
THESIS = ROOT / "data/processed/thesis/thesis_clean.csv"
JOBS = ROOT / "data/processed/jobs/jobs_clean.csv"
