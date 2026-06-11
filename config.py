# ============================================================
# config.py — Konfigurasi Aplikasi Flask
# ============================================================
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Base Paths ---
BASE_DIR = Path(__file__).parent.resolve()
MODEL_DIR = BASE_DIR / "models"

# --- Flask Config ---
SECRET_KEY = os.getenv("SECRET_KEY", "sentimens-indobert-skripsi-secret-key-2025")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB maks upload CSV (NFR-S-03)
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# --- Model Config ---
MODEL_PATH = str(MODEL_DIR)
TOKENIZER_PATH = str(MODEL_DIR)
MAX_TOKEN_LENGTH = 512  # Max token BERT (FR-PP-08)

# --- Label Mapping (dari config.json model) ---
# LABEL_0 → Negatif, LABEL_1 → Netral, LABEL_2 → Positif
LABEL_MAP = {
    0: "Negatif",
    1: "Netral",
    2: "Positif",
}
LABEL_COLORS = {
    "Positif": "#28a745",   # Hijau (FR-VZ-05)
    "Negatif": "#dc3545",   # Merah (FR-VZ-05)
    "Netral":  "#6c757d",   # Abu-abu (FR-VZ-05)
}

# --- FastAPI Scraper Config ---
SCRAPER_BASE_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")
SCRAPER_ENDPOINT = "/scrape"
# FIX #1: Timeout diperbesar dari 60s → 300s
# Dual-scraping (Twitter + web search paralel) bisa butuh 60-120 detik.
# 300s = buffer aman agar pipeline tidak timeout sebelum scraper selesai.
SCRAPER_TIMEOUT  = 300
DEFAULT_SCRAPE_LIMIT = int(os.getenv("SCRAPE_LIMIT", "200"))
DEFAULT_DAYS_BACK    = int(os.getenv("DAYS_BACK",    "7"))

# --- Batch Processing ---
BATCH_CHUNK_SIZE = 32  # Proses per-batch untuk efisiensi memori

# --- Kolom CSV Output (FR-BT-05) ---
CSV_OUTPUT_COLUMNS = [
    "teks_asli",
    "teks_bersih",
    "sentimen",
    "confidence_positif",
    "confidence_negatif",
    "confidence_netral",
    "source",
    "date",
]

# --- Model Evaluation Metrics (hasil testing pada FINAL_TEST_verified, n=1873) ---
MODEL_METRICS = {
    "Accuracy":  90.76,
    "Precision": 88.12,
    "Recall":    85.70,
    "F1_Score":  86.73,
    "per_class": {
        "Negatif": {"precision": 89.38, "recall": 94.52, "f1": 91.88, "support": 730},
        "Netral":  {"precision": 80.68, "recall": 69.01, "f1": 74.39, "support": 242},
        "Positif": {"precision": 94.30, "recall": 93.56, "f1": 93.93, "support": 901},
    },
}

